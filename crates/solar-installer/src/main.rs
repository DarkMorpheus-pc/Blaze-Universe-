use anyhow::{bail, Context, Result};
use clap::{Parser, Subcommand};
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::collections::HashSet;
use std::fs;
use std::fs::{File, OpenOptions};
use std::io::{Read, Write};
use std::os::unix::fs::{FileTypeExt, MetadataExt, PermissionsExt};
use std::os::unix::io::AsRawFd;
use std::path::{Path, PathBuf};
use std::process::{Command as ProcessCommand, Stdio};
use std::thread;
use std::time::{Duration, Instant};
use tempfile::TempDir;

const MIN_TARGET_BYTES: u64 = 16 * 1024 * 1024 * 1024;
const ESP_BYTES: u64 = 512 * 1024 * 1024;
const BIOS_BOOT_BYTES: u64 = 1024 * 1024;
const BIOS_BOOT_GUID: &str = "21686148-6449-6e6f-744e-656564454649";
const ESP_GUID: &str = "c12a7328-f81f-11d2-ba4b-00a0c93ec93b";
const ROOT_GUID: &str = "4f68bce3-e8cd-4db1-96e7-fbcaf984b709";
const BLKGETSIZE64: libc::c_ulong = 0x8008_1272;

#[derive(Parser)]
#[command(name = "solar-installer", version, about)]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    /// List installation candidates without modifying them.
    Probe {
        #[arg(long)]
        json: bool,
    },
    /// Validate a target and print the exact installation layout.
    Plan {
        #[arg(long)]
        target: PathBuf,
        #[arg(long, default_value = "/run/live/media/blaze/rootfs.squashfs")]
        source: PathBuf,
        /// Test-only support for sparse regular-file targets.
        #[arg(long, hide = true)]
        allow_file_target: bool,
        #[arg(long)]
        json: bool,
    },
    /// Erase a whole disk and deploy BlazeOS. Intended for the live environment.
    Apply {
        #[arg(long)]
        target: PathBuf,
        #[arg(long, default_value = "/run/live/media/blaze/rootfs.squashfs")]
        source: PathBuf,
        #[arg(long, default_value = "/run/live/media/boot")]
        boot_directory: PathBuf,
        #[arg(long, default_value = "/run/live/media/installer")]
        limine_directory: PathBuf,
        /// Must exactly match the canonical target path (for example /dev/vdb).
        #[arg(long)]
        confirm_erase: String,
        /// Permit installation to a device marked removable by the kernel.
        #[arg(long)]
        allow_removable: bool,
    },
}

#[derive(Debug, Serialize)]
struct DiskCandidate {
    path: PathBuf,
    bytes: u64,
    model: String,
    removable: bool,
    read_only: bool,
    mounted: bool,
    eligible: bool,
    rejection_reasons: Vec<String>,
}

#[derive(Debug, Serialize)]
struct InstallPlan {
    schema_version: u32,
    target: PathBuf,
    target_bytes: u64,
    source: PathBuf,
    destructive: bool,
    partition_table: &'static str,
    bios_boot_bytes: u64,
    esp_bytes: u64,
    root_bytes: u64,
    bios_boot_type_guid: &'static str,
    esp_type_guid: &'static str,
    root_type_guid: &'static str,
    bootloader: &'static str,
    steps: Vec<&'static str>,
}

fn read_trimmed(path: impl AsRef<Path>) -> String {
    fs::read_to_string(path)
        .unwrap_or_default()
        .trim()
        .to_string()
}

fn mounted_sources() -> HashSet<String> {
    let mut sources = HashSet::new();
    if let Ok(mounts) = fs::read_to_string("/proc/self/mountinfo") {
        for line in mounts.lines() {
            if let Some((_, tail)) = line.split_once(" - ") {
                let mut fields = tail.split_whitespace();
                let _fstype = fields.next();
                if let Some(source) = fields.next() {
                    sources.insert(source.to_string());
                }
            }
        }
    }
    sources
}

fn device_or_partition_is_mounted(device: &Path, mounted: &HashSet<String>) -> bool {
    let value = device.to_string_lossy();
    mounted.iter().any(|source| {
        source == value.as_ref()
            || (source.starts_with(value.as_ref())
                && source[value.len()..]
                    .chars()
                    .next()
                    .is_some_and(|c| c == 'p' || c.is_ascii_digit()))
    })
}

