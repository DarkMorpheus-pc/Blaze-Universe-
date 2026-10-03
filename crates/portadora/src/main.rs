use std::path::{Path, PathBuf};

use anyhow::{bail, Context, Result};
use clap::{Parser, Subcommand};
use portadora_core::{BlzReader, Database};

#[derive(Parser, Debug)]
#[command(name = "portadora")]
#[command(author = "BlazeOS Core Team <core@blazeos.org>")]
#[command(version = "0.1.0")]
#[command(about = "Native package manager for BlazeOS", long_about = None)]
struct Cli {
    /// Target root directory for package operations (e.g. for bootstrap/chroot staging)
    #[arg(long, default_value = "/")]
    root: PathBuf,

    /// Custom path to Portadora SQLite database
    #[arg(long)]
    db_path: Option<PathBuf>,

    /// Enable verbose diagnostic output
    #[arg(short, long)]
    verbose: bool,

    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand, Debug)]
enum Commands {
    /// Install one or more .blz packages into the target rootfs
    Install {
        /// Paths to .blz package archives
        #[arg(required = true)]
        packages: Vec<PathBuf>,
    },

    /// Remove an installed package from the system
    Remove {
        /// Name of the package to remove
        package: String,
    },

    /// List installed packages
    List,

    /// Display detailed information about a package or .blz archive
    Info {
        /// Package name or path to a .blz file
        target: String,
    },

    /// Verify integrity of installed files (checksums, permissions, missing files)
    Verify {
        /// Optional package name to verify specifically
        package: Option<String>,
    },
}

fn resolve_db_path(root: &Path, custom_db: Option<&Path>) -> PathBuf {
    if let Some(p) = custom_db {
        p.to_path_buf()
    } else {
        root.join("var/lib/portadora/db.sqlite")
    }
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let root = cli.root.canonicalize().unwrap_or_else(|_| cli.root.clone());
    let db_path = resolve_db_path(&root, cli.db_path.as_deref());

    if cli.verbose {
        eprintln!("[portadora] Operating with target root: {}", root.display());
        eprintln!("[portadora] Using database: {}", db_path.display());
    }

    match cli.command {
        Commands::Install { packages } => {
            let mut db = Database::open_or_create(&db_path)?;

            for pkg_path in packages {
                let reader = BlzReader::open(&pkg_path)
                    .with_context(|| format!("Failed to open package: {}", pkg_path.display()))?;

                let manifest = reader.read_manifest()?;
                let files = reader.read_files()?;

                println!(
                    "Installing {} {}-{} ({})...",
                    manifest.package.name,
                    manifest.package.version,
                    manifest.package.release,
                    manifest.package.architecture
                );

                // 1. Pre-flight check: Prevent file ownership conflicts BEFORE touching disk
                db.check_conflicts(&manifest.package.name, &files)?;

                // 2. Extract payload safely
                if let Err(e) = reader.extract_payload(&root) {
                    bail!("Failed to extract package {}: {:#}", manifest.package.name, e);
                }

                // 3. Record into database atomically
                if let Err(e) = db.record_installed(&manifest, &files, &root) {
                    // Rollback files if DB record fails
                    eprintln!("Database error, rolling back extracted files...");
                    for file in &files {
                        let abs_file = root.join(&file.path);
                        if abs_file.is_file() || abs_file.is_symlink() {
                            let _ = std::fs::remove_file(&abs_file);
                        }
                    }
                    return Err(e);
                }

                // 4. Declarative triggers execution (sysusers, tmpfiles, ldconfig)
                execute_declarative_triggers(&root, &manifest, cli.verbose);

                println!(
                    "Successfully installed {} ({})",
                    manifest.package.name, manifest.package.version
                );
            }
        }

        Commands::Remove { package } => {
            let mut db = Database::open_or_create(&db_path)?;
            println!("Removing package '{}'...", package);
            db.remove_package(&package, &root)?;
            println!("Successfully removed '{}'", package);
        }

        Commands::List => {
            if !db_path.exists() {
                println!("No packages installed (database does not exist).");
                return Ok(());
            }

            let db = Database::open_or_create(&db_path)?;
            let packages = db.list_packages()?;

            if packages.is_empty() {
                println!("No packages installed.");
                return Ok(());
            }

            for pkg in packages {
                println!("{} {}-{}", pkg.name, pkg.version, pkg.release);
            }
        }

        Commands::Info { target } => {
            let target_path = Path::new(&target);
            if target_path.exists() && target.ends_with(".blz") {
                // Read from .blz archive directly
                let reader = BlzReader::open(target_path)?;
                let manifest = reader.read_manifest()?;
                let files = reader.read_files()?;

                println!("Name         : {}", manifest.package.name);
                println!("Version      : {}-{}", manifest.package.version, manifest.package.release);
                println!("Architecture : {}", manifest.package.architecture);
                println!("Summary      : {}", manifest.package.summary);
                println!("License      : {}", manifest.package.license);
                println!("Maintainer   : {}", manifest.package.maintainer);
                println!("URL          : {}", manifest.package.url);
                println!("Size         : {} bytes", manifest.package.installed_size);
                println!("Requires     : {:?}", manifest.dependencies.requires);
                println!("Provides     : {:?}", manifest.dependencies.provides);
                println!("Files count  : {}", files.len());
            } else {
                // Read from database
                if !db_path.exists() {
                    bail!("Database does not exist at {}", db_path.display());
                }
                let db = Database::open_or_create(&db_path)?;
                match db.get_package(&target)? {
                    Some((pkg, files)) => {
                        println!("Name         : {}", pkg.name);
                        println!("Version      : {}-{}", pkg.version, pkg.release);
                        println!("Architecture : {}", pkg.architecture);
                        println!("Summary      : {}", pkg.summary);
                        println!("Description  : {}", pkg.description);
                        println!("License      : {}", pkg.license);
                        println!("Size         : {} bytes", pkg.installed_size);
                        println!("Installed At : {}", pkg.install_time);
                        println!("Files count  : {}", files.len());
                    }
                    None => {
                        bail!("Package '{}' is not installed", target);
                    }
                }
            }
        }

        Commands::Verify { package } => {
            if !db_path.exists() {
                bail!("Database does not exist at {}", db_path.display());
            }
            let db = Database::open_or_create(&db_path)?;
            let issues = db.verify_files(&root, package.as_deref())?;

            if issues.is_empty() {
                println!("All managed files verified.");
            } else {
                eprintln!("Verification issues detected ({}):", issues.len());
                for issue in issues {
                    eprintln!(
                        "[{}] {}: {} ({})",
                        issue.package_name, issue.path, issue.issue_type, issue.details
                    );
                }
                bail!("Package verification failed.");
            }
        }
    }

    Ok(())
}

