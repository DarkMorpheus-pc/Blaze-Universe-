<div align="center">

# BlazeOS Native — Resmi Kullanım Kılavuzu & Sistem Rehberi
# BlazeOS Native — Official User Guide & System Manual

**[🇹🇷 Türkçe Kılavuz](#-türkçe-kullanım-kılavuzu) • [🇬🇧 English User Guide](#-english-user-guide)**

</div>

---

# 🇹🇷 Türkçe Kullanım Kılavuzu

**BlazeOS Native (Blaze Universe)**; herhangi bir dağıtımın (Ubuntu, Fedora, Arch vb.) çatallaması olmayan, sıfırdan kendi **Linux 7.2.9 Amiral Gemisi Çekirdeği**, **Portadora (`.blz`)** kriptografik paket yöneticisi, **SolarUI (Niri + Noctalia / Caelestia / end4-pC)** masaüstü ortamı, **FireHub 1.9.0** evrensel uygulama mağazası ve **Blaze Sentinel** güvenlik mimarisiyle inşa edilmiş bağımsız bir işletim sistemidir.

Bu kılavuz; sisteme ilk girişten sabit diske kuruluma, pencere ve OmniBar yönetiminden oyun optimizasyonlarına kadar tüm işlemleri adım adım açıklar.

---

## İçindekiler (TR)
1. [Hızlı Başlangıç ve Varsayılan Hesap Bilgileri](#1-hızlı-başlangıç-ve-varsayılan-hesap-bilgileri)
2. [BlazeOS'u Sabit Diske Kurma (Solar Installer)](#2-blazeosu-sabit-diske-kurma-solar-installer)
3. [SolarUI Masaüstü, OmniBar ve Kabuk Motorları](#3-solarui-masaüstü-omnibar-ve-kabuk-motorları)
4. [Klavye Kısayolları Rehberi](#4-klavye-kısayolları-rehberi)
5. [Uygulama Yükleme: FireHub Mağaza, Portadora (.blz) ve Flathub](#5-uygulama-yükleme-firehub-mağaza-portadora-blz-ve-flathub)
6. [Oyun Performans Merkezi: Solar GameZone, Proton-GE ve NTSYNC](#6-oyun-performans-merkezi-solar-gamezone-proton-ge-ve-ntsync)
7. [Güvenlik (Blaze Sentinel), USB Kalkanı ve BERP Kurtarma](#7-güvenlik-blaze-sentinel-usb-kalkanı-ve-berp-kurtarma)
8. [Blaze Continuum — Oturum Dondurma ve Cihazlar Arası Işınlama](#8-blaze-continuum--oturum-dondurma-ve-cihazlar-arası-ışınlama)
9. [Sık Karşılaşılan Sorunlar ve Pratik Çözümler (SSS)](#9-sık-karşılaşılan-sorunlar-ve-pratik-çözümler-sss)

---

## 1. Hızlı Başlangıç ve Varsayılan Hesap Bilgileri

Sistemi QEMU/KVM üzerinde veya Canlı ISO (Live USB) ile başlattığınızda yaklaşık **3.8 saniye** içinde doğrudan **SolarUI** Wayland masaüstüne ulaşırsınız:

```bash
# Ana bilgisayarınızda QEMU KVM ile çalıştırmak için:
./tools/run-blazeos-native.sh
```

| Hesap | Kullanıcı Adı | Varsayılan Parola | Yetki Durumu |
| :--- | :--- | :--- | :--- |
| **Masaüstü Kullanıcısı** | `blaze` | `blaze` | `wheel`, `video`, `audio`, `input`, `seat` (`sudo` yetkili) |
| **Sistem Yöneticisi** | `root` | `blaze` | Tam Sistem Yetkisi |

> **Güvenlik Notu:** Canlı (Live) oturumda test kolaylığı için `sudo` şifresiz çalışır. Ancak sistemi **Solar Installer** ile sabit diskinize kurduğunuzda, kurulum sihirbazı otomatik olarak sıkılaştırılmış parola politikasını (`0440`) devreye alır ve `sudo` işlemleri belirlediğiniz kullanıcı parolasını sorar.

---

## 2. BlazeOS'u Sabit Diske Kurma (Solar Installer)

BlazeOS Native'i sabit diskinize (NVMe, SSD veya sanal disk) kurmak için iki yöntem bulunur:

### A) Grafiksel Kurulum Sihirbazı (Önerilen)
1. Masaüstü açıldığında karşınıza gelen **BlazeOS Karşılama Merkezi** penceresindeki **"BlazeOS'u Diske Kur (Solar Installer)"** butonuna tıklayın veya terminal/OmniBar üzerinden şu komutu çalıştırın:
   ```bash
   solar-shell installer
   # veya kısaca:
   solar-installer-gui
   ```
2. **Adım 1 — Hedef Disk Seçimi:** Listeden kurulum yapılacak diski seçin. Sihirbaz; mevcut bölümleri, EFI/Windows varlığını ve güvenlik uyarılarını otomatik denetler. Harici/USB diske kurulum yapacaksanız *"Çıkarılabilir / USB diske kuruluma izin ver"* kutucuğunu işaretleyin.
3. **Adım 2 — Kullanıcı ve Bölge Ayarları:**
   - **Tam Ad, Kullanıcı Adı, Bilgisayar Adı (Hostname)** ve **Parola** bilgilerinizi girin (en az 8 karakter).
   - **Klavye Düzeni** (`tr` Türkçe Q, `us` İngilizce, `de`, `fr`, `gb`), **Sistem Dili** (`tr_TR.UTF-8`, `en_US.UTF-8`) ve **Saat Dilimi** (`Europe/Istanbul`, `UTC` vb.) seçiminizi yapın. Klavye düzenini seçtiğiniz anda canlı oturumun klavyesi de anında güncellenir.
4. **Adım 3 — Kurulum Planı Özeti ve Onay:** `solar-installer plan` tarafından üretilen GPT bölümleme tablosunu (EFI System Partition + `blaze-root` ext4) inceleyin, onay kutusunu işaretleyin ve **"Kurulumu Başlat"** butonuna tıklayın.

### B) Komut Satırı (CLI) ile Kurulum
```bash
# 1. Uygun diskleri ve güvenlik durumunu JSON olarak inceleyin:
solar-installer probe --json

# 2. Diskte hiçbir değişiklik yapmadan kurulum planını görüntüleyin (Dry-Run):
solar-installer plan --disk /dev/nvme0n1

# 3. Yanıt dosyası ile kurulumu gerçekleştirin:
sudo solar-installer apply --disk /dev/nvme0n1 --answers /tmp/answers.json --password-stdin --yes
```

---

## 3. SolarUI Masaüstü, OmniBar ve Kabuk Motorları

### 3.1. OmniBar (Birleşik Komut, Arama ve Hesaplama Merkezi)
**SolarUI OmniBar**, uygulama başlatma, matematiksel hesaplama, döviz/birim çevirme, pano geçmişi ve sistem komutlarını tek bir merkezde toplar.

#### OmniBar Nasıl Açılır ve Nasıl Kapatılır?
* **Açma / Kapatma (Toggle):** Klavyeden **`Super + Space`** (veya terminalden `solar-shell omnibar`) tuşlarına basın. OmniBar açıkken **tekrar `Super + Space` tuşlarına basarsanız** OmniBar anında kapanır.
* **Klavye ile Kapatma (`Esc`):** Arama kutusunda yazarken veya aşağı/yukarı ok tuşlarıyla sonuç listesinde gezinirken **`Esc`** tuşuna basmanız OmniBar'ı her koşulda derhal kapatır.
* **Fare ile Kapatma (`✕ Esc` Butonu):** OmniBar penceresinin sağ üst köşesinde yer alan **`✕ Esc`** butonuna tıklayarak pencereyi tek tıkla kapatabilirsiniz.
* **Genel Pencere Kapatma Kısayolu:** Herhangi bir pencere gibi **`Super + Q`** veya **`Super + Shift + Q`** kısayoluyla da kapatılabilir.

#### OmniBar İçinde Kullanabileceğiniz Özel Komutlar:
| Ne Yapmak İstiyorsunuz? | OmniBar'a Yazacağınız Örnek İfade | Açıklama |
| :--- | :--- | :--- |
| **Uygulama Açmak** | `firehub`, `alacritty`, `ayarlar` | Bulanık (fuzzy) arama ile eşleşen uygulamayı başlatır. |
| **Matematiksel Hesaplama** | `= 25 * 1024` veya `sqrt(144)` | Sonucu anında hesaplar; `Enter` ile panoya kopyalar. |
| **Döviz / Kripto / Birim Çeviri** | `100 usd to try`, `1 btc in usd`, `50 km in miles`, `16 gb in mb` | Çeviri sonucunu gösterir ve `Enter` ile panoya kopyalar. |
| **Pano Geçmişi (Clipboard)** | `cb` veya `pano` (örn: `cb parola`) | Kopyaladığınız son metinleri listeler, seçileni panoya geri yükler. |
| **Takılan Süreci Kapatmak** | `kill firefox` veya `/kill Wayland` | Eşleşen süreçleri PID numarasıyla listeler, `Enter` ile sonlandırır. |
| **Uygulama Mağazasını Açmak** | `store` | FireHub Uygulama Mağazasını başlatır. |
| **Sistem Kurucusunu Açmak** | `install` | Solar Installer grafiksel kurulum sihirbazını açar. |
| **Oyun Modunu Açmak** | `game` | Solar GameZone tam ekran oyun merkezini başlatır. |
| **Kurtarma Konsolunu Açmak** | `berp` veya `kurtarma` | Blaze Emergency Recovery (`blaze-recovery`) aracını açar. |

---

### 3.2. Masaüstü Kabuk Motorları (Noctalia, Caelestia, end4-pC)
SolarUI, **ChromeOS Ash** benzeri bir Rust gözetmen (`solar-core`) üzerinde çalışır ve üç farklı masaüstü kabuk motorunu canlı olarak (oturumu kapatmadan) değiştirebilir:
1. **Noctalia (`noctalia`):** Varsayılan, ultra hızlı yerel C++ Wayland katman kabuğu (üst/alt bar, bildirim merkezi, takvim, ses/ağ/güç menüsü).
2. **Caelestia (`caelestia`):** Quickshell/Qt6 tabanlı akıcı animasyonlu masaüstü kabuğu.
3. **end4-pC (`end4-pc`):** Gelişmiş Material 3 üretkenlik ve widget kabuğu.

**Kabuk Motorunu Değiştirmek İçin:**
* **Grafiksel Arayüzden:** `Solar Sistem Ayarları` (`solar-shell settings`) -> **Görev Çubuğu & Kabuk** sekmesinden istediğiniz motoru seçin.
* **Terminalden:**
  ```bash
  solar-shell switch noctalia
  solar-shell switch caelestia
  solar-shell switch end4-pc
  ```
* **Görev Çubuğunu (Bar) Gizlemek / Gösterim Durumunu Değiştirmek İçin:**
  ```bash
  solar-shell toggle-taskbar
  ```

---

## 4. Klavye Kısayolları Rehberi

> **Not:** `Super` (veya `Mod`) tuşu klavyenizdeki **Windows / Command (⌘)** tuşudur. Sanal makinelerde (QEMU) `Alt` tuşu da ikincil modifikatör olarak desteklenir.

### Sistem ve Uygulama Kısayolları
| Kısayol | İşlev |
| :--- | :--- |
| `Super + Return` (veya `Super + T`) | **Alacritty** Terminal Öykünücüsünü Aç |
| `Super + Space` (veya `Alt + Space`) | **SolarUI OmniBar** Komut ve Arama Merkezini Aç / Kapat |
| `Super + D` | **Noctalia** Uygulama Başlatıcısını (App Launcher) Aç / Kapat |
| `Super + H` | **FireHub** Uygulama Mağazasını Aç |
| `Super + I` | **Solar Sistem Ayarları** Penceresini Aç |
| `Super + G` | **Solar GameZone** Oyun Performans Merkezini Aç |
| `Super + V` | Pano Geçmişini (Clipboard History) Aç |
| `Super + L` | Ekranı Kilitle |
| `Super + Shift + E` | Oturumu Kapat / Çıkış Yap |
| `Super + Shift + /` | Canlı Kısayol Yardım Panelini Göster |

### Pencere ve Çalışma Alanı (Niri Scrollable Tiling) Yönetimi
| Kısayol | İşlev |
| :--- | :--- |
| `Super + Q` veya `Super + Shift + Q` | Aktif Pencereyi Kapat |
| `Super + Sol / Sağ Ok` (veya `H / L`) | Şerit Üzerinde Sol / Sağ Pencere Sütununa Kaydır |
| `Super + Yukarı / Aşağı Ok` (veya `J / K`) | Aynı Sütun İçindeki Pencereler Arasında Geçiş Yap |
| `Super + Ctrl + Sol / Sağ Ok` | Aktif Pencereyi Sol / Sağ Sütuna Taşı |
| `Super + 1 .. 9` | `1` – `9` Numaralı Çalışma Alanına (Workspace) Geç |
| `Super + Ctrl + 1 .. 9` | Aktif Pencereyi `1` – `9` Numaralı Çalışma Alanına Gönder |
| `Super + R` | Pencere Sütun Genişliğini Döngüsel Değiştir (%33 -> %50 -> %66) |
| `Super + F` | Pencereyi Sütun İçinde Tam Boyuta Genişlet (Maximize Column) |
| `Super + Shift + F` | Pencereyi Tam Ekran (Fullscreen) Yap |
| `Super + Shift + V` | Pencereyi Yüzer (Floating) Moda Al / Döşemeye Geri Döndür |
| `Super + -` / `Super + =` | Pencere Genişliğini %10 Küçült / Büyüt |
| `Print` | Bölge Seçerek Ekran Görüntüsü Al |
| `Ctrl + Print` | Tüm Ekranın Görüntüsünü Al |
| `Alt + Print` | Sadece Aktif Pencerenin Görüntüsünü Al |

---

## 5. Uygulama Yükleme: FireHub Mağaza, Portadora (`.blz`) ve Flathub

BlazeOS Native, hem kendi yerel **Portadora (`.blz`)** paketlerini hem de **Flathub (`flatpak`)** ekosistemindeki binlerce uygulamayı destekler.

### 5.1. FireHub 1.9.0 Evrensel Uygulama Mağazası (`Super + H` / `firehub`)
1. **Katalogdan Tek Tıkla Kurulum:** FireHub içinde yer alan 83 seçkin uygulama için **"Yükle"** butonuna tıkladığınızda dağıtım seçim penceresinde en üstteki **`BlazeOS Native (Portadora & Flathub)`** seçeneğini seçin. FireHub, ilgili paketi otomatik olarak Portadora veya Flathub üzerinden indirip kurar.
2. **Canlı Flathub Evrensel Arama:** FireHub üst arama çubuğuna katalogda olmayan herhangi bir uygulamanın adını (ör. `LibreOffice`, `Obsidian`, `Kdenlive`, `Blender`, `Lutris`) yazın. Katalog sonuçlarının hemen altında **"Flathub Evrensel Deposu"** sonuçları canlı olarak listelenir ve **"Flathub'dan Kur"** butonuyla doğrudan kurulur.
3. **Yerel Paket Kurucu (`.blz`, `.flatpakref`, `.AppImage`):** İndirdiğiniz bir `.blz` paketini çift tıklayarak veya FireHub üzerinden açarak paket meta verilerini (`portadora info`) inceleyebilir ve tek tıkla kurabilirsiniz.

### 5.2. Portadora Komut Satırı (CLI) Kullanımı
```bash
# Sistemde kurulu tüm paketleri listele (124+ temel paket):
portadora list

# Bir paketin detaylı bilgisini ve dosya sayısını görüntüle:
portadora info firehub
portadora info linux-blaze

# Uzak depoda paket ara:
portadora search alacritty

# Yerel bir .blz paketini veya depo paketini kur:
sudo portadora install ./paket-adi-1.0.0-1.x86_64.blz

# Çakışan dosyaların üzerine yazarak zorla kur:
sudo portadora install --force ./paket-adi-1.0.0-1.x86_64.blz

# Kurulu bir paketi kaldır:
sudo portadora remove paket-adi

# Tüm sistem dosyalarının SHA-256 ve izin bütünlüğünü doğrula:
portadora verify

# Yarım kalmış bir paket işlemini kurtar:
sudo portadora recover
```

### 5.3. Flatpak Komut Satırı (CLI) Kullanımı
```bash
# Flathub deposunu kullanıcı bazlı ekle (FireHub ilk kurulumda otomatik yapar):
flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo

# Flathub'dan uygulama ara ve kur:
flatpak search org.libreoffice.LibreOffice
flatpak install --user -y flathub org.libreoffice.LibreOffice
```

---

## 6. Oyun Performans Merkezi: Solar GameZone, Proton-GE ve NTSYNC

BlazeOS Native, **Linux 7.2.9 Amiral Gemisi Çekirdeği** içinde oyunlar için kritik olan **`CONFIG_NTSYNC=y` (`/dev/ntsync`)**, **`CONFIG_SCHED_CLASS_EXT=y` (`sched_ext` eBPF zamanlayıcı)**, **1000 Hz (`CONFIG_HZ_1000=y`)** ve **Tam Öncelikli (`CONFIG_PREEMPT=y`)** mimariyle gelir.

1. **Solar GameZone'u Başlatma:** `Super + G` tuşlarına basın veya `solar-shell gamezone` komutunu çalıştırın.
2. **Yerleşik Proton-GE & NTSYNC Yöneticisi:** GameZone içerisindeki **"Proton-GE & NTSYNC"** butonuna tıklayarak:
   - Çekirdekteki `/dev/ntsync` ve `sched_ext` durumunu canlı görebilir,
   - **"En Son GE-Proton Sürümünü İndir & Kur"** butonuyla harici hiçbir araca ihtiyaç duymadan GitHub üzerinden en güncel `GloriousEggroll/proton-ge-custom` sürümünü doğrudan `~/.steam/root/compatibilitytools.d` dizinine kurabilirsiniz.
3. **Blaze GameMode CLI (`blaze-gamemode`):**
   ```bash
   # Oyun performans modunu etkinleştir (CPU governor=performance, split_lock_mitigate=0, ntsync):
   sudo blaze-gamemode on

   # Mevcut oyun çekirdeği telemetrisini sorgula:
   blaze-gamemode status

   # Normal masaüstü güç profiline dön:
   sudo blaze-gamemode off
   ```

---

## 7. Güvenlik (Blaze Sentinel), USB Kalkanı ve BERP Kurtarma

### 7.1. Blaze Sentinel Güvenlik Denetimi
BlazeOS Native, CIS ve KSPP standartlarına göre sıkılaştırılmıştır (**Lynis Hardening Index: 87/100**).
```bash
# 7 katmanlı güvenlik postürünü (AppArmor, Lockdown, Landlock, Yama, nftables, sysctl, auditd) kontrol et:
blaze-sentinel status

# JSON çıktısı al:
blaze-sentinel status --json
```

### 7.2. USB Depolama Kalkanı (Paranoid Mod)
Fiziksel port güvenliği gerektiren ortamlarda yabancı USB belleklerin bağlanmasını engellemek için:
1. `Solar Sistem Ayarları` (`solar-shell settings`) -> **Sistem Sağlığı** sekmesini açın.
2. **"USB Depolama Kalkanı (Fiziksel Port Güvenliği / Paranoid Mod)"** anahtarını etkinleştirin. Bu işlem `/etc/modprobe.d/blaze-usb-guard.conf` kuralını yazar ve yeni USB yığın depolama aygıtlarını engeller. Normal USB bellek kullanımı için bu anahtarı kapalı tutabilirsiniz.

### 7.3. BERP (Blaze Emergency Recovery Protocol) & `blaze-recovery`
Sistemde bir yapılandırma hatası veya paket bozulması yaşandığında:
* **Masaüstünden veya TTY'den:** `blaze-recovery` komutunu çalıştırın (veya OmniBar'a `berp` yazın).
  - **Sistem Tanılama:** Disk alanı, bellek, `portadora verify` ve `blaze-sentinel` durumunu denetler.
  - **Ayarları Sıfırla:** Kullanıcı masaüstü ayarlarını (`~/.config/solarui/config.toml`) temiz önyükleme durumuna döndürür ve bozuk paket işlemlerini (`portadora recover`) onarır.
* **Açılışta (Bootloader):** Limine önyükleme menüsünden **"Blaze Universe Emergency Recovery (BERP Core)"** seçeneğini seçerek erken önyükleme (initramfs) kurtarma konsoluna girebilirsiniz.

---

## 8. Blaze Continuum — Oturum Dondurma ve Cihazlar Arası Işınlama

**Blaze Continuum**, açık pencerelerinizi ve süreç durumunuzu `.blz-state` kapsülüne dondurup yerel ağdaki (LAN) başka bir BlazeOS makinesine milisaniyeler içinde ışınlamanızı sağlar:

```bash
# 1. Çekirdek (sched_ext, Checkpoint/Restore), Niri ve CPU P-Core/E-Core topolojisini denetle:
blaze-continuum check

# 2. Mevcut Niri masaüstü pencere ve sütun yerleşimini yakala:
blaze-continuum capture-desktop

# 3. Bir süreci ve masaüstü durumunu kapsüle dondur / geri yükle:
blaze-continuum freeze --pid <PID> --out /tmp/oturum.blz-state
blaze-continuum restore --capsule /tmp/oturum.blz-state

# 4. Hedef makinede dinleyici başlat ve kaynak makineden odaklı pencereyi ışınla:
blaze-continuum listen --port 45821
blaze-continuum cast --target 192.168.1.50:45821
```

---

## 9. Sık Karşılaşılan Sorunlar ve Pratik Çözümler (SSS)

* **S: OmniBar'ı açtım ama nasıl kapatacağımı bulamadım?**
  * **C:** Klavyeden **`Esc`** tuşuna basabilir, **`Super + Space`** kısayoluna tekrar basabilir veya OmniBar'ın sağ üst köşesindeki **`✕ Esc`** butonuna tıklayabilirsiniz.
* **S: Klavye düzenimi (Türkçe Q / İngilizce US) oturumu kapatmadan nasıl değiştiririm?**
  * **C:** Terminalden `niri msg action switch-layout next` komutunu çalıştırabilir veya `Solar Sistem Ayarları -> Sistem & Güç` sekmesinden klavye düzenini değiştirebilirsiniz.
* **S: Masaüstü barı (Noctalia / Caelestia) kapandıysa veya donduysa ne yapmalıyım?**
  * **C:** `solar-core` Watchdog servisi çöken kabuğu 3 saniye içinde otomatik yeniden başlatır. Manuel onarım için terminalden `solar-shell repair` komutunu çalıştırabilirsiniz.
* **S: Sistemde ses gelmiyorsa ne kontrol edilmeli?**
  * **C:** `solar-session` başlangıçta `pipewire` ve `wireplumber` servislerini otomatik başlatır. Durumu kontrol etmek için `pgrep -a pipewire` veya `Solar Sistem Ayarları -> Ses & Medya` sekmesini kullanabilirsiniz.

---
---

# 🇬🇧 English User Guide

**BlazeOS Native (Blaze Universe)** is an independent, source-built Linux operating system — not a fork or derivative of Ubuntu, Fedora, or Arch Linux. It features a custom **Linux 7.2.9 Flagship Kernel** (`sched_ext`, `NTSYNC`, `CRIU`, KSPP hardening), the **Portadora (`.blz`)** cryptographic package manager with TUF verification, the **SolarUI** Wayland desktop environment (**Niri** + **Noctalia / Caelestia / end4-pC**), the **FireHub 1.9.0** universal app store (Portadora + Flathub), and the **Blaze Sentinel** security architecture.

---

## Table of Contents (EN)
1. [Quickstart & Default Credentials](#1-quickstart--default-credentials)
2. [Installing BlazeOS to Disk (Solar Installer)](#2-installing-blazeos-to-disk-solar-installer)
3. [SolarUI Desktop, OmniBar & Shell Engines](#3-solarui-desktop-omnibar--shell-engines)
4. [Complete Keyboard Shortcuts Reference](#4-complete-keyboard-shortcuts-reference)
5. [Installing Applications: FireHub Store, Portadora (.blz) & Flathub](#5-installing-applications-firehub-store-portadora-blz--flathub)
6. [Gaming Center: Solar GameZone, Proton-GE & NTSYNC](#6-gaming-center-solar-gamezone-proton-ge--ntsync)
7. [Security (Blaze Sentinel), USB Guard & BERP Recovery](#7-security-blaze-sentinel-usb-guard--berp-recovery)
8. [Blaze Continuum — Stateful Session Teleportation](#8-blaze-continuum--stateful-session-teleportation)
9. [Troubleshooting & FAQ](#9-troubleshooting--faq)

---

## 1. Quickstart & Default Credentials

Booting BlazeOS Native via QEMU/KVM or a Live USB takes approximately **3.8 seconds** directly into the **SolarUI** Wayland desktop:

```bash
# Launch BlazeOS Native in QEMU with KVM and VirtIO acceleration:
./tools/run-blazeos-native.sh
```

| Role | Username | Default Password | Privileges |
| :--- | :--- | :--- | :--- |
| **Desktop User** | `blaze` | `blaze` | Member of `wheel`, `video`, `audio`, `input`, `seat` (`sudo` enabled) |
| **Administrator** | `root` | `blaze` | Full System Administrator |

> **Security Note:** On the Live ISO/VM image, passwordless `sudo` is enabled for convenience. When you install BlazeOS to a persistent disk using **Solar Installer**, the installer automatically replaces the live rule with a hardened password-authenticated `sudo` policy (`0440`).

---

## 2. Installing BlazeOS to Disk (Solar Installer)

### A) Graphical Installer Wizard (Recommended)
1. Click **"BlazeOS'u Diske Kur (Solar Installer)"** in the Welcome Center (`solar-shell welcome`), or run:
   ```bash
   solar-shell installer
   # or:
   solar-installer-gui
   ```
2. **Step 1 — Target Disk Selection:** Select your target drive. The installer automatically inspects partitions, mounted paths, and EFI/Windows presence. Check *"Allow installation to removable/USB drives"* if targeting an external disk.
3. **Step 2 — Identity & Localization:** Enter your **Full Name, Username, Hostname, Password**, and select your **Keyboard Layout** (`tr`, `us`, `de`, `fr`, `gb`), **Locale**, and **Timezone**. Selecting a keyboard layout immediately switches the active Wayland layout so you can test typing your password accurately.
4. **Step 3 — Plan Preview & Apply:** Review the dry-run GPT partition layout generated by `solar-installer plan`, check the confirmation box, and click **"Start Installation"**.

### B) Command-Line Installation (CLI)
```bash
# 1. Inspect candidate disks and safety checks in JSON:
solar-installer probe --json

# 2. Preview the partition and deployment plan (non-destructive dry-run):
solar-installer plan --disk /dev/nvme0n1

# 3. Apply the installation:
sudo solar-installer apply --disk /dev/nvme0n1 --answers /tmp/answers.json --password-stdin --yes
```

---

## 3. SolarUI Desktop, OmniBar & Shell Engines

### 3.1. OmniBar (Unified Command, Search & Calculation Hub)
**SolarUI OmniBar** combines fuzzy app launching, instant math evaluation, currency/unit conversion, clipboard history, and system commands.

#### How to Open and Close OmniBar:
* **Toggle Open / Close:** Press **`Super + Space`** (or `Alt + Space`). Pressing **`Super + Space` a second time** while OmniBar is open immediately closes it.
* **Close with Keyboard (`Esc`):** Pressing **`Esc`** closes OmniBar at any time — even after navigating down the result list with the arrow keys.
* **Close with Mouse (`✕ Esc` Button):** Click the **`✕ Esc`** button in the top-right corner of the OmniBar card.
* **Standard Window Close:** Press **`Super + Q`** or **`Super + Shift + Q`**.

#### Built-in OmniBar Power Commands:
| Feature | Example Query | Action |
| :--- | :--- | :--- |
| **Launch Apps** | `firehub`, `alacritty`, `settings` | Fuzzy-matches installed desktop applications. |
| **Math Calculator** | `= 25 * 1024` or `sqrt(144)` | Evaluates expression; press `Enter` to copy result to clipboard. |
| **Currency & Unit Converter** | `100 usd to try`, `1 btc in usd`, `50 km in miles`, `16 gb in mb` | Converts value; press `Enter` to copy to clipboard. |
| **Clipboard History** | `cb` or `clip` (e.g., `cb token`) | Searches recent copied items via `cliphist` / `wl-paste`. |
| **Process Killer** | `kill firefox` or `/kill app` | Lists matching running processes by PID; press `Enter` to terminate. |
| **System Actions** | `store`, `install`, `game`, `berp`, `settings`, `theme`, `lock`, `reboot`, `power` | Launches the corresponding BlazeOS system tool or power action. |

---

### 3.2. Hot-Swapping Desktop Shell Engines
SolarUI's Rust supervisor (`solar-core`) supports hot-swapping between three Wayland shell engines without logging out:
1. **Noctalia (`noctalia`):** Default native C++ Wayland layer-shell desktop bar and launcher.
2. **Caelestia (`caelestia`):** Fluid Quickshell/Qt6 desktop experience.
3. **end4-pC (`end4-pc`):** Feature-rich Material 3 desktop widget and panel suite.

```bash
# Switch shell engine live from terminal (or via Solar Settings -> Taskbar & Shell):
solar-shell switch noctalia
solar-shell switch caelestia
solar-shell switch end4-pc

# Toggle taskbar visibility:
solar-shell toggle-taskbar
```

---

## 4. Complete Keyboard Shortcuts Reference

| Shortcut | Action |
| :--- | :--- |
| `Super + Return` (or `Super + T`) | Launch **Alacritty** Terminal |
| `Super + Space` (or `Alt + Space`) | Toggle **SolarUI OmniBar** (Open / Close) |
| `Super + D` | Toggle **Noctalia** Application Launcher |
| `Super + H` | Launch **FireHub** Universal App Store |
| `Super + I` | Open **Solar System Settings** |
| `Super + G` | Launch **Solar GameZone** Gaming Center |
| `Super + Q` or `Super + Shift + Q` | Close Active Focused Window |
| `Super + Left / Right` (or `H / L`) | Focus Column Left / Right (Scrollable Tiling) |
| `Super + Up / Down` (or `J / K`) | Focus Window Up / Down in Column |
| `Super + Ctrl + Left / Right` | Move Active Window Left / Right |
| `Super + 1 .. 9` | Switch to Workspace `1` – `9` |
| `Super + Ctrl + 1 .. 9` | Move Window to Workspace `1` – `9` |
| `Super + R` | Cycle Preset Column Widths (33% -> 50% -> 66%) |
| `Super + F` | Maximize Column |
| `Super + Shift + F` | Fullscreen Window |
| `Super + Shift + V` | Toggle Floating / Tiling Mode |
| `Print` / `Ctrl + Print` / `Alt + Print` | Screenshot (Selection / Full Screen / Active Window) |
| `Super + L` | Lock Screen |
| `Super + Shift + E` | Exit Wayland Session |

---

## 5. Installing Applications: FireHub Store, Portadora (`.blz`) & Flathub

### 5.1. FireHub 1.9.0 Universal App Store (`Super + H` / `firehub`)
* **Native & Curated Catalog:** Click **Install** on any catalog app and choose **`BlazeOS Native (Portadora & Flathub)`**. FireHub automatically resolves and installs the package via Flathub or Portadora.
* **Live Flathub Universal Search:** Type any app name into FireHub's search bar (e.g., `LibreOffice`, `Obsidian`, `Blender`, `VLC`). Live results from `flathub.org/api/v2/search` appear directly below catalog matches with one-click installation.
* **Local Package Installer:** Open local `.blz`, `.flatpakref`, or `.AppImage` files directly inside FireHub to inspect metadata (`portadora info`) and install them graphically.

### 5.2. Portadora CLI (`portadora`)
```bash
# List all 124+ tracked system packages:
portadora list

# Show detailed metadata and file count for a package:
portadora info firehub

# Install a local .blz archive (use --force to overwrite conflicting files):
sudo portadora install ./package-1.0.0-1.x86_64.blz

# Verify SHA-256 and permission integrity of all managed files on disk:
portadora verify
```

---

## 6. Gaming Center: Solar GameZone, Proton-GE & NTSYNC

BlazeOS Native ships with **Linux 7.2.9** compiled with **`CONFIG_NTSYNC=y` (`/dev/ntsync`)**, **`CONFIG_SCHED_CLASS_EXT=y` (`sched_ext`)**, **1000 Hz tick rate**, and **Full Preemption (`CONFIG_PREEMPT=y`)**, plus on-demand **Variable Refresh Rate (VRR)** in Niri.

* **Built-in Proton-GE Manager:** Open `solar-shell gamezone` (`Super + G`) and click **"Proton-GE & NTSYNC"** to inspect `/dev/ntsync` status and download/extract the latest `GloriousEggroll/proton-ge-custom` release directly into `~/.steam/root/compatibilitytools.d`.
* **GameMode Performance Script (`blaze-gamemode`):**
  ```bash
  sudo blaze-gamemode on      # Sets CPU governor=performance, split_lock_mitigate=0, loads ntsync
  blaze-gamemode status       # Reports active governor, split_lock, /dev/ntsync, and sched_ext state
  sudo blaze-gamemode off     # Restores normal schedutil desktop profile
  ```

---

## 7. Security (Blaze Sentinel), USB Guard & BERP Recovery

* **Blaze Sentinel (`blaze-sentinel status`):** Verifies `7/7` security controls at runtime (AppArmor enforce/complain profiles, Kernel Lockdown `integrity`, Landlock, Yama `ptrace_scope=2`, `nftables` default-drop firewall, `16/16` KSPP sysctls, and `auditd` rules).
* **USB Storage Shield (Paranoid Mode):** Toggle `/etc/modprobe.d/blaze-usb-guard.conf` with one click in `Solar Settings -> System Health -> USB Storage Shield`.
* **BERP Recovery (`blaze-recovery`):** Run `blaze-recovery` from terminal/OmniBar (or select **BERP Core** in the Limine boot menu) to run diagnostics, verify/recover `portadora` packages, or reset desktop configurations.

---

## 8. Blaze Continuum — Stateful Session Teleportation

```bash
# Check kernel sched_ext, Checkpoint/Restore (CONFIG_CHECKPOINT_RESTORE=y), Niri IPC, and CPU topology:
blaze-continuum check

# Freeze a process + Niri window layout into a .blz-state capsule and restore it:
blaze-continuum freeze --pid <PID> --out /tmp/session.blz-state
blaze-continuum restore --capsule /tmp/session.blz-state

# Teleport a live session over LAN:
blaze-continuum listen --port 45821
blaze-continuum cast --target 192.168.1.50:45821
```

---

## 9. Troubleshooting & FAQ

* **Q: How do I close OmniBar once it is open?**
  * **A:** Press **`Esc`**, press **`Super + Space`** again (toggle), or click the **`✕ Esc`** button in the top-right corner of the OmniBar window.
* **Q: How do I switch keyboard layouts (e.g., Turkish Q vs. US English) live?**
  * **A:** Run `niri msg action switch-layout next` or change it inside `Solar Settings -> System & Power`.
* **Q: What if the desktop shell bar crashes or freezes?**
  * **A:** The `solar-core` Watchdog automatically restarts crashed shell engines within 3 seconds, or you can run `solar-shell repair` manually.
