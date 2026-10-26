use std::fs;
use std::path::Path;
use std::process::Command;

use anyhow::Result;
use clap::{Parser, Subcommand};

#[derive(Parser, Debug)]
#[command(name = "blaze-sentinel")]
#[command(author = "BlazeOS Core Team <core@blazeos.org>")]
#[command(version = "0.3.0")]
#[command(about = "BlazeOS Sentinel: system security posture inspector (SELinux, AppArmor, Secure Boot, lockdown, firewall, kernel hardening)")]
struct Cli {
    #[command(subcommand)]
    command: Option<Commands>,
}

#[derive(Subcommand, Debug)]
enum Commands {
    /// Show security posture of this system (default)
    Status {
        /// Machine-readable JSON output
        #[arg(long)]
        json: bool,
    },
    /// List mandatory-access-control policy state (SELinux / AppArmor)
    Policy {
        #[arg(default_value = "list")]
        action: String,
    },
    /// Verify posture; exits non-zero when a critical control is missing
    Verify {
        #[arg(long)]
        json: bool,
    },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Level {
    Pass,
    Warn,
    Fail,
    Info,
}

impl Level {
    fn tag(self) -> &'static str {
        match self {
            Level::Pass => "PASS",
            Level::Warn => "WARN",
            Level::Fail => "FAIL",
            Level::Info => "INFO",
        }
    }
}

#[derive(Debug)]
struct Check {
    id: &'static str,
    title: &'static str,
    level: Level,
    detail: String,
    /// Critical checks make `verify` return a non-zero exit status when they fail.
    critical: bool,
}

fn read_trim(path: &str) -> Option<String> {
    fs::read_to_string(path).ok().map(|s| s.trim().to_string())
}

fn query_lsm() -> String {
    read_trim("/sys/kernel/security/lsm")
        .unwrap_or_else(|| "none (securityfs unmounted or unsupported)".to_string())
}

fn query_apparmor_profiles() -> Vec<String> {
    read_trim_lines("/sys/kernel/security/apparmor/profiles")
}

fn read_trim_lines(path: &str) -> Vec<String> {
    fs::read_to_string(path)
        .map(|c| c.lines().map(|s| s.to_string()).collect())
        .unwrap_or_default()
}

/// SELinux: Fedora's default MAC. Returns (present, enforcing).
fn selinux_state() -> (bool, bool) {
    let enforce = read_trim("/sys/fs/selinux/enforce");
    match enforce.as_deref() {
        Some("1") => (true, true),
        Some(_) => (true, false),
        None => (false, false),
    }
}

fn secure_boot_state() -> Option<bool> {
    if !Path::new("/sys/firmware/efi").exists() {
        return None; // legacy BIOS
    }
    let dir = fs::read_dir("/sys/firmware/efi/efivars").ok()?;
    for entry in dir.flatten() {
        let name = entry.file_name().to_string_lossy().to_string();
        if name.starts_with("SecureBoot-") {
            let data = fs::read(entry.path()).ok()?;
            // 4 attribute bytes followed by the 1-byte value
            return data.get(4).map(|b| *b == 1);
        }
    }
    None
}

fn lockdown_mode() -> Option<String> {
    // Format: "none [integrity] confidentiality" - selected mode is bracketed
    let raw = read_trim("/sys/kernel/security/lockdown")?;
    raw.split_whitespace()
        .find(|t| t.starts_with('[') && t.ends_with(']'))
        .map(|t| t.trim_matches(|c| c == '[' || c == ']').to_string())
}

fn systemd_active(unit: &str) -> bool {
    Command::new("systemctl")
        .args(["is-active", "--quiet", unit])
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}

fn sysctl(name: &str) -> Option<String> {
    read_trim(&format!("/proc/sys/{}", name.replace('.', "/")))
}

