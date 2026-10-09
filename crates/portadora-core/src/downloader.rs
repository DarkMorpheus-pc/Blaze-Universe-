use std::fs::{self, File, OpenOptions};
use std::io::{Read, Seek, SeekFrom, Write};
use std::path::{Path, PathBuf};

use anyhow::{bail, Context, Result};
use sha2::{Digest, Sha256};

pub struct PackageDownloader {
    cache_dir: PathBuf,
}

impl PackageDownloader {
    pub fn new<P: AsRef<Path>>(cache_dir: P) -> Result<Self> {
        let cache_dir = cache_dir.as_ref().to_path_buf();
        fs::create_dir_all(&cache_dir)
            .with_context(|| format!("Failed to create package cache dir: {}", cache_dir.display()))?;
        Ok(Self { cache_dir })
    }

    pub fn download_or_cached(
        &self,
        base_url: &str,
        filename: &str,
        expected_sha256: &str,
        expected_size: u64,
    ) -> Result<PathBuf> {
        let target_path = self.cache_dir.join(filename);
        let part_path = self.cache_dir.join(format!("{}.part", filename));

        // Check if fully downloaded file already exists in cache with matching hash
        if target_path.is_file() {
            if let Ok(mut f) = File::open(&target_path) {
                let mut hasher = Sha256::new();
                let mut buf = [0u8; 65536];
                let mut actual_len = 0u64;
                while let Ok(n) = f.read(&mut buf) {
                    if n == 0 { break; }
                    hasher.update(&buf[..n]);
                    actual_len += n as u64;
                }
                let actual_hash = hex::encode(hasher.finalize());
                if actual_hash == expected_sha256 && actual_len == expected_size {
                    return Ok(target_path);
                }
            }
        }

        let full_url = format!("{}/packages/{}", base_url.trim_end_matches('/'), filename);

        // Support local file URLs for offline / fast testing
        if full_url.starts_with("file://") {
            let src_path = full_url.trim_start_matches("file://");
            let data = fs::read(src_path)
                .with_context(|| format!("Failed to read local package file {}", src_path))?;
            let actual_hash = hex::encode(Sha256::digest(&data));
            if actual_hash != expected_sha256 {
                bail!("Checksum mismatch for {}: expected {}, got {}", filename, expected_sha256, actual_hash);
            }
            fs::write(&target_path, &data)?;
            return Ok(target_path);
        }

        // HTTP/HTTPS download with Range header resume
        let client = reqwest::blocking::Client::builder()
            .timeout(std::time::Duration::from_secs(60))
            .build()?;

        let mut existing_bytes = 0u64;
        if part_path.exists() {
            if let Ok(meta) = fs::metadata(&part_path) {
                existing_bytes = meta.len();
                if existing_bytes > expected_size {
                    let _ = fs::remove_file(&part_path);
                    existing_bytes = 0;
                }
            }
        }

        let mut req = client.get(&full_url);
        if existing_bytes > 0 && existing_bytes < expected_size {
            req = req.header("Range", format!("bytes={}-", existing_bytes));
        }

        let mut resp = req.send()
            .with_context(|| format!("Failed to connect to {}", full_url))?;

        let status = resp.status();
        let mut file = if status == reqwest::StatusCode::PARTIAL_CONTENT {
            OpenOptions::new().create(true).append(true).open(&part_path)?
        } else if status == reqwest::StatusCode::OK {
            existing_bytes = 0;
            File::create(&part_path)?
        } else {
            bail!("Failed to download {}: HTTP status {}", full_url, status);
        };

        let mut buf = [0u8; 65536];
        let mut downloaded = existing_bytes;
        loop {
            let n = resp.read(&mut buf)?;
            if n == 0 { break; }
            file.write_all(&buf[..n])?;
            downloaded += n as u64;
        }
        file.sync_all()?;
        drop(file);

        if downloaded != expected_size {
            bail!("Downloaded size mismatch for {}: expected {}, got {}", filename, expected_size, downloaded);
        }

        // Verify SHA-256 of completed part file
        let mut check_file = File::open(&part_path)?;
        let mut hasher = Sha256::new();
        while let Ok(n) = check_file.read(&mut buf) {
            if n == 0 { break; }
            hasher.update(&buf[..n]);
        }
        let actual_hash = hex::encode(hasher.finalize());
        if actual_hash != expected_sha256 {
            let _ = fs::remove_file(&part_path);
            bail!("SecurityError::ChecksumMismatch: Package '{}' SHA-256 mismatch (expected: {}, actual: {})", filename, expected_sha256, actual_hash);
        }

        // Rename .part to final target
        fs::rename(&part_path, &target_path)?;
        Ok(target_path)
    }
}
