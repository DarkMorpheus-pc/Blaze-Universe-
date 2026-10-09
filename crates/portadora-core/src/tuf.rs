use std::collections::HashMap;
use std::fs;
use std::path::Path;

use anyhow::{bail, Context, Result};
use chrono::{DateTime, Utc};
use ed25519_dalek::{Signature, VerifyingKey};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KeyDefinition {
    pub keytype: String,
    pub scheme: String,
    pub keyval: String, // hex encoded ed25519 public key
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RoleDefinition {
    pub keyids: Vec<String>,
    pub threshold: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SignatureEntry {
    pub keyid: String,
    pub sig: String, // hex encoded signature
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SignedMetadata<T> {
    pub signatures: Vec<SignatureEntry>,
    pub signed: T,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RootMetadata {
    pub _type: String,
    pub spec_version: String,
    pub version: u64,
    pub expires: DateTime<Utc>,
    pub keys: HashMap<String, KeyDefinition>,
    pub roles: HashMap<String, RoleDefinition>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MetaFileInfo {
    pub version: u64,
    pub length: Option<u64>,
    pub hashes: HashMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TimestampMetadata {
    pub _type: String,
    pub spec_version: String,
    pub version: u64,
    pub expires: DateTime<Utc>,
    pub meta: HashMap<String, MetaFileInfo>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SnapshotMetadata {
    pub _type: String,
    pub spec_version: String,
    pub version: u64,
    pub expires: DateTime<Utc>,
    pub meta: HashMap<String, MetaFileInfo>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TargetCustom {
    pub name: String,
    pub version: String,
    pub release: u32,
    pub architecture: String,
    pub summary: Option<String>,
    pub requires: Vec<String>,
    pub provides: Vec<String>,
    pub conflicts: Vec<String>,
    pub replaces: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TargetFile {
    pub length: u64,
    pub hashes: HashMap<String, String>,
    pub custom: Option<TargetCustom>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TargetsMetadata {
    pub _type: String,
    pub spec_version: String,
    pub version: u64,
    pub expires: DateTime<Utc>,
    pub targets: HashMap<String, TargetFile>,
}

pub fn canonical_json<T: Serialize>(value: &T) -> Result<Vec<u8>> {
    let val = serde_json::to_value(value)?;
    let canonical_val = sort_json_value(val);
    Ok(serde_json::to_vec(&canonical_val)?)
}

fn sort_json_value(val: serde_json::Value) -> serde_json::Value {
    match val {
        serde_json::Value::Object(map) => {
            let mut sorted_map = serde_json::Map::new();
            let mut keys: Vec<String> = map.keys().cloned().collect();
            keys.sort();
            for k in keys {
                if let Some(v) = map.get(&k) {
                    sorted_map.insert(k, sort_json_value(v.clone()));
                }
            }
            serde_json::Value::Object(sorted_map)
        }
        serde_json::Value::Array(arr) => {
            serde_json::Value::Array(arr.into_iter().map(sort_json_value).collect())
        }
        other => other,
    }
}

pub fn verify_signature(
    public_key_hex: &str,
    sig_hex: &str,
    message: &[u8],
) -> Result<bool> {
    let key_bytes = hex::decode(public_key_hex)
        .context("Invalid hex public key")?;
    let sig_bytes = hex::decode(sig_hex)
        .context("Invalid hex signature")?;

    if key_bytes.len() != 32 {
        bail!("Invalid ed25519 public key length: {}", key_bytes.len());
    }
    if sig_bytes.len() != 64 {
        bail!("Invalid ed25519 signature length: {}", sig_bytes.len());
    }

    let mut key_arr = [0u8; 32];
    key_arr.copy_from_slice(&key_bytes);
    let verifying_key = VerifyingKey::from_bytes(&key_arr)
        .map_err(|e| anyhow::anyhow!("Failed to parse VerifyingKey: {e}"))?;

    let mut sig_arr = [0u8; 64];
    sig_arr.copy_from_slice(&sig_bytes);
    let signature = Signature::from_bytes(&sig_arr);

    use ed25519_dalek::Verifier;
    Ok(verifying_key.verify(message, &signature).is_ok())
}

pub struct TufVerifier {
    pub root: RootMetadata,
    pub timestamp: Option<TimestampMetadata>,
    pub snapshot: Option<SnapshotMetadata>,
    pub targets: Option<TargetsMetadata>,
}

impl TufVerifier {
    pub fn new_with_trusted_root(root: RootMetadata) -> Self {
        Self {
            root,
            timestamp: None,
            snapshot: None,
            targets: None,
        }
    }

    pub fn load_trusted_root<P: AsRef<Path>>(path: P) -> Result<Self> {
        let content = fs::read(path.as_ref())
            .with_context(|| format!("Failed to read trusted root from {}", path.as_ref().display()))?;
        let signed_root: SignedMetadata<RootMetadata> = serde_json::from_slice(&content)
            .context("Failed to parse trusted root JSON")?;
        
        let message = canonical_json(&signed_root.signed)?;
        let role = signed_root.signed.roles.get("root")
            .context("Missing 'root' role in root metadata")?;

        let mut valid_signatures = 0;
        for sig in &signed_root.signatures {
            if role.keyids.contains(&sig.keyid) {
                if let Some(key_def) = signed_root.signed.keys.get(&sig.keyid) {
                    if verify_signature(&key_def.keyval, &sig.sig, &message)? {
                        valid_signatures += 1;
                    }
                }
            }
        }

        if valid_signatures < role.threshold {
            bail!(
                "Trusted root signature check failed: got {} valid signatures, required threshold is {}",
                valid_signatures,
                role.threshold
            );
        }

        Ok(Self::new_with_trusted_root(signed_root.signed))
    }

    pub fn load_cached_metadata<P: AsRef<Path>>(&mut self, meta_dir: P) {
        let meta_dir = meta_dir.as_ref();
        let ts_path = meta_dir.join("timestamp.json");
        if ts_path.is_file() {
            if let Ok(c) = fs::read(&ts_path) {
                if let Ok(signed) = serde_json::from_slice::<SignedMetadata<TimestampMetadata>>(&c) {
                    self.timestamp = Some(signed.signed);
                }
            }
        }
        let snap_path = meta_dir.join("snapshot.json");
        if snap_path.is_file() {
            if let Ok(c) = fs::read(&snap_path) {
                if let Ok(signed) = serde_json::from_slice::<SignedMetadata<SnapshotMetadata>>(&c) {
                    self.snapshot = Some(signed.signed);
                }
            }
        }
        let targets_path = meta_dir.join("targets.json");
        if targets_path.is_file() {
            if let Ok(c) = fs::read(&targets_path) {
                if let Ok(signed) = serde_json::from_slice::<SignedMetadata<TargetsMetadata>>(&c) {
                    self.targets = Some(signed.signed);
                }
            }
        }
    }

    pub fn update_root(&mut self, new_root_raw: &[u8]) -> Result<()> {
        let signed_new: SignedMetadata<RootMetadata> = serde_json::from_slice(new_root_raw)
            .context("Failed to parse candidate root.json")?;

        if signed_new.signed.version < self.root.version {
            bail!(
                "SecurityError::RollbackDetected: candidate root version {} < current version {}",
                signed_new.signed.version,
                self.root.version
            );
        }

        if signed_new.signed.expires < Utc::now() {
            bail!("SecurityError::ExpiredMetadata: candidate root.json has expired");
        }

        let message = canonical_json(&signed_new.signed)?;

        let current_role = self.root.roles.get("root").context("Missing current root role")?;
        let mut old_valid = 0;
        for sig in &signed_new.signatures {
            if current_role.keyids.contains(&sig.keyid) {
                if let Some(key_def) = self.root.keys.get(&sig.keyid) {
                    if verify_signature(&key_def.keyval, &sig.sig, &message)? {
                        old_valid += 1;
                    }
                }
            }
        }
        if old_valid < current_role.threshold {
            bail!(
                "SecurityError::ThresholdNotMet: candidate root not signed by current root threshold ({}/{})",
                old_valid, current_role.threshold
            );
        }

        let new_role = signed_new.signed.roles.get("root").context("Missing candidate root role")?;
        let mut new_valid = 0;
        for sig in &signed_new.signatures {
            if new_role.keyids.contains(&sig.keyid) {
                if let Some(key_def) = signed_new.signed.keys.get(&sig.keyid) {
                    if verify_signature(&key_def.keyval, &sig.sig, &message)? {
                        new_valid += 1;
                    }
                }
            }
        }
        if new_valid < new_role.threshold {
            bail!(
                "SecurityError::ThresholdNotMet: candidate root not signed by new root threshold ({}/{})",
                new_valid, new_role.threshold
            );
        }

        self.root = signed_new.signed;
        Ok(())
    }

    pub fn verify_timestamp(&mut self, timestamp_raw: &[u8]) -> Result<&TimestampMetadata> {
        let signed: SignedMetadata<TimestampMetadata> = serde_json::from_slice(timestamp_raw)
            .context("Failed to parse candidate timestamp.json")?;

        if let Some(ref cur) = self.timestamp {
            if signed.signed.version < cur.version {
                bail!(
                    "SecurityError::RollbackDetected: timestamp version {} < current {}",
                    signed.signed.version, cur.version
                );
            }
        }

        if signed.signed.expires < Utc::now() {
            bail!("SecurityError::ExpiredMetadata: timestamp.json has expired (freeze attack defense)");
        }

        let role = self.root.roles.get("timestamp").context("Missing 'timestamp' role in root")?;
        let message = canonical_json(&signed.signed)?;
        let mut valid = 0;
        for sig in &signed.signatures {
            if role.keyids.contains(&sig.keyid) {
                if let Some(key_def) = self.root.keys.get(&sig.keyid) {
                    if verify_signature(&key_def.keyval, &sig.sig, &message)? {
                        valid += 1;
                    }
                }
            }
        }

        if valid < role.threshold {
            bail!("SecurityError::ThresholdNotMet: timestamp signatures below threshold ({}/{})", valid, role.threshold);
        }

        self.timestamp = Some(signed.signed);
        Ok(self.timestamp.as_ref().unwrap())
    }

    pub fn verify_snapshot(&mut self, snapshot_raw: &[u8]) -> Result<&SnapshotMetadata> {
        let timestamp = self.timestamp.as_ref().context("Timestamp must be verified before snapshot")?;
        let snap_meta_info = timestamp.meta.get("snapshot.json").context("timestamp does not declare snapshot.json")?;

        let actual_hash = hex::encode(Sha256::digest(snapshot_raw));
        if let Some(expected_hash) = snap_meta_info.hashes.get("sha256") {
            if &actual_hash != expected_hash {
                bail!("SecurityError::HashMismatch: snapshot.json sha256 mismatch (mix-and-match defense)");
            }
        }

        let signed: SignedMetadata<SnapshotMetadata> = serde_json::from_slice(snapshot_raw)
            .context("Failed to parse candidate snapshot.json")?;

        if signed.signed.version < snap_meta_info.version {
            bail!("SecurityError::RollbackDetected: snapshot version < declared timestamp version");
        }

        if signed.signed.expires < Utc::now() {
            bail!("SecurityError::ExpiredMetadata: snapshot.json has expired");
        }

        let role = self.root.roles.get("snapshot").context("Missing 'snapshot' role in root")?;
        let message = canonical_json(&signed.signed)?;
        let mut valid = 0;
        for sig in &signed.signatures {
            if role.keyids.contains(&sig.keyid) {
                if let Some(key_def) = self.root.keys.get(&sig.keyid) {
                    if verify_signature(&key_def.keyval, &sig.sig, &message)? {
                        valid += 1;
                    }
                }
            }
        }

        if valid < role.threshold {
            bail!("SecurityError::ThresholdNotMet: snapshot signatures below threshold ({}/{})", valid, role.threshold);
        }

        self.snapshot = Some(signed.signed);
        Ok(self.snapshot.as_ref().unwrap())
    }

    pub fn verify_targets(&mut self, targets_raw: &[u8]) -> Result<&TargetsMetadata> {
        let snapshot = self.snapshot.as_ref().context("Snapshot must be verified before targets")?;
        let targets_meta_info = snapshot.meta.get("targets.json").context("snapshot does not declare targets.json")?;

        let actual_hash = hex::encode(Sha256::digest(targets_raw));
        if let Some(expected_hash) = targets_meta_info.hashes.get("sha256") {
            if &actual_hash != expected_hash {
                bail!("SecurityError::HashMismatch: targets.json sha256 mismatch (mix-and-match defense)");
            }
        }

        let signed: SignedMetadata<TargetsMetadata> = serde_json::from_slice(targets_raw)
            .context("Failed to parse candidate targets.json")?;

        if signed.signed.version < targets_meta_info.version {
            bail!("SecurityError::RollbackDetected: targets version < declared snapshot version");
        }

        if signed.signed.expires < Utc::now() {
            bail!("SecurityError::ExpiredMetadata: targets.json has expired");
        }

        let role = self.root.roles.get("targets").context("Missing 'targets' role in root")?;
        let message = canonical_json(&signed.signed)?;
        let mut valid = 0;
        for sig in &signed.signatures {
            if role.keyids.contains(&sig.keyid) {
                if let Some(key_def) = self.root.keys.get(&sig.keyid) {
                    if verify_signature(&key_def.keyval, &sig.sig, &message)? {
                        valid += 1;
                    }
                }
            }
        }

        if valid < role.threshold {
            bail!("SecurityError::ThresholdNotMet: targets signatures below threshold ({}/{})", valid, role.threshold);
        }

        self.targets = Some(signed.signed);
        Ok(self.targets.as_ref().unwrap())
    }

    pub fn verify_target_payload(&self, target_name: &str, payload_bytes: &[u8]) -> Result<&TargetFile> {
        let targets = self.targets.as_ref().context("Targets metadata not loaded or verified")?;
        let target_file = targets.targets.get(target_name)
            .with_context(|| format!("Package '{}' not found in targets metadata", target_name))?;

        if payload_bytes.len() as u64 != target_file.length {
            bail!(
                "Payload size mismatch for {}: expected {} bytes, got {}",
                target_name, target_file.length, payload_bytes.len()
            );
        }

        let actual_sha256 = hex::encode(Sha256::digest(payload_bytes));
        if let Some(expected_sha256) = target_file.hashes.get("sha256") {
            if &actual_sha256 != expected_sha256 {
                bail!(
                    "SecurityError::ChecksumMismatch: Package '{}' SHA-256 mismatch (expected: {}, actual: {})",
                    target_name, expected_sha256, actual_sha256
                );
            }
        } else {
            bail!("Target metadata for '{}' does not provide sha256 checksum", target_name);
        }

        Ok(target_file)
    }
}
