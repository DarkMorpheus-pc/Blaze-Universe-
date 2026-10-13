use anyhow::{bail, Context, Result};
use clap::{Parser, Subcommand};
use serde::Serialize;
use std::collections::HashSet;
use std::fs;
use std::os::unix::fs::FileTypeExt;
use std::path::{Path, PathBuf};
use std::process::Command as ProcessCommand;

const MIN_TARGET_BYTES: u64 = 16 * 1024 * 1024 * 1024;
const ESP_BYTES: u64 = 512 * 1024 * 1024;

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
    esp_bytes: u64,
    root_bytes: u64,
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
        let output = ProcessCommand::new("blockdev")
            .arg("--getsize64")
            .arg(target)
            .output()
            .context("running blockdev --getsize64")?;
        if !output.status.success() {
            bail!("could not read target block-device size");
        }
        return String::from_utf8(output.stdout)?
            .trim()
            .parse::<u64>()
            .context("parsing target block-device size");
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
        schema_version: 1,
        target: canonical_target,
        target_bytes: bytes,
        source,
        destructive: true,
        partition_table: "gpt",
        esp_bytes: ESP_BYTES,
        root_bytes: bytes - ESP_BYTES,
        esp_type_guid: "c12a7328-f81f-11d2-ba4b-00a0c93ec93b",
        root_type_guid: "4f68bce3-e8cd-4db1-96e7-fbcaf984b709",
        bootloader: "Limine 12.x (UEFI + BIOS)",
        steps: vec![
            "acquire an exclusive target-device lock",
            "wipe stale filesystem and partition signatures",
            "create an aligned GPT with 512 MiB ESP and Linux x86-64 root",
            "format ESP as FAT32 and root as ext4",
            "extract the verified live SquashFS into the target root",
            "write UUID-based fstab and installed-system identity",
            "install Limine for UEFI and legacy BIOS",
            "verify filesystems, boot assets, ownership, and installed manifest",
        ],
    })
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
                println!("Layout: GPT, 512 MiB ESP, remaining space ext4 root");
                for (index, step) in plan.steps.iter().enumerate() {
                    println!("{}. {step}", index + 1);
                }
            }
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

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
}