fn collect_checks() -> Vec<Check> {
    let mut checks = Vec::new();
    let lsm = query_lsm();

    // --- Mandatory access control -------------------------------------
    let (se_present, se_enforcing) = selinux_state();
    let aa_profiles = query_apparmor_profiles();
    let aa_active = lsm.contains("apparmor") && !aa_profiles.is_empty();
    let (level, detail) = if se_present && se_enforcing {
        (Level::Pass, "SELinux enforcing".to_string())
    } else if aa_active {
        (Level::Pass, format!("AppArmor active ({} profiles)", aa_profiles.len()))
    } else if se_present {
        (Level::Fail, "SELinux present but permissive/disabled".to_string())
    } else {
        (Level::Fail, "no mandatory access control active".to_string())
    };
    checks.push(Check { id: "mac", title: "Mandatory access control", level, detail, critical: true });

    // --- Secure Boot ---------------------------------------------------
    let (level, detail) = match secure_boot_state() {
        Some(true) => (Level::Pass, "Secure Boot enabled".to_string()),
        Some(false) => (Level::Warn, "Secure Boot disabled in firmware".to_string()),
        None => (Level::Info, "legacy BIOS or EFI variables unavailable".to_string()),
    };
    checks.push(Check { id: "secureboot", title: "Secure Boot", level, detail, critical: false });

    // --- Kernel lockdown -----------------------------------------------
    let (level, detail) = match lockdown_mode().as_deref() {
        Some("integrity") | Some("confidentiality") => {
            (Level::Pass, format!("lockdown: {}", lockdown_mode().unwrap()))
        }
        Some(m) => (Level::Warn, format!("lockdown: {m}")),
        None => (Level::Info, "lockdown LSM not available".to_string()),
    };
    checks.push(Check { id: "lockdown", title: "Kernel lockdown", level, detail, critical: false });

    // --- Landlock / Yama ----------------------------------------------
    for (key, id, title) in [("landlock", "landlock", "Landlock sandboxing"), ("yama", "yama", "Yama ptrace scope")] {
        let on = lsm.split(',').any(|m| m == key);
        checks.push(Check {
            id,
            title,
            level: if on { Level::Pass } else { Level::Warn },
            detail: if on { "enabled".into() } else { "not in active LSM list".into() },
            critical: false,
        });
    }

    // --- Firewall --------------------------------------------------------
    let fw = systemd_active("firewalld.service") || systemd_active("nftables.service") || systemd_active("ufw.service");
    checks.push(Check {
        id: "firewall",
        title: "Firewall",
        level: if fw { Level::Pass } else { Level::Fail },
        detail: if fw { "firewalld/nftables/ufw active".into() } else { "no active firewall service".into() },
        critical: true,
    });

    // --- Kernel hardening sysctls ---------------------------------------
    let hardening = [
        ("kernel.kptr_restrict", "1", "kernel pointer exposure"),
        ("kernel.dmesg_restrict", "1", "dmesg restricted to root"),
        ("kernel.unprivileged_bpf_disabled", "1", "unprivileged BPF disabled"),
        ("net.ipv4.conf.all.rp_filter", "1", "reverse-path filtering"),
    ];
    let mut weak: Vec<String> = Vec::new();
    for (name, want, desc) in hardening {
        match sysctl(name) {
            Some(v) if v == want || (name == "kernel.kptr_restrict" && v == "2") || (name == "kernel.unprivileged_bpf_disabled" && v == "2") => {}
            Some(v) => weak.push(format!("{desc} ({name}={v})")),
            None => {}
        }
    }
    checks.push(Check {
        id: "sysctl",
        title: "Kernel hardening sysctls",
        level: if weak.is_empty() { Level::Pass } else { Level::Warn },
        detail: if weak.is_empty() { "all inspected values hardened".into() } else { weak.join("; ") },
        critical: false,
    });

    // --- Audit -------------------------------------------------------------
    let audit = systemd_active("auditd.service") || Path::new("/var/run/auditd.pid").exists();
    checks.push(Check {
        id: "audit",
        title: "Audit daemon",
        level: if audit { Level::Pass } else { Level::Info },
        detail: if audit { "auditd running".into() } else { "auditd not running".into() },
        critical: false,
    });

    checks
}

fn json_escape(s: &str) -> String {
    s.replace('\\', "\\\\").replace('"', "\\\"")
}

fn print_json(checks: &[Check]) {
    println!("{{\"checks\":[");
    for (i, c) in checks.iter().enumerate() {
        println!(
            "  {{\"id\":\"{}\",\"title\":\"{}\",\"level\":\"{}\",\"critical\":{},\"detail\":\"{}\"}}{}",
            c.id,
            json_escape(c.title),
            c.level.tag().to_lowercase(),
            c.critical,
            json_escape(&c.detail),
            if i + 1 == checks.len() { "" } else { "," }
        );
    }
    println!("]}}");
}

fn print_report(checks: &[Check]) {
    println!("==================================================================");
    println!("   Blaze Sentinel — Security Posture (v0.3.0)");
    println!("==================================================================");
    for c in checks {
        println!("[{}] {:<28} {}", c.level.tag(), c.title, c.detail);
    }
    let pass = checks.iter().filter(|c| c.level == Level::Pass).count();
    let scored = checks.iter().filter(|c| c.level != Level::Info).count();
    println!("------------------------------------------------------------------");
    println!("Score: {pass}/{scored} controls passing");
}

fn main() -> Result<()> {
    let cli = Cli::parse();

    match cli.command.unwrap_or(Commands::Status { json: false }) {
        Commands::Status { json } => {
            let checks = collect_checks();
            if json { print_json(&checks) } else { print_report(&checks) }
        }
        Commands::Policy { action } => {
            println!("--- Blaze Sentinel Policy Manager ({action}) ---");
            let (se_present, se_enforcing) = selinux_state();
            if se_present {
                println!("SELinux: {}", if se_enforcing { "enforcing" } else { "permissive" });
            }
            let profiles = query_apparmor_profiles();
            if profiles.is_empty() {
                if !se_present {
                    println!("No SELinux or AppArmor policy is active on this system.");
                }
            } else {
                println!("Loaded AppArmor profiles:");
                for p in profiles {
                    println!("  - {p}");
                }
            }
        }
        Commands::Verify { json } => {
            let checks = collect_checks();
            if json { print_json(&checks) } else { print_report(&checks) }
            let failed = checks.iter().filter(|c| c.critical && c.level == Level::Fail).count();
            if failed > 0 {
                eprintln!("[SENTINEL VERIFY] {failed} critical control(s) failing");
                std::process::exit(2);
            }
            println!("[SENTINEL VERIFY] all critical controls satisfied");
        }
    }

    Ok(())
}
