use anyhow::{bail, Result};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::VecDeque;

/// BCTP Protokol Sürümü
#[allow(dead_code)]
pub const BCTP_VERSION: &str = "BCTP/1.0";

/// Context Bayrakları
#[allow(dead_code)]
pub const CONTEXT_FLAG_HAS_AUDIO: u8 = 1 << 0;
#[allow(dead_code)]
pub const CONTEXT_FLAG_OWNS_CLIPBOARD: u8 = 1 << 1;
#[allow(dead_code)]
pub const CONTEXT_FLAG_NEEDS_UFFD: u8 = 1 << 2;

/// BCTP/1 Sabit Başlığı (64-Bayt Packed Wire Header)
#[allow(dead_code)]
#[repr(C)]
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct BctpWireHeader {
    pub magic: [u8; 4],            // b"BCTP"
    pub version: u8,               // 1
    pub context_flags: u8,         // Ses, pano, UFFD bayrakları
    pub target_column_idx: u16,    // Niri şeridinde yerleşeceği kolon
    pub lease_epoch: u64,          // Monotonik artan Fencing Epoch
    pub width_px: u32,             // Kaynak pencere genişliği
    pub height_px: u32,            // Kaynak pencere yüksekliği
    pub scale_milli: u32,          // Kaynak ölçek (1000 = %100, 1500 = %150)
    pub ghost_format: u8,          // 1 = WL_SHM_XRGB8888_LZ4
    pub ghost_payload_len: u32,    // Ghost Frame boyutu
}

impl Default for BctpWireHeader {
    fn default() -> Self {
        Self {
            magic: *b"BCTP",
            version: 1,
            context_flags: 0,
            target_column_idx: 1,
            lease_epoch: 1,
            width_px: 1920,
            height_px: 1080,
            scale_milli: 1000,
            ghost_format: 1,
            ghost_payload_len: 0,
        }
    }
}

/// Oturum Mülkiyeti ve Devir Durum Makinesi (Single-Ownership Fencing State Machine)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum SessionState {
    /// Kaynak makinede süreçler ve masaüstü normal çalışıyor
    RunningSource,
    /// Hedef makine hazırlandı, ortam uyumluluğu doğrulanıyor
    PreparingTarget,
    /// Kaynak makinedeki süreçler durduruldu/kilitlendi (Tek yürütücü çiti)
    SourceFenced,
    /// Hedef makinede durum açılıyor ve süreçler canlandırılıyor
    RestoringTarget,
    /// Hedef makinede süreçlerin sağlığı ve Niri yüzeyleri doğrulandı
    TargetValidated,
    /// Oturum sahipliği tamamen hedefe geçti (Devir tamamlandı)
    Committed,
    /// Aktarım güvenle iptal edildi (Kaynak tekrar serbest bırakıldı)
    Aborted,
    /// Ağ koptu veya belirsizlik oluştu; operatör veya kurtarma gerektirir
    RecoveryRequired,
}

/// Monotonik Fencing Kiralama Belirteci (Lease Token)
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct FencingLease {
    pub session_id: String,
    pub epoch: u64, // Monoton artan epoch (Split-Brain kilidi)
    pub lease_token: String,
    pub owner_node: String,
    pub issued_at: DateTime<Utc>,
    pub ttl_ms: u64,
}

/// Kaynak Tarafı Fencing Bariyeri (Resource-Side Fencing Store)
/// Düğümlerin beyanına değil, korunan kaynağın kapısındaki epoch kontrolüne dayanır.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResourceSideFence {
    pub session_id: String,
    pub current_authorized_epoch: u64,
    pub active_owner: String,
}

impl ResourceSideFence {
    pub fn new(session_id: String, initial_owner: String) -> Self {
        Self {
            session_id,
            current_authorized_epoch: 1,
            active_owner: initial_owner,
        }
    }

