use anyhow::{bail, Result};

pub const BCTP_MAGIC: &[u8; 4] = b"BCTP";
pub const BCTP_WIRE_VERSION: u8 = 1;
pub const MAX_SAFE_PAYLOAD_SIZE: u32 = 64 * 1024 * 1024; // 64 MB emniyet sınırı (OOM koruması)

/// Mesaj Tipleri
#[repr(u8)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BctpMessageType {
    Hello = 1,
    Capabilities = 2,
    Offer = 3,
    Prepare = 4,
    Ready = 5,
    GhostFrame = 6,
    StateChunk = 7,
    Commit = 8,
    CommitAck = 9,
    Abort = 10,
}

impl BctpMessageType {
    pub fn from_u8(v: u8) -> Result<Self> {
        match v {
            1 => Ok(Self::Hello),
            2 => Ok(Self::Capabilities),
            3 => Ok(Self::Offer),
            4 => Ok(Self::Prepare),
            5 => Ok(Self::Ready),
            6 => Ok(Self::GhostFrame),
            7 => Ok(Self::StateChunk),
            8 => Ok(Self::Commit),
            9 => Ok(Self::CommitAck),
            10 => Ok(Self::Abort),
            _ => bail!("Bilinmeyen BCTP mesaj tipi: {}", v),
        }
    }
}

/// 64-Bayt Taşınabilir, Hizalanmış Kablo Başlığı (Portable Wire Header)
/// Rust bellek hizalamasına (UB) takılmadan, Little-Endian bayt dönüşümüyle güvenli çözülür.
#[repr(C)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct BctpWireHeader {
    pub magic: [u8; 4],            // 0..4: "BCTP"
    pub version: u8,               // 4: 1
    pub msg_type: u8,              // 5: BctpMessageType
    pub context_flags: u16,        // 6..8: Audio/Clipboard/UFFD
    pub lease_epoch: u64,          // 8..16: Monotonik Fencing Epoch
    pub sequence: u64,             // 16..24: Mesaj sıra numarası (Replay koruması)
    pub session_id_hash: [u8; 8],  // 24..32: Oturum ID hash kesiti
    pub payload_len: u32,          // 32..36: Payload boyutu
    pub width_px: u16,             // 36..38: Pencere genişliği
    pub height_px: u16,            // 38..40: Pencere yüksekliği
    pub scale_milli: u16,          // 40..42: Ölçek faktörü (1000 = %100)
    pub target_column_idx: u16,    // 42..44: Niri hedef sütun indexi
    pub payload_checksum: [u8; 4], // 44..48: Checksum (CRC32/SHA kesiti)
    pub reserved: [u8; 16],        // 48..64: Gelecek genişlemeler için sıfır dolgu
}

// Derleme anında tam 64 bayt olduğunu garantiye alıyoruz
const _: () = assert!(std::mem::size_of::<BctpWireHeader>() == 64);

impl BctpWireHeader {
    pub fn new(msg_type: BctpMessageType, epoch: u64, sequence: u64, payload_len: u32) -> Self {
        Self {
            magic: *BCTP_MAGIC,
            version: BCTP_WIRE_VERSION,
            msg_type: msg_type as u8,
            context_flags: 0,
            lease_epoch: epoch,
            sequence,
            session_id_hash: [0u8; 8],
            payload_len,
            width_px: 1920,
            height_px: 1080,
            scale_milli: 1000,
            target_column_idx: 1,
            payload_checksum: [0u8; 4],
            reserved: [0u8; 16],
        }
    }

    /// Başlığı tam 64 baytlık Little-Endian diziye kodlar
    pub fn encode(&self) -> [u8; 64] {
        let mut buf = [0u8; 64];
        buf[0..4].copy_from_slice(&self.magic);
        buf[4] = self.version;
        buf[5] = self.msg_type;
        buf[6..8].copy_from_slice(&self.context_flags.to_le_bytes());
        buf[8..16].copy_from_slice(&self.lease_epoch.to_le_bytes());
        buf[16..24].copy_from_slice(&self.sequence.to_le_bytes());
        buf[24..32].copy_from_slice(&self.session_id_hash);
        buf[32..36].copy_from_slice(&self.payload_len.to_le_bytes());
        buf[36..38].copy_from_slice(&self.width_px.to_le_bytes());
        buf[38..40].copy_from_slice(&self.height_px.to_le_bytes());
        buf[40..42].copy_from_slice(&self.scale_milli.to_le_bytes());
        buf[42..44].copy_from_slice(&self.target_column_idx.to_le_bytes());
        buf[44..48].copy_from_slice(&self.payload_checksum);
        buf[48..64].copy_from_slice(&self.reserved);
        buf
    }

    /// 64 baytlık diziyi doğrular ve başlığı çözer (Allocation Gate ile güvenli)
    pub fn decode(buf: &[u8; 64]) -> Result<Self> {
        let magic = [buf[0], buf[1], buf[2], buf[3]];
        if &magic != BCTP_MAGIC {
            bail!("Geçersiz BCTP Sihirli Baytları (Magic): {:?}", magic);
        }

        let version = buf[4];
        if version != BCTP_WIRE_VERSION {
            bail!("Desteklenmeyen BCTP Sürümü: {}", version);
        }

        let msg_type = buf[5];
        let _ = BctpMessageType::from_u8(msg_type)?;

        let context_flags = u16::from_le_bytes([buf[6], buf[7]]);
        let lease_epoch = u64::from_le_bytes(buf[8..16].try_into().unwrap());
        let sequence = u64::from_le_bytes(buf[16..24].try_into().unwrap());

        let mut session_id_hash = [0u8; 8];
        session_id_hash.copy_from_slice(&buf[24..32]);

        let payload_len = u32::from_le_bytes(buf[32..36].try_into().unwrap());
        // Allocation Gate (OOM Saldırı Koruması)
        if payload_len > MAX_SAFE_PAYLOAD_SIZE {
            bail!(
                "[Allocation Gate]: Aşırı büyük payload boyutu reddedildi ({} MB > 64 MB)",
                payload_len / 1024 / 1024
            );
        }

        let width_px = u16::from_le_bytes([buf[36], buf[37]]);
        let height_px = u16::from_le_bytes([buf[38], buf[39]]);
        let scale_milli = u16::from_le_bytes([buf[40], buf[41]]);
        let target_column_idx = u16::from_le_bytes([buf[42], buf[43]]);

        let mut payload_checksum = [0u8; 4];
        payload_checksum.copy_from_slice(&buf[44..48]);

        let mut reserved = [0u8; 16];
        reserved.copy_from_slice(&buf[48..64]);

        Ok(Self {
            magic,
            version,
            msg_type,
            context_flags,
            lease_epoch,
            sequence,
            session_id_hash,
            payload_len,
            width_px,
            height_px,
            scale_milli,
            target_column_idx,
            payload_checksum,
            reserved,
        })
    }
}
