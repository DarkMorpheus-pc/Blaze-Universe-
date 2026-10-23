use sha2::{Digest, Sha256};
use std::fs::OpenOptions;
use std::io::Write;
use std::thread::sleep;
use std::time::Duration;

/// Doğrulanabilir, bellek durumu tutan canlı test iş yükü
pub fn run_test_workload() {
    let pid = std::process::id();
    println!("=======================================================");
    println!("[RESTORE] BLAZE CONTINUUM TEST WORKLOAD BAŞLATILDI");
    println!("   PID: {}", pid);
    println!("   Hedef: Bellek ve sayaç durumunu canlı korumak.");
    println!("=======================================================");

    let mut counter: u64 = 0;
    // Bellekte 1 MB'lık dinamik bir durum tamponu tutuyoruz
    let mut memory_buffer: Vec<u8> = vec![0u8; 1024 * 1024];

    loop {
        counter += 1;

        // Her saniye belleğin bir parçasını değiştiriyoruz
        let idx = (counter as usize * 17) % memory_buffer.len();
        memory_buffer[idx] = (counter % 255) as u8;

        // Tamponun hash'ini hesapla (bellek durumunu doğrulamak için)
        let mut hasher = Sha256::new();
        hasher.update(&memory_buffer[0..4096]);
        let mem_hash = hex::encode(&hasher.finalize()[0..8]);

        let log_line = format!(
            "[PID: {}] Tick #{:05} | Memory State Hash: {} | Timestamp: {:?}\n",
            pid,
            counter,
            mem_hash,
            chrono::Utc::now().to_rfc3339()
        );

        print!("{}", log_line);
        let _ = std::io::stdout().flush();

        // Ayrıca /tmp/blaze_workload_state.log dosyasına da yazıyoruz
        if let Ok(mut file) = OpenOptions::new()
            .create(true)
            .append(true)
            .open("/tmp/blaze_workload_state.log")
        {
            let _ = file.write_all(log_line.as_bytes());
        }

        sleep(Duration::from_millis(1000));
    }
}