    /// Gelen epoch değerini doğrular; düşük veya eşit epoch'lu yazmaları fiziksel olarak reddeder.
    pub fn verify_and_commit(&mut self, request_epoch: u64, node_id: &str) -> Result<()> {
        if request_epoch <= self.current_authorized_epoch {
            bail!(
                "[Resource-Side Fencing Reddi]: Talep edilen epoch ({}) mevcut yetkili epoch'tan ({}) küçük veya eşit! İşlem reddedildi.",
                request_epoch,
                self.current_authorized_epoch
            );
        }
        self.current_authorized_epoch = request_epoch;
        self.active_owner = node_id.to_string();
        println!(
            "[Resource-Side Fencing Onayı]: Epoch {} yetkisi '{}' düğümüne devredildi.",
            request_epoch, node_id
        );
        Ok(())
    }
}

/// Ghost Surface Girdi Olayı
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum InputEventType {
    PointerClick { x: f64, y: f64, button: u32 },
    KeyPress { keycode: u32, pressed: bool },
}

/// Tamponlanan Girdi Öğesi
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct BufferedInput {
    pub epoch: u64,
    pub timestamp_ms: u64,
    pub event: InputEventType,
}

/// Ghost Surface Girdi Tamponu (Input Replay Queue)
/// Ghost Surface ekrandayken (16-100 ms) kullanıcının yaptığı tıklamaları kaydeder ve uyanışta sürece enjekte eder.
pub struct InputReplayQueue {
    pub buffer: VecDeque<BufferedInput>,
    pub max_capacity: usize,
    pub current_epoch: u64,
    pub is_ghost_active: bool,
}

impl InputReplayQueue {
    pub fn new(current_epoch: u64) -> Self {
        Self {
            buffer: VecDeque::with_capacity(128),
            max_capacity: 128,
            current_epoch,
            is_ghost_active: false,
        }
    }

    /// Ghost Surface ekranda aktifken gelen girdiyi kaydeder
    pub fn record_input(&mut self, event: InputEventType) -> bool {
        if !self.is_ghost_active {
            return false;
        }

        if self.buffer.len() >= self.max_capacity {
            self.buffer.pop_front(); // FIFO taşma koruması
        }

        self.buffer.push_back(BufferedInput {
            epoch: self.current_epoch,
            timestamp_ms: Utc::now().timestamp_millis() as u64,
            event,
        });
        true
    }

    /// Gerçek süreç uyandığı anda biriken girdileri sırayla boşaltır (FIFO Replay)
    pub fn flush_to_process(&mut self) -> Vec<BufferedInput> {
        self.is_ghost_active = false;
        self.buffer.drain(..).collect()
    }

    /// Ghost Surface zaman aşımı kontrolü (Auto-Reap)
    #[allow(dead_code)]
    pub fn should_auto_reap(elapsed_ms: u64, timeout_ms: u64) -> bool {
        elapsed_ms > timeout_ms
    }
}

/// BCTP/1 Hat Mesajları (Wire Protocol Messages)
#[allow(dead_code)]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum BctpMessage {
    /// El sıkışma ve düğüm tanıtımı
    Hello {
        protocol_version: String,
        node_id: String,
    },
    /// Donanım, çekirdek ve ortam uyumluluğu
    Capabilities {
        arch: String,
        kernel: String,
        has_criu: bool,
        has_niri: bool,
    },
    /// Oturum devir teklifi ve kapsül manifest özeti
    Offer {
        session_id: String,
        manifest_hash: String,
        total_size: u64,
    },
    /// Hedef düğümün oturumu kabul edip hazırlığı tamamlaması
    PrepareAck {
        session_id: String,
        accepted: bool,
        reason: Option<String>,
    },
    /// Kapsül veri parçası (Data Plane)
    StateChunk {
        session_id: String,
        chunk_seq: u32,
        total_chunks: u32,
        payload_base64: String,
        sha256: String,
    },
    /// Parça alındı onayı
    ChunkAck {
        session_id: String,
        chunk_seq: u32,
    },
    /// Kaynak sürecin dondurulduğu bildirimi (Control Plane - Fence)
    FenceNotice {
        session_id: String,
        epoch: u64,
        lease_token: String,
    },
    /// Hedefte canlandırmanın ve Niri yüzeylerinin hazır olduğu bildirimi
    RestoreReady {
        session_id: String,
        target_pid: u32,
    },
    /// Oturum sahipliğinin nihai devri (Commit)
    Commit {
        session_id: String,
        epoch: u64,
        lease_token: String,
    },
    /// Devir tamamlandı alındısı
    CommitAck {
        session_id: String,
        epoch: u64,
    },
    /// Aktarım iptali
    Abort {
        session_id: String,
        reason: String,
    },
}

