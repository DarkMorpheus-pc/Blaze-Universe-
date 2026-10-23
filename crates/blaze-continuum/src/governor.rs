use anyhow::{Context, Result};
use serde_json::Value;
use std::collections::HashSet;
use std::fs;
use std::io::{BufRead, BufReader, Write};
use std::path::Path;
use std::process::{Command, Stdio};

/// Linux Çekirdek Kaynak Baskısı (PSI - Pressure Stall Information)
#[derive(Debug, Clone, Copy, Default)]
pub struct CpuPressure {
    pub some_avg10: f32,
    pub some_avg60: f32,
    pub some_avg300: f32,
}

impl CpuPressure {
    /// /proc/pressure/cpu dosyasından anlık CPU kuyruk baskısını okur
    pub fn read_current() -> Self {
        if let Ok(content) = fs::read_to_string("/proc/pressure/cpu") {
            for line in content.lines() {
                if line.starts_with("some ") {
                    let mut pressure = CpuPressure::default();
                    for part in line.split_whitespace().skip(1) {
                        if let Some((k, v)) = part.split_once('=') {
                            let val = v.parse::<f32>().unwrap_or(0.0);
                            match k {
                                "avg10" => pressure.some_avg10 = val,
                                "avg60" => pressure.some_avg60 = val,
                                "avg300" => pressure.some_avg300 = val,
                                _ => {}
                            }
                        }
                    }
                    return pressure;
                }
            }
        }
        CpuPressure::default()
    }

    /// Sistemde CPU darboğazı / baskısı var mı?
    pub fn is_under_pressure(&self) -> bool {
        self.some_avg10 > 2.0
    }
}

use crate::topology::CpuTopology;

/// Niri Viewport ve Niyet Duyarlı (Intent-Aware) Çekirdek Governor'ı
pub struct ViewportGovernor;

