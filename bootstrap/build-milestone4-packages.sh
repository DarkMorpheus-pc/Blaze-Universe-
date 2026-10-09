#!/usr/bin/env bash
# ==============================================================================
# Blaze Universe — Milestone 4 Networking Packages Builder
# ==============================================================================
set -euo pipefail

BLAZE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${BLAZE_ROOT}/build/m4_work"
PKGS_DIR="${BLAZE_ROOT}/build/packages"
BUILDER="${BLAZE_ROOT}/target/release/blaze-builder"
[ -x "${BUILDER}" ] || BUILDER="${BLAZE_ROOT}/target/debug/blaze-builder"

chmod -R u+w "${WORK_DIR}" 2>/dev/null || true
mkdir -p "${WORK_DIR}" "${PKGS_DIR}"

echo "=== Building Milestone 4 Networking Packages ==="
echo "Using builder: ${BUILDER}"

# ------------------------------------------------------------------------------
# 0. filesystem (0.1.0-2) with network and ssh users
# ------------------------------------------------------------------------------
echo "--- Packaging filesystem 0.1.0-2 ---"
"${BUILDER}" "${BLAZE_ROOT}/recipes/core/filesystem/recipe.toml" --output-dir "${PKGS_DIR}"

# ------------------------------------------------------------------------------
# 1. jansson (2.14)
# ------------------------------------------------------------------------------
echo "--- Packaging jansson 2.14 ---"
JANSSON_DEST="${WORK_DIR}/jansson-dest"
rm -rf "${JANSSON_DEST}"
mkdir -p "${JANSSON_DEST}/usr/lib/pkgconfig" "${JANSSON_DEST}/usr/include"
cp -a /usr/lib/libjansson.so* "${JANSSON_DEST}/usr/lib/"
cp -a /usr/lib/pkgconfig/jansson.pc "${JANSSON_DEST}/usr/lib/pkgconfig/" 2>/dev/null || true
cp -a /usr/include/jansson*.h "${JANSSON_DEST}/usr/include/" 2>/dev/null || true

cat << 'EOF' > "${WORK_DIR}/recipe-jansson.toml"
[package]
name = "jansson"
version = "2.14"
release = 1
architecture = "x86_64"
summary = "C library for encoding, decoding and manipulating JSON data"
license = "MIT"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://digip.org/jansson/"

[dependencies]
requires = ["glibc = 2.44"]
provides = [
    "jansson = 2.14",
    "lib:libjansson.so.4"
]

[triggers]
run_ldconfig = true

[build]
script = """
cp -a "$CURRENT_DIR/build/m4_work/jansson-dest/"* "$DESTDIR/"
"""
EOF
"${BUILDER}" "${WORK_DIR}/recipe-jansson.toml" --output-dir "${PKGS_DIR}"