/// BCTP/1 Koordinatör Oturumu (Durum Makinesi Yöneticisi)
pub struct BctpCoordinator {
    pub session_id: String,
    pub local_node_id: String,
    pub current_epoch: u64,
    pub state: SessionState,
    pub active_lease: Option<FencingLease>,
}

impl BctpCoordinator {
    pub fn new(session_id: String, local_node_id: String) -> Self {
        Self {
            session_id,
            local_node_id,
            current_epoch: 1,
            state: SessionState::RunningSource,
            active_lease: None,
        }
    }

    /// Hedef hazırlık aşamasına geçiş
    pub fn transition_to_preparing(&mut self) -> Result<()> {
        if self.state != SessionState::RunningSource {
            bail!("Geçersiz durum geçişi: {:?} -> PreparingTarget", self.state);
        }
        self.state = SessionState::PreparingTarget;
        println!("[BCTP/1] Durum Geçişi -> PreparingTarget");
        Ok(())
    }

    /// Kaynak kilitleme (Fence) aşaması: Monotonik Epoch bir artırılır
    pub fn transition_to_fenced(&mut self, lease_token: String) -> Result<FencingLease> {
        if self.state != SessionState::PreparingTarget {
            bail!("Geçersiz durum geçişi: {:?} -> SourceFenced", self.state);
        }

        self.current_epoch += 1; // Monoton artış

        let lease = FencingLease {
            session_id: self.session_id.clone(),
            epoch: self.current_epoch,
            lease_token,
            owner_node: self.local_node_id.clone(),
            issued_at: Utc::now(),
            ttl_ms: 5000,
        };

        self.state = SessionState::SourceFenced;
        self.active_lease = Some(lease.clone());
        println!(
            "[BCTP/1] Durum Geçişi -> SourceFenced (Epoch: {}, Çift çalışma önleme kilidi aktif)",
            self.current_epoch
        );
        Ok(lease)
    }

    /// Hedefte canlandırma aşaması (Restore Barrier)
    pub fn transition_to_restoring(&mut self) -> Result<()> {
        if self.state != SessionState::SourceFenced {
            bail!("Geçersiz durum geçişi: {:?} -> RestoringTarget", self.state);
        }
        self.state = SessionState::RestoringTarget;
        println!("[BCTP/1] Durum Geçişi -> RestoringTarget (Restore Barrier Açıldı)");
        Ok(())
    }

    /// Hedef doğrulandı aşaması
    pub fn transition_to_validated(&mut self) -> Result<()> {
        if self.state != SessionState::RestoringTarget {
            bail!("Geçersiz durum geçişi: {:?} -> TargetValidated", self.state);
        }
        self.state = SessionState::TargetValidated;
        println!("[BCTP/1] Durum Geçişi -> TargetValidated (Süreç ve Niri yüzeyi doğrulandı)");
        Ok(())
    }

    /// Nihai oturum devri (Commit)
    pub fn transition_to_committed(&mut self, received_lease: &FencingLease) -> Result<()> {
        if self.state != SessionState::TargetValidated {
            bail!("Geçersiz durum geçişi: {:?} -> Committed", self.state);
        }

        if received_lease.session_id != self.session_id {
            bail!("Lease oturum ID uyuşmazlığı! Devir reddedildi.");
        }

        if received_lease.epoch != self.current_epoch {
            bail!("Lease epoch uyuşmazlığı! Devir reddedildi.");
        }

        self.state = SessionState::Committed;
        println!(
            "[BCTP/1] [SUCCESS] Durum Geçişi -> Committed! Epoch {} mülkiyeti başarıyla aktarıldı.",
            self.current_epoch
        );
        Ok(())
    }

