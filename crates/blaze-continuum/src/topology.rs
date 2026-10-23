use std::collections::{BTreeMap, HashSet};
use std::fs;
use std::path::Path;
use std::process::{Command, Stdio};

/// Donanım CPU Topolojisi ve Çekirdek Dağıtım Bilgisi
#[derive(Debug, Clone)]
pub struct CpuTopology {
    pub total_logical_cpus: usize,
    pub perf_cpus_str: String,
    pub eff_cpus_str: String,
    pub all_cpus_str: String,
    pub mode_description: String,
}

impl CpuTopology {
    /// Sistemdeki sysfs düğümlerini inceleyerek CPU topolojisini otomatik keşfeder
    pub fn detect() -> Self {
        // 1. Durum: Intel Hibrit Mimari (P-Cores & E-Cores sysfs düğümleri)
        let intel_p_path = Path::new("/sys/devices/cpu_core/cpus");
        let intel_e_path = Path::new("/sys/devices/cpu_atom/cpus");
        if intel_p_path.exists() && intel_e_path.exists() {
            if let (Ok(p_str), Ok(e_str)) = (fs::read_to_string(intel_p_path), fs::read_to_string(intel_e_path)) {
                let p = p_str.trim().to_string();
                let e = e_str.trim().to_string();
                let all = fs::read_to_string("/sys/devices/system/cpu/online")
                    .unwrap_or_else(|_| "0-15".to_string())
                    .trim()
                    .to_string();
                let count = Self::count_cpus_in_range(&all);

                return Self {
                    total_logical_cpus: count,
                    perf_cpus_str: p,
                    eff_cpus_str: e,
                    all_cpus_str: all,
                    mode_description: "Intel Hybrid (cpu_core/cpu_atom Donanım Ayrımı)".to_string(),
                };
            }
        }

        // 2. Durum: Standart x86_64 SMT / Hyper-Threading veya Çok Çekirdekli CPU
        // thread_siblings_list taranarak fiziksel çekirdekler gruplanır.
        let mut physical_cores: BTreeMap<usize, Vec<usize>> = BTreeMap::new();
        let cpu_dir = Path::new("/sys/devices/system/cpu");
        if let Ok(entries) = fs::read_dir(cpu_dir) {
            for entry in entries.filter_map(|e| e.ok()) {
                let name = entry.file_name();
                let name_str = name.to_string_lossy();
                if name_str.starts_with("cpu") && name_str[3..].chars().all(|c| c.is_ascii_digit()) {
                    let sib_path = entry.path().join("topology/thread_siblings_list");
                    if let Ok(content) = fs::read_to_string(sib_path) {
                        let parsed: Vec<usize> = content
                            .trim()
                            .replace('-', ",")
                            .split(',')
                            .filter_map(|s| s.parse::<usize>().ok())
                            .collect();
                        if let Some(&first) = parsed.first() {
                            physical_cores.entry(first).or_insert(parsed);
                        }
                    }
                }
            }
        }

        let total_phys = physical_cores.len();
        let all_online = fs::read_to_string("/sys/devices/system/cpu/online")
            .unwrap_or_else(|_| "0-15".to_string())
            .trim()
            .to_string();
        let total_logical = Self::count_cpus_in_range(&all_online);

        if total_phys >= 4 {
            // 4 veya daha fazla fiziksel çekirdek: %75'i P-Core (Odak), %25'i E-Core (Arka Plan)
            let perf_core_count = (total_phys * 3) / 4;
            let mut perf_list = Vec::new();
            let mut eff_list = Vec::new();

            for (idx, (_core_id, siblings)) in physical_cores.into_iter().enumerate() {
                if idx < perf_core_count {
                    perf_list.extend(siblings);
                } else {
                    eff_list.extend(siblings);
                }
            }

            perf_list.sort_unstable();
            eff_list.sort_unstable();

            let perf_str = perf_list.iter().map(|c| c.to_string()).collect::<Vec<_>>().join(",");
            let eff_str = eff_list.iter().map(|c| c.to_string()).collect::<Vec<_>>().join(",");

            Self {
                total_logical_cpus: total_logical,
                perf_cpus_str: perf_str,
                eff_cpus_str: eff_str,
                all_cpus_str: all_online,
                mode_description: format!("Fiziksel Çekirdek İzolasyonu ({} Fiziksel Çekirdek)", total_phys),
            }
        } else if total_phys >= 2 {
            // 2 veya 3 çekirdekli sistem
            let mut keys: Vec<usize> = physical_cores.keys().cloned().collect();
            keys.sort_unstable();
            let eff_key = keys.pop().unwrap();
            let mut perf_list: Vec<usize> = Vec::new();
            for k in keys {
                if let Some(sibs) = physical_cores.get(&k) {
                    perf_list.extend(sibs);
                }
            }
            let eff_list: Vec<usize> = physical_cores.get(&eff_key).cloned().unwrap_or_default();

            let perf_str = perf_list.iter().map(|c| c.to_string()).collect::<Vec<_>>().join(",");
            let eff_str = eff_list.iter().map(|c| c.to_string()).collect::<Vec<_>>().join(",");

            Self {
                total_logical_cpus: total_logical,
                perf_cpus_str: perf_str,
                eff_cpus_str: eff_str,
                all_cpus_str: all_online,
                mode_description: "Dengeli Çift Çekirdek Ayrımı".to_string(),
            }
        } else {
            // Tek çekirdek veya sanal makine: Tüm çekirdekler ortak kullanılır
            Self {
                total_logical_cpus: total_logical,
                perf_cpus_str: all_online.clone(),
                eff_cpus_str: all_online.clone(),
                all_cpus_str: all_online,
                mode_description: "Tekil/Sanal Çekirdek (Nice Tabanlı Zamanlama)".to_string(),
            }
        }
    }

    /// Bir sürecin TÜM iş parçacıklarına (TID) topluca CPU Affinity uygular
    pub fn apply_affinity_to_all_threads(pid: i32, cpu_list: &str) -> usize {
        let mut pinned_count = 0;
        let task_dir = format!("/proc/{}/task", pid);
        if let Ok(entries) = fs::read_dir(task_dir) {
            for entry in entries.filter_map(|e| e.ok()) {
                let tid_name = entry.file_name();
                let tid_str = tid_name.to_string_lossy();
                if let Ok(tid) = tid_str.parse::<i32>() {
                    let status = Command::new("taskset")
                        .arg("-c")
                        .arg("-p")
                        .arg(cpu_list)
                        .arg(tid.to_string())
                        .stdout(Stdio::null())
                        .stderr(Stdio::null())
                        .status();
                    if let Ok(s) = status {
                        if s.success() {
                            pinned_count += 1;
                        }
                    }
                }
            }
        } else {
            // task dizini okunamadıysa en azından ana PID'ye uygula
            let _ = Command::new("taskset")
                .arg("-c")
                .arg("-p")
                .arg(cpu_list)
                .arg(pid.to_string())
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .status();
            pinned_count = 1;
        }
        pinned_count
    }

    fn count_cpus_in_range(range_str: &str) -> usize {
        let mut set = HashSet::new();
        for part in range_str.split(',') {
            if let Some((start, end)) = part.split_once('-') {
                if let (Ok(s), Ok(e)) = (start.parse::<usize>(), end.parse::<usize>()) {
                    for i in s..=e {
                        set.insert(i);
                    }
                }
            } else if let Ok(s) = part.parse::<usize>() {
                set.insert(s);
            }
        }
        set.len()
    }
}
