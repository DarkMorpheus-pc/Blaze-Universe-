use std::fs;
use std::path::Path;
use anyhow::Result;
use clap::{Parser, Subcommand};

#[derive(Parser, Debug)]
#[command(name = "blaze-sentinel")]
#[command(author = "BlazeOS Core Team <core@blazeos.org>")]
#[command(version = "0.2.0")]
#[command(about = "BlazeOS Native Sentinel Security Subsystem CLI & Service")]
struct Cli {
    #[command(subcommand)]
    command: Option<Commands>,
}

#[derive(Subcommand, Debug)]
enum Commands {
    /// Show system LSM and Sentinel security subsystem status
    Status,
    /// Manage AppArmor profiles and security policies
    Policy {
        #[arg(default_value = "list")]
        action: String,
    },
    /// Run security policy verification against loaded LSM
    Verify,
}

fn query_lsm() -> String {
    let lsm_path = Path::new("/sys/kernel/security/lsm");
    if lsm_path.exists() {
        if let Ok(content) = fs::read_to_string(lsm_path) {
            return content.trim().to_string();
        }
    }
    "none (securityfs unmounted or unsupported)".to_string()
}

fn query_apparmor_profiles() -> Vec<String> {
    let profiles_path = Path::new("/sys/kernel/security/apparmor/profiles");
    if profiles_path.exists() {
        if let Ok(content) = fs::read_to_string(profiles_path) {
            return content.lines().map(|s| s.to_string()).collect();
        }
    }
    Vec::new()
}

fn main() -> Result<()> {
    let cli = Cli::parse();

    match cli.command.unwrap_or(Commands::Status) {
        Commands::Status => {
            println!("==================================================================");
            println!("   Blaze Sentinel Security Engine — Status Report (v0.2.0 Native)");
            println!("==================================================================");
            let lsm = query_lsm();
            println!("[LSM Subsystem] Active LSM Order: {}", lsm);
            
            let profiles = query_apparmor_profiles();
            if !profiles.is_empty() {
                println!("[Policy Engine] AppArmor: Active ({} profiles loaded in kernel)", profiles.len());
            } else if lsm.contains("apparmor") {
                println!("[Policy Engine] AppArmor: Active (LSM enabled, 0 profiles loaded)");
            } else {
                println!("[Policy Engine] AppArmor: Inactive");
            }

            if lsm.contains("landlock") {
                println!("[Policy Engine] Landlock: Active in Kernel LSM");
            }
            if lsm.contains("lockdown") {
                println!("[Policy Engine] Lockdown: Active in Kernel LSM");
            }
            if lsm.contains("bpf") {
                println!("[Policy Engine] BPF LSM: Active in Kernel LSM");
            }

            let audit_active = Path::new("/var/run/auditd.pid").exists() || Path::new("/proc/net/netlink").exists();
            println!("[Audit Engine] Audit Subsystem: {}", if audit_active { "Available" } else { "Idle" });
        }
        Commands::Policy { action } => {
            println!("--- Blaze Sentinel Policy Manager ({}) ---", action);
            let profiles = query_apparmor_profiles();
            if profiles.is_empty() {
                println!("No active kernel profiles found under /sys/kernel/security/apparmor/profiles");
            } else {
                println!("Loaded Kernel AppArmor Profiles:");
                for p in profiles {
                    println!("  - {}", p);
                }
            }
        }
        Commands::Verify => {
            println!("[SENTINEL VERIFY] Probing kernel security enforcement...");
            let lsm = query_lsm();
            if lsm.contains("apparmor") || lsm.contains("landlock") {
                println!("[PASS] Kernel LSM active with: {}", lsm);
            } else {
                eprintln!("[WARN] No modern LSM detected in /sys/kernel/security/lsm");
            }
        }
    }

    Ok(())
}
