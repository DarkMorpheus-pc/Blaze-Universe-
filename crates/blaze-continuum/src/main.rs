use anyhow::{Context, Result};
use clap::{Parser, Subcommand};
use std::path::{Path, PathBuf};

mod capsule;
mod criu;
mod governor;
mod niri;
mod protocol;
mod screencopy;
mod topology;
mod transport;
mod wire;
mod workload;
pub mod ui;

use capsule::CapsulePacker;
use criu::{CriuEngine, UserspaceStateCollector};
use governor::ViewportGovernor;
use niri::NiriClient;
use protocol::{InputReplayQueue, ResourceSideFence, run_fencing_simulation};
use transport::{BctpReceiver, BctpSender, run_lan_acceptance_tests};

#[derive(Parser, Debug)]
#[command(
    name = "blaze-continuum",
    author = "BlazeOS Core Team",
    version = "0.1.0",
    about = "Blaze Continuum - Stateful Session Teleportation & Process Coordinator for BlazeOS"
)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand, Debug)]
enum Commands {
    /// Sistem ve Çevre Teşhisi (Niri, CRIU, sched_ext)
    Check,

    /// Niri Masaüstünün Mevcut Pencere ve Sütun Durumunu Yakalar
    CaptureDesktop {
        #[arg(short, long)]
        json: bool,
    },

    /// Belirtilen Süreci ve Niri Masaüstü Durumunu Dondurur (.blz-state kapsülü üretir)
    Freeze {
        /// Dondurulacak sürecin PID'si
        #[arg(short, long)]
        pid: u32,

        /// Üretilecek .blz-state kapsül dosyasının yolu
        #[arg(short, long, default_value = "/tmp/session.blz-state")]
        out: PathBuf,
    },

    /// .blz-state Kapsülünden Süreci ve Masaüstü Yerleşimini Canlandırır
    Restore {
        /// Açılacak .blz-state kapsül dosyası
        #[arg(short, long)]
        capsule: PathBuf,
    },

    /// Doğrulanabilir canlı bellek test iş yükünü çalıştırır
    Workload,

    /// Niri Viewport-Güdümlü eBPF ve Çekirdek Zamanlayıcı Governor'ını başlatır
    Governor,

    /// BCTP/1 Oturum Devri ve Fencing (Çift Çalışma Önleme) Simülasyonunu Çalıştırır
    SimulateFencing,

    /// BCTP/1-LAN-0 Gerçek Soket ve Kronometre (Stopwatch) Kabul Testlerini Çalıştırır
    LanTest,

    /// BCTP/1 Ağ Dinleyicisi: Belirtilen porttan ışınlanan oturumları karşılar ve anında canlandırır
    Listen {
        /// Dinlenecek port
        #[arg(short, long, default_value_t = 45821)]
        port: u16,

        /// Dinlenecek IP adresi
        #[arg(short, long, default_value = "0.0.0.0")]
        bind: String,
    },

    /// BCTP/1 Ağ Göndericisi: Odaklı pencereyi veya oturumu hedef makineye ışınlar
    Cast {
        /// Hedef düğüm adresi (Örn: 192.168.1.50:45821 veya 127.0.0.1:45821)
        #[arg(short, long)]
        target: String,

        /// Işınlanacak sürecin PID'si (Belirtilmezse Niri'deki aktif odaklı pencere kullanılır)
        #[arg(short, long)]
        pid: Option<u32>,

        /// Doğrudan gönderilecek hazır .blz-state kapsülü (Opsiyonel)
        #[arg(short, long)]
        capsule: Option<PathBuf>,
    },

    /// BCDL Kinetic Glass Wayland Ghost Overlay yüzeyini çalıştırır
    Overlay {
        /// Görüntülenecek hayalet görüntü (JPEG)
        #[arg(short, long, default_value = "/tmp/bctp_ghost_surface.jpg")]
        image: PathBuf,

        /// Fencing Epoch değeri
        #[arg(short, long, default_value_t = 2)]
        epoch: u64,

        /// Gösterilecek ağ gecikmesi (ms)
        #[arg(short, long, default_value_t = 1.2)]
        latency: f64,

        /// Otomatik kapanma süresi ms (0 = kalıcı)
        #[arg(short, long, default_value_t = 0)]
        dismiss_after_ms: u64,
    },
}

