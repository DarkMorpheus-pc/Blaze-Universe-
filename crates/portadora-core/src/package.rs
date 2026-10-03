use std::fs::{self, File};
use std::io::Read;
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};

use anyhow::{bail, Context, Result};
use sha2::{Digest, Sha256};
use walkdir::WalkDir;

use crate::manifest::{FileEntry, FileType, Manifest};

pub const MANIFEST_FILENAME: &str = "manifest.toml";
pub const FILES_FILENAME: &str = "files.json";
pub const DATA_FILENAME: &str = "data.tar.zst";

pub struct BlzReader {
    path: PathBuf,
}

impl BlzReader {
    pub fn open<P: AsRef<Path>>(path: P) -> Result<Self> {
        let p = path.as_ref().to_path_buf();
        if !p.exists() {
            bail!("Package file does not exist: {}", p.display());
        }
        Ok(Self { path: p })
    }

    pub fn read_manifest(&self) -> Result<Manifest> {
        let file = File::open(&self.path)?;
        let mut archive = tar::Archive::new(file);

        for entry_result in archive.entries()? {
            let mut entry = entry_result?;
            let path = entry.path()?;
            if path == Path::new(MANIFEST_FILENAME) {
                let mut content = String::new();
                entry.read_to_string(&mut content)?;
                return Manifest::from_toml(&content);
            }
        }
        bail!("Missing {} in package {}", MANIFEST_FILENAME, self.path.display());
    }

    pub fn read_files(&self) -> Result<Vec<FileEntry>> {
        let file = File::open(&self.path)?;
        let mut archive = tar::Archive::new(file);

        for entry_result in archive.entries()? {
            let mut entry = entry_result?;
            let path = entry.path()?;
            if path == Path::new(FILES_FILENAME) {
                let mut content = String::new();
                entry.read_to_string(&mut content)?;
                let files: Vec<FileEntry> = serde_json::from_str(&content)?;
                return Ok(files);
            }
        }
        bail!("Missing {} in package {}", FILES_FILENAME, self.path.display());
    }

    pub fn extract_payload<P: AsRef<Path>>(&self, target_root: P) -> Result<()> {
        let target_root = target_root.as_ref();
        let file = File::open(&self.path)?;
        let mut archive = tar::Archive::new(file);

        for entry_result in archive.entries()? {
            let mut entry = entry_result?;
            let path = entry.path()?;
            if path == Path::new(DATA_FILENAME) {
                let zstd_decoder = zstd::stream::Decoder::new(&mut entry)?;
                let mut payload_archive = tar::Archive::new(zstd_decoder);
                payload_archive.set_preserve_permissions(true);
                payload_archive.set_preserve_mtime(true);
                payload_archive.set_unpack_xattrs(false);

                let mut installed_paths: Vec<PathBuf> = Vec::new();

                let unpack_result = (|| -> Result<()> {
                    for p_entry in payload_archive.entries()? {
                        let mut p_entry = p_entry?;
                        let raw_path = p_entry.path()?.to_path_buf();

                        // 1. Strict Path Traversal Check
                        for comp in raw_path.components() {
                            if let std::path::Component::ParentDir = comp {
                                bail!("Security violation: Path traversal ('..') detected in package path: {}", raw_path.display());
                            }
                        }

                        let clean_rel: PathBuf = raw_path
                            .components()
                            .filter_map(|c| match c {
                                std::path::Component::Normal(s) => Some(s),
                                _ => None,
                            })
                            .collect();

                        if clean_rel.as_os_str().is_empty() {
                            continue;
                        }

                        let dest_path = target_root.join(&clean_rel);

                        // 2. Symlink Escape Check
                        if p_entry.header().entry_type().is_symlink() {
                            if let Some(target) = p_entry.link_name()? {
                                let target_path = target.as_ref();
                                // Check if target escapes target_root
                                if target_path.is_absolute() {
                                    // Absolute symlink: in target_root context, make sure it stays inside or is a known FHS path
                                    // Absolute symlinks inside rootfs are valid (e.g. /usr/lib/ld-linux...), but cannot contain '..'
                                    for comp in target_path.components() {
                                        if let std::path::Component::ParentDir = comp {
                                            bail!("Security violation: Absolute symlink escape with '..' detected: {} -> {}", clean_rel.display(), target_path.display());
                                        }
                                    }
                                } else {
                                    // Relative symlink: resolve from dest_path's parent
                                    let mut resolved = dest_path.parent().unwrap_or(target_root).to_path_buf();
                                    for comp in target_path.components() {
                                        match comp {
                                            std::path::Component::ParentDir => {
                                                if !resolved.pop() || !resolved.starts_with(target_root) {
                                                    bail!("Security violation: Symlink escape detected outside rootfs: {} -> {}", clean_rel.display(), target_path.display());
                                                }
                                            }
                                            std::path::Component::Normal(c) => resolved.push(c),
                                            _ => {}
                                        }
                                    }
                                }
                            }
                        }

                        if p_entry.header().entry_type().is_dir() {
                            if dest_path.exists() {
                                continue;
                            }
                        } else if dest_path.exists() || dest_path.is_symlink() {
                            let _ = fs::remove_file(&dest_path);
                        }

                        if let Some(parent) = dest_path.parent() {
                            fs::create_dir_all(parent)?;
                        }

                        p_entry.unpack(&dest_path).with_context(|| {
                            format!("Failed to unpack entry to {}", dest_path.display())
                        })?;

                        // Explicitly restore file permissions bypassing host umask
                        if !p_entry.header().entry_type().is_symlink() {
                            if let Ok(mode) = p_entry.header().mode() {
                                let _ = fs::set_permissions(
                                    &dest_path,
                                    std::fs::Permissions::from_mode(mode),
                                );
                            }
                        }

                        installed_paths.push(dest_path);
                    }
                    Ok(())
                })();

                if let Err(e) = unpack_result {
                    // Rollback newly extracted files on unpack failure
                    rollback_paths(&installed_paths);
                    return Err(e);
                }

                return Ok(());
            }
        }

        bail!("Missing {} in package {}", DATA_FILENAME, self.path.display());
    }
}

