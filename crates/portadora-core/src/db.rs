use std::fs::{self, File};
use std::io::Read;
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};

use anyhow::{bail, Context, Result};
use rusqlite::{params, Connection};
use sha2::{Digest, Sha256};

use crate::manifest::{FileEntry, FileType, Manifest};

pub struct Database {
    conn: Connection,
    pub db_path: PathBuf,
}

#[derive(Debug, Clone)]
pub struct InstalledPackage {
    pub id: i64,
    pub name: String,
    pub version: String,
    pub release: u32,
    pub architecture: String,
    pub summary: String,
    pub description: String,
    pub license: String,
    pub installed_size: u64,
    pub install_time: i64,
}

#[derive(Debug, Clone)]
pub struct VerificationIssue {
    pub package_name: String,
    pub path: String,
    pub issue_type: String,
    pub details: String,
}

impl Database {
    pub fn open_or_create<P: AsRef<Path>>(db_path: P) -> Result<Self> {
        let db_path = db_path.as_ref().to_path_buf();
        if let Some(parent) = db_path.parent() {
            fs::create_dir_all(parent)?;
        }

        let conn = Connection::open(&db_path)
            .with_context(|| format!("Failed to open SQLite database at {}", db_path.display()))?;

        conn.execute_batch(
            "PRAGMA foreign_keys = ON;
             PRAGMA journal_mode = WAL;
             
             CREATE TABLE IF NOT EXISTS packages (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 name TEXT NOT NULL UNIQUE,
                 version TEXT NOT NULL,
                 release INTEGER NOT NULL,
                 architecture TEXT NOT NULL,
                 summary TEXT,
                 description TEXT,
                 license TEXT,
                 installed_size INTEGER NOT NULL,
                 install_time INTEGER NOT NULL
             );

             CREATE TABLE IF NOT EXISTS package_files (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 package_id INTEGER NOT NULL REFERENCES packages(id) ON DELETE CASCADE,
                 path TEXT NOT NULL UNIQUE,
                 file_type TEXT NOT NULL,
                 mode TEXT NOT NULL,
                 size INTEGER NOT NULL,
                 sha256 TEXT,
                 symlink_target TEXT
             );

             CREATE TABLE IF NOT EXISTS package_provides (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 package_id INTEGER NOT NULL REFERENCES packages(id) ON DELETE CASCADE,
                 capability TEXT NOT NULL
             );

             CREATE TABLE IF NOT EXISTS package_dependencies (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 package_id INTEGER NOT NULL REFERENCES packages(id) ON DELETE CASCADE,
                 requirement TEXT NOT NULL
             );

             CREATE INDEX IF NOT EXISTS idx_files_path ON package_files(path);
             CREATE INDEX IF NOT EXISTS idx_provides_cap ON package_provides(capability);
            ",
        )?;

        Ok(Self { conn, db_path })
    }

    pub fn is_installed(&self, name: &str) -> Result<bool> {
        let mut stmt = self.conn.prepare("SELECT 1 FROM packages WHERE name = ?1")?;
        let exists = stmt.exists(params![name])?;
        Ok(exists)
    }

    pub fn check_conflicts(&self, pkg_name: &str, files: &[FileEntry]) -> Result<()> {
        let mut stmt = self.conn.prepare(
            "SELECT p.name FROM package_files pf
             JOIN packages p ON pf.package_id = p.id
             WHERE pf.path = ?1 AND pf.file_type != 'dir' AND p.name != ?2",
        )?;

        for file in files {
            if file.file_type == FileType::Directory {
                continue;
            }

            let conflicting_pkg: Option<String> = stmt
                .query_row(params![&file.path, pkg_name], |row| row.get(0))
                .ok();

            if let Some(other_pkg) = conflicting_pkg {
                bail!(
                    "Package ownership conflict: file '{}' is already owned by package '{}'",
                    file.path,
                    other_pkg
                );
            }
        }

        Ok(())
    }

