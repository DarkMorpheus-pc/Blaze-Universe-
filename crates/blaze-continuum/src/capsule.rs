use anyhow::{Context, Result};
use chrono::Utc;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::fs::{self, File};
use std::io::Read;
use std::path::Path;

use crate::criu::ProcessMetadata;
use crate::niri::DesktopSnapshot;

/// Continuum Kapsül Manifestosu
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CapsuleManifest {
    pub schema_version: u32,
    pub capsule_id: String,
    pub created_at: String,
    pub source_hostname: String,
    pub desktop: DesktopSnapshot,
    pub processes: Vec<ProcessMetadata>,
    pub integrity_hashes: Vec<(String, String)>,
}

pub struct CapsulePacker;

impl CapsulePacker {
    /// Masaüstü ve Süreç Durumunu tek bir `.blz-state` kapsülü haline getirir
    pub fn build_capsule(
        desktop: DesktopSnapshot,
        processes: Vec<ProcessMetadata>,
        criu_dir: Option<&Path>,
        output_file: &Path,
    ) -> Result<()> {
        let temp_dir = tempfile::tempdir().context("Geçici çalışma dizini oluşturulamadı")?;
        let capsule_root = temp_dir.path();

        let mut integrity_hashes = Vec::new();

        // 1. CRIU İmajlarını kopyala (varsa)
        if let Some(c_dir) = criu_dir {
            if c_dir.exists() {
                let target_criu = capsule_root.join("criu");
                fs::create_dir_all(&target_criu)?;
                for entry in fs::read_dir(c_dir)? {
                    let entry = entry?;
                    let dest = target_criu.join(entry.file_name());
                    fs::copy(entry.path(), &dest)?;

                    // Hash al
                    let mut file = File::open(&dest)?;
                    let mut hasher = Sha256::new();
                    let mut buf = Vec::new();
                    file.read_to_end(&mut buf)?;
                    hasher.update(&buf);
                    integrity_hashes.push((
                        format!("criu/{}", entry.file_name().to_string_lossy()),
                        hex::encode(hasher.finalize()),
                    ));
                }
            }
        }

        // 2. Manifest oluştur
        let hostname = std::env::var("HOSTNAME")
            .unwrap_or_else(|_| "blaze-node".to_string());

        let manifest = CapsuleManifest {
            schema_version: 1,
            capsule_id: format!("blz-cap-{}", Utc::now().timestamp()),
            created_at: Utc::now().to_rfc3339(),
            source_hostname: hostname,
            desktop,
            processes,
            integrity_hashes,
        };

        let manifest_json = serde_json::to_string_pretty(&manifest)?;
        let manifest_path = capsule_root.join("manifest.json");
        fs::write(&manifest_path, manifest_json)?;

        // 3. Tar + Zstandard ile arşivle
        let out_file = File::create(output_file)
            .with_context(|| format!("Çıktı dosyası oluşturulamadı: {:?}", output_file))?;
        let zstd_encoder = zstd::stream::Encoder::new(out_file, 3)
            .context("Zstd encoder başlatılamadı")?;
        let mut tar_builder = tar::Builder::new(zstd_encoder.auto_finish());

        tar_builder
            .append_dir_all(".", capsule_root)
            .context("Kapsül dosyaları tar arşivine eklenemedi")?;
        tar_builder.finish()?;

        println!(
            "[+] Continuum Kapsülü başarıyla paketlendi: {:?}",
            output_file
        );
        Ok(())
    }

    /// `.blz-state` Kapsülünü açar ve manifestoyu döner
    pub fn unpack_capsule(
        capsule_file: &Path,
        extract_to: &Path,
    ) -> Result<CapsuleManifest> {
        fs::create_dir_all(extract_to)?;

        let in_file = File::open(capsule_file)
            .with_context(|| format!("Kapsül dosyası açılamadı: {:?}", capsule_file))?;
        let zstd_decoder = zstd::stream::Decoder::new(in_file)
            .context("Zstd decompressor başlatılamadı")?;
        let mut archive = tar::Archive::new(zstd_decoder);

        archive
            .unpack(extract_to)
            .context("Kapsül arşivi açılamadı")?;

        let manifest_path = extract_to.join("manifest.json");
        if !manifest_path.exists() {
            anyhow::bail!("Kapsül içinde manifest.json bulunamadı. Bozuk arşiv.");
        }

        let manifest_content = fs::read_to_string(&manifest_path)?;
        let manifest: CapsuleManifest = serde_json::from_str(&manifest_content)
            .context("manifest.json okunamadı")?;

        Ok(manifest)
    }
}