fn probe_disks() -> Result<Vec<DiskCandidate>> {
    let mounted = mounted_sources();
    let mut disks = Vec::new();

    for entry in fs::read_dir("/sys/class/block").context("reading /sys/class/block")? {
        let entry = entry?;
        let name = entry.file_name().to_string_lossy().into_owned();
        if name.starts_with("loop")
            || name.starts_with("ram")
            || name.starts_with("zram")
            || name.starts_with("dm-")
            || name.starts_with("sr")
        {
            continue;
        }

        let sys = entry.path();
        if sys.join("partition").exists() {
            continue;
        }

        let path = PathBuf::from(format!("/dev/{name}"));
        let sectors = read_trimmed(sys.join("size")).parse::<u64>().unwrap_or(0);
        let bytes = sectors.saturating_mul(512);
        let removable = read_trimmed(sys.join("removable")) == "1";
        let read_only = read_trimmed(sys.join("ro")) == "1";
        let mounted_now = device_or_partition_is_mounted(&path, &mounted);
        let model = read_trimmed(sys.join("device/model"));
        let mut rejection_reasons = Vec::new();
        if bytes < MIN_TARGET_BYTES {
            rejection_reasons.push("smaller than 16 GiB".into());
        }
        if read_only {
            rejection_reasons.push("read-only device".into());
        }
        if mounted_now {
            rejection_reasons.push("device or partition is mounted".into());
        }

        disks.push(DiskCandidate {
            path,
            bytes,
            model,
            removable,
            read_only,
            mounted: mounted_now,
            eligible: rejection_reasons.is_empty(),
            rejection_reasons,
        });
    }

    disks.sort_by(|a, b| a.path.cmp(&b.path));
    Ok(disks)
}

fn target_size(target: &Path, allow_file_target: bool) -> Result<u64> {
    let metadata = fs::metadata(target)
        .with_context(|| format!("target does not exist: {}", target.display()))?;
    if metadata.file_type().is_block_device() {
        let name = target
            .file_name()
            .context("target has no block-device name")?;
        let sys = Path::new("/sys/class/block").join(name);
        if sys.join("partition").exists() {
            bail!("target must be a whole disk, not a partition");
        }
        if read_trimmed(sys.join("ro")) == "1" {
            bail!("target is a read-only block device");
        }
        let file = File::open(target)?;
        let mut bytes = 0_u64;
        // SAFETY: BLKGETSIZE64 writes one u64 to the valid pointer supplied here.
        if unsafe { libc::ioctl(file.as_raw_fd(), BLKGETSIZE64, &mut bytes) } != 0 {
            bail!(
                "could not read target block-device size: {}",
                std::io::Error::last_os_error()
            );
        }
        return Ok(bytes);
    }
    if !(allow_file_target && metadata.is_file()) {
        bail!("target must be a whole block device");
    }
    Ok(metadata.len())
}

fn build_plan(target: PathBuf, source: PathBuf, allow_file_target: bool) -> Result<InstallPlan> {
    let canonical_target = fs::canonicalize(&target)
        .with_context(|| format!("cannot resolve target: {}", target.display()))?;
    let bytes = target_size(&canonical_target, allow_file_target)?;
    if bytes < MIN_TARGET_BYTES {
        bail!("target is smaller than the required 16 GiB");
    }

    if !source.is_file() {
        bail!("live SquashFS source not found: {}", source.display());
    }

    let mounted = mounted_sources();
    if !allow_file_target && device_or_partition_is_mounted(&canonical_target, &mounted) {
        bail!("refusing a target that has mounted filesystems");
    }

    Ok(InstallPlan {
        schema_version: 2,
        target: canonical_target,
        target_bytes: bytes,
        source,
        destructive: true,
        partition_table: "gpt",
        esp_bytes: ESP_BYTES,
        bios_boot_bytes: BIOS_BOOT_BYTES,
        root_bytes: bytes - ESP_BYTES - BIOS_BOOT_BYTES,
        bios_boot_type_guid: BIOS_BOOT_GUID,
        esp_type_guid: ESP_GUID,
        root_type_guid: ROOT_GUID,
        bootloader: "Limine 12.x (UEFI + BIOS)",
        steps: vec![
            "acquire an exclusive target-device lock",
            "wipe stale filesystem and partition signatures",
            "create an aligned GPT with BIOS Boot, 512 MiB ESP, and Linux x86-64 root",
            "format ESP as FAT32 and root as ext4",
            "extract the verified live SquashFS into the target root",
            "write UUID-based fstab and installed-system identity",
            "install Limine for UEFI and legacy BIOS",
            "verify filesystems, boot assets, ownership, and installed manifest",
        ],
    })
}

