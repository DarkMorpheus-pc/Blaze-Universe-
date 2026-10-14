use std::collections::HashSet;
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::Command;

use anyhow::{bail, Context, Result};
use clap::{Parser, Subcommand};
use portadora_core::{
    is_version_release_newer, BlzReader, Database, DependencyResolver, JournalOp,
    PackageDownloader, TargetsMetadata, Transaction, TransactionRecovery, TufVerifier,
};

#[derive(Parser, Debug)]
#[command(name = "portadora")]
#[command(author = "BlazeOS Core Team <core@blazeos.org>")]
#[command(version = "0.2.0")]
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
    /// Update repository metadata and trust anchors via TUF
    Update {
        /// Optional repository URL override
        #[arg(long)]
        repo_url: Option<String>,
    },

    /// Search for packages in remote repository
    Search {
        /// Search keyword (name or summary)
        query: String,
        /// Optional repository URL override
        #[arg(long)]
        repo_url: Option<String>,
    },

    /// Install one or more packages (local .blz file or remote package name)
    Install {
        /// Package names or paths to .blz archives
        #[arg(required = true)]
        packages: Vec<String>,

        /// Optional repository URL override
        #[arg(long)]
        repo_url: Option<String>,
    },

    /// Upgrade installed packages to latest repository versions
    Upgrade {
        /// Simulate the upgrade transaction without applying changes
        #[arg(long)]
        dry_run: bool,

        /// Optional specific package to upgrade
        package: Option<String>,

        /// Optional repository URL override
        #[arg(long)]
        repo_url: Option<String>,
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

    /// Display package manager transaction history
    History,

    /// Recover any interrupted or uncommitted package transactions
    Recover,
}

fn resolve_db_path(root: &Path, custom_db: Option<&Path>) -> PathBuf {
    if let Some(p) = custom_db {
        p.to_path_buf()
    } else {
        root.join("var/lib/portadora/db.sqlite")
    }
}

fn get_repo_url(root: &Path, override_url: Option<&str>) -> String {
    if let Some(u) = override_url {
        return u.trim_end_matches('/').to_string();
    }
    if let Ok(env_url) = std::env::var("BLAZE_REPO_URL") {
        if !env_url.trim().is_empty() {
            return env_url.trim().trim_end_matches('/').to_string();
        }
    }
    let conf_path = root.join("etc/portadora/repos.conf");
    if conf_path.is_file() {
        if let Ok(content) = fs::read_to_string(&conf_path) {
            for line in content.lines() {
                let l = line.trim();
                if !l.is_empty() && !l.starts_with('#') {
                    if let Some(url_part) = l.strip_prefix("url=") {
                        return url_part.trim().trim_end_matches('/').to_string();
                    }
                    if l.starts_with("http://") || l.starts_with("https://") || l.starts_with("file://") {
                        return l.trim_end_matches('/').to_string();
                    }
                }
            }
        }
    }
    "http://127.0.0.1:8080".to_string()
}

fn fetch_url_bytes(url: &str) -> Result<Vec<u8>> {
    if url.starts_with("file://") {
        let path = url.trim_start_matches("file://");
        let data = fs::read(path).with_context(|| format!("Failed to read {}", path))?;
        return Ok(data);
    }
    let client = reqwest::blocking::Client::builder()
        .timeout(std::time::Duration::from_secs(30))
        .build()?;
    let resp = client.get(url).send()
        .with_context(|| format!("Failed to request {}", url))?;
    if !resp.status().is_success() {
        bail!("HTTP error {} requesting {}", resp.status(), url);
    }
    let bytes = resp.bytes()?.to_vec();
    Ok(bytes)
}

fn load_or_update_targets(root: &Path, repo_url: &str, verbose: bool) -> Result<TargetsMetadata> {
    if verbose {
        eprintln!("[portadora] Refreshing and verifying repository metadata from {}", repo_url);
    }
    execute_update(root, repo_url, verbose)
}

fn atomic_write(path: &Path, data: &[u8]) -> Result<()> {
    let parent = path.parent().context("metadata path has no parent")?;
    fs::create_dir_all(parent)?;
    let temporary = path.with_extension("json.new");
    let mut file = fs::File::create(&temporary)?;
    file.write_all(data)?;
    file.sync_all()?;
    fs::rename(&temporary, path)?;
    fs::File::open(parent)?.sync_all()?;
    Ok(())
}

