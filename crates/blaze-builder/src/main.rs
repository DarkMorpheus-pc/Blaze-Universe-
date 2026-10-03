mod recipe;

use std::fs::{self, File};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::process::Command;

use anyhow::{bail, Context, Result};
use clap::Parser;
use portadora_core::{
    scan_elf, BlzWriter, BuildMeta, Dependencies, Manifest, PackageMeta, Triggers,
};
use recipe::Recipe;
use sha2::{Digest, Sha256};
use walkdir::WalkDir;

#[derive(Parser, Debug)]
#[command(name = "blaze-builder")]
#[command(author = "BlazeOS Core Team <core@blazeos.org>")]
#[command(version = "0.1.0")]
#[command(about = "Deterministic package builder and recipe compiler for BlazeOS Native")]
struct Args {
    /// Path to recipe.toml
    #[arg(required = true)]
    recipe: PathBuf,

    /// Output directory for generated .blz packages
    #[arg(long, default_value = "build/packages")]
    output_dir: PathBuf,

    /// Cache directory for downloaded sources
    #[arg(long, default_value = "build/sources")]
    sources_dir: PathBuf,

    /// Scratch working directory for compiling
    #[arg(long, default_value = "build/work")]
    work_dir: PathBuf,

    /// Keep build artifacts after completion (for debugging)
    #[arg(long)]
    keep_work: bool,

    /// Zstd compression level (1-22, default: 3 for rapid local dev)
    #[arg(long, default_value_t = 3)]
    compression_level: i32,
}

fn calculate_sha256<P: AsRef<Path>>(path: P) -> Result<String> {
    let mut file = File::open(path)?;
    let mut hasher = Sha256::new();
    let mut buffer = [0u8; 64 * 1024];
    loop {
        let n = file.read(&mut buffer)?;
        if n == 0 {
            break;
        }
        hasher.update(&buffer[..n]);
    }
    Ok(hex::encode(hasher.finalize()))
}

fn download_source(url: &str, target_path: &Path, expected_sha256: &str) -> Result<()> {
    if target_path.exists() {
        let actual_hash = calculate_sha256(target_path)?;
        if actual_hash.eq_ignore_ascii_case(expected_sha256) {
            println!("Cached source verified: {}", target_path.display());
            return Ok(());
        } else {
            eprintln!("Cached source checksum mismatch, re-downloading...");
            fs::remove_file(target_path)?;
        }
    }

    if let Some(parent) = target_path.parent() {
        fs::create_dir_all(parent)?;
    }

    println!("Downloading source: {}", url);
    let mut response = reqwest::blocking::get(url)
        .with_context(|| format!("Failed to fetch source from {}", url))?;

    if !response.status().is_success() {
        bail!("Failed to download {}: HTTP {}", url, response.status());
    }

    let mut dest_file = File::create(target_path)?;
    response.copy_to(&mut dest_file)?;

    let actual_hash = calculate_sha256(target_path)?;
    if !actual_hash.eq_ignore_ascii_case(expected_sha256) {
        fs::remove_file(target_path)?;
        bail!(
            "Checksum mismatch for {}: expected {}, got {}",
            url,
            expected_sha256,
            actual_hash
        );
    }

    println!("Source verified: {}", target_path.display());
    Ok(())
}

fn extract_archive(archive_path: &Path, extract_to: &Path) -> Result<()> {
    fs::create_dir_all(extract_to)?;
    let path_str = archive_path.to_string_lossy();

    let file = File::open(archive_path)?;

    if path_str.ends_with(".tar.gz") || path_str.ends_with(".tgz") {
        let gz = flate2::read::GzDecoder::new(file);
        let mut tar = tar::Archive::new(gz);
        tar.unpack(extract_to)?;
    } else if path_str.ends_with(".tar.xz") {
        let xz = xz2::read::XzDecoder::new(file);
        let mut tar = tar::Archive::new(xz);
        tar.unpack(extract_to)?;
    } else if path_str.ends_with(".tar.bz2") {
        let bz = bzip2::read::BzDecoder::new(file);
        let mut tar = tar::Archive::new(bz);
        tar.unpack(extract_to)?;
    } else if path_str.ends_with(".tar.zst") {
        let zst = zstd::stream::Decoder::new(file)?;
        let mut tar = tar::Archive::new(zst);
        tar.unpack(extract_to)?;
    } else if path_str.ends_with(".tar") {
        let mut tar = tar::Archive::new(file);
        tar.unpack(extract_to)?;
    } else {
        bail!("Unsupported archive format: {}", path_str);
    }

    Ok(())
}