fn run(program: &str, args: &[&str]) -> Result<()> {
    let status = ProcessCommand::new(program)
        .args(args)
        .status()
        .with_context(|| format!("running {program}"))?;
    if !status.success() {
        bail!("{program} failed with {status}");
    }
    Ok(())
}

fn output(program: &str, args: &[&str]) -> Result<String> {
    let result = ProcessCommand::new(program)
        .args(args)
        .output()
        .with_context(|| format!("running {program}"))?;
    if !result.status.success() {
        bail!(
            "{program} failed: {}",
            String::from_utf8_lossy(&result.stderr).trim()
        );
    }
    Ok(String::from_utf8(result.stdout)?.trim().to_owned())
}

fn run_with_input(program: &str, args: &[&str], input: &str) -> Result<()> {
    let mut child = ProcessCommand::new(program)
        .args(args)
        .stdin(Stdio::piped())
        .spawn()
        .with_context(|| format!("running {program}"))?;
    child
        .stdin
        .take()
        .context("opening command stdin")?
        .write_all(input.as_bytes())?;
    let status = child.wait()?;
    if !status.success() {
        bail!("{program} failed with {status}");
    }
    Ok(())
}

fn partition_path(target: &Path, number: u8) -> PathBuf {
    let suffix = if target
        .to_string_lossy()
        .ends_with(|c: char| c.is_ascii_digit())
    {
        format!("p{number}")
    } else {
        number.to_string()
    };
    PathBuf::from(format!("{}{}", target.display(), suffix))
}

struct TargetLock(File);

impl TargetLock {
    fn acquire(target: &Path) -> Result<Self> {
        let file = OpenOptions::new().read(true).write(true).open(target)?;
        // SAFETY: flock only consumes the valid file descriptor owned by `file`.
        if unsafe { libc::flock(file.as_raw_fd(), libc::LOCK_EX | libc::LOCK_NB) } != 0 {
            bail!("target is locked or in use: {}", target.display());
        }
        Ok(Self(file))
    }
}

impl Drop for TargetLock {
    fn drop(&mut self) {
        // SAFETY: the descriptor remains valid until this Drop implementation returns.
        unsafe { libc::flock(self.0.as_raw_fd(), libc::LOCK_UN) };
    }
}

struct MountedTarget {
    root: TempDir,
    esp_mounted: bool,
    root_mounted: bool,
}

impl MountedTarget {
    fn new(root_partition: &Path, esp_partition: &Path) -> Result<Self> {
        let root = tempfile::Builder::new()
            .prefix("solar-installer-")
            .tempdir_in("/run")?;
        let root_path = root.path().to_string_lossy().into_owned();
        run(
            "mount",
            &[
                root_partition
                    .to_str()
                    .context("non-UTF-8 root partition")?,
                &root_path,
            ],
        )?;
        let mut mounted = Self {
            root,
            esp_mounted: false,
            root_mounted: true,
        };
        fs::create_dir_all(mounted.root.path().join("boot"))?;
        let boot_path = mounted.root.path().join("boot");
        run(
            "mount",
            &[
                esp_partition.to_str().context("non-UTF-8 ESP partition")?,
                boot_path.to_str().context("non-UTF-8 mount path")?,
            ],
        )?;
        mounted.esp_mounted = true;
        Ok(mounted)
    }
}

impl Drop for MountedTarget {
    fn drop(&mut self) {
        if self.esp_mounted {
            let _ = ProcessCommand::new("umount")
                .arg(self.root.path().join("boot"))
                .status();
        }
        if self.root_mounted {
            let _ = ProcessCommand::new("umount").arg(self.root.path()).status();
        }
    }
}

fn required_file(directory: &Path, name: &str) -> Result<PathBuf> {
    let path = directory.join(name);
    if !path.is_file() {
        bail!("required installation asset is missing: {}", path.display());
    }
    Ok(path)
}

