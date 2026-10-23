use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

/// CRIU Destek Durumu
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CriuSupportStatus {
    pub is_installed: bool,
    pub criu_path: Option<String>,
    pub has_capability: bool,
    pub message: String,
}

/// Süreç Durumu (CRIU veya Userspace Snapshot)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessMetadata {
    pub pid: u32,
    pub name: String,
    pub cmdline: Vec<String>,
    pub cwd: PathBuf,
    pub environ: HashMap<String, String>,
    pub is_criu_dumped: bool,
}

pub struct CriuEngine;

impl CriuEngine {
    /// Sistemde CRIU desteğini ve yetkilerini doğrular
    pub fn check_support() -> CriuSupportStatus {
        let which = Command::new("which").arg("criu").output();
        let is_installed = which.map(|o| o.status.success()).unwrap_or(false);

        if !is_installed {
            return CriuSupportStatus {
                is_installed: false,
                criu_path: None,
                has_capability: false,
                message: "criu ikili dosyası sistemde bulunamadı.".to_string(),
            };
        }

        let criu_path = Command::new("which")
            .arg("criu")
            .output()
            .ok()
            .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string());

        // criu check kontrolü
        let check_res = Command::new("criu").arg("check").output();
        let has_capability = match check_res {
            Ok(output) => output.status.success(),
            Err(_) => false,
        };

        let message = if has_capability {
            "CRIU çekirdek ve yetki kontrolünden başarıyla geçti (CAP_CHECKPOINT_RESTORE aktif)."
                .to_string()
        } else {
            "CRIU kurulu ancak CAP_CHECKPOINT_RESTORE veya root yetkisi gerekiyor. (setcap cap_checkpoint_restore+eip criu veya sudo kullanılabilir)"
                .to_string()
        };

        CriuSupportStatus {
            is_installed: true,
            criu_path,
            has_capability,
            message,
        }
    }

    /// Bir süreci CRIU kullanarak belirtilen dizine dondurur (Checkpoint / Dump)
    pub fn dump_process(pid: u32, images_dir: &Path) -> Result<()> {
        // 1. GUI ve GPU Preflight Emniyet Kontrolü
        let preflight = ProcessPreflight::inspect(pid);
        if preflight.is_gui_app {
            anyhow::bail!(
                "[WARN] [Preflight Guard]: Süreç {} bir GUI/GPU uygulamasıdır ({:?}). Wayland ve DRM donanım tamponları ağ üzerinden doğrudan taşınamaz; güvenli Rehydrate adaptörüne yönlendiriliyor.",
                pid,
                preflight.details
            );
        }

        fs::create_dir_all(images_dir).with_context(|| {
            format!("CRIU imaj dizini oluşturulamadı: {:?}", images_dir)
        })?;

        println!(
            "[*] CRIU: Süreç {} donduruluyor -> {:?}",
            pid, images_dir
        );

        let status = Command::new("criu")
            .arg("dump")
            .arg("-D")
            .arg(images_dir)
            .arg("-t")
            .arg(pid.to_string())
            .arg("--shell-job")
            .arg("--tcp-established")
            .status()
            .context("CRIU dump komutu çalıştırılamadı")?;

        if !status.success() {
            anyhow::bail!(
                "CRIU dump başarısız oldu (çıkış kodu: {:?}). Yetki eksikliği veya açık kaynak uyumsuzluğu olabilir.",
                status.code()
            );
        }

        println!("[+] CRIU: Süreç {} başarıyla donduruldu.", pid);
        Ok(())
    }

    /// Daha önce dondurulmuş bir süreci geri yükler (Restore)
    pub fn restore_process(images_dir: &Path) -> Result<()> {
        println!("[*] CRIU: Süreç geri yükleniyor <- {:?}", images_dir);

        let status = Command::new("criu")
            .arg("restore")
            .arg("-D")
            .arg(images_dir)
            .arg("--shell-job")
            .arg("--restore-detached")
            .status()
            .context("CRIU restore komutu çalıştırılamadı")?;

        if !status.success() {
            anyhow::bail!(
                "CRIU restore başarısız oldu (çıkış kodu: {:?})",
                status.code()
            );
        }

        println!("[+] CRIU: Süreç başarıyla canlandırıldı.");
        Ok(())
    }
}

pub struct UserspaceStateCollector;

impl UserspaceStateCollector {
    /// /proc/[pid] üzerinden sürecin ortam, argüman ve çalışma dizini durumunu yakalar
    pub fn collect(pid: u32) -> Result<ProcessMetadata> {
        let proc_path = PathBuf::from(format!("/proc/{}", pid));
        if !proc_path.exists() {
            anyhow::bail!("Süreç /proc/{} bulunamadı. Süreç sonlanmış olabilir.", pid);
        }

        // CWD
        let cwd = fs::read_link(proc_path.join("cwd"))
            .unwrap_or_else(|_| PathBuf::from("/"));

        // Cmdline
        let cmdline_raw = fs::read(proc_path.join("cmdline")).unwrap_or_default();
        let cmdline: Vec<String> = cmdline_raw
            .split(|&b| b == 0)
            .filter(|slice| !slice.is_empty())
            .map(|slice| String::from_utf8_lossy(slice).to_string())
            .collect();

        let name = cmdline
            .first()
            .cloned()
            .unwrap_or_else(|| format!("proc_{}", pid));

        // Environ
        let environ_raw = fs::read(proc_path.join("environ")).unwrap_or_default();
        let mut environ = HashMap::new();
        for slice in environ_raw.split(|&b| b == 0) {
            if let Ok(entry) = std::str::from_utf8(slice) {
                if let Some((k, v)) = entry.split_once('=') {
                    environ.insert(k.to_string(), v.to_string());
                }
            }
        }

        Ok(ProcessMetadata {
            pid,
            name,
            cmdline,
            cwd,
            environ,
            is_criu_dumped: false,
        })
    }
}

/// Sürecin GUI (Wayland/X11) veya GPU (Vulkan/DRM) bağlamı olup olmadığını doğrular
pub struct ProcessPreflight;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessCapabilities {
    pub has_gpu_context: bool,
    pub has_wayland_display: bool,
    pub has_x11_display: bool,
    pub is_gui_app: bool,
    pub details: Vec<String>,
}

impl ProcessPreflight {
    pub fn inspect(pid: u32) -> ProcessCapabilities {
        let fd_dir = format!("/proc/{}/fd", pid);
        let mut has_gpu = false;
        let mut has_wayland = false;
        let mut has_x11 = false;
        let mut details = Vec::new();

        if let Ok(entries) = fs::read_dir(fd_dir) {
            for entry in entries.filter_map(|e| e.ok()) {
                if let Ok(target) = fs::read_link(entry.path()) {
                    let target_str = target.to_string_lossy();
                    if target_str.contains("/dev/dri/") {
                        has_gpu = true;
                        details.push(format!("GPU DRM: {}", target_str));
                    }
                    if target_str.contains("wayland") || target_str.contains("memfd:wayland") {
                        has_wayland = true;
                        details.push(format!("Wayland: {}", target_str));
                    }
                    if target_str.contains("/tmp/.X11-unix/") {
                        has_x11 = true;
                        details.push(format!("X11: {}", target_str));
                    }
                }
            }
        }

        let is_gui = has_gpu || has_wayland || has_x11;
        ProcessCapabilities {
            has_gpu_context: has_gpu,
            has_wayland_display: has_wayland,
            has_x11_display: has_x11,
            is_gui_app: is_gui,
            details,
        }
    }
}