pub fn rollback_paths(paths: &[PathBuf]) {
    for path in paths.iter().rev() {
        if path.is_file() || path.is_symlink() {
            let _ = fs::remove_file(path);
        } else if path.is_dir() {
            let _ = fs::remove_dir(path); // Only removes if empty
        }
    }
}

pub struct BlzWriter;

impl BlzWriter {
    pub fn create_package<P: AsRef<Path>>(
        output_blz: P,
        manifest: &Manifest,
        destdir: P,
        compression_level: i32,
    ) -> Result<(Manifest, Vec<FileEntry>)> {
        let destdir = destdir.as_ref();
        let output_blz = output_blz.as_ref();

        if let Some(parent) = output_blz.parent() {
            fs::create_dir_all(parent)?;
        }

        // 1. Scan DESTDIR and build file list with hashes and permissions
        let mut file_entries = Vec::new();
        let mut total_installed_size: u64 = 0;

        for entry in WalkDir::new(destdir).min_depth(1) {
            let entry = entry?;
            let abs_path = entry.path();
            let rel_path = abs_path.strip_prefix(destdir)?.to_path_buf();
            let rel_path_str = rel_path.to_string_lossy().to_string();

            let symlink_meta = fs::symlink_metadata(abs_path)?;
            let file_type = if symlink_meta.file_type().is_symlink() {
                let target = fs::read_link(abs_path)?;
                let mode = format!("{:04o}", symlink_meta.permissions().mode() & 0o7777);
                file_entries.push(FileEntry {
                    path: rel_path_str,
                    file_type: FileType::Symlink,
                    mode,
                    size: 0,
                    sha256: None,
                    symlink_target: Some(target.to_string_lossy().to_string()),
                });
                continue;
            } else if symlink_meta.is_dir() {
                FileType::Directory
            } else {
                FileType::File
            };

            let mode = format!("{:04o}", symlink_meta.permissions().mode() & 0o7777);
            let size = symlink_meta.len();
            total_installed_size += size;

            let sha256 = if file_type == FileType::File {
                let mut f = File::open(abs_path)?;
                let mut hasher = Sha256::new();
                let mut buf = [0u8; 64 * 1024];
                loop {
                    let n = f.read(&mut buf)?;
                    if n == 0 {
                        break;
                    }
                    hasher.update(&buf[..n]);
                }
                Some(hex::encode(hasher.finalize()))
            } else {
                None
            };

            file_entries.push(FileEntry {
                path: rel_path_str,
                file_type,
                mode,
                size,
                sha256,
                symlink_target: None,
            });
        }

        // Sort entries deterministically
        file_entries.sort_by(|a, b| a.path.cmp(&b.path));

        // Update installed_size in manifest
        let mut final_manifest = manifest.clone();
        final_manifest.package.installed_size = total_installed_size;

        // 2. Build data.tar.zst in a temporary buffer or file
        let temp_dir = tempfile::tempdir()?;
        let data_zst_path = temp_dir.path().join(DATA_FILENAME);

        {
            let data_file = File::create(&data_zst_path)?;
            let zstd_encoder = zstd::stream::Encoder::new(data_file, compression_level)?;
            let mut tar_builder = tar::Builder::new(zstd_encoder.auto_finish());

            for file_entry in &file_entries {
                let source_path = destdir.join(&file_entry.path);
                let rel_path = Path::new(&file_entry.path);

                if file_entry.file_type == FileType::Directory {
                    tar_builder.append_dir(rel_path, &source_path)?;
                } else if file_entry.file_type == FileType::Symlink {
                    let mut header = tar::Header::new_gnu();
                    header.set_entry_type(tar::EntryType::Symlink);
                    header.set_size(0);
                    header.set_mode(0o777);
                    header.set_uid(0);
                    header.set_gid(0);
                    header.set_mtime(final_manifest.build.as_ref().map(|b| b.timestamp).unwrap_or(0));
                    let target = file_entry.symlink_target.as_deref().unwrap_or("");
                    tar_builder.append_link(&mut header, rel_path, target)?;
                } else {
                    let mut file = File::open(&source_path)?;
                    let mut header = tar::Header::new_gnu();
                    header.set_metadata_in_mode(&fs::metadata(&source_path)?, tar::HeaderMode::Deterministic);
                    let parsed_mode = u32::from_str_radix(&file_entry.mode, 8).unwrap_or(0o644);
                    header.set_mode(parsed_mode);
                    header.set_uid(0);
                    header.set_gid(0);
                    header.set_mtime(final_manifest.build.as_ref().map(|b| b.timestamp).unwrap_or(0));
                    tar_builder.append_data(&mut header, rel_path, &mut file)?;
                }
            }

            tar_builder.finish()?;
        }

        // 3. Assemble outer .blz archive
        let out_file = File::create(output_blz)?;
        let mut blz_tar = tar::Builder::new(out_file);

        // Append manifest.toml
        let manifest_bytes = final_manifest.to_toml()?.into_bytes();
        let mut manifest_header = tar::Header::new_gnu();
        manifest_header.set_size(manifest_bytes.len() as u64);
        manifest_header.set_mode(0o644);
        manifest_header.set_entry_type(tar::EntryType::Regular);
        manifest_header.set_mtime(0);
        blz_tar.append_data(&mut manifest_header, MANIFEST_FILENAME, &manifest_bytes[..])?;

        // Append files.json
        let files_bytes = serde_json::to_vec_pretty(&file_entries)?;
        let mut files_header = tar::Header::new_gnu();
        files_header.set_size(files_bytes.len() as u64);
        files_header.set_mode(0o644);
        files_header.set_entry_type(tar::EntryType::Regular);
        files_header.set_mtime(0);
        blz_tar.append_data(&mut files_header, FILES_FILENAME, &files_bytes[..])?;

        // Append data.tar.zst
        let mut data_zst_file = File::open(&data_zst_path)?;
        let data_zst_meta = data_zst_file.metadata()?;
        let mut data_header = tar::Header::new_gnu();
        data_header.set_size(data_zst_meta.len());
        data_header.set_mode(0o644);
        data_header.set_entry_type(tar::EntryType::Regular);
        data_header.set_mtime(0);
        blz_tar.append_data(&mut data_header, DATA_FILENAME, &mut data_zst_file)?;

        blz_tar.finish()?;

        Ok((final_manifest, file_entries))
    }
}