    pub fn record_installed(
        &mut self,
        manifest: &Manifest,
        files: &[FileEntry],
        _root_path: &Path,
    ) -> Result<()> {
        // Enforce ownership conflict checking before writing
        self.check_conflicts(&manifest.package.name, files)?;

        let tx = self.conn.transaction()?;

        // If package already exists, delete old records first
        let existing_id: Option<i64> = tx
            .query_row(
                "SELECT id FROM packages WHERE name = ?1",
                params![&manifest.package.name],
                |row| row.get(0),
            )
            .ok();

        if let Some(old_id) = existing_id {
            tx.execute("DELETE FROM packages WHERE id = ?1", params![old_id])?;
        }

        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)?
            .as_secs() as i64;

        tx.execute(
            "INSERT INTO packages (name, version, release, architecture, summary, description, license, installed_size, install_time)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)",
            params![
                &manifest.package.name,
                &manifest.package.version,
                manifest.package.release,
                &manifest.package.architecture,
                &manifest.package.summary,
                &manifest.package.description,
                &manifest.package.license,
                manifest.package.installed_size,
                now,
            ],
        )?;

        let pkg_id = tx.last_insert_rowid();

        for file in files {
            let file_type_str = match file.file_type {
                FileType::File => "file",
                FileType::Directory => "dir",
                FileType::Symlink => "symlink",
            };

            // INSERT OR REPLACE in case directories are shared or overwritten
            tx.execute(
                "INSERT INTO package_files (package_id, path, file_type, mode, size, sha256, symlink_target)
                 VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
                 ON CONFLICT(path) DO UPDATE SET
                    package_id = excluded.package_id,
                    file_type = excluded.file_type,
                    mode = excluded.mode,
                    size = excluded.size,
                    sha256 = excluded.sha256,
                    symlink_target = excluded.symlink_target",
                params![
                    pkg_id,
                    &file.path,
                    file_type_str,
                    &file.mode,
                    file.size,
                    file.sha256.as_deref(),
                    file.symlink_target.as_deref(),
                ],
            )?;
        }

        for prov in &manifest.dependencies.provides {
            tx.execute(
                "INSERT INTO package_provides (package_id, capability) VALUES (?1, ?2)",
                params![pkg_id, prov],
            )?;
        }

        for req in &manifest.dependencies.requires {
            tx.execute(
                "INSERT INTO package_dependencies (package_id, requirement) VALUES (?1, ?2)",
                params![pkg_id, req],
            )?;
        }

