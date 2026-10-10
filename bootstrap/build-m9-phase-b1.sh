#!/usr/bin/env bash
# ==============================================================================
# Blaze Universe — Milestone 9 Phase B.1: Solar Shell Core Native Builder
# Native Packaging of Rust solar-shell Supervisor & Niri State Controller
# ==============================================================================
set -euo pipefail

BLAZE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${BLAZE_ROOT}/build/m9_b1_solar_work"
PKGS_DIR="${BLAZE_ROOT}/build/packages"
BUILDER="${BLAZE_ROOT}/target/debug/blaze-builder"
SOLAR_SRC="/home/darkmorpheus/solarui/target/release"

mkdir -p "${WORK_DIR}" "${PKGS_DIR}"

SOLAR_DEST="${WORK_DIR}/solar-shell-dest"
rm -rf "${SOLAR_DEST}"
mkdir -p "${SOLAR_DEST}/usr/bin" \
         "${SOLAR_DEST}/usr/share/wayland-sessions" \
         "${SOLAR_DEST}/etc/solar" \
         "${SOLAR_DEST}/usr/libexec"

if [ -f "${SOLAR_SRC}/solar-shell" ] && [ -f "${SOLAR_SRC}/solar-core" ]; then
    echo "[BUILD] Copying compiled Rust ELF binaries for solar-shell, solar-core, and solar-session..."
    cp -a "${SOLAR_SRC}/solar-shell" "${SOLAR_DEST}/usr/bin/solar-shell"
    cp -a "${SOLAR_SRC}/solar-core" "${SOLAR_DEST}/usr/bin/solar-core"
    cp -a "${SOLAR_SRC}/solar-session" "${SOLAR_DEST}/usr/bin/solar-session"
    chmod 0755 "${SOLAR_DEST}/usr/bin/solar-shell" "${SOLAR_DEST}/usr/bin/solar-core" "${SOLAR_DEST}/usr/bin/solar-session"
else
    echo "[ERROR] Compiled SolarUI binaries not found at ${SOLAR_SRC}!"
    exit 1
fi

cat << 'EOF_SOLAR_DESKTOP' > "${SOLAR_DEST}/usr/share/wayland-sessions/solarui-niri.desktop"
[Desktop Entry]
Name=SolarUI (Niri Native Shell)
Comment=Scrollable-tiling Wayland desktop with SolarUI Rust Supervisor
Exec=/usr/bin/solar-session
Type=Application
DesktopNames=solarui:niri
EOF_SOLAR_DESKTOP

cat << 'EOF_SOLAR_CONF' > "${SOLAR_DEST}/etc/solar/config.toml"
# BlazeOS Native — SolarUI Rust Supervisor Configuration
[supervisor]
compositor = "niri"
auto_restart = true
max_retries = 3

[niri]
socket = "wayland-0"
event_stream = true
EOF_SOLAR_CONF

"${BUILDER}" "${BLAZE_ROOT}/recipes/core/solar-shell/recipe.toml"

echo "=== Milestone 9 Phase B.1 Solar Shell Package Built Successfully ==="
ls -lh "${PKGS_DIR}/solar-shell-"*
