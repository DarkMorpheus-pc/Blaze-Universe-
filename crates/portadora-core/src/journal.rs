use std::fs::{self, File};
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};

use anyhow::{bail, Context, Result};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum TxState {
    Prepared,
    Staged,
    Journaled,
    Applying,
    Committed,
    Aborted,
    RolledBack,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum JournalOp {
    Create {
        target_path: PathBuf,
        staging_path: PathBuf,
    },
    Replace {
        target_path: PathBuf,
        staging_path: PathBuf,
        backup_path: PathBuf,
    },
    Remove {
        target_path: PathBuf,
        backup_path: PathBuf,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TransactionJournal {
    pub tx_id: String,
    pub state: TxState,
    pub package_names: Vec<String>,
    pub operations: Vec<JournalOp>,
    pub timestamp: i64,
}

pub struct Transaction {
    pub root: PathBuf,
    pub tx_id: String,
    pub journal: TransactionJournal,
    pub staging_dir: PathBuf,
    pub journal_dir: PathBuf,
}

impl Transaction {
    pub fn begin<P: AsRef<Path>>(root: P, tx_id: &str, package_names: Vec<String>) -> Result<Self> {
        let root = root.as_ref().to_path_buf();
        let staging_dir = root.join("var/lib/portadora/staging").join(tx_id);
        let journal_dir = root.join("var/lib/portadora/journal").join(tx_id);

        fs::create_dir_all(&staging_dir)
            .with_context(|| format!("Failed to create staging dir: {}", staging_dir.display()))?;
        fs::create_dir_all(&journal_dir)
            .with_context(|| format!("Failed to create journal dir: {}", journal_dir.display()))?;
        fs::create_dir_all(journal_dir.join("backups"))?;

        let journal = TransactionJournal {
            tx_id: tx_id.to_string(),
            state: TxState::Prepared,
            package_names,
            operations: Vec::new(),
            timestamp: chrono::Utc::now().timestamp(),
        };

        let mut tx = Self {
            root,
            tx_id: tx_id.to_string(),
            journal,
            staging_dir,
            journal_dir,
        };
        tx.flush_journal()?;
        Ok(tx)
    }

    pub fn record_op(&mut self, op: JournalOp) {
        self.journal.operations.push(op);
    }

    pub fn set_state(&mut self, state: TxState) -> Result<()> {
        self.journal.state = state;
        self.flush_journal()?;
        Ok(())
    }

    pub fn flush_journal(&self) -> Result<()> {
        let journal_file = self.journal_dir.join("journal.json");
        let content = serde_json::to_vec_pretty(&self.journal)?;
        fs::write(&journal_file, &content)
            .with_context(|| format!("Failed to write journal: {}", journal_file.display()))?;
        
        // fsync journal file and journal directory
        if let Ok(file) = File::open(&journal_file) {
            let _ = file.sync_all();
        }
        if let Ok(dir) = File::open(&self.journal_dir) {
            let _ = dir.sync_all();
        }
        Ok(())
    }

    pub fn apply(&mut self) -> Result<()> {
        self.set_state(TxState::Applying)?;

        // Sort operations:
        // 1. Libraries (/usr/lib/*.so*)
        // 2. Data / etc (/etc/*, /usr/share/*)
        // 3. Helper binaries
        // 4. Primary executables (/usr/bin/*)
        let mut ops = self.journal.operations.clone();
        ops.sort_by_key(|op| {
            let path = match op {
                JournalOp::Create { target_path, .. } => target_path,
                JournalOp::Replace { target_path, .. } => target_path,
                JournalOp::Remove { target_path, .. } => target_path,
            };
            let path_str = path.to_string_lossy();
            if path_str.contains("/lib/") || path_str.ends_with(".so") || path_str.contains(".so.") {
                1
            } else if path_str.contains("/etc/") || path_str.contains("/share/") {
                2
            } else if path_str.contains("/bin/") {
                4
            } else {
                3
            }
        });

        for op in &ops {
            match op {
                JournalOp::Create { target_path, staging_path } => {
                    if let Some(parent) = target_path.parent() {
                        fs::create_dir_all(parent)?;
                    }
                    if staging_path.is_file() || staging_path.is_symlink() {
                        fs::rename(staging_path, target_path)
                            .with_context(|| format!("Failed to move {} to {}", staging_path.display(), target_path.display()))?;
                        sync_file_and_parent(target_path);
                    }
                }
                JournalOp::Replace { target_path, staging_path, backup_path } => {
                    if let Some(parent) = backup_path.parent() {
                        fs::create_dir_all(parent)?;
                    }
                    if target_path.exists() || target_path.is_symlink() {
                        // Backup existing file
                        copy_or_move(target_path, backup_path)?;
                        sync_file_and_parent(backup_path);
                    }
                    if staging_path.is_file() || staging_path.is_symlink() {
                        fs::rename(staging_path, target_path)
                            .with_context(|| format!("Failed to move replacement {} to {}", staging_path.display(), target_path.display()))?;
                        sync_file_and_parent(target_path);
                    }
                }
                JournalOp::Remove { target_path, backup_path } => {
                    if let Some(parent) = backup_path.parent() {
                        fs::create_dir_all(parent)?;
                    }
                    if target_path.exists() || target_path.is_symlink() {
                        copy_or_move(target_path, backup_path)?;
                        sync_file_and_parent(backup_path);
                        let _ = fs::remove_file(target_path);
                        if let Some(parent) = target_path.parent() {
                            if let Ok(d) = File::open(parent) {
                                let _ = d.sync_all();
                            }
                        }
                    }
                }
            }
        }

        Ok(())
    }

    pub fn commit(&mut self) -> Result<()> {
        self.set_state(TxState::Committed)?;
        Ok(())
    }

    pub fn rollback(&mut self) -> Result<()> {
        eprintln!("[portadora::journal] Rolling back transaction '{}'...", self.tx_id);
        let mut ops = self.journal.operations.clone();
        ops.reverse();

        for op in &ops {
            match op {
                JournalOp::Create { target_path, .. } => {
                    if target_path.is_file() || target_path.is_symlink() {
                        let _ = fs::remove_file(target_path);
                        if let Some(parent) = target_path.parent() {
                            if let Ok(d) = File::open(parent) {
                                let _ = d.sync_all();
                            }
                        }
                    }
                }
                JournalOp::Replace { target_path, backup_path, .. } => {
                    if backup_path.is_file() || backup_path.is_symlink() {
                        let _ = fs::rename(backup_path, target_path);
                        sync_file_and_parent(target_path);
                    }
                }
                JournalOp::Remove { target_path, backup_path } => {
                    if backup_path.is_file() || backup_path.is_symlink() {
                        let _ = fs::rename(backup_path, target_path);
                        sync_file_and_parent(target_path);
                    }
                }
            }
        }

        self.set_state(TxState::RolledBack)?;
        eprintln!("[portadora::journal] Transaction '{}' rolled back cleanly.", self.tx_id);
        Ok(())
    }

    pub fn cleanup(&self) -> Result<()> {
        let _ = fs::remove_dir_all(&self.staging_dir);
        let _ = fs::remove_dir_all(&self.journal_dir);
        Ok(())
    }
}

fn sync_file_and_parent(path: &Path) {
    if let Ok(f) = File::open(path) {
        let _ = f.sync_all();
    }
    if let Some(parent) = path.parent() {
        if let Ok(d) = File::open(parent) {
            let _ = d.sync_all();
        }
    }
}

fn copy_or_move(src: &Path, dst: &Path) -> Result<()> {
    if src.is_symlink() {
        let target = fs::read_link(src)?;
        if dst.exists() || dst.is_symlink() {
            let _ = fs::remove_file(dst);
        }
        std::os::unix::fs::symlink(target, dst)?;
    } else if src.is_dir() {
        fs::create_dir_all(dst)?;
    } else {
        if let Some(parent) = dst.parent() {
            fs::create_dir_all(parent)?;
        }
        fs::copy(src, dst)?;
        if let Ok(meta) = fs::symlink_metadata(src) {
            let _ = fs::set_permissions(dst, meta.permissions());
            #[cfg(unix)]
            {
                use std::os::unix::fs::MetadataExt;
                let _ = std::os::unix::fs::chown(dst, Some(meta.uid()), Some(meta.gid()));
            }
        }
    }
    Ok(())
}

pub struct TransactionRecovery;

impl TransactionRecovery {
    pub fn recover_pending_transactions<P: AsRef<Path>>(root: P) -> Result<Vec<String>> {
        let root = root.as_ref();
        let journal_base = root.join("var/lib/portadora/journal");
        if !journal_base.exists() {
            return Ok(Vec::new());
        }

        let mut recovered = Vec::new();
        let entries = match fs::read_dir(&journal_base) {
            Ok(e) => e,
            Err(_) => return Ok(Vec::new()),
        };

        for entry in entries.flatten() {
            let journal_file = entry.path().join("journal.json");
            if !journal_file.is_file() {
                continue;
            }

            let content = match fs::read(&journal_file) {
                Ok(c) => c,
                Err(_) => continue,
            };

            let journal: TransactionJournal = match serde_json::from_slice(&content) {
                Ok(j) => j,
                Err(_) => continue,
            };

            let tx_id = journal.tx_id.clone();
            let staging_dir = root.join("var/lib/portadora/staging").join(&tx_id);
            let journal_dir = entry.path();

            let mut tx = Transaction {
                root: root.to_path_buf(),
                tx_id: tx_id.clone(),
                journal,
                staging_dir,
                journal_dir,
            };

            match tx.journal.state {
                TxState::Prepared | TxState::Staged => {
                    eprintln!("[portadora::recovery] Aborting unapplied transaction '{}'", tx_id);
                    let _ = tx.cleanup();
                    recovered.push(format!("aborted:{}", tx_id));
                }
                TxState::Journaled | TxState::Applying => {
                    eprintln!("[portadora::recovery] Detected interrupted transaction '{}' in state {:?}, triggering rollback...", tx_id, tx.journal.state);
                    tx.rollback()?;
                    let _ = tx.cleanup();
                    recovered.push(format!("rolled_back:{}", tx_id));
                }
                TxState::Committed => {
                    eprintln!("[portadora::recovery] Finalizing cleanup for committed transaction '{}'", tx_id);
                    let _ = tx.cleanup();
                    recovered.push(format!("finalized:{}", tx_id));
                }
                TxState::Aborted | TxState::RolledBack => {
                    let _ = tx.cleanup();
                }
            }
        }

        Ok(recovered)
    }
}