fn execute_update(root: &Path, repo_url: &str, verbose: bool) -> Result<TargetsMetadata> {
    let trusted_root_path = root.join("etc/portadora/trusted/root.json");
    if !trusted_root_path.exists() {
        bail!(
            "Missing trusted TUF root anchor at {}. Bootstrapped root.json is required for secure updates.",
            trusted_root_path.display()
        );
    }

    if verbose {
        eprintln!("[portadora] Loading trusted root anchor: {}", trusted_root_path.display());
    }
    let mut verifier = TufVerifier::load_trusted_root(&trusted_root_path)?;
    verifier.load_cached_metadata(&root.join("var/lib/portadora/metadata"));

    // Root rotations are accepted one version at a time. Every intermediate
    // root must be signed by both its predecessor and its own threshold.
    let root_url = format!("{}/metadata/root.json", repo_url);
    if let Ok(latest_root_bytes) = fetch_url_bytes(&root_url) {
        let latest: portadora_core::tuf::SignedMetadata<portadora_core::tuf::RootMetadata> =
            serde_json::from_slice(&latest_root_bytes).context("parsing repository root.json")?;
        if latest.signed.version > verifier.root.version {
            let rotations = latest.signed.version - verifier.root.version;
            if rotations > 32 {
                bail!("SecurityError::RootRotationLimit: refusing more than 32 root rotations in one update");
            }
            for version in (verifier.root.version + 1)..=latest.signed.version {
                let versioned_url = format!("{}/metadata/{}.root.json", repo_url, version);
                let candidate = fetch_url_bytes(&versioned_url)
                    .with_context(|| format!("fetching required intermediate root version {version}"))?;
                verifier.update_root(&candidate)?;
                atomic_write(&trusted_root_path, &candidate)?;
                atomic_write(
                    &root.join("var/lib/portadora/metadata/root.json"),
                    &candidate,
                )?;
                println!("TUF trust anchor updated to version {}", verifier.root.version);
            }
        }
    }

    // 1. Fetch timestamp.json
    let timestamp_url = format!("{}/metadata/timestamp.json", repo_url);
    let timestamp_bytes = fetch_url_bytes(&timestamp_url)?;
    verifier.verify_timestamp(&timestamp_bytes)?;
    if verbose {
        eprintln!("[portadora] Verified timestamp.json (anti-freeze check passed)");
    }

    // 2. Fetch snapshot.json
    let snapshot_url = format!("{}/metadata/snapshot.json", repo_url);
    let snapshot_bytes = fetch_url_bytes(&snapshot_url)?;
    verifier.verify_snapshot(&snapshot_bytes)?;
    if verbose {
        eprintln!("[portadora] Verified snapshot.json (anti-mix-and-match check passed)");
    }

    // 3. Fetch targets.json
    let targets_url = format!("{}/metadata/targets.json", repo_url);
    let targets_bytes = fetch_url_bytes(&targets_url)?;
    verifier.verify_targets(&targets_bytes)?;
    if verbose {
        eprintln!("[portadora] Verified targets.json (TUF threshold signatures verified)");
    }

    // Save verified metadata into /var/lib/portadora/metadata/
    let meta_dir = root.join("var/lib/portadora/metadata");
    atomic_write(&meta_dir.join("timestamp.json"), &timestamp_bytes)?;
    atomic_write(&meta_dir.join("snapshot.json"), &snapshot_bytes)?;
    atomic_write(&meta_dir.join("targets.json"), &targets_bytes)?;

    println!("Repository metadata successfully updated and verified (TUF v1.0.36)");
    Ok(verifier.targets.unwrap())
}

