use anyhow::{Context, Result};
use std::env;
use std::process::{Command, Stdio};

/// Wayland Screencopy Çerçeve Yakalama Motoru
pub struct ScreencopyEngine;

impl ScreencopyEngine {
    /// Sistemde grim veya screencopy desteğinin olup olmadığını kontrol eder
    pub fn is_available() -> bool {
        Command::new("which")
            .arg("grim")
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .map(|s| s.success())
            .unwrap_or(false)
    }

    /// Aktif ekrandan veya belirtilen pencere geometrisinden Ghost Frame yakalar
    /// Geriye JPEG formatında sıkıştırılmış bayt dizisi döner.
    pub fn capture_ghost_frame(geometry: Option<&str>) -> Result<Vec<u8>> {
        if !Self::is_available() {
            println!("   [INFO] grim bulunamadı, sentetik Ghost Frame deseni üretiliyor...");
            return Ok(Self::generate_synthetic_frame());
        }

        // Wayland çevre değişkenlerini kontrol et
        let wayland_display = env::var("WAYLAND_DISPLAY").unwrap_or_else(|_| "wayland-1".to_string());
        let xdg_runtime = env::var("XDG_RUNTIME_DIR").unwrap_or_else(|_| "/run/user/1000".to_string());

        let mut cmd = Command::new("grim");
        cmd.env("WAYLAND_DISPLAY", &wayland_display);
        cmd.env("XDG_RUNTIME_DIR", &xdg_runtime);

        if let Some(geo) = geometry {
            cmd.arg("-g").arg(geo);
        }

        cmd.arg("-t").arg("jpeg");
        cmd.arg("-q").arg("75");
        cmd.arg("-"); // stdout'a yaz

        let output = cmd.output().context("grim ekran görüntüsü alma çağrısı başarısız oldu")?;

        if !output.status.success() || output.stdout.is_empty() {
            println!("   [WARN] grim çalıştı ancak çıktı üretemedi, sentetik Ghost Frame'e dönülüyor...");
            return Ok(Self::generate_synthetic_frame());
        }

        if let Some(geo) = geometry {
            println!("   [Wayland Screencopy]: Pencere sınırları kırpılarak yakalandı (Bölge: {}, Boyut: {} bayt)", geo, output.stdout.len());
        } else {
            println!("   [Wayland Screencopy]: Tam ekran Ghost Frame yakalandı (Boyut: {} bayt, Format: JPEG)", output.stdout.len());
        }
        Ok(output.stdout)
    }

    /// Eğer ekran yakalayıcı yoksa veya sanal/headless oturumdaysa deterministik bir desen üretir
    pub fn generate_synthetic_frame() -> Vec<u8> {
        let mut frame = Vec::with_capacity(64 * 1024);
        for i in 0..(64 * 1024) {
            frame.push(((i * 7 + 13) % 256) as u8);
        }
        frame
    }
}