fn main() -> Result<()> {
    let args = Args::parse();
    let recipe = Recipe::load_from_file(&args.recipe)?;

    println!(
        "Building package: {} {}-{} ({})",
        recipe.package.name,
        recipe.package.version,
        recipe.package.release,
        recipe.package.architecture
    );

    // Prepare directories
    let current_dir = std::env::current_dir()?;
    let output_dir = current_dir.join(&args.output_dir);
    let sources_dir = current_dir.join(&args.sources_dir);
    let work_dir = current_dir.join(&args.work_dir);

    fs::create_dir_all(&output_dir)?;
    fs::create_dir_all(&sources_dir)?;

    let pkg_work_dir = work_dir.join(format!(
        "{}-{}-{}",
        recipe.package.name, recipe.package.version, recipe.package.release
    ));

    if pkg_work_dir.exists() {
        fs::remove_dir_all(&pkg_work_dir)?;
    }
    fs::create_dir_all(&pkg_work_dir)?;

    let src_dir = pkg_work_dir.join("src");
    let dest_dir = pkg_work_dir.join("dest");
    fs::create_dir_all(&src_dir)?;
    fs::create_dir_all(&dest_dir)?;

    // Handle source download & extraction
    let mut source_url = String::new();
    let mut source_sha256 = String::new();

    if let Some(src) = &recipe.source {
        source_url = src.url.clone();
        source_sha256 = src.sha256.clone();

        let filename = src.filename.clone().unwrap_or_else(|| {
            src.url
                .split('/')
                .last()
                .unwrap_or("source.tar.gz")
                .to_string()
        });

        let local_source_path = args.sources_dir.join(filename);
        download_source(&src.url, &local_source_path, &src.sha256)?;

        println!("Extracting source archive into {}...", src_dir.display());
        extract_archive(&local_source_path, &src_dir)?;
    }

    // Determine actual source root (if tarball unpacked into a single subdirectory)
    let mut build_cwd = src_dir.clone();
    let entries: Vec<_> = fs::read_dir(&src_dir)?.filter_map(|e| e.ok()).collect();
    if entries.len() == 1 && entries[0].file_type()?.is_dir() {
        build_cwd = entries[0].path();
    }

    // Run build script
    println!("Executing build script in {}...", build_cwd.display());
    let script_path = pkg_work_dir.join("build.sh");
    {
        let mut script_file = File::create(&script_path)?;
        writeln!(script_file, "#!/usr/bin/env bash")?;
        writeln!(script_file, "set -euo pipefail")?;
        writeln!(script_file, "export DESTDIR=\"{}\"", dest_dir.display())?;
        writeln!(script_file, "export PREFIX=\"/usr\"")?;
        writeln!(script_file, "export ARCH=\"{}\"", recipe.package.architecture)?;
        writeln!(script_file, "export JOBS=\"{}\"", num_cpus())?;
        writeln!(script_file, "export CURRENT_DIR=\"{}\"", current_dir.display())?;
        writeln!(script_file, "{}", recipe.build.script)?;
    }

    let status = Command::new("bash")
        .arg(&script_path)
        .current_dir(&build_cwd)
        .status()
        .with_context(|| "Failed to execute build script")?;

    if !status.success() {
        bail!("Build script failed with exit code: {:?}", status.code());
    }

    // ELF Scan for SONAME and DT_NEEDED capabilities
    println!("Scanning DESTDIR for ELF binaries and libraries...");
    let mut auto_provides = recipe.dependencies.provides.clone();
    let mut auto_requires = recipe.dependencies.requires.clone();

    for entry in WalkDir::new(&dest_dir).min_depth(1) {
        let entry = entry?;
        let path = entry.path();
        if path.is_file() {
            if let Ok(Some(elf)) = scan_elf(path) {
                if let Some(soname) = elf.soname {
                    let prov = format!("lib:{}", soname);
                    if !auto_provides.contains(&prov) {
                        println!("  Discovered SONAME provide: {}", prov);
                        auto_provides.push(prov);
                    }
                }
            }
        }
    }

    auto_provides.sort();
    auto_provides.dedup();
    auto_requires.sort();
    auto_requires.dedup();

    // Assemble Manifest
    let timestamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)?
        .as_secs();

    let manifest = Manifest {
        package: PackageMeta {
            name: recipe.package.name.clone(),
            version: recipe.package.version.clone(),
            release: recipe.package.release,
            architecture: recipe.package.architecture.clone(),
            summary: recipe.package.summary.clone(),
            description: recipe.package.description.clone(),
            license: recipe.package.license.clone(),
            maintainer: recipe.package.maintainer.clone(),
            url: recipe.package.url.clone(),
            installed_size: 0, // Will be computed by BlzWriter
        },
        dependencies: Dependencies {
            requires: auto_requires,
            provides: auto_provides,
            conflicts: recipe.dependencies.conflicts.clone(),
        },
        build: Some(BuildMeta {
            builder: "blaze-builder 0.1.0".into(),
            timestamp,
            source_url,
            source_sha256,
        }),
        triggers: Triggers::default(),
        sysusers: recipe.sysusers.clone(),
        tmpfiles: recipe.tmpfiles.clone(),
        services: recipe.services.clone(),
    };

    let output_filename = format!(
        "{}-{}-{}.{}.blz",
        manifest.package.name,
        manifest.package.version,
        manifest.package.release,
        manifest.package.architecture
    );
    let output_path = output_dir.join(output_filename);

    println!("Creating package archive: {}...", output_path.display());
    let (final_manifest, files) = BlzWriter::create_package(
        &output_path,
        &manifest,
        &dest_dir,
        args.compression_level,
    )?;

    println!(
        "Package created successfully! Files: {}, Size: {} bytes -> {}",
        files.len(),
        final_manifest.package.installed_size,
        output_path.display()
    );

    if !args.keep_work {
        let _ = fs::remove_dir_all(&pkg_work_dir);
    }

    Ok(())
}

fn num_cpus() -> usize {
    std::thread::available_parallelism()
        .map(|p| p.get())
        .unwrap_or(2)
}