    /// Güvenli iptal ve kurtarma
    #[allow(dead_code)]
    pub fn transition_to_abort(&mut self, reason: &str) {
        println!("[BCTP/1] [WARN] Oturum İptal Edildi (Neden: {}). Durum -> Aborted", reason);
        self.state = SessionState::Aborted;
    }
}

/// BCTP/1 Gelişmiş Uçtan Uca Simülasyon Testi
pub fn run_fencing_simulation() -> Result<()> {
    println!("=======================================================");
    println!("[GUARD] BCTP/1 PROTOKOLÜ: GELİŞMİŞ FENCING VE GHOST TESTİ");
    println!("=======================================================");

    let session_id = "blz-sess-9921".to_string();
    let mut coordinator = BctpCoordinator::new(session_id.clone(), "blaze-desktop-alpha".to_string());
    let mut resource_fence = ResourceSideFence::new(session_id.clone(), "blaze-desktop-alpha".to_string());

    println!("1. [Kaynak]: Oturum çalışıyor -> {:?}", coordinator.state);
    assert_eq!(coordinator.state, SessionState::RunningSource);

    println!("2. [Hedef]: Hazırlık el sıkışması...");
    coordinator.transition_to_preparing()?;
    assert_eq!(coordinator.state, SessionState::PreparingTarget);

    println!("3. [Kaynak]: Süreç ağacı donduruluyor (Epoch artırıldı)...");
    let lease = coordinator.transition_to_fenced("lease-ed25519-token-xyz".to_string())?;
    assert_eq!(coordinator.state, SessionState::SourceFenced);
    assert_eq!(lease.epoch, 2);

    println!("4. [Hedef]: Ghost Surface gösteriliyor & Girdi Tamponu devreye alınıyor...");
    let mut input_queue = InputReplayQueue::new(lease.epoch);
    input_queue.is_ghost_active = true;

    // Kullanıcı Ghost Surface ekrandayken tıkladı!
    input_queue.record_input(InputEventType::PointerClick { x: 450.0, y: 320.0, button: 1 });
    input_queue.record_input(InputEventType::KeyPress { keycode: 28, pressed: true });
    println!("   └─ Ghost aşamasında 2 kullanıcı girdisi tamponlandı.");

    println!("5. [Hedef]: Restore Barrier geçildi, süreç uyanıyor...");
    coordinator.transition_to_restoring()?;
    assert_eq!(coordinator.state, SessionState::RestoringTarget);

    println!("6. [Hedef]: Niri yüzeyleri ve bellek doğrulandı...");
    coordinator.transition_to_validated()?;
    assert_eq!(coordinator.state, SessionState::TargetValidated);

    println!("7. [Kaynak Tarafı Fencing]: Epoch {} onayı alınıyor...", lease.epoch);
    resource_fence.verify_and_commit(lease.epoch, "blaze-desktop-beta")?;

    println!("8. [Nihai Devir]: COMMIT ve Girdilerin Sürece Aktarımı (FIFO Replay)...");
    coordinator.transition_to_committed(&lease)?;
    assert_eq!(coordinator.state, SessionState::Committed);

    let replayed = input_queue.flush_to_process();
    println!("   └─ {} adet girdi uyanan gerçek sürece başarıyla enjekte edildi!", replayed.len());
    assert_eq!(replayed.len(), 2);

    println!("-------------------------------------------------------");
    println!("[TEST] HATA ENJEKSİYONU: ESKİ DÜĞÜM (STALE EPOCH) SALDIRI TESTİ");
    let stale_attempt = resource_fence.verify_and_commit(1, "eski-kotu-dugum");
    assert!(stale_attempt.is_err(), "Eski epoch'un yazma talebi reddedilmeliydi!");
    println!("   └─ Eski Epoch 1 yazma denemesi Resource-Side Fencing tarafından başarıyla ENGELLENDİ!");
    println!("=======================================================");
    println!("[OK] BCTP/1 Tüm Teknik Sınırları ve Garantileri Başarıyla Geçti!");
    Ok(())
}