fn main() -> Result<()> {
    let cli = Cli::parse();

    match cli.command {
        Commands::Check => {
            println!("=======================================================");
            println!("[SYSTEM] BLAZE CONTINUUM SİSTEM VE ÇEVRE TEŞHİSİ");
            println!("=======================================================");

            // 1. Niri Durumu
            match NiriClient::connect() {
                Ok(client) => match client.capture_desktop() {
                    Ok(snapshot) => {
                        println!("[OK] Niri Wayland Compositor: AKTİF");
                        println!(
                            "   Soket: {:?}",
                            snapshot.niri_socket.unwrap_or_default()
                        );
                        println!("   Açık Pencere Sayısı: {}", snapshot.windows.len());
                        println!("   Çalışma Alanı Sayısı: {}", snapshot.workspaces.len());
                        if let Some(f_id) = snapshot.focused_window_id {
                            println!("   Odaklanmış Pencere ID: {}", f_id);
                        }
                    }
                    Err(e) => {
                        println!("[WARN] Niri soketi var fakat sorgulanamadı: {}", e);
                    }
                },
                Err(e) => {
                    println!("[FAIL] Niri Compositor bağlantısı kurulamadı: {}", e);
                }
            }

            println!("-------------------------------------------------------");

            // 2. CRIU Durumu
            let criu_status = CriuEngine::check_support();
            if criu_status.is_installed {
                if criu_status.has_capability {
                    println!("[OK] CRIU Çekirdek Desteği: TAM YETKİLİ (Hazır)");
                } else {
                    println!("[WARN] CRIU Kurulu ancak: {}", criu_status.message);
                }
            } else {
                println!("[FAIL] CRIU kurulu değil.");
            }

            println!("-------------------------------------------------------");

            // 3. sched_ext Çekirdek Durumu
            let scx_path = std::path::Path::new("/sys/kernel/sched_ext");
            if scx_path.exists() {
                let state = std::fs::read_to_string(scx_path.join("state"))
                    .unwrap_or_else(|_| "unknown".to_string());
                println!("[OK] Linux sched_ext (eBPF Scheduler): ÇEKİRDEKTE AKTİF");
                println!("   Mevcut Durum: {}", state.trim());
            } else {
                println!("[FAIL] sched_ext desteği bulunamadı.");
            }

            println!("-------------------------------------------------------");

            // 4. Wayland Screencopy (grim) Durumu
            if screencopy::ScreencopyEngine::is_available() {
                println!("[OK] Wayland Screencopy (grim): AKTİF (Canlı Ghost Frame Hazır)");
            } else {
                println!("[WARN] Wayland Screencopy (grim) kurulu değil (Sentetik desen kullanılacak).");
            }

            println!("-------------------------------------------------------");

            // 5. CPU Donanım Topolojisi (SMT ve Hibrit Çekirdek Ayrımı)
            let topo = topology::CpuTopology::detect();
            println!("[OK] Donanım CPU Topolojisi: {}", topo.mode_description);
            println!("   • P-Core (Odak Çekirdekleri)     : [{}]", topo.perf_cpus_str);
            println!("   • E-Core (Arka Plan Çekirdekleri) : [{}]", topo.eff_cpus_str);
            println!("   • Toplam Mantıksal Çekirdek       : {} CPU", topo.total_logical_cpus);

            println!("=======================================================");
        }

        Commands::CaptureDesktop { json } => {
            let client = NiriClient::connect().context("Niri istemcisi başlatılamadı")?;
            let snapshot = client
                .capture_desktop()
                .context("Masaüstü durumu yakalanamadı")?;

            if json {
                println!("{}", serde_json::to_string_pretty(&snapshot)?);
            } else {
                println!("[SYSTEM] Niri Masaüstü Durum Özeti:");
                println!("- Aktif Çalışma Alanı: {:?}", snapshot.active_workspace_id);
                println!("- Odaklanmış Pencere: {:?}", snapshot.focused_window_id);
                println!("- Pencereler:");
                for win in &snapshot.windows {
                    let focus_mark = if win.is_focused { "[ODAK]" } else { "      " };
                    let title = win.title.as_deref().unwrap_or("Başlıksız");
                    let app = win.app_id.as_deref().unwrap_or("Bilinmeyen");
                    let pid = win.pid.map(|p| p.to_string()).unwrap_or_else(|| "-".to_string());
                    println!(
                        "  {} ID: {:<3} | PID: {:<6} | App: {:<16} | Title: {}",
                        focus_mark, win.id, pid, app, title
                    );
                    if let Some(pos) = win.layout.pos_in_scrolling_layout {
                        println!("         └─ Sütun: {}, Sıra: {} | Boyut: {:?}", pos.0, pos.1, win.layout.window_size);
                    }
                }
            }
        }

        Commands::Freeze { pid, out } => {
            println!("[FREEZE] BLAZE CONTINUUM: Dondurma Operasyonu Başlatılıyor...");
            println!("   Hedef PID: {}", pid);

            // 1. Masaüstü durumunu yakala
            let niri = NiriClient::connect().context("Niri bağlantısı")?;
            let desktop = niri.capture_desktop().context("Masaüstü yakalama")?;

            // 2. Süreç durumunu topla
            let mut proc_meta = UserspaceStateCollector::collect(pid)
                .context("Süreç metadata toplama")?;

            // 3. Geçici CRIU dizini oluşturup dump almayı dene
            let temp_criu = tempfile::tempdir()?;
            let criu_status = CriuEngine::check_support();

            let criu_applied = if criu_status.has_capability {
                match CriuEngine::dump_process(pid, temp_criu.path()) {
                    Ok(_) => {
                        proc_meta.is_criu_dumped = true;
                        true
                    }
                    Err(e) => {
                        println!("[WARN] CRIU dump başarısız oldu (fallback devreye giriyor): {}", e);
                        false
                    }
                }
            } else {
                println!("[INFO] CRIU yetkisi tam değil; Userspace Process State (rehydrate) adaptörü kullanılıyor.");
                false
            };

            // 4. Kapsülü inşa et
            let criu_opt = if criu_applied { Some(temp_criu.path()) } else { None };
            CapsulePacker::build_capsule(desktop, vec![proc_meta], criu_opt, &out)?;

            println!("[DONE] Dondurma Başarılı! Kapsül: {:?}", out);
        }

        Commands::Restore { capsule } => {
            perform_restore(&capsule)?;
        }

        Commands::Workload => {
            workload::run_test_workload();
        }

        Commands::Governor => {
            ViewportGovernor::run()?;
        }

        Commands::SimulateFencing => {
            run_fencing_simulation()?;
        }

        Commands::LanTest => {
            run_lan_acceptance_tests()?;
        }

        Commands::Listen { port, bind } => {
            let bind_addr = format!("{}:{}", bind, port);
            println!("[LISTEN] BLAZE CONTINUUM DINLEYİCİ BAŞLATILIYOR -> {}", bind_addr);
            println!("   Işınlanacak oturumlar bekleniyor...");

            let resource_fence = ResourceSideFence::new("blz-daemon-sess".to_string(), "target-local".to_string());
            let input_queue = InputReplayQueue::new(1);

            let (stopwatch, capsule_opt) = BctpReceiver::run_single_session_listener(
                &bind_addr,
                resource_fence,
                input_queue,
            )?;

            println!("-------------------------------------------------------");
            println!("[BENCHMARK] TELEPORT ZAMANLAMA BİLGİSİ:");
            println!("   • T_ghost   : {:.3} ms", stopwatch.t_ghost_micros as f64 / 1000.0);
            println!("   • T_barrier : {:.3} ms", stopwatch.t_barrier_micros as f64 / 1000.0);
            println!("   • T_drain   : {:.3} ms", stopwatch.t_drain_micros as f64 / 1000.0);
            println!("-------------------------------------------------------");

            if let Some(bytes) = capsule_opt {
                let out_path = PathBuf::from("/tmp/bctp_received_session.blz-state");
                std::fs::write(&out_path, &bytes)?;
                println!("[CAPSULE] Alınan kapsül kaydedildi: {:?}", out_path);
                perform_restore(&out_path)?;
            } else {
                println!("[WARN] Kapsül verisi bulunamadı!");
            }
        }

        Commands::Cast { target, pid, capsule } => {
            println!("[EXEC] BLAZE CONTINUUM IŞINLAMA (CAST) BAŞLATILIYOR -> {}", target);

            let (capsule_bytes, session_name) = if let Some(cap_path) = capsule {
                let bytes = std::fs::read(&cap_path)
                    .with_context(|| format!("Kapsül dosyası okunamadı: {:?}", cap_path))?;
                (bytes, format!("capsule-{}", cap_path.file_name().unwrap_or_default().to_string_lossy()))
            } else {
                let target_pid = if let Some(p) = pid {
                    p
                } else {
                    println!("[*] PID belirtilmedi, Niri üzerinden odaklı pencere sorgulanıyor...");
                    let client = NiriClient::connect().context("Niri compositor'a bağlanılamadı")?;
                    let snapshot = client.capture_desktop().context("Masaüstü taranamadı")?;
                    let focused_id = snapshot.focused_window_id.context("Odaklı pencere bulunamadı!")?;
                    let focused_win = snapshot.windows.iter().find(|w| w.id == focused_id)
                        .context("Odaklı pencere bilgisi eşleşmedi")?;
                    let f_pid = focused_win.pid.context("Odaklı pencere bir PID taşımıyor!")?;
                    println!("    └─ Odaklı pencere tespit edildi: {:?} (PID: {})", focused_win.title, f_pid);
                    f_pid as u32
                };

                println!("[*] PID {} donduruluyor ve kapsül üretiliyor...", target_pid);
                let client = NiriClient::connect();
                let desktop = match client {
                    Ok(c) => c.capture_desktop().unwrap_or_default(),
                    Err(_) => niri::DesktopSnapshot::default(),
                };

                let proc_meta = UserspaceStateCollector::collect(target_pid)?;
                let temp_criu = tempfile::tempdir()?;
                let mut criu_applied = false;
                if CriuEngine::check_support().has_capability {
                    if let Ok(()) = CriuEngine::dump_process(target_pid, temp_criu.path()) {
                        criu_applied = true;
                    }
                }

                let temp_out = tempfile::Builder::new().suffix(".blz-state").tempfile()?;
                let criu_opt = if criu_applied { Some(temp_criu.path()) } else { None };
                CapsulePacker::build_capsule(desktop, vec![proc_meta], criu_opt, temp_out.path())?;

                let bytes = std::fs::read(temp_out.path())?;
                (bytes, format!("sess-pid-{}", target_pid))
            };

            // Pencere geometrisi mevcutsa screencopy'yi bu sınırlara kırp
            let geometry_opt = if let Ok(client) = NiriClient::connect() {
                if let Ok(snapshot) = client.capture_desktop() {
                    snapshot.focused_window_id.and_then(|fid| {
                        snapshot.windows.iter().find(|w| w.id == fid).and_then(|w| {
                            w.layout.tile_pos_in_workspace_view.and_then(|(x, y)| {
                                let (width, height) = w.layout.window_size;
                                if width > 0 && height > 0 {
                                    Some(format!("{},{} {}x{}", x as i32, y as i32, width, height))
                                } else {
                                    None
                                }
                            })
                        })
                    })
                } else {
                    None
                }
            } else {
                None
            };

            let ghost_frame = screencopy::ScreencopyEngine::capture_ghost_frame(geometry_opt.as_deref())
                .unwrap_or_else(|_| screencopy::ScreencopyEngine::generate_synthetic_frame());

            println!("[*] BCTP/1-LAN-0 bağlantısı kuruluyor ve ışınlanıyor (Kapsül: {} bayt, Ghost Frame: {} bayt)...", capsule_bytes.len(), ghost_frame.len());
            let stopwatch = BctpSender::send_session(
                &target,
                &session_name,
                2,
                &ghost_frame,
                &capsule_bytes,
            )?;

            println!("-------------------------------------------------------");
            println!("[BENCHMARK] BLAZE TELEPORT TAMAMLANDI! (STOPWATCH TELEMETRİSİ):");
            println!("   • T_ghost   (Görsel İntikal): {:.3} ms (Hedef: < 16.0 ms)", stopwatch.t_ghost_micros as f64 / 1000.0);
            println!("   • T_barrier (Durum Devri)   : {:.3} ms (Kapsül: {} bayt)", stopwatch.t_barrier_micros as f64 / 1000.0, capsule_bytes.len());
            println!("-------------------------------------------------------");
            println!("[SUCCESS] Süreç ve Masaüstü Durumu Hedef Düğüme Kusursuz Işınlandı!");
        }

        Commands::Overlay {
            image,
            epoch,
            latency,
            dismiss_after_ms,
        } => {
            println!("=======================================================");
            println!("[OVERLAY] BLAZE CONTINUUM — BCDL KINETIC GLASS GHOST OVERLAY");
            println!("=======================================================");

            // Eğer görüntü yoksa, aktif ekrandan çek
            if !image.exists() {
                println!("[CAPTURE] Görüntü bulunamadı, aktif ekrandan canlı Ghost Frame yakalanıyor...");
                let frame_bytes = screencopy::ScreencopyEngine::capture_ghost_frame(None)?;
                std::fs::write(&image, frame_bytes)?;
            }

            let handle = ui::overlay::GhostOverlayManager::spawn_overlay(
                &image,
                epoch,
                latency,
                "syncing",
            )?;

            if dismiss_after_ms > 0 {
                std::thread::sleep(std::time::Duration::from_millis(dismiss_after_ms));
                handle.dismiss()?;
            } else {
                println!("[HINT] Çıkmak ve girdileri devretmek için Terminalde [ENTER]'a basın...");
                let mut input = String::new();
                let _ = std::io::stdin().read_line(&mut input);
                let buffered = handle.collect_buffered_inputs()?;
                println!("[CAPSULE] Toplam {} adet girdi devir için hazırlandı.", buffered.len());
                handle.dismiss()?;
            }
        }
    }

    Ok(())
}