fn check_mutation_privileges(db_path: &Path) -> Result<()> {
    if db_path.exists() {
        if fs::OpenOptions::new().write(true).open(db_path).is_err() {
            bail!("Root privileges required for package operations. Please run with sudo or as root.");
        }
    } else if let Some(parent) = db_path.parent() {
        if !parent.exists() {
            if fs::create_dir_all(parent).is_err() {
                bail!("Root privileges required for package operations. Please run with sudo or as root.");
            }
        } else {
            let probe = parent.join(".portadora_probe_write");
            if fs::File::create(&probe).map(|_| { let _ = fs::remove_file(&probe); }).is_err() {
                bail!("Root privileges required for package operations. Please run with sudo or as root.");
            }
        }
    }
    Ok(())
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let root = cli.root.canonicalize().unwrap_or_else(|_| cli.root.clone());
    let db_path = resolve_db_path(&root, cli.db_path.as_deref());

    if cli.verbose {
        eprintln!("[portadora] Operating with target root: {}", root.display());
        eprintln!("[portadora] Using database: {}", db_path.display());
    }

    // Startup check: Recover any interrupted transactions for mutating commands
    let is_mutating = matches!(
        cli.command,
        Commands::Update { .. }
            | Commands::Install { .. }
            | Commands::Upgrade { .. }
            | Commands::Remove { .. }
            | Commands::Recover
    );
    if is_mutating {
        check_mutation_privileges(&db_path)?;
        if let Ok(recovered) = TransactionRecovery::recover_pending_transactions(&root) {
            if !recovered.is_empty() {
                eprintln!("[portadora] Auto-recovered {} interrupted transaction(s): {:?}", recovered.len(), recovered);
            }
        }
    }

    match cli.command {
        Commands::Update { repo_url } => {
            let url = get_repo_url(&root, repo_url.as_deref());
            execute_update(&root, &url, cli.verbose)?;
        }

        Commands::Search { query, repo_url } => {
            let url = get_repo_url(&root, repo_url.as_deref());
            let targets = load_or_update_targets(&root, &url, cli.verbose)?;
            let q = query.to_lowercase();
            let mut matches = Vec::new();

            for (_filename, tf) in &targets.targets {
                if let Some(ref custom) = tf.custom {
                    if custom.name.to_lowercase().contains(&q)
                        || custom.summary.as_deref().unwrap_or("").to_lowercase().contains(&q)
                    {
                        matches.push(custom);
                    }
                }
            }

            if matches.is_empty() {
                println!("No packages found matching '{}'.", query);
            } else {
                println!("{:<24} {:<16} {:<12} {}", "NAME", "VERSION", "ARCH", "SUMMARY");
                println!("{}", "-".repeat(70));
                for m in matches {
                    let summary = m.summary.as_deref().unwrap_or("");
                    println!(
                        "{:<24} {:<16} {:<12} {}",
                        m.name,
                        format!("{}-{}", m.version, m.release),
                        m.architecture,
                        summary
                    );
                }
            }
        }

        Commands::Info { target } => {
            let db = if db_path.exists() {
                Some(Database::open_read_only(&db_path)?)
            } else {
                None
            };

            // Check if installed first
            if let Some(ref db) = db {
                if let Ok(Some((pkg, files))) = db.get_package(&target) {
                    println!("Name         : {}", pkg.name);
                    println!("Version      : {}-{}", pkg.version, pkg.release);
                    println!("Status       : Installed");
                    println!("Architecture : {}", pkg.architecture);
                    println!("Summary      : {}", pkg.summary);
                    println!("Description  : {}", pkg.description);
                    println!("License      : {}", pkg.license);
                    println!("Size         : {} bytes", pkg.installed_size);
                    println!("Installed At : {}", pkg.install_time);
                    println!("Files count  : {}", files.len());
                    return Ok(());
                }
            }

            // Check if local file
            let target_path = Path::new(&target);
            if target_path.is_file() {
                let reader = BlzReader::open(target_path)?;
                let manifest = reader.read_manifest()?;
                let files = reader.read_files()?;
                println!("Name         : {}", manifest.package.name);
                println!("Version      : {}-{}", manifest.package.version, manifest.package.release);
                println!("Status       : Local Archive ({})", target);
                println!("Architecture : {}", manifest.package.architecture);
                println!("Summary      : {}", manifest.package.summary);
                println!("License      : {}", manifest.package.license);
                println!("Files count  : {}", files.len());
                return Ok(());
            }

            // Check repository
            let url = get_repo_url(&root, None);
            let targets = load_or_update_targets(&root, &url, cli.verbose)?;
            for (_filename, tf) in &targets.targets {
                if let Some(ref custom) = tf.custom {
                    if custom.name == target {
                        println!("Name         : {}", custom.name);
                        println!("Version      : {}-{}", custom.version, custom.release);
                        println!("Status       : Available (Remote Repository)");
                        println!("Architecture : {}", custom.architecture);
                        println!("Summary      : {}", custom.summary.as_deref().unwrap_or_default());
                        println!("Download Size: {} bytes", tf.length);
                        println!("Requires     : {}", custom.requires.join(", "));
                        println!("Provides     : {}", custom.provides.join(", "));
                        return Ok(());
                    }
                }
            }

            bail!("Package '{}' not found in database or repository.", target);
        }

        Commands::Install { packages, repo_url } => {
            let mut db = Database::open_or_create(&db_path)?;
            let url = get_repo_url(&root, repo_url.as_deref());

            // Classify packages into local files vs remote names
            let mut local_pkgs = Vec::new();
            let mut remote_pkgs = Vec::new();

            for p in &packages {
                let path = Path::new(p);
                if path.is_file() && p.ends_with(".blz") {
                    local_pkgs.push(path.to_path_buf());
                } else {
                    // Check local package cache (/var/cache/portadora/packages) for matching package
                    let cache_dir = root.join("var/cache/portadora/packages");
                    let mut found_cached = None;
                    if cache_dir.is_dir() {
                        if let Ok(entries) = fs::read_dir(&cache_dir) {
                            for entry in entries.flatten() {
                                let ep = entry.path();
                                if ep.extension().map(|e| e == "blz").unwrap_or(false) {
                                    if let Some(fname) = ep.file_name().and_then(|f| f.to_str()) {
                                        if fname.starts_with(&format!("{}-", p)) {
                                            found_cached = Some(ep);
                                            break;
                                        }
                                    }
                                }
                            }
                        }
                    }
                    if let Some(cached_pkg) = found_cached {
                        local_pkgs.push(cached_pkg);
                    } else {
                        remote_pkgs.push(p.clone());
                    }
                }
            }

            if !local_pkgs.is_empty() {
                for pkg_path in local_pkgs {
                    install_local_package(&root, &mut db, &pkg_path, cli.verbose)?;
                }
            }

            if !remote_pkgs.is_empty() {
                install_remote_packages(&root, &mut db, &remote_pkgs, &url, cli.verbose)?;
            }
        }

        Commands::Upgrade { dry_run, package, repo_url } => {
            let mut db = Database::open_or_create(&db_path)?;
            let url = get_repo_url(&root, repo_url.as_deref());
            let targets = load_or_update_targets(&root, &url, cli.verbose)?;
            let installed_pkgs = db.list_packages()?;

            let mut upgradable = Vec::new();

            for inst in &installed_pkgs {
                if let Some(ref filter_pkg) = package {
                    if &inst.name != filter_pkg {
                        continue;
                    }
                }

                let mut newest = None;
                for (_filename, tf) in &targets.targets {
                    if let Some(ref custom) = tf.custom {
                        if custom.name != inst.name
                            || !is_version_release_newer(
                                &custom.version,
                                custom.release,
                                &inst.version,
                                inst.release,
                            )
                        {
                            continue;
                        }
                        let replace = newest.as_ref().is_none_or(|current: &portadora_core::tuf::TargetCustom| {
                            is_version_release_newer(
                                &custom.version,
                                custom.release,
                                &current.version,
                                current.release,
                            )
                        });
                        if replace {
                            newest = Some(custom.clone());
                        }
                    }
                }
                if let Some(newest) = newest {
                    upgradable.push((inst.clone(), newest));
                }
            }

            if upgradable.is_empty() {
                println!("All packages are up to date. Nothing to upgrade.");
                return Ok(());
            }

            println!("Packages eligible for upgrade ({}):", upgradable.len());
            for (old_pkg, new_pkg) in &upgradable {
                println!(
                    "  {} {}-{} -> {}-{}",
                    old_pkg.name, old_pkg.version, old_pkg.release,
                    new_pkg.version, new_pkg.release
                );
            }

            if dry_run {
                println!("\n[dry-run] Simulation completed. No filesystem changes were made.");
                return Ok(());
            }

            let pkg_names: Vec<String> = upgradable.into_iter().map(|(_, n)| n.name).collect();
            install_remote_packages(&root, &mut db, &pkg_names, &url, cli.verbose)?;
        }

        Commands::Remove { package } => {
            let mut db = Database::open_or_create(&db_path)?;
            println!("Removing package '{}'...", package);
            db.remove_package(&package, &root)?;
            let tx_id = format!("rm-{}", chrono::Utc::now().timestamp_millis());
            let _ = db.record_history(&tx_id, "REMOVE", &package, "", 0, "SUCCESS");
            println!("Successfully removed '{}'", package);
        }

        Commands::List => {
            if !db_path.exists() {
                println!("No packages installed (database does not exist).");
                return Ok(());
            }

            let db = Database::open_read_only(&db_path)?;
            let packages = db.list_packages()?;

            if packages.is_empty() {
                println!("No packages installed.");
                return Ok(());
            }

            for pkg in packages {
                println!("{} {}-{}", pkg.name, pkg.version, pkg.release);
            }
        }

        Commands::Verify { package } => {
            if !db_path.exists() {
                bail!("Database does not exist at {}", db_path.display());
            }
            let db = Database::open_read_only(&db_path)?;
            let issues = db.verify_files(&root, package.as_deref())?;

            let mut critical_failures = 0;
            let mut notices = 0;
            let mut unreadable_privileged = 0;

            for issue in &issues {
                match issue.issue_type.as_str() {
                    "UNREADABLE_PRIVILEGED" => {
                        unreadable_privileged += 1;
                        if cli.verbose {
                            eprintln!("[NOTICE] [{}] {}: {} ({})", issue.package_name, issue.path, issue.issue_type, issue.details);
                        }
                    }
                    "MUTABLE_CONFIG" => {
                        notices += 1;
                        if cli.verbose {
                            eprintln!("[NOTICE] [{}] {}: {} ({})", issue.package_name, issue.path, issue.issue_type, issue.details);
                        }
                    }
                    _ => {
                        critical_failures += 1;
                        eprintln!(
                            "[{}] {}: {} ({})",
                            issue.package_name, issue.path, issue.issue_type, issue.details
                        );
                    }
                }
            }

            if critical_failures > 0 {
                bail!("Package verification failed with {} integrity issue(s).", critical_failures);
            }

            if unreadable_privileged > 0 || notices > 0 {
                println!("Package verification completed with notices ({} unreadable privileged, {} mutable config).", unreadable_privileged, notices);
            } else {
                println!("All managed files verified.");
            }
        }

        Commands::History => {
            if !db_path.exists() {
                println!("No transaction history found.");
                return Ok(());
            }
            let db = Database::open_read_only(&db_path)?;
            let history = db.list_history()?;
            if history.is_empty() {
                println!("No transactions recorded.");
                return Ok(());
            }
            println!("{:<20} {:<10} {:<24} {:<16} {:<10}", "TX_ID", "ACTION", "PACKAGE", "VERSION", "STATUS");
            println!("{}", "-".repeat(84));
            for h in history {
                println!(
                    "{:<20} {:<10} {:<24} {:<16} {:<10}",
                    h.tx_id, h.action, h.package_name, format!("{}-{}", h.version, h.release), h.status
                );
            }
        }

        Commands::Recover => {
            let recovered = TransactionRecovery::recover_pending_transactions(&root)?;
            if recovered.is_empty() {
                println!("No interrupted transactions to recover. System is consistent.");
            } else {
                println!("Successfully recovered {} transaction(s):", recovered.len());
                for r in recovered {
                    println!("  - {}", r);
                }
            }
        }
    }

    Ok(())
}