        tx.commit()?;
        Ok(())
    }

    pub fn remove_package(&mut self, name: &str, root_path: &Path) -> Result<()> {
        let pkg_info: Option<(i64, String)> = self
            .conn
            .query_row(
                "SELECT id, version FROM packages WHERE name = ?1",
                params![name],
                |row| Ok((row.get(0)?, row.get(1)?)),
            )
            .ok();

        let (pkg_id, _) = match pkg_info {
            Some(v) => v,
            None => bail!("Package '{}' is not installed", name),
        };

        // Fetch all files owned by this package
        let mut stmt = self.conn.prepare(
            "SELECT path, file_type FROM package_files WHERE package_id = ?1 ORDER BY LENGTH(path) DESC",
        )?;

        let files: Vec<(String, String)> = stmt
            .query_map(params![pkg_id], |row| Ok((row.get(0)?, row.get(1)?)))?
            .filter_map(|r| r.ok())
            .collect();

        // Remove files and symlinks first, then directories if empty
        for (rel_path, file_type) in &files {
            let abs_path = root_path.join(rel_path);
            if !abs_path.exists() && !abs_path.is_symlink() {
                continue;
            }

            if file_type == "dir" {
                let _ = fs::remove_dir(&abs_path); // only succeeds if empty
            } else {
                fs::remove_file(&abs_path)
                    .with_context(|| format!("Failed to remove file {}", abs_path.display()))?;
            }
        }

        // Delete from database
        self.conn.execute("DELETE FROM packages WHERE id = ?1", params![pkg_id])?;

        Ok(())
    }

    pub fn list_packages(&self) -> Result<Vec<InstalledPackage>> {
        let mut stmt = self.conn.prepare(
            "SELECT id, name, version, release, architecture, summary, description, license, installed_size, install_time
             FROM packages ORDER BY name ASC",
        )?;

        let iter = stmt.query_map([], |row| {
            Ok(InstalledPackage {
                id: row.get(0)?,
                name: row.get(1)?,
                version: row.get(2)?,
                release: row.get(3)?,
                architecture: row.get(4)?,
                summary: row.get(5).unwrap_or_default(),
                description: row.get(6).unwrap_or_default(),
                license: row.get(7).unwrap_or_default(),
                installed_size: row.get(8)?,
                install_time: row.get(9)?,
            })
        })?;

        let mut list = Vec::new();
        for item in iter {
            list.push(item?);
        }
        Ok(list)
    }

    pub fn get_package(&self, name: &str) -> Result<Option<(InstalledPackage, Vec<FileEntry>)>> {
        let pkg: Option<InstalledPackage> = self
            .conn
            .query_row(
                "SELECT id, name, version, release, architecture, summary, description, license, installed_size, install_time
                 FROM packages WHERE name = ?1",
                params![name],
                |row| {
                    Ok(InstalledPackage {
                        id: row.get(0)?,
                        name: row.get(1)?,
                        version: row.get(2)?,
                        release: row.get(3)?,
                        architecture: row.get(4)?,
                        summary: row.get(5).unwrap_or_default(),
                        description: row.get(6).unwrap_or_default(),
                        license: row.get(7).unwrap_or_default(),
                        installed_size: row.get(8)?,
                        install_time: row.get(9)?,
                    })
                },
            )
            .ok();

        let pkg = match pkg {
            Some(p) => p,
            None => return Ok(None),
        };

        let mut stmt = self.conn.prepare(
            "SELECT path, file_type, mode, size, sha256, symlink_target 
             FROM package_files WHERE package_id = ?1 ORDER BY path ASC",
        )?;

        let files = stmt
            .query_map(params![pkg.id], |row| {
                let ft_str: String = row.get(1)?;
                let file_type = match ft_str.as_str() {
                    "dir" => FileType::Directory,
                    "symlink" => FileType::Symlink,
                    _ => FileType::File,
                };

                Ok(FileEntry {
                    path: row.get(0)?,
                    file_type,
                    mode: row.get(2)?,
                    size: row.get(3)?,
                    sha256: row.get(4)?,
                    symlink_target: row.get(5)?,
                })
            })?
            .filter_map(|r| r.ok())
            .collect();

        Ok(Some((pkg, files)))
    }

    pub fn verify_files(&self, root_path: &Path, specific_package: Option<&str>) -> Result<Vec<VerificationIssue>> {
        let mut issues = Vec::new();

        let query = match specific_package {
            Some(_) => {
                "SELECT p.name, f.path, f.file_type, f.mode, f.size, f.sha256, f.symlink_target
                 FROM package_files f
                 JOIN packages p ON f.package_id = p.id
                 WHERE p.name = ?1"
            }
            None => {
                "SELECT p.name, f.path, f.file_type, f.mode, f.size, f.sha256, f.symlink_target
                 FROM package_files f
                 JOIN packages p ON f.package_id = p.id"
            }
        };

        let mut stmt = self.conn.prepare(query)?;
        let mut rows = match specific_package {
            Some(pkg) => stmt.query(params![pkg])?,
            None => stmt.query([])?,
        };

        while let Some(row) = rows.next()? {
            let pkg_name: String = row.get(0)?;
            let rel_path: String = row.get(1)?;
            let file_type: String = row.get(2)?;
            let expected_mode: String = row.get(3)?;
            let _expected_size: u64 = row.get(4)?;
            let expected_sha256: Option<String> = row.get(5)?;
            let expected_symlink: Option<String> = row.get(6)?;

            let abs_path = root_path.join(&rel_path);

            if !abs_path.exists() && !abs_path.is_symlink() {
                issues.push(VerificationIssue {
                    package_name: pkg_name,
                    path: rel_path,
                    issue_type: "MISSING".into(),
                    details: "File or directory does not exist on disk".into(),
                });
                continue;
            }

            let meta = match fs::symlink_metadata(&abs_path) {
                Ok(m) => m,
                Err(e) => {
                    issues.push(VerificationIssue {
                        package_name: pkg_name,
                        path: rel_path,
                        issue_type: "ACCESS_ERROR".into(),
                        details: format!("Cannot read metadata: {}", e),
                    });
                    continue;
                }
            };

            let is_actual_symlink = meta.file_type().is_symlink();
            let is_actual_dir = meta.file_type().is_dir();
            let is_actual_file = meta.file_type().is_file();

            let type_ok = match file_type.as_str() {
                "symlink" => is_actual_symlink,
                "dir" => is_actual_dir,
                "file" => is_actual_file,
                _ => false,
            };

            if !type_ok {
                issues.push(VerificationIssue {
                    package_name: pkg_name.clone(),
                    path: rel_path.clone(),
                    issue_type: "TYPE_MISMATCH".into(),
                    details: format!("Expected file type '{}', found different type on disk", file_type),
                });
                continue;
            }

            // Mode check (compare last 4 octal digits)
            let is_runtime_mount = matches!(rel_path.as_str(), "run" | "proc" | "sys" | "dev");
            let actual_mode = format!("{:04o}", meta.permissions().mode() & 0o7777);
            if actual_mode != expected_mode && file_type != "symlink" && !is_runtime_mount {
                issues.push(VerificationIssue {
                    package_name: pkg_name.clone(),
                    path: rel_path.clone(),
                    issue_type: "MODE_MISMATCH".into(),
                    details: format!("Expected mode {}, got {}", expected_mode, actual_mode),
                });
            }

            if file_type == "symlink" {
                match fs::read_link(&abs_path) {
                    Ok(target) => {
                        let target_str = target.to_string_lossy().to_string();
                        if let Some(ref exp) = expected_symlink {
                            if &target_str != exp {
                                issues.push(VerificationIssue {
                                    package_name: pkg_name,
                                    path: rel_path,
                                    issue_type: "SYMLINK_MISMATCH".into(),
                                    details: format!("Expected link to '{}', but points to '{}'", exp, target_str),
                                });
                            }
                        }
                    }
                    Err(e) => {
                        issues.push(VerificationIssue {
                            package_name: pkg_name,
                            path: rel_path,
                            issue_type: "CORRUPT_SYMLINK".into(),
                            details: format!("Failed to read symlink target: {}", e),
                        });
                    }
                }
            } else if file_type == "file" {
                if let Some(ref expected_hash) = expected_sha256 {
                    let mut file = match File::open(&abs_path) {
                        Ok(f) => f,
                        Err(e) => {
                            issues.push(VerificationIssue {
                                package_name: pkg_name,
                                path: rel_path,
                                issue_type: "READ_ERROR".into(),
                                details: format!("Failed to open file: {}", e),
                            });
                            continue;
                        }
                    };

                    let mut hasher = Sha256::new();
                    let mut buf = [0u8; 64 * 1024];
                    let mut hash_err = false;
                    loop {
                        match file.read(&mut buf) {
                            Ok(0) => break,
                            Ok(n) => hasher.update(&buf[..n]),
                            Err(e) => {
                                issues.push(VerificationIssue {
                                    package_name: pkg_name.clone(),
                                    path: rel_path.clone(),
                                    issue_type: "READ_ERROR".into(),
                                    details: format!("Failed reading file for hashing: {}", e),
                                });
                                hash_err = true;
                                break;
                            }
                        }
                    }

                    if !hash_err {
                        let actual_hash = hex::encode(hasher.finalize());
                        if actual_hash != *expected_hash {
                            issues.push(VerificationIssue {
                                package_name: pkg_name,
                                path: rel_path,
                                issue_type: "CHECKSUM_MISMATCH".into(),
                                details: format!("Expected SHA256 {}, got {}", expected_hash, actual_hash),
                            });
                        }
                    }
                }
            }
        }

        Ok(issues)
    }
}