fn execute_declarative_triggers(root: &Path, manifest: &portadora_core::Manifest, verbose: bool) {
    use std::process::Command;

    // 1. ldconfig trigger
    if manifest.triggers.run_ldconfig {
        let ldconfig_path = root.join("usr/bin/ldconfig");
        if ldconfig_path.exists() {
            if verbose {
                eprintln!("[trigger] Running ldconfig...");
            }
            let _ = Command::new(&ldconfig_path)
                .arg("-r")
                .arg(root)
                .status();
        }
    }

    // 2. sysusers trigger
    if let Some(ref sysusers) = manifest.sysusers {
        let sysusers_bin = root.join("usr/bin/systemd-sysusers");
        if sysusers_bin.exists() {
            for conf_file in &sysusers.files {
                let conf_path = root.join(conf_file);
                if conf_path.exists() {
                    if verbose {
                        eprintln!("[trigger] Running systemd-sysusers on {}", conf_file);
                    }
                    let _ = Command::new(&sysusers_bin)
                        .arg(format!("--root={}", root.display()))
                        .arg(&conf_path)
                        .status();
                }
            }
        }
    }

    // 3. tmpfiles trigger
    if let Some(ref tmpfiles) = manifest.tmpfiles {
        let tmpfiles_bin = root.join("usr/bin/systemd-tmpfiles");
        if tmpfiles_bin.exists() {
            for conf_file in &tmpfiles.files {
                let conf_path = root.join(conf_file);
                if conf_path.exists() {
                    if verbose {
                        eprintln!("[trigger] Running systemd-tmpfiles --create on {}", conf_file);
                    }
                    let _ = Command::new(&tmpfiles_bin)
                        .arg("--create")
                        .arg(format!("--root={}", root.display()))
                        .arg(&conf_path)
                        .status();
                }
            }
        }
    }
}