fn wait_for_partitions(partitions: &[&Path], timeout: Duration) -> Result<()> {
    let deadline = Instant::now() + timeout;
    loop {
        if partitions.iter().all(|partition| partition.exists()) {
            return Ok(());
        }
        if Instant::now() >= deadline {
            let missing = partitions
                .iter()
                .filter(|partition| !partition.exists())
                .map(|partition| partition.display().to_string())
                .collect::<Vec<_>>()
                .join(", ");
            bail!("partition nodes did not appear: {missing}");
        }
        thread::sleep(Duration::from_millis(100));
    }
}

fn verify_live_source(source: &Path) -> Result<String> {
    let media_root = source
        .parent()
        .and_then(Path::parent)
        .context("source must be inside the live-media blaze directory")?;
    let manifest_path = media_root.join("SHA256SUMS");
    let manifest = fs::read_to_string(&manifest_path)
        .with_context(|| format!("reading {}", manifest_path.display()))?;
    let expected = manifest
        .lines()
        .find_map(|line| {
            let (digest, name) = line.split_once(char::is_whitespace)?;
            (name.trim_start_matches([' ', '*']) == "blaze/rootfs.squashfs")
                .then(|| digest.to_ascii_lowercase())
        })
        .context("SHA256SUMS has no blaze/rootfs.squashfs entry")?;
    if expected.len() != 64 || !expected.bytes().all(|byte| byte.is_ascii_hexdigit()) {
        bail!("invalid rootfs digest in SHA256SUMS");
    }
    let mut file = File::open(source)?;
    let mut hasher = Sha256::new();
    let mut buffer = vec![0_u8; 1024 * 1024];
    loop {
        let count = file.read(&mut buffer)?;
        if count == 0 {
            break;
        }
        hasher.update(&buffer[..count]);
    }
    let actual = hex::encode(hasher.finalize());
    if actual != expected {
        bail!("live root checksum mismatch (expected {expected}, got {actual})");
    }
    Ok(actual)
}

