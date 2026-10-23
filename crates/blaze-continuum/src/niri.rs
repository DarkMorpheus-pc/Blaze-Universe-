use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::env;
use std::io::{BufRead, BufReader, Write};
use std::os::unix::net::UnixStream;
use std::path::{Path, PathBuf};
use std::process::Command;

/// Repräsentasyon der Niri-Pencere Layout Bilgisi
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct WindowLayout {
    pub pos_in_scrolling_layout: Option<(usize, usize)>,
    pub tile_size: (f64, f64),
    pub window_size: (i32, i32),
    pub tile_pos_in_workspace_view: Option<(f64, f64)>,
    pub window_offset_in_tile: (f64, f64),
}

/// Niri Penceresi
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NiriWindow {
    pub id: u64,
    pub title: Option<String>,
    pub app_id: Option<String>,
    pub pid: Option<i32>,
    pub workspace_id: Option<u64>,
    pub is_focused: bool,
    pub is_floating: bool,
    pub is_urgent: bool,
    pub layout: WindowLayout,
}

/// Niri Çalışma Alanı (Workspace)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NiriWorkspace {
    pub id: u64,
    pub idx: u8,
    pub name: Option<String>,
    pub output: Option<String>,
    pub is_active: bool,
    pub is_focused: bool,
}

/// Tam Masaüstü Durum Raporu
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct DesktopSnapshot {
    pub compositor: String,
    pub niri_socket: Option<String>,
    pub focused_window_id: Option<u64>,
    pub active_workspace_id: Option<u64>,
    pub windows: Vec<NiriWindow>,
    pub workspaces: Vec<NiriWorkspace>,
}

/// Niri IPC İstemcisi
pub struct NiriClient {
    socket_path: Option<PathBuf>,
}

#[allow(dead_code)]
impl NiriClient {
    /// Ortam değişkenlerinden veya varsayılan konumlardan Niri istemcisi türetir
    pub fn connect() -> Result<Self> {
        let socket_path = match env::var("NIRI_SOCKET") {
            Ok(p) => Some(PathBuf::from(p)),
            Err(_) => {
                // Deneme: /run/user/$UID/niri.*.sock taraması
                if let Ok(runtime_dir) = env::var("XDG_RUNTIME_DIR") {
                    let runtime_path = Path::new(&runtime_dir);
                    if let Ok(entries) = std::fs::read_dir(runtime_path) {
                        entries
                            .filter_map(|e| e.ok())
                            .map(|e| e.path())
                            .find(|p| {
                                p.file_name()
                                    .and_then(|n| n.to_str())
                                    .map(|n| n.starts_with("niri") && n.ends_with(".sock"))
                                    .unwrap_or(false)
                            })
                    } else {
                        None
                    }
                } else {
                    None
                }
            }
        };

        Ok(Self { socket_path })
    }

    /// Sokete ham JSON isteği gönderip yanıtı okur
    fn request_raw(&self, req_json: &str) -> Result<String> {
        if let Some(ref sock_path) = self.socket_path {
            if sock_path.exists() {
                let mut stream = UnixStream::connect(sock_path)
                    .with_context(|| format!("Niri soketine bağlanılamadı: {:?}", sock_path))?;
                stream.write_all(req_json.as_bytes())?;
                stream.write_all(b"\n")?;
                stream.flush()?;

                let mut reader = BufReader::new(stream);
                let mut response = String::new();
                reader.read_line(&mut response)?;
                return Ok(response);
            }
        }

        // Yedek fallback: `niri msg` CLI aracılığıyla çağır
        let output = Command::new("niri")
            .arg("msg")
            .arg("-j")
            .arg("windows")
            .output()
            .context("niri msg komutu çalıştırılamadı")?;

        if !output.status.success() {
            anyhow::bail!(
                "niri msg hata verdi: {}",
                String::from_utf8_lossy(&output.stderr)
            );
        }

        Ok(String::from_utf8_lossy(&output.stdout).to_string())
    }

    /// Tüm açık pencereleri sorgular
    pub fn get_windows(&self) -> Result<Vec<NiriWindow>> {
        let output = Command::new("niri")
            .arg("msg")
            .arg("-j")
            .arg("windows")
            .output()
            .context("niri msg -j windows çalıştırılamadı")?;

        if !output.status.success() {
            anyhow::bail!(
                "niri msg windows başarısız oldu: {}",
                String::from_utf8_lossy(&output.stderr)
            );
        }

        let windows: Vec<NiriWindow> = serde_json::from_slice(&output.stdout)
            .context("Niri pencereleri JSON olarak ayrıştırılamadı")?;
        Ok(windows)
    }

    /// Tüm çalışma alanlarını sorgular
    pub fn get_workspaces(&self) -> Result<Vec<NiriWorkspace>> {
        let output = Command::new("niri")
            .arg("msg")
            .arg("-j")
            .arg("workspaces")
            .output()
            .context("niri msg -j workspaces çalıştırılamadı")?;

        if !output.status.success() {
            anyhow::bail!(
                "niri msg workspaces başarısız oldu: {}",
                String::from_utf8_lossy(&output.stderr)
            );
        }

        let workspaces: Vec<NiriWorkspace> = serde_json::from_slice(&output.stdout)
            .context("Niri çalışma alanları JSON olarak ayrıştırılamadı")?;
        Ok(workspaces)
    }

    /// Tam Masaüstü Durumunun Anlık Görüntüsünü Alır
    pub fn capture_desktop(&self) -> Result<DesktopSnapshot> {
        let windows = self.get_windows().unwrap_or_default();
        let workspaces = self.get_workspaces().unwrap_or_default();

        let focused_window_id = windows.iter().find(|w| w.is_focused).map(|w| w.id);
        let active_workspace_id = workspaces.iter().find(|ws| ws.is_active).map(|ws| ws.id);

        Ok(DesktopSnapshot {
            compositor: "niri".to_string(),
            niri_socket: self.socket_path.as_ref().map(|p| p.to_string_lossy().to_string()),
            focused_window_id,
            active_workspace_id,
            windows,
            workspaces,
        })
    }

    /// Niri Action komutu çalıştırır
    pub fn action(&self, args: &[&str]) -> Result<()> {
        let mut cmd = Command::new("niri");
        cmd.arg("msg").arg("action");
        for arg in args {
            cmd.arg(arg);
        }

        let status = cmd.status().context("niri msg action yürütülemedi")?;
        if !status.success() {
            anyhow::bail!("niri action başarısız oldu: {:?}", args);
        }
        Ok(())
    }

    /// Bir uygulamayı başlatır ve Niri döşemesine yerleştirir
    pub fn spawn(&self, cmd: &[&str]) -> Result<()> {
        let mut args = vec!["spawn", "--"];
        args.extend_from_slice(cmd);
        self.action(&args)
    }
}