impl ViewportGovernor {
    /// Bir sürecin veya alt süreçlerinin PipeWire/ALSA üzerinden aktif ses akışı olup olmadığını denetler
    pub fn has_active_audio(pid: i32) -> bool {
        // 1. Ana sürecin dosya tanıtıcılarını denetle
        if Self::check_proc_audio_fds(pid) {
            return true;
        }

        // 2. Çoklu süreç mimarisi (Chrome, Firefox, Discord alt ses servisleri) taraması
        if let Ok(entries) = fs::read_dir("/proc") {
            for entry in entries.filter_map(|e| e.ok()) {
                let name = entry.file_name();
                let name_str = name.to_string_lossy();
                if let Ok(child_pid) = name_str.parse::<i32>() {
                    let stat_path = format!("/proc/{}/stat", child_pid);
                    if let Ok(stat) = fs::read_to_string(stat_path) {
                        if let Some(rparen) = stat.rfind(')') {
                            let rest = &stat[rparen + 2..];
                            let parts: Vec<&str> = rest.split_whitespace().collect();
                            if let Some(ppid_str) = parts.get(1) {
                                if let Ok(ppid) = ppid_str.parse::<i32>() {
                                    if ppid == pid && Self::check_proc_audio_fds(child_pid) {
                                        return true;
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        false
    }

    fn check_proc_audio_fds(pid: i32) -> bool {
        let fd_dir = format!("/proc/{}/fd", pid);
        if let Ok(entries) = fs::read_dir(fd_dir) {
            for entry in entries.filter_map(|e| e.ok()) {
                if let Ok(target) = fs::read_link(entry.path()) {
                    let target_str = target.to_string_lossy();
                    if target_str.contains("pipewire") || target_str.contains("/dev/snd") {
                        return true;
                    }
                }
            }
        }
        false
    }

    /// CPU Affinity (Çekirdek Pinleme) uygular - Sürecin TÜM iş parçacıklarını kapsar
    pub fn set_cpu_affinity(pid: i32, core_range: &str) -> usize {
        CpuTopology::apply_affinity_to_all_threads(pid, core_range)
    }

    /// I/O Öncelik sınıfı ve seviyesi atar (ionice)
    pub fn set_io_priority(pid: i32, class: u32, level: u32) {
        let _ = Command::new("ionice")
            .arg("-c")
            .arg(class.to_string())
            .arg("-n")
            .arg(level.to_string())
            .arg("-p")
            .arg(pid.to_string())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status();
    }

    /// Niri olay akışını dinleyerek ekrandaki ve şerit dışındaki süreçlerin önceliğini dinamik yönetir
    pub fn run() -> Result<()> {
        let topology = CpuTopology::detect();

        println!("=======================================================");
        println!("[EXEC] BLAZE INTENT-AWARE VIEWPORT GOVERNOR v2");
        println!("   Çekirdek Entegrasyonu: Niri Viewport + Linux PSI + PipeWire");
        println!("   Donanım Topolojisi   : {}", topology.mode_description);
        println!("     • P-Core (Odak)     : Çekirdekler [{}]", topology.perf_cpus_str);
        println!("     • E-Core (Arka Plan): Çekirdekler [{}]", topology.eff_cpus_str);
        println!("     • Toplam Mantıksal  : {} CPU", topology.total_logical_cpus);
        println!("   Politika: ");
        println!("     1. [Focus Boost]: Odaklanan pencereye yüksek CPU (Nice: -10) + P-Core + Real-Time I/O");
        println!("     2. [Audio Immunity]: Arka plandaki alt süreçler dahil ses akışı asla kısılmaz");
        println!("     3. [Pressure-Aware]: Sadece CPU baskısı (PSI > 2.0) varsa arka plan kısılır");
        println!("=======================================================");
        let _ = std::io::stdout().flush();

        let mut child = Command::new("niri")
            .arg("msg")
            .arg("-j")
            .arg("event-stream")
            .stdout(Stdio::piped())
            .spawn()
            .context("niri msg -j event-stream başlatılamadı")?;

        let stdout = child.stdout.take().context("Event stream stdout alınamadı")?;
        let reader = BufReader::new(stdout);

        let mut last_focused_pid: Option<i32> = None;
        let mut throttled_pids: HashSet<i32> = HashSet::new();

        for line in reader.lines() {
            let line = match line {
                Ok(l) => l,
                Err(_) => break,
            };

            if let Ok(event) = serde_json::from_str::<Value>(&line) {
                if let Some(windows_obj) = event.get("WindowsChanged") {
                    if let Some(windows) = windows_obj.get("windows").and_then(|w| w.as_array()) {
                        let mut current_focused_pid = None;
                        let mut current_offscreen_pids = Vec::new();

                        // 1. Pencereleri tara
                        for win in windows {
                            let pid = win.get("pid").and_then(|p| p.as_i64()).map(|p| p as i32);
                            let is_focused = win.get("is_focused").and_then(|f| f.as_bool()).unwrap_or(false);
                            let app_id = win.get("app_id").and_then(|a| a.as_str()).unwrap_or("App");
                            let tile_pos = win.get("layout")
                                .and_then(|l| l.get("tile_pos_in_workspace_view"));

                            if is_focused {
                                current_focused_pid = pid;
                                if let Some(p) = pid {
                                    if last_focused_pid != Some(p) {
                                        let pinned = Self::set_cpu_affinity(p, &topology.perf_cpus_str);
                                        println!(
                                            "[FOCUS BOOST] Odaklanan: {} (PID: {}) -> Nice: -10 | P-Core: [{}] ({} Thread Pinlendi) | I/O: Sınıf 2, Seviye 0",
                                            app_id, p, topology.perf_cpus_str, pinned
                                        );
                                        let _ = std::io::stdout().flush();
                                        // 1. CPU Önceliği (Nice)
                                        let _ = Command::new("renice")
                                            .arg("-n")
                                            .arg("-10")
                                            .arg("-p")
                                            .arg(p.to_string())
                                            .output();

                                        // 2. I/O Önceliği
                                        Self::set_io_priority(p, 2, 0);

                                        throttled_pids.remove(&p);
                                    }
                                }
                            } else if tile_pos.is_none() || tile_pos.unwrap().is_null() {
                                if let Some(p) = pid {
                                    current_offscreen_pids.push((p, app_id));
                                }
                            }
                        }

                        // 2. Sistem baskısını (PSI) kontrol et
                        let psi = CpuPressure::read_current();
                        let under_pressure = psi.is_under_pressure();

                        // 3. Şerit dışındakileri niyet ve baskıya göre değerlendir
                        for (off_pid, app_name) in current_offscreen_pids {
                            if Some(off_pid) == current_focused_pid {
                                continue;
                            }

                            // Ses denetimi (Audio Immunity)
                            if Self::has_active_audio(off_pid) {
                                if throttled_pids.contains(&off_pid) {
                                    let pinned = Self::set_cpu_affinity(off_pid, &topology.all_cpus_str);
                                    println!(
                                        "[AUDIO IMMUNITY] Ses akışı tespit edildi: {} (PID: {}) -> Kısıtlama kaldırıldı (Nice: 0, Çekirdekler: [{}], {} Thread)",
                                        app_name, off_pid, topology.all_cpus_str, pinned
                                    );
                                    let _ = std::io::stdout().flush();
                                    let _ = Command::new("renice")
                                        .arg("-n")
                                        .arg("0")
                                        .arg("-p")
                                        .arg(off_pid.to_string())
                                        .output();
                                    Self::set_io_priority(off_pid, 2, 4);
                                    throttled_pids.remove(&off_pid);
                                }
                                continue;
                            }

                            // CPU baskısı yoksa gereksiz yere cezalandırma
                            if !under_pressure {
                                if throttled_pids.contains(&off_pid) {
                                    // Baskı kalktı, normale döndür
                                    Self::set_cpu_affinity(off_pid, &topology.all_cpus_str);
                                    let _ = Command::new("renice")
                                        .arg("-n")
                                        .arg("0")
                                        .arg("-p")
                                        .arg(off_pid.to_string())
                                        .output();
                                    Self::set_io_priority(off_pid, 2, 4);
                                    throttled_pids.remove(&off_pid);
                                }
                                continue;
                            }

                            // Baskı var ve ses çalmıyor -> Background Throttle
                            if !throttled_pids.contains(&off_pid) {
                                throttled_pids.insert(off_pid);
                                let pinned = Self::set_cpu_affinity(off_pid, &topology.eff_cpus_str);
                                println!(
                                    "⏳ [BACKGROUND THROTTLE] Şerit Dışı (Baskı: {:.2}%): {} (PID: {}) -> Nice: +10 | E-Core: [{}] ({} Thread) | I/O: Idle(7)",
                                    psi.some_avg10, app_name, off_pid, topology.eff_cpus_str, pinned
                                );
                                let _ = std::io::stdout().flush();
                                let _ = Command::new("renice")
                                    .arg("-n")
                                    .arg("10")
                                    .arg("-p")
                                    .arg(off_pid.to_string())
                                    .output();
                                Self::set_io_priority(off_pid, 2, 7);
                            }
                        }

                        last_focused_pid = current_focused_pid;
                    }
                }
            }
        }

        Ok(())
    }

    /// cgroup v2 freezer kullanarak bir süreci dondurur (Explicit Freeze)
    #[allow(dead_code)]
    pub fn freeze_cgroup(cgroup_path: &Path) -> Result<()> {
        let freeze_file = cgroup_path.join("cgroup.freeze");
        if freeze_file.exists() {
            fs::write(freeze_file, "1")?;
            println!("[+] cgroup.freeze: Süreç grubu dondu.");
        }
        Ok(())
    }

    /// cgroup v2 freezer kullanarak bir süreci çözer (Explicit Thaw)
    #[allow(dead_code)]
    pub fn thaw_cgroup(cgroup_path: &Path) -> Result<()> {
        let freeze_file = cgroup_path.join("cgroup.freeze");
        if freeze_file.exists() {
            fs::write(freeze_file, "0")?;
            println!("[+] cgroup.freeze: Süreç grubu çözüldü.");
        }
        Ok(())
    }
}