fn install_local_package(root: &Path, db: &mut Database, pkg_path: &Path, verbose: bool) -> Result<()> {
    let reader = BlzReader::open(pkg_path)
        .with_context(|| format!("Failed to open package: {}", pkg_path.display()))?;

    let manifest = reader.read_manifest()?;
    let files = reader.read_files()?;

    println!(
        "Installing {} {}-{} ({})...",
        manifest.package.name, manifest.package.version, manifest.package.release, manifest.package.architecture
    );

    db.check_conflicts(&manifest.package.name, &files)?;

    // Extract payload safely into rootfs
    reader.extract_payload(root)?;

    // Atomically commit to database
    db.record_installed(&manifest, &files, root)?;

    let tx_id = format!("tx-local-{}", chrono::Utc::now().timestamp_millis());
    let _ = db.record_history(
        &tx_id, "INSTALL", &manifest.package.name, &manifest.package.version, manifest.package.release, "SUCCESS"
    );

    execute_declarative_triggers(root, &manifest, verbose);
    println!("Successfully installed {} ({})", manifest.package.name, manifest.package.version);
    Ok(())
}

fn install_remote_packages(
    root: &Path,
    db: &mut Database,
    package_names: &[String],
    repo_url: &str,
    verbose: bool,
) -> Result<()> {
    let targets = load_or_update_targets(root, repo_url, verbose)?;

    // 1. Resolve dependency DAG with cycle detection
    let installed_pkgs: HashSet<String> = db.list_packages()?.into_iter().map(|p| p.name).collect();
    let installed_provides = db.get_installed_provides_map()?;

    let resolver = DependencyResolver::new(&targets, installed_pkgs, installed_provides);
    let resolved_nodes = resolver.resolve(package_names)?;

    if resolved_nodes.is_empty() {
        println!("All requested packages are already satisfied.");
        return Ok(());
    }

    println!("Packages to install ({}):", resolved_nodes.len());
    for node in &resolved_nodes {
        println!("  - {} {}-{} ({})", node.name, node.version, node.release, node.filename);
    }

    // 2. Download and verify artifacts using PackageDownloader
    let cache_dir = root.join("var/cache/portadora/packages");
    let downloader = PackageDownloader::new(&cache_dir)?;

    let mut downloaded_paths = Vec::new();
    for node in &resolved_nodes {
        let expected_sha256 = node.target_file.hashes.get("sha256")
            .context("Missing SHA-256 in target metadata")?;
        let expected_size = node.target_file.length;

        if verbose {
            eprintln!("[portadora] Fetching artifact: {}", node.filename);
        }
        let pkg_path = downloader.download_or_cached(repo_url, &node.filename, expected_sha256, expected_size)?;
        downloaded_paths.push((node, pkg_path));
    }

    // 3. Begin durable filesystem transaction with write-ahead journal
    let tx_id = format!("tx-{}", chrono::Utc::now().timestamp_millis());
    let all_pkg_names: Vec<String> = resolved_nodes.iter().map(|n| n.name.clone()).collect();
    let mut tx = Transaction::begin(root, &tx_id, all_pkg_names)?;

    let mut is_self_upgrade = false;

    // 4. Staging & Journal Preparation Phase
    for (node, pkg_path) in &downloaded_paths {
        let reader = BlzReader::open(pkg_path)?;
        let files = reader.read_files()?;

        // Pre-flight file conflict check
        db.check_conflicts(&node.name, &files)?;

        // Extract package into staging directory
        let stage_root = tx.staging_dir.clone();
        reader.extract_payload(&stage_root)?;

        for file in &files {
            if file.file_type == portadora_core::FileType::Directory {
                continue;
            }
            let target_path = root.join(&file.path);
            let staging_path = stage_root.join(&file.path);
            let backup_path = tx.journal_dir.join("backups").join(&file.path);

            if file.path == "usr/bin/portadora" {
                is_self_upgrade = true;
            }

            if target_path.exists() || target_path.is_symlink() {
                tx.record_op(JournalOp::Replace {
                    target_path,
                    staging_path,
                    backup_path,
                });
            } else {
                tx.record_op(JournalOp::Create {
                    target_path,
                    staging_path,
                });
            }
        }
    }

    // Flush durable journal to disk before applying any live filesystem change
    tx.set_state(portadora_core::TxState::Journaled)?;

    // 5. Apply changes to live rootfs
    if let Err(e) = tx.apply() {
        eprintln!("[portadora] Error applying transaction, executing rollback: {:#}", e);
        tx.rollback()?;
        bail!("Transaction failed and was rolled back: {:#}", e);
    }

    // 6. Portadora Self-Upgrade Verification
    if is_self_upgrade {
        if verbose {
            eprintln!("[portadora] Self-upgrade detected, running sanity check on new portadora binary...");
        }
        let portadora_bin = root.join("usr/bin/portadora");
        let status = Command::new(&portadora_bin)
            .arg("--version")
            .status();

        match status {
            Ok(s) if s.success() => {
                if verbose {
                    eprintln!("[portadora] New portadora binary verified successfully!");
                }
            }
            _ => {
                eprintln!("[portadora] ERROR: New portadora binary failed verification! Rolling back self-upgrade...");
                tx.rollback()?;
                bail!("PortadoraSelfUpgradeFailed: new binary failed verification and was rolled back");
            }
        }
    }

    // 7. Update database and history
    for (node, pkg_path) in &downloaded_paths {
        let reader = BlzReader::open(pkg_path)?;
        let manifest = reader.read_manifest()?;
        let files = reader.read_files()?;

        db.record_installed(&manifest, &files, root)?;
        let _ = db.record_history(&tx_id, "INSTALL", &node.name, &node.version, node.release, "SUCCESS");

        execute_declarative_triggers(root, &manifest, verbose);
        println!("Successfully installed {} ({}-{})", node.name, node.version, node.release);
    }

    // 8. Finalize transaction & cleanup
    tx.commit()?;
    tx.cleanup()?;
    Ok(())
}

fn execute_declarative_triggers(root: &Path, manifest: &portadora_core::Manifest, verbose: bool) {
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