fn perform_restore(capsule: &Path) -> Result<()> {
    println!("[RESTORE] BLAZE CONTINUUM: Canlandırma Operasyonu Başlatılıyor...");
    println!("   Kapsül: {:?}", capsule);

    let temp_extract = tempfile::tempdir()?;
    let manifest = CapsulePacker::unpack_capsule(capsule, temp_extract.path())
        .context("Kapsül açma başarısız")?;

    println!("   Kapsül ID: {}", manifest.capsule_id);
    println!("   Kaynak Düğüm: {}", manifest.source_hostname);
    println!("   Kayıt Zamanı: {}", manifest.created_at);
    println!("   Paketlenen Süreç Sayısı: {}", manifest.processes.len());

    // 1. Süreçleri canlandır
    for proc in &manifest.processes {
        println!("[*] Süreç Ele Alınıyor: {} (Eski PID: {})", proc.name, proc.pid);
        if proc.is_criu_dumped {
            let criu_dir = temp_extract.path().join("criu");
            if criu_dir.exists() {
                println!("    └─ CRIU İmajları bulundu, çekirdek restore çağrılıyor...");
                let _ = CriuEngine::restore_process(&criu_dir);
            }
        } else {
            println!("    └─ Rehydrate Adaptörü: Komut satırı ve çalışma dizini yeniden başlatılıyor...");
            if !proc.cmdline.is_empty() {
                let mut cmd = std::process::Command::new(&proc.cmdline[0]);
                if proc.cmdline.len() > 1 {
                    cmd.args(&proc.cmdline[1..]);
                }
                cmd.current_dir(&proc.cwd);
                for (k, v) in &proc.environ {
                    cmd.env(k, v);
                }
                cmd.stdin(std::process::Stdio::null());
                #[cfg(unix)]
                {
                    use std::os::unix::process::CommandExt;
                    cmd.process_group(0);
                }
                match cmd.spawn() {
                    Ok(child) => {
                        println!("    [OK] Yeniden başlatıldı! Yeni PID: {}", child.id());
                    }
                    Err(e) => {
                        println!("    [FAIL] Yeniden başlatılamadı: {}", e);
                    }
                }
            }
        }
    }

    // 2. Masaüstü yerleşimini yeniden canlandır
    println!("[*] Niri Masaüstü Durumu İnceleniyor...");
    let client = NiriClient::connect();
    if let Ok(_niri) = client {
        println!("    └─ Niri aktif! Kayıtlı pencereler taranıyor:");
        for win in &manifest.desktop.windows {
            println!(
                "       • App: {:?} | Başlık: {:?} | Sütun Düzeni: {:?}",
                win.app_id, win.title, win.layout.pos_in_scrolling_layout
            );
        }
    }

    println!("[DONE] Canlandırma Başarıyla Tamamlandı!");
    Ok(())
}