# ------------------------------------------------------------------------------
# 2. libmnl (1.0.5)
# ------------------------------------------------------------------------------
echo "--- Packaging libmnl 1.0.5 ---"
LIBMNL_DEST="${WORK_DIR}/libmnl-dest"
rm -rf "${LIBMNL_DEST}"
mkdir -p "${LIBMNL_DEST}/usr/lib/pkgconfig" "${LIBMNL_DEST}/usr/include/libmnl"
cp -a /usr/lib/libmnl.so* "${LIBMNL_DEST}/usr/lib/"
cp -a /usr/lib/pkgconfig/libmnl.pc "${LIBMNL_DEST}/usr/lib/pkgconfig/" 2>/dev/null || true
cp -a /usr/include/libmnl/* "${LIBMNL_DEST}/usr/include/libmnl/" 2>/dev/null || true

cat << 'EOF' > "${WORK_DIR}/recipe-libmnl.toml"
[package]
name = "libmnl"
version = "1.0.5"
release = 1
architecture = "x86_64"
summary = "Minimalistic user-space library oriented to Netlink developers"
license = "LGPL-2.1-or-later"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://netfilter.org/projects/libmnl/"

[dependencies]
requires = ["glibc = 2.44"]
provides = [
    "libmnl = 1.0.5",
    "lib:libmnl.so.0"
]

[triggers]
run_ldconfig = true

[build]
script = """
cp -a "$CURRENT_DIR/build/m4_work/libmnl-dest/"* "$DESTDIR/"
"""
EOF
"${BUILDER}" "${WORK_DIR}/recipe-libmnl.toml" --output-dir "${PKGS_DIR}"

# ------------------------------------------------------------------------------
# 3. libnftnl (1.3.0)
# ------------------------------------------------------------------------------
echo "--- Packaging libnftnl 1.3.0 ---"
LIBNFTNL_DEST="${WORK_DIR}/libnftnl-dest"
rm -rf "${LIBNFTNL_DEST}"
mkdir -p "${LIBNFTNL_DEST}/usr/lib/pkgconfig" "${LIBNFTNL_DEST}/usr/include/libnftnl"
cp -a /usr/lib/libnftnl.so* "${LIBNFTNL_DEST}/usr/lib/"
cp -a /usr/lib/pkgconfig/libnftnl.pc "${LIBNFTNL_DEST}/usr/lib/pkgconfig/" 2>/dev/null || true
cp -a /usr/include/libnftnl/* "${LIBNFTNL_DEST}/usr/include/libnftnl/" 2>/dev/null || true

cat << 'EOF' > "${WORK_DIR}/recipe-libnftnl.toml"
[package]
name = "libnftnl"
version = "1.3.0"
release = 1
architecture = "x86_64"
summary = "Netfilter nftables userspace interface library"
license = "GPL-2.0-or-later"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://netfilter.org/projects/libnftnl/"

[dependencies]
requires = ["glibc = 2.44", "libmnl = 1.0.5"]
provides = [
    "libnftnl = 1.3.0",
    "lib:libnftnl.so.11"
]

[triggers]
run_ldconfig = true

[build]
script = """
cp -a "$CURRENT_DIR/build/m4_work/libnftnl-dest/"* "$DESTDIR/"
"""
EOF
"${BUILDER}" "${WORK_DIR}/recipe-libnftnl.toml" --output-dir "${PKGS_DIR}"

# ------------------------------------------------------------------------------
# 4. nftables (1.1.7)
# ------------------------------------------------------------------------------
echo "--- Packaging nftables 1.1.7 ---"
NFT_DEST="${WORK_DIR}/nftables-dest"
rm -rf "${NFT_DEST}"
mkdir -p "${NFT_DEST}/usr/bin" "${NFT_DEST}/usr/lib" "${NFT_DEST}/usr/lib/systemd/system/multi-user.target.wants" "${NFT_DEST}/etc"

cp -a /usr/bin/nft "${NFT_DEST}/usr/bin/"
cp -a /usr/lib/libnftables.so* "${NFT_DEST}/usr/lib/"

cat << 'EOF_NFT_CONF' > "${NFT_DEST}/etc/nftables.conf"
#!/usr/bin/nft -f

flush ruleset

table inet filter {
    chain input {
        type filter hook input priority filter; policy drop;

        # Accept loopback traffic
        iif "lo" accept

        # Accept established and related connections (stateful firewall)
        ct state established,related accept

        # Drop invalid connections
        ct state invalid drop

        # Accept ICMP and ICMPv6
        ip protocol icmp accept
        ip6 nexthdr icmpv6 accept
    }

    chain forward {
        type filter hook forward priority filter; policy drop;
    }

    chain output {
        type filter hook output priority filter; policy accept;
    }
}
EOF_NFT_CONF
chmod 0644 "${NFT_DEST}/etc/nftables.conf"

cat << 'EOF_NFT_SVC' > "${NFT_DEST}/usr/lib/systemd/system/nftables.service"
[Unit]
Description=Netfilter Tables (Blaze Sentinel Base)
Documentation=man:nft(8)
Wants=network-pre.target
Before=network-pre.target shutdown.target
Conflicts=shutdown.target
DefaultDependencies=no

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/bin/nft -f /etc/nftables.conf
ExecStop=/usr/bin/nft flush ruleset

[Install]
WantedBy=multi-user.target
EOF_NFT_SVC

ln -sf ../nftables.service "${NFT_DEST}/usr/lib/systemd/system/multi-user.target.wants/nftables.service"

cat << 'EOF' > "${WORK_DIR}/recipe-nftables.toml"
[package]
name = "nftables"
version = "1.1.7"
release = 1
architecture = "x86_64"
summary = "Netfilter project packet filtering utility (Blaze Sentinel Foundation)"
license = "GPL-2.0-only"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://netfilter.org/projects/nftables/"

[dependencies]
requires = ["glibc = 2.44", "libmnl = 1.0.5", "libnftnl = 1.3.0", "jansson = 2.14"]
provides = [
    "nftables = 1.1.7",
    "cmd:nft",
    "lib:libnftables.so.1"
]

[triggers]
run_ldconfig = true

[build]
script = """
cp -a "$CURRENT_DIR/build/m4_work/nftables-dest/"* "$DESTDIR/"
"""
EOF
"${BUILDER}" "${WORK_DIR}/recipe-nftables.toml" --output-dir "${PKGS_DIR}"

# ------------------------------------------------------------------------------
# 5. iproute2 (7.2.0)
# ------------------------------------------------------------------------------
echo "--- Packaging iproute2 7.2.0 ---"
IPROUTE_DEST="${WORK_DIR}/iproute2-dest"
rm -rf "${IPROUTE_DEST}"
mkdir -p "${IPROUTE_DEST}/usr/bin" "${IPROUTE_DEST}/etc/iproute2"

for b in ip ss bridge rtmon tc nstat routel; do
    [ -f "/usr/bin/$b" ] && cp -a "/usr/bin/$b" "${IPROUTE_DEST}/usr/bin/"
done
if [ -d "/etc/iproute2" ]; then
    cp -a /etc/iproute2/* "${IPROUTE_DEST}/etc/iproute2/" 2>/dev/null || true
fi

cat << 'EOF' > "${WORK_DIR}/recipe-iproute2.toml"
[package]
name = "iproute2"
version = "7.2.0"
release = 1
architecture = "x86_64"
summary = "IP routing and network configuration utilities"
license = "GPL-2.0-only"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://wiki.linuxfoundation.org/networking/iproute2"

[dependencies]
requires = ["glibc = 2.44", "libmnl = 1.0.5"]
provides = [
    "iproute2 = 7.2.0",
    "cmd:ip",
    "cmd:ss",
    "cmd:bridge"
]

[build]
script = """
cp -a "$CURRENT_DIR/build/m4_work/iproute2-dest/"* "$DESTDIR/"
"""
EOF
"${BUILDER}" "${WORK_DIR}/recipe-iproute2.toml" --output-dir "${PKGS_DIR}"

# ------------------------------------------------------------------------------
# 5b. iputils (20240905)
# ------------------------------------------------------------------------------
echo "--- Packaging iputils 20240905 ---"
IPUTILS_DEST="${WORK_DIR}/iputils-dest"
rm -rf "${IPUTILS_DEST}"
mkdir -p "${IPUTILS_DEST}/usr/bin"
cp -a /usr/bin/ping "${IPUTILS_DEST}/usr/bin/"
[ -f /usr/bin/tracepath ] && cp -a /usr/bin/tracepath "${IPUTILS_DEST}/usr/bin/"

cat << 'EOF' > "${WORK_DIR}/recipe-iputils.toml"
[package]
name = "iputils"
version = "20240905"
release = 1
architecture = "x86_64"
summary = "Network monitoring tools including ping and tracepath"
license = "BSD-3-Clause"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://github.com/iputils/iputils"

[dependencies]
requires = ["glibc = 2.44"]
provides = [
    "iputils = 20240905",
    "cmd:ping",
    "cmd:tracepath"
]

[build]
script = """
cp -a "$CURRENT_DIR/build/m4_work/iputils-dest/"* "$DESTDIR/"
"""
EOF
"${BUILDER}" "${WORK_DIR}/recipe-iputils.toml" --output-dir "${PKGS_DIR}"

# ------------------------------------------------------------------------------
# 6. ca-certificates (2026.09)
# ------------------------------------------------------------------------------
echo "--- Packaging ca-certificates 2026.09 ---"
CACERTS_DEST="${WORK_DIR}/ca-certificates-dest"
chmod -R u+w "${CACERTS_DEST}" 2>/dev/null || true
rm -rf "${CACERTS_DEST}"
mkdir -p "${CACERTS_DEST}/etc/ca-certificates/extracted"

# Copy Mozilla master extracted bundles
cp -a /etc/ca-certificates/extracted/* "${CACERTS_DEST}/etc/ca-certificates/extracted/"
chmod -R u+w "${CACERTS_DEST}"
if [ -d /usr/share/ca-certificates ]; then
    mkdir -p "${CACERTS_DEST}/usr/share/ca-certificates"
    cp -a /usr/share/ca-certificates/* "${CACERTS_DEST}/usr/share/ca-certificates/" 2>/dev/null || true
fi

cat << 'EOF' > "${WORK_DIR}/recipe-ca-certificates.toml"
[package]
name = "ca-certificates"
version = "2026.09"
release = 1
architecture = "x86_64"
summary = "Common CA certificates from Mozilla NSS"
license = "MPL-2.0"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://curl.se/docs/caextract.html"

[dependencies]
provides = ["ca-certificates = 2026.09"]

[build]
script = """
cp -a "$CURRENT_DIR/build/m4_work/ca-certificates-dest/"* "$DESTDIR/"
chmod -R u+w "$DESTDIR"
"""
EOF
"${BUILDER}" "${WORK_DIR}/recipe-ca-certificates.toml" --output-dir "${PKGS_DIR}"

# ------------------------------------------------------------------------------
# 7. curl (8.22.0)
# ------------------------------------------------------------------------------
echo "--- Packaging curl 8.22.0 ---"
CURL_DEST="${WORK_DIR}/curl-dest"
rm -rf "${CURL_DEST}"
mkdir -p "${CURL_DEST}/usr/bin" "${CURL_DEST}/usr/lib/pkgconfig" "${CURL_DEST}/usr/include/curl"

cp -a /usr/bin/curl "${CURL_DEST}/usr/bin/"
# Note: libcurl.so is provided by rust-runtime-deps
cp -a /usr/lib/pkgconfig/libcurl.pc "${CURL_DEST}/usr/lib/pkgconfig/" 2>/dev/null || true
cp -a /usr/include/curl/* "${CURL_DEST}/usr/include/curl/" 2>/dev/null || true

cat << 'EOF' > "${WORK_DIR}/recipe-curl.toml"
[package]
name = "curl"
version = "8.22.0"
release = 1
architecture = "x86_64"
summary = "Command line tool and library for transferring data with URLs"
license = "curl"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://curl.se/"

[dependencies]
requires = ["glibc = 2.44", "ca-certificates = 2026.09"]
provides = [
    "curl = 8.22.0",
    "cmd:curl",
    "lib:libcurl.so.4"
]

[triggers]
run_ldconfig = true

[build]
script = """
cp -a "$CURRENT_DIR/build/m4_work/curl-dest/"* "$DESTDIR/"
"""
EOF
"${BUILDER}" "${WORK_DIR}/recipe-curl.toml" --output-dir "${PKGS_DIR}"

# ------------------------------------------------------------------------------
# 8. openssh (10.5p1)
# ------------------------------------------------------------------------------
echo "--- Packaging openssh 10.5p1 ---"
OPENSSH_DEST="${WORK_DIR}/openssh-dest"
rm -rf "${OPENSSH_DEST}"
mkdir -p "${OPENSSH_DEST}/usr/bin" \
         "${OPENSSH_DEST}/usr/lib/ssh" \
         "${OPENSSH_DEST}/usr/lib/systemd/system" \
         "${OPENSSH_DEST}/usr/lib/sysusers.d" \
         "${OPENSSH_DEST}/etc/ssh" \
         "${OPENSSH_DEST}/etc/pam.d" \
         "${OPENSSH_DEST}/var/empty" \
         "${OPENSSH_DEST}/usr/share/empty.sshd"

for b in ssh scp sftp ssh-add ssh-agent ssh-keygen ssh-keyscan; do
    [ -f "/usr/bin/$b" ] && cp -a "/usr/bin/$b" "${OPENSSH_DEST}/usr/bin/"
done
[ -f "/usr/bin/sshd" ] && cp -a "/usr/bin/sshd" "${OPENSSH_DEST}/usr/bin/"
for helper in sftp-server sshd-auth sshd-session ssh-pkcs11-helper ssh-sk-helper; do
    [ -f "/usr/lib/ssh/$helper" ] && cp -a "/usr/lib/ssh/$helper" "${OPENSSH_DEST}/usr/lib/ssh/"
done

# Pre-generate standard host keys
ssh-keygen -q -N "" -t ed25519 -f "${OPENSSH_DEST}/etc/ssh/ssh_host_ed25519_key"
ssh-keygen -q -N "" -t rsa -b 2048 -f "${OPENSSH_DEST}/etc/ssh/ssh_host_rsa_key"
ssh-keygen -q -N "" -t ecdsa -b 256 -f "${OPENSSH_DEST}/etc/ssh/ssh_host_ecdsa_key"
chmod 0600 "${OPENSSH_DEST}/etc/ssh"/ssh_host_*_key
chmod 0644 "${OPENSSH_DEST}/etc/ssh"/ssh_host_*_key.pub

# PAM configuration for sshd
cat << 'EOF_PAM_SSHD' > "${OPENSSH_DEST}/etc/pam.d/sshd"
#%PAM-1.0
auth      include   system-auth
account   include   system-auth
password  include   system-auth
session   include   system-auth
EOF_PAM_SSHD

cat << 'EOF_SSHD_CFG' > "${OPENSSH_DEST}/etc/ssh/sshd_config"
# BlazeOS Native OpenSSH Server Configuration
Port 22
AddressFamily any
ListenAddress 0.0.0.0
ListenAddress ::

PermitRootLogin prohibit-password
PubkeyAuthentication yes
AuthorizedKeysFile .ssh/authorized_keys

PasswordAuthentication yes
PermitEmptyPasswords no
UsePAM yes

X11Forwarding no
PrintMotd no
AcceptEnv LANG LC_*
Subsystem sftp /usr/lib/ssh/sftp-server
EOF_SSHD_CFG

cat << 'EOF_SSH_CFG' > "${OPENSSH_DEST}/etc/ssh/ssh_config"
# BlazeOS Native OpenSSH Client Configuration
Host *
    SendEnv LANG LC_*
    HashKnownHosts yes
EOF_SSH_CFG

cat << 'EOF_SSHD_SVC' > "${OPENSSH_DEST}/usr/lib/systemd/system/sshd.service"
[Unit]
Description=OpenSSH Server Daemon
Documentation=man:sshd(8) man:sshd_config(5)
After=network.target

[Service]
Type=exec
ExecStartPre=-/usr/bin/ssh-keygen -A
ExecStart=/usr/bin/sshd -D
ExecReload=/bin/kill -HUP $MAINPID
KillMode=process
Restart=on-failure
RestartSec=42s

[Install]
WantedBy=multi-user.target
EOF_SSHD_SVC
# NOTE: NOT symlinked into multi-user.target.wants! SSH is DISABLED by default.

cat << 'EOF_SSH_SYSUSERS' > "${OPENSSH_DEST}/usr/lib/sysusers.d/openssh.conf"
u! sshd - "Privilege-separated SSH" /usr/share/empty.sshd /usr/bin/nologin
EOF_SSH_SYSUSERS

cat << 'EOF' > "${WORK_DIR}/recipe-openssh.toml"
[package]
name = "openssh"
version = "10.5p1"
release = 3
architecture = "x86_64"
summary = "Premier connectivity tool for remote login with SSH protocol"
license = "SSH"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://www.openssh.com/"

[dependencies]
requires = ["glibc = 2.44"]
provides = [
    "openssh = 10.5p1",
    "cmd:ssh",
    "cmd:sshd",
    "cmd:scp",
    "cmd:sftp",
    "cmd:ssh-keygen"
]

[build]
script = """
cp -a "$CURRENT_DIR/build/m4_work/openssh-dest/"* "$DESTDIR/"
chmod 0755 "$DESTDIR/var/empty"
chmod 0755 "$DESTDIR/usr/share/empty.sshd"
chmod 0755 "$DESTDIR/usr/lib/ssh"/*
[ -f "$DESTDIR/usr/lib/ssh/ssh-keysign" ] && chmod 4711 "$DESTDIR/usr/lib/ssh/ssh-keysign"
chmod 0755 "$DESTDIR/etc/ssh"
chmod 0600 "$DESTDIR/etc/ssh"/ssh_host_*_key
chmod 0644 "$DESTDIR/etc/ssh"/ssh_host_*_key.pub
"""
EOF
"${BUILDER}" "${WORK_DIR}/recipe-openssh.toml" --output-dir "${PKGS_DIR}"

# ------------------------------------------------------------------------------
# 9. blaze-network-config (0.1.0)
# ------------------------------------------------------------------------------
echo "--- Packaging blaze-network-config 0.1.0-2 ---"
BLZNET_DEST="${WORK_DIR}/blaze-network-config-dest"
rm -rf "${BLZNET_DEST}"
mkdir -p "${BLZNET_DEST}/usr/bin" \
         "${BLZNET_DEST}/usr/lib/systemd/network" \
         "${BLZNET_DEST}/usr/lib/systemd/system" \
         "${BLZNET_DEST}/usr/lib/systemd/system/multi-user.target.wants" \
         "${BLZNET_DEST}/usr/lib/systemd/system-preset" \
         "${BLZNET_DEST}/usr/lib/sysusers.d" \
         "${BLZNET_DEST}/etc"

# System presets
cat << 'EOF_PRESET_DEF' > "${BLZNET_DEST}/usr/lib/systemd/system-preset/99-default.preset"
disable *
EOF_PRESET_DEF

cat << 'EOF_PRESET_BLZ' > "${BLZNET_DEST}/usr/lib/systemd/system-preset/50-blaze-network.preset"
enable systemd-networkd.service
enable systemd-resolved.service
enable nftables.service
disable sshd.service
EOF_PRESET_BLZ

# Command line utilities
cp -a /usr/bin/networkctl "${BLZNET_DEST}/usr/bin/"
cp -a /usr/bin/resolvectl "${BLZNET_DEST}/usr/bin/"

# Generic DHCPv4/v6 matching all ethernet and virtio network interfaces
cat << 'EOF_NET' > "${BLZNET_DEST}/usr/lib/systemd/network/80-dhcp.network"
[Match]
Name=en* eth* virt*

[Network]
DHCP=yes
IPv6AcceptRA=yes

[DHCPv4]
RouteMetric=10
UseDNS=yes
UseDomains=yes

[DHCPv6]
UseDNS=yes
EOF_NET

# Systemd units & sockets for networkd and resolved
cp -a /usr/lib/systemd/system/systemd-networkd* "${BLZNET_DEST}/usr/lib/systemd/system/"
cp -a /usr/lib/systemd/system/systemd-resolved* "${BLZNET_DEST}/usr/lib/systemd/system/"

# Sysusers configs
cp -a /usr/lib/sysusers.d/systemd-network.conf "${BLZNET_DEST}/usr/lib/sysusers.d/"
cp -a /usr/lib/sysusers.d/systemd-resolve.conf "${BLZNET_DEST}/usr/lib/sysusers.d/"

# Enable networkd and resolved by default
ln -sf ../systemd-networkd.service "${BLZNET_DEST}/usr/lib/systemd/system/multi-user.target.wants/systemd-networkd.service"
ln -sf ../systemd-resolved.service "${BLZNET_DEST}/usr/lib/systemd/system/multi-user.target.wants/systemd-resolved.service"

# Standard stub resolver symlink
ln -sf /run/systemd/resolve/stub-resolv.conf "${BLZNET_DEST}/etc/resolv.conf"

cat << 'EOF' > "${WORK_DIR}/recipe-blaze-network-config.toml"
[package]
name = "blaze-network-config"
version = "0.1.0"
release = 2
architecture = "x86_64"
summary = "Default network configuration and service enablement for BlazeOS"
license = "MIT"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://blazeos.org"

[dependencies]
provides = [
    "blaze-network-config = 0.1.0",
    "cmd:networkctl",
    "cmd:resolvectl"
]

[build]
script = """
cp -a "$CURRENT_DIR/build/m4_work/blaze-network-config-dest/"* "$DESTDIR/"
"""
EOF
"${BUILDER}" "${WORK_DIR}/recipe-blaze-network-config.toml" --output-dir "${PKGS_DIR}"

echo "=== All Milestone 4 Packages Built Successfully ==="
ls -lh "${PKGS_DIR}"/