fn apply_install(
    target: PathBuf,
    source: PathBuf,
    boot_directory: PathBuf,
    limine_directory: PathBuf,
    confirm_erase: String,
    allow_removable: bool,
) -> Result<()> {
    if unsafe { libc::geteuid() } != 0 {
        bail!("installation requires root privileges");
    }
    let plan = build_plan(target, source.clone(), false)?;
    if confirm_erase != plan.target.to_string_lossy() {
        bail!(
            "confirmation mismatch; --confirm-erase must be exactly {}",
            plan.target.display()
        );
    }
    let name = plan
        .target
        .file_name()
        .context("target has no device name")?;
    if read_trimmed(Path::new("/sys/class/block").join(name).join("removable")) == "1"
        && !allow_removable
    {
        bail!("target is removable; pass --allow-removable only after verifying its identity");
    }
    for command in [
        "sfdisk",
        "mkfs.vfat",
        "mkfs.ext4",
        "unsquashfs",
        "mount",
        "umount",
        "blkid",
    ] {
        if output("sh", &["-c", &format!("command -v {command}")]).is_err() {
            bail!("required installation tool is missing: {command}");
        }
    }
    let kernel = required_file(&boot_directory, "vmlinuz-blaze-7.2.9")?;
    let initramfs = required_file(&boot_directory, "initramfs-blaze-7.2.9.img")?;
    let efi = required_file(&limine_directory, "BOOTX64.EFI")?;
    let bios_sys = required_file(&limine_directory, "limine-bios.sys")?;
    let limine = required_file(&limine_directory, "limine")?;

    println!("[0/8] Verifying live root SHA-256...");
    let source_sha256 = verify_live_source(&source)?;

    let _lock = TargetLock::acquire(&plan.target)?;
    let target_s = plan.target.to_str().context("non-UTF-8 target path")?;
    let table = format!(
        "label: gpt\nsize=1MiB, type={BIOS_BOOT_GUID}, name=\"blaze-bios\"\nsize=512MiB, type={ESP_GUID}, name=\"BLAZE-EFI\"\ntype={ROOT_GUID}, name=\"blaze-root\"\n"
    );
    println!("[1/8] Partitioning {}...", plan.target.display());
    // The process already holds a non-blocking exclusive flock for the whole transaction.
    run_with_input(
        "sfdisk",
        &["--wipe", "always", "--wipe-partitions", "always", target_s],
        &table,
    )?;
    let bios_partition = partition_path(&plan.target, 1);
    let esp_partition = partition_path(&plan.target, 2);
    let root_partition = partition_path(&plan.target, 3);
    wait_for_partitions(
        &[&bios_partition, &esp_partition, &root_partition],
        Duration::from_secs(10),
    )?;
    println!("[2/8] Formatting filesystems...");
    run(
        "mkfs.vfat",
        &[
            "-F",
            "32",
            "-n",
            "BLAZE-EFI",
            esp_partition.to_str().context("non-UTF-8 ESP path")?,
        ],
    )?;
    run(
        "mkfs.ext4",
        &[
            "-F",
            "-L",
            "blaze-root",
            root_partition.to_str().context("non-UTF-8 root path")?,
        ],
    )?;

    let mounted = MountedTarget::new(&root_partition, &esp_partition)?;
    let root = mounted.root.path();
    println!("[3/8] Extracting the verified live root...");
    run(
        "unsquashfs",
        &[
            "-f",
            "-d",
            root.to_str().context("non-UTF-8 root mount")?,
            source.to_str().context("non-UTF-8 source")?,
        ],
    )?;
    for directory in ["dev", "proc", "run", "sys", "tmp"] {
        fs::create_dir_all(root.join(directory))?;
    }

    println!("[4/8] Installing kernel and Limine assets...");
    let boot = root.join("boot");
    fs::create_dir_all(boot.join("EFI/BOOT"))?;
    fs::copy(kernel, boot.join("vmlinuz-blaze-7.2.9"))?;
    fs::copy(initramfs, boot.join("initramfs-blaze-7.2.9.img"))?;
    fs::copy(efi, boot.join("EFI/BOOT/BOOTX64.EFI"))?;
    fs::copy(bios_sys, boot.join("limine-bios.sys"))?;
    let limine_conf = "timeout: 3\ndefault_entry: 1\n\n/BlazeOS Native\n    protocol: linux\n    kernel_path: boot():/vmlinuz-blaze-7.2.9\n    module_path: boot():/initramfs-blaze-7.2.9.img\n    cmdline: root=PARTLABEL=blaze-root rw console=ttyS0 console=tty0 quiet loglevel=3\n\n/Blaze Emergency Recovery Environment\n    protocol: linux\n    kernel_path: boot():/vmlinuz-blaze-7.2.9\n    module_path: boot():/initramfs-blaze-7.2.9.img\n    cmdline: root=PARTLABEL=blaze-root rw console=ttyS0 console=tty0 berp\n";
    fs::write(boot.join("limine.conf"), limine_conf)?;
    fs::write(boot.join("EFI/BOOT/limine.conf"), limine_conf)?;

    println!("[5/8] Writing UUID-based fstab...");
    let root_uuid = output(
        "blkid",
        &[
            "-s",
            "UUID",
            "-o",
            "value",
            root_partition.to_str().unwrap(),
        ],
    )?;
    let esp_uuid = output(
        "blkid",
        &["-s", "UUID", "-o", "value", esp_partition.to_str().unwrap()],
    )?;
    fs::create_dir_all(root.join("etc"))?;
    fs::write(
        root.join("etc/fstab"),
        format!(
            "UUID={root_uuid} / ext4 rw,relatime 0 1\nUUID={esp_uuid} /boot vfat umask=0077 0 2\n"
        ),
    )?;
    fs::write(root.join("etc/machine-id"), "")?;
    let install_manifest = serde_json::json!({
        "schema_version": 1,
        "installer": env!("CARGO_PKG_VERSION"),
        "source_sha256": source_sha256,
        "kernel": "7.2.9",
        "bootloader": "Limine 12.9.1",
        "layout": ["bios-boot", "efi-system", "linux-x86-64-root"]
    });
    fs::create_dir_all(root.join("var/lib/solar-installer"))?;
    fs::write(
        root.join("var/lib/solar-installer/install.json"),
        serde_json::to_vec_pretty(&install_manifest)?,
    )?;

    println!("[6/8] Installing legacy BIOS boot stages...");
    run(
        limine.to_str().context("non-UTF-8 Limine path")?,
        &["bios-install", target_s, "1"],
    )?;
    println!("[7/8] Flushing installation data...");
    run("sync", &[])?;
    println!("[8/8] Verifying installed boot and system files...");
    for path in [
        root.join("etc/fstab"),
        boot.join("limine.conf"),
        boot.join("limine-bios.sys"),
        boot.join("EFI/BOOT/BOOTX64.EFI"),
        root.join("usr/lib/systemd/systemd"),
        root.join("var/lib/solar-installer/install.json"),
    ] {
        if !path.is_file() {
            bail!("post-install verification failed: {}", path.display());
        }
    }
    for path in [
        root.join("usr/lib/systemd/systemd"),
        root.join("usr/bin/su"),
    ] {
        let metadata = fs::metadata(&path)?;
        if metadata.uid() != 0 || metadata.gid() != 0 {
            bail!(
                "post-install ownership verification failed: {}",
                path.display()
            );
        }
    }
    let su_mode = fs::metadata(root.join("usr/bin/su"))?.permissions().mode();
    if su_mode & 0o4000 == 0 {
        bail!("post-install SUID verification failed: /usr/bin/su");
    }
    println!(
        "BlazeOS installation completed successfully on {}",
        plan.target.display()
    );
    Ok(())
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Command::Probe { json } => {
            let disks = probe_disks()?;
            if json {
                println!("{}", serde_json::to_string_pretty(&disks)?);
            } else if disks.is_empty() {
                println!("No whole-disk installation candidates detected.");
            } else {
                for disk in disks {
                    println!(
                        "{}  {:>6.1} GiB  {:<24}  {}",
                        disk.path.display(),
                        disk.bytes as f64 / 1024_f64.powi(3),
                        disk.model,
                        if disk.eligible { "eligible" } else { "blocked" }
                    );
                    for reason in disk.rejection_reasons {
                        println!("  - {reason}");
                    }
                }
            }
        }
        Command::Plan {
            target,
            source,
            allow_file_target,
            json,
        } => {
            let plan = build_plan(target, source, allow_file_target)?;
            if json {
                println!("{}", serde_json::to_string_pretty(&plan)?);
            } else {
                println!("BlazeOS installation plan (NO CHANGES APPLIED)");
                println!("Target: {}", plan.target.display());
                println!("Source: {}", plan.source.display());
                println!("Layout: GPT, 1 MiB BIOS Boot, 512 MiB ESP, remaining space ext4 root");
                for (index, step) in plan.steps.iter().enumerate() {
                    println!("{}. {step}", index + 1);
                }
            }
        }
        Command::Apply {
            target,
            source,
            boot_directory,
            limine_directory,
            confirm_erase,
            allow_removable,
        } => {
            apply_install(
                target,
                source,
                boot_directory,
                limine_directory,
                confirm_erase,
                allow_removable,
            )?;
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn mounted_partition_matching_is_boundary_aware() {
        let mounted = HashSet::from(["/dev/vda2".to_string(), "/dev/nvme0n1p1".to_string()]);
        assert!(device_or_partition_is_mounted(
            Path::new("/dev/vda"),
            &mounted
        ));
        assert!(device_or_partition_is_mounted(
            Path::new("/dev/nvme0n1"),
            &mounted
        ));
        assert!(!device_or_partition_is_mounted(
            Path::new("/dev/vd"),
            &mounted
        ));
    }

    #[test]
    fn partition_paths_cover_sd_and_nvme_names() {
        assert_eq!(
            partition_path(Path::new("/dev/vdb"), 3),
            Path::new("/dev/vdb3")
        );
        assert_eq!(
            partition_path(Path::new("/dev/nvme0n1"), 3),
            Path::new("/dev/nvme0n1p3")
        );
        assert_eq!(
            partition_path(Path::new("/dev/mmcblk0"), 2),
            Path::new("/dev/mmcblk0p2")
        );
    }

    #[test]
    fn live_source_digest_is_mandatory_and_verified() {
        let directory = tempdir().unwrap();
        let blaze = directory.path().join("blaze");
        fs::create_dir(&blaze).unwrap();
        let source = blaze.join("rootfs.squashfs");
        fs::write(&source, b"BlazeOS test root").unwrap();
        let digest = hex::encode(Sha256::digest(b"BlazeOS test root"));
        fs::write(
            directory.path().join("SHA256SUMS"),
            format!("{digest}  blaze/rootfs.squashfs\n"),
        )
        .unwrap();
        verify_live_source(&source).unwrap();
        fs::write(&source, b"tampered").unwrap();
        assert!(verify_live_source(&source).is_err());
    }
}
