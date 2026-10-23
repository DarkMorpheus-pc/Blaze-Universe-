//! Blaze Continuum — Ghost Overlay Wayland Entegrasyonu
//! BCDL Kinetic Glass standartlarında hayalet yüzeyi Niri üzerinde açar ve yönetir.

use anyhow::{Context, Result};
use std::env;
use std::fs::File;
use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::process::{Child, Command};
use std::time::Duration;

use crate::protocol::{BufferedInput, InputEventType};

/// Canlı Hayalet Yüzey Tutamacı (Ghost Overlay Handle)
pub struct GhostOverlayHandle {
    process: Child,
    event_log_path: PathBuf,
}

impl GhostOverlayHandle {
    /// Hayalet yüzeyi sonlandırır (120ms BCDL sönümlü çıkış sinyali gönderir)
    pub fn dismiss(mut self) -> Result<()> {
        let pid = self.process.id() as libc::pid_t;
        println!("[Ghost Overlay]: Kapatma sinyali (SIGUSR1) gönderiliyor -> PID {}", pid);
        unsafe {
            libc::kill(pid, libc::SIGUSR1);
        }

        // 150ms bekle, kapanmazsa SIGTERM/kill
        std::thread::sleep(Duration::from_millis(150));
        match self.process.try_wait()? {
            Some(status) => {
                println!("[OK] [Ghost Overlay]: Yüzey kapandı ve asıl sürece devredildi (Çıkış kodu: {})", status);
            }
            None => {
                let _ = self.process.kill();
                let _ = self.process.wait();
            }
        }
        Ok(())
    }

    /// Ghost Surface ekrandayken kaydedilen girdi olaylarını okur
    pub fn collect_buffered_inputs(&self) -> Result<Vec<BufferedInput>> {
        if !self.event_log_path.exists() {
            return Ok(Vec::new());
        }

        let file = File::open(&self.event_log_path)?;
        let reader = BufReader::new(file);
        let mut inputs = Vec::new();

        for line in reader.lines() {
            let line = line?;
            if line.trim().is_empty() {
                continue;
            }

            if let Ok(val) = serde_json::from_str::<serde_json::Value>(&line) {
                let epoch = val.get("epoch").and_then(|e| e.as_u64()).unwrap_or(1);
                let timestamp_ms = val.get("timestamp_ms").and_then(|t| t.as_u64()).unwrap_or(0);
                
                if let Some(event_obj) = val.get("event") {
                    let ev_type = event_obj.get("type").and_then(|t| t.as_str()).unwrap_or("");
                    let event = match ev_type {
                        "PointerClick" => {
                            let x = event_obj.get("x").and_then(|v| v.as_f64()).unwrap_or(0.0);
                            let y = event_obj.get("y").and_then(|v| v.as_f64()).unwrap_or(0.0);
                            let button = event_obj.get("button").and_then(|v| v.as_u64()).unwrap_or(1) as u32;
                            Some(InputEventType::PointerClick { x, y, button })
                        }
                        "KeyPress" => {
                            let keycode = event_obj.get("keycode").and_then(|v| v.as_u64()).unwrap_or(0) as u32;
                            let pressed = event_obj.get("pressed").and_then(|v| v.as_bool()).unwrap_or(true);
                            Some(InputEventType::KeyPress { keycode, pressed })
                        }
                        _ => None,
                    };

                    if let Some(ev) = event {
                        inputs.push(BufferedInput {
                            epoch,
                            timestamp_ms,
                            event: ev,
                        });
                    }
                }
            }
        }

        println!("[Input Replay]: Toplam {} adet tamponlanmış girdi olayı okundu.", inputs.len());
        Ok(inputs)
    }
}

/// Hayalet Yüzey Yöneticisi
pub struct GhostOverlayManager;

impl GhostOverlayManager {
    /// BCDL standartlarında Wayland üzerinde bir Ghost Surface Overlay başlatır
    pub fn spawn_overlay(
        image_path: &Path,
        epoch: u64,
        latency_ms: f64,
        status: &str,
    ) -> Result<GhostOverlayHandle> {
        let script_path = Self::find_overlay_script();
        let event_log_path = PathBuf::from("/tmp/bctp_input_events.jsonl");

        // Önceki log dosyasını temizle
        if event_log_path.exists() {
            let _ = std::fs::remove_file(&event_log_path);
        }

        let wayland_display = env::var("WAYLAND_DISPLAY").unwrap_or_else(|_| "wayland-1".to_string());
        let xdg_runtime = env::var("XDG_RUNTIME_DIR").unwrap_or_else(|_| "/run/user/1000".to_string());

        let mut cmd = Command::new("python3");
        cmd.arg(&script_path)
            .arg("--image")
            .arg(image_path)
            .arg("--epoch")
            .arg(epoch.to_string())
            .arg("--latency")
            .arg(format!("{:.1}", latency_ms))
            .arg("--status")
            .arg(status)
            .arg("--event-log")
            .arg(&event_log_path)
            .env("WAYLAND_DISPLAY", wayland_display)
            .env("XDG_RUNTIME_DIR", xdg_runtime);

        let child = cmd.spawn().with_context(|| {
            format!(
                "Ghost Overlay betiği ({}) başlatılamadı!",
                script_path.display()
            )
        })?;

        println!(
            "[Ghost Overlay]: PID {} ile Wayland üzerinde başlatıldı. (Epoch: {}, Gecikme: {:.1}ms)",
            child.id(),
            epoch,
            latency_ms
        );

        Ok(GhostOverlayHandle {
            process: child,
            event_log_path,
        })
    }

    /// Sistemde veya geliştirme ortamında Ghost Overlay betiğini arar
    pub fn find_overlay_script() -> PathBuf {
        let candidates = [
            PathBuf::from("/usr/bin/blaze-ghost-overlay"),
            PathBuf::from("/usr/local/bin/blaze-ghost-overlay"),
            PathBuf::from("/usr/share/blaze-continuum/scripts/blaze_ghost_overlay.py"),
            PathBuf::from("crates/blaze-continuum/scripts/blaze_ghost_overlay.py"),
            PathBuf::from("./scripts/blaze_ghost_overlay.py"),
        ];

        for candidate in &candidates {
            if candidate.exists() {
                return candidate.clone();
            }
        }

        if let Ok(exe) = env::current_exe() {
            if let Some(parent) = exe.parent() {
                let sibling = parent.join("blaze-ghost-overlay");
                if sibling.exists() {
                    return sibling;
                }
                let dev_script = parent.join("../../../crates/blaze-continuum/scripts/blaze_ghost_overlay.py");
                if dev_script.exists() {
                    return dev_script;
                }
            }
        }

        // Bulunamazsa sistemdeki varsayılan ikiliye başvur
        PathBuf::from("/usr/bin/blaze-ghost-overlay")
    }
}
