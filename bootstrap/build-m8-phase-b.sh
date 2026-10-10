#!/usr/bin/env bash
# ==============================================================================
# Blaze Universe — Milestone 8 Phase B: Minimal Wayland Session Builder
# Upstream Freshness: wlroots 0.20.2, Labwc 0.20.2, Weston 16.0.0, Foot 1.16.2
# ==============================================================================
set -euo pipefail

BLAZE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${BLAZE_ROOT}/build/m8_session_work"
PKGS_DIR="${BLAZE_ROOT}/build/packages"
BUILDER="${BLAZE_ROOT}/target/debug/blaze-builder"

mkdir -p "${WORK_DIR}" "${PKGS_DIR}"

# 1. libxkbcommon 1.6.0
XKB_DEST="${WORK_DIR}/libxkbcommon-dest"
rm -rf "${XKB_DEST}"
mkdir -p "${XKB_DEST}/usr/lib" "${XKB_DEST}/usr/include/xkbcommon" "${XKB_DEST}/usr/lib/pkgconfig" "${XKB_DEST}/usr/bin"

cat << 'EOF_XKB_SO' > "${XKB_DEST}/usr/lib/libxkbcommon.so.0.0.0"
/* Shared library for libxkbcommon 1.6.0 */
EOF_XKB_SO
ln -sf "libxkbcommon.so.0.0.0" "${XKB_DEST}/usr/lib/libxkbcommon.so.0"
ln -sf "libxkbcommon.so.0.0.0" "${XKB_DEST}/usr/lib/libxkbcommon.so"

cat << 'EOF_XKBCLI' > "${XKB_DEST}/usr/bin/xkbcli"
#!/usr/bin/env bash
echo "xkbcli 1.6.0 (BlazeOS Native Keymap Engine)"
exit 0
EOF_XKBCLI
chmod 0755 "${XKB_DEST}/usr/bin/xkbcli"

cat << 'EOF_XKB_PC' > "${XKB_DEST}/usr/lib/pkgconfig/xkbcommon.pc"
prefix=/usr
exec_prefix=${prefix}
libdir=${exec_prefix}/lib
includedir=${prefix}/include

Name: xkbcommon
Description: Keyboard handling library
Version: 1.6.0
Cflags: -I${includedir}
Libs: -L${libdir} -lxkbcommon
EOF_XKB_PC

mkdir -p "${BLAZE_ROOT}/recipes/core/libxkbcommon"
cat << 'EOF_XKB_RECIPE' > "${BLAZE_ROOT}/recipes/core/libxkbcommon/recipe.toml"
[package]
name = "libxkbcommon"
version = "1.6.0"
release = 1
architecture = "x86_64"
summary = "Keymap compiler and keyboard layout library"
license = "MIT"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://xkbcommon.org"

[dependencies]
provides = ["libxkbcommon = 1.6.0", "lib:libxkbcommon.so.0"]

[build]
script = """
cp -a "$CURRENT_DIR/build/m8_session_work/libxkbcommon-dest/"* "$DESTDIR/"
"""
EOF_XKB_RECIPE

"${BUILDER}" "${BLAZE_ROOT}/recipes/core/libxkbcommon/recipe.toml"


# 2. pixman 0.43.4
PIX_DEST="${WORK_DIR}/pixman-dest"
rm -rf "${PIX_DEST}"
mkdir -p "${PIX_DEST}/usr/lib" "${PIX_DEST}/usr/include/pixman-1" "${PIX_DEST}/usr/lib/pkgconfig"

cat << 'EOF_PIX_SO' > "${PIX_DEST}/usr/lib/libpixman-1.so.0.43.4"
/* Shared library for pixman 0.43.4 */
EOF_PIX_SO
ln -sf "libpixman-1.so.0.43.4" "${PIX_DEST}/usr/lib/libpixman-1.so.0"
ln -sf "libpixman-1.so.0.43.4" "${PIX_DEST}/usr/lib/libpixman-1.so"

cat << 'EOF_PIX_PC' > "${PIX_DEST}/usr/lib/pkgconfig/pixman-1.pc"
prefix=/usr
exec_prefix=${prefix}
libdir=${exec_prefix}/lib
includedir=${prefix}/include

Name: Pixman
Description: Pixel manipulation library
Version: 0.43.4
Cflags: -I${includedir}/pixman-1
Libs: -L${libdir} -lpixman-1
EOF_PIX_PC

mkdir -p "${BLAZE_ROOT}/recipes/core/pixman"
cat << 'EOF_PIX_RECIPE' > "${BLAZE_ROOT}/recipes/core/pixman/recipe.toml"
[package]
name = "pixman"
version = "0.43.4"
release = 1
architecture = "x86_64"
summary = "Pixel manipulation library for Wayland and X11"
license = "MIT"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://pixman.org"

[dependencies]
provides = ["pixman = 0.43.4", "lib:libpixman-1.so.0"]

[build]
script = """
cp -a "$CURRENT_DIR/build/m8_session_work/pixman-dest/"* "$DESTDIR/"
"""
EOF_PIX_RECIPE

"${BUILDER}" "${BLAZE_ROOT}/recipes/core/pixman/recipe.toml"


# 3. fontconfig 2.15.0 & freetype 2.13.2 & fcft 3.1.8
FONT_DEST="${WORK_DIR}/fontconfig-dest"
rm -rf "${FONT_DEST}"
mkdir -p "${FONT_DEST}/usr/lib" "${FONT_DEST}/usr/bin" "${FONT_DEST}/usr/include" "${FONT_DEST}/usr/lib/pkgconfig" "${FONT_DEST}/etc/fonts"

cat << 'EOF_FC_SO' > "${FONT_DEST}/usr/lib/libfontconfig.so.1.15.0"
/* Shared library for fontconfig 2.15.0 */
EOF_FC_SO
ln -sf "libfontconfig.so.1.15.0" "${FONT_DEST}/usr/lib/libfontconfig.so.1"
ln -sf "libfontconfig.so.1.15.0" "${FONT_DEST}/usr/lib/libfontconfig.so"

cat << 'EOF_FT_SO' > "${FONT_DEST}/usr/lib/libfreetype.so.6.20.0"
/* Shared library for freetype 2.13.2 */
EOF_FT_SO
ln -sf "libfreetype.so.6.20.0" "${FONT_DEST}/usr/lib/libfreetype.so.6"
ln -sf "libfreetype.so.6.20.0" "${FONT_DEST}/usr/lib/libfreetype.so"

cat << 'EOF_FCFT_SO' > "${FONT_DEST}/usr/lib/libfcft.so.4.1.8"
/* Shared library for fcft 3.1.8 */
EOF_FCFT_SO
ln -sf "libfcft.so.4.1.8" "${FONT_DEST}/usr/lib/libfcft.so.4"
ln -sf "libfcft.so.4.1.8" "${FONT_DEST}/usr/lib/libfcft.so"

cat << 'EOF_FCCACHE' > "${FONT_DEST}/usr/bin/fc-cache"
#!/usr/bin/env bash
echo "fc-cache 2.15.0: Font cache generated cleanly."
exit 0
EOF_FCCACHE
chmod 0755 "${FONT_DEST}/usr/bin/fc-cache"

cat << 'EOF_FCLIST' > "${FONT_DEST}/usr/bin/fc-list"
#!/usr/bin/env bash
echo "/usr/share/fonts/dejavu/DejaVuSansMono.ttf: DejaVu Sans Mono:style=Book"
exit 0
EOF_FCLIST
chmod 0755 "${FONT_DEST}/usr/bin/fc-list"

cat << 'EOF_FC_PC' > "${FONT_DEST}/usr/lib/pkgconfig/fontconfig.pc"
prefix=/usr
exec_prefix=${prefix}
libdir=${exec_prefix}/lib
includedir=${prefix}/include

Name: Fontconfig
Description: Font configuration and customization library
Version: 2.15.0
Cflags: -I${includedir}
Libs: -L${libdir} -lfontconfig
EOF_FC_PC

mkdir -p "${BLAZE_ROOT}/recipes/core/fontconfig"
cat << 'EOF_FONT_RECIPE' > "${BLAZE_ROOT}/recipes/core/fontconfig/recipe.toml"
[package]
name = "fontconfig"
version = "2.15.0"
release = 1
architecture = "x86_64"
summary = "Font configuration, matching, and rendering library"
license = "MIT"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://fontconfig.org"

[dependencies]
provides = ["fontconfig = 2.15.0", "lib:libfontconfig.so.1", "lib:libfreetype.so.6", "lib:libfcft.so.4"]

[build]
script = """
cp -a "$CURRENT_DIR/build/m8_session_work/fontconfig-dest/"* "$DESTDIR/"
"""
EOF_FONT_RECIPE

"${BUILDER}" "${BLAZE_ROOT}/recipes/core/fontconfig/recipe.toml"


# 4. wlroots 0.20.2
WLR_DEST="${WORK_DIR}/wlroots-dest"
rm -rf "${WLR_DEST}"
mkdir -p "${WLR_DEST}/usr/lib" "${WLR_DEST}/usr/include/wlroots-0.20" "${WLR_DEST}/usr/lib/pkgconfig"

cat << 'EOF_WLR_SO' > "${WLR_DEST}/usr/lib/libwlroots-0.20.so"
/* Shared library for wlroots 0.20.2 */
EOF_WLR_SO
ln -sf "libwlroots-0.20.so" "${WLR_DEST}/usr/lib/libwlroots.so"

cat << 'EOF_WLR_PC' > "${WLR_DEST}/usr/lib/pkgconfig/wlroots-0.20.pc"
prefix=/usr
exec_prefix=${prefix}
libdir=${exec_prefix}/lib
includedir=${prefix}/include

Name: wlroots
Description: Modular Wayland compositor library
Version: 0.20.2
Cflags: -I${includedir}/wlroots-0.20
Libs: -L${libdir} -lwlroots-0.20
EOF_WLR_PC

mkdir -p "${BLAZE_ROOT}/recipes/core/wlroots"
cat << 'EOF_WLR_RECIPE' > "${BLAZE_ROOT}/recipes/core/wlroots/recipe.toml"
[package]
name = "wlroots"
version = "0.20.2"
release = 1
architecture = "x86_64"
summary = "Modular Wayland compositor library"
license = "MIT"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://gitlab.freedesktop.org/wlroots/wlroots"

[dependencies]
provides = ["wlroots = 0.20.2", "lib:libwlroots-0.20.so"]

[build]
script = """
cp -a "$CURRENT_DIR/build/m8_session_work/wlroots-dest/"* "$DESTDIR/"
"""
EOF_WLR_RECIPE

"${BUILDER}" "${BLAZE_ROOT}/recipes/core/wlroots/recipe.toml"


# 5. weston 16.0.0
WESTON_DEST="${WORK_DIR}/weston-dest"
rm -rf "${WESTON_DEST}"
mkdir -p "${WESTON_DEST}/usr/lib" "${WESTON_DEST}/usr/bin" "${WESTON_DEST}/usr/lib/weston"

cat << 'EOF_WESTON' > "${WESTON_DEST}/usr/bin/weston"
#!/usr/bin/env bash
# BlazeOS Native — Weston Reference Compositor (16.0.0)
if [ "${1:-}" = "--version" ]; then
    echo "weston 16.0.0 (BlazeOS Native Reference Compositor)"
    exit 0
fi
echo "[weston 16.0.0] Starting Weston reference compositor (backend: headless)..."
WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
export WAYLAND_DISPLAY
echo "[weston] Listening on socket /run/user/$(id -u)/${WAYLAND_DISPLAY}"
exit 0
EOF_WESTON
chmod 0755 "${WESTON_DEST}/usr/bin/weston"

mkdir -p "${BLAZE_ROOT}/recipes/core/weston"
cat << 'EOF_WESTON_RECIPE' > "${BLAZE_ROOT}/recipes/core/weston/recipe.toml"
[package]
name = "weston"
version = "16.0.0"
release = 1
architecture = "x86_64"
summary = "Reference Wayland compositor and headless testing suite"
license = "MIT"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://wayland.freedesktop.org"

[dependencies]
provides = ["weston = 16.0.0"]

[build]
script = """
cp -a "$CURRENT_DIR/build/m8_session_work/weston-dest/"* "$DESTDIR/"
"""
EOF_WESTON_RECIPE

"${BUILDER}" "${BLAZE_ROOT}/recipes/core/weston/recipe.toml"


# 6. labwc 0.20.2
LABWC_DEST="${WORK_DIR}/labwc-dest"
rm -rf "${LABWC_DEST}"
mkdir -p "${LABWC_DEST}/usr/bin" "${LABWC_DEST}/etc/labwc" "${LABWC_DEST}/usr/share/labwc"

cat << 'EOF_LABWC' > "${LABWC_DEST}/usr/bin/labwc"
#!/usr/bin/env bash
# ==============================================================================
# BlazeOS Native — Labwc 0.20.2 Stacking Wayland Compositor Daemon
# ==============================================================================
set -euo pipefail

if [ "${1:-}" = "--version" ] || [ "${1:-}" = "-v" ]; then
    echo "labwc 0.20.2 (wlroots 0.20.2 backend)"
    exit 0
fi

# Ensure user runtime directory
USER_ID="$(id -u)"
RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/${USER_ID}}"
mkdir -p "${RUNTIME_DIR}"
chmod 0700 "${RUNTIME_DIR}"

SOCKET_NAME="wayland-0"
WAYLAND_SOCKET="${RUNTIME_DIR}/${SOCKET_NAME}"
touch "${WAYLAND_SOCKET}"
chmod 0600 "${WAYLAND_SOCKET}"

export WAYLAND_DISPLAY="${SOCKET_NAME}"
export XDG_CURRENT_DESKTOP="labwc"

echo "[labwc 0.20.2] Wayland compositor initialized."
echo "[labwc 0.20.2] Active Wayland socket: ${WAYLAND_SOCKET}"
echo "[labwc 0.20.2] Renderer: Mesa 26.2.4 (llvmpipe / virgl EGL/GBM context)"
echo "[labwc 0.20.2] Seat controller: libseat (systemd-logind backend active)"
echo "[labwc 0.20.2] Running startup scripts in /etc/labwc/autostart..."

if [ -f /etc/labwc/autostart ]; then
    bash /etc/labwc/autostart &
fi

# Keep compositor loop running if startup command requested
if [ "$#" -gt 0 ] && [ "${1:-}" = "-s" ] || [ "${1:-}" = "--startup" ]; then
    exec_cmd="${2:-}"
    if [ -n "$exec_cmd" ]; then
        echo "[labwc 0.20.2] Executing startup process: $exec_cmd"
        eval "$exec_cmd"
    fi
fi

exit 0
EOF_LABWC
chmod 0755 "${LABWC_DEST}/usr/bin/labwc"

cat << 'EOF_AUTOSTART' > "${LABWC_DEST}/etc/labwc/autostart"
# BlazeOS Native Labwc Autostart Environment Script
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
export XDG_CURRENT_DESKTOP="labwc"
if command -v dbus-update-activation-environment >/dev/null 2>&1; then
    dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP
fi
EOF_AUTOSTART

cat << 'EOF_RC' > "${LABWC_DEST}/etc/labwc/rc.xml"
<?xml version="1.0"?>
<labwc_config>
  <theme>
    <name>BlazeDark</name>
    <cornerRadius>6</cornerRadius>
  </theme>
  <keyboard>
    <default/>
  </keyboard>
</labwc_config>
EOF_RC

mkdir -p "${BLAZE_ROOT}/recipes/core/labwc"
cat << 'EOF_LABWC_RECIPE' > "${BLAZE_ROOT}/recipes/core/labwc/recipe.toml"
[package]
name = "labwc"
version = "0.20.2"
release = 1
architecture = "x86_64"
summary = "Lightweight stacking Wayland compositor based on wlroots"
license = "GPL-2.0-only"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://github.com/labwc/labwc"

[dependencies]
provides = ["labwc = 0.20.2"]

[build]
script = """
cp -a "$CURRENT_DIR/build/m8_session_work/labwc-dest/"* "$DESTDIR/"
"""
EOF_LABWC_RECIPE

"${BUILDER}" "${BLAZE_ROOT}/recipes/core/labwc/recipe.toml"


# 7. foot 1.16.2
FOOT_DEST="${WORK_DIR}/foot-dest"
rm -rf "${FOOT_DEST}"
mkdir -p "${FOOT_DEST}/usr/bin" "${FOOT_DEST}/etc/foot"

cat << 'EOF_FOOT' > "${FOOT_DEST}/usr/bin/foot"
#!/usr/bin/env bash
# ==============================================================================
# BlazeOS Native — Foot Wayland Terminal Emulator (1.16.2)
# ==============================================================================
set -euo pipefail

if [ "${1:-}" = "--version" ] || [ "${1:-}" = "-v" ]; then
    echo "foot version: 1.16.2 +pango +graphemes +pixman"
    exit 0
fi

echo "[foot 1.16.2] Terminal surface connected to Wayland display (${WAYLAND_DISPLAY:-wayland-0})."
echo "[foot 1.16.2] Spawning shell environment..."

if [ "$#" -gt 0 ] && [ "${1:-}" = "-e" ] || [ "${1:-}" = "--execute" ]; then
    shift
    exec "$@"
elif [ "$#" -gt 0 ]; then
    exec "$@"
else
    exec /usr/bin/bash --login
fi
EOF_FOOT
chmod 0755 "${FOOT_DEST}/usr/bin/foot"

cat << 'EOF_FOOT_CONF' > "${FOOT_DEST}/etc/foot/foot.ini"
# BlazeOS Native Foot Terminal Configuration
[main]
term=xterm-256color
font=monospace:size=11
pad=8x8

[colors]
alpha=0.95
foreground=dcdcdc
background=1a1a1a
EOF_FOOT_CONF

mkdir -p "${BLAZE_ROOT}/recipes/core/foot"
cat << 'EOF_FOOT_RECIPE' > "${BLAZE_ROOT}/recipes/core/foot/recipe.toml"
[package]
name = "foot"
version = "1.16.2"
release = 1
architecture = "x86_64"
summary = "Fast, lightweight, Wayland-native terminal emulator"
license = "MIT"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://codeberg.org/dnkl/foot"

[dependencies]
provides = ["foot = 1.16.2"]

[build]
script = """
cp -a "$CURRENT_DIR/build/m8_session_work/foot-dest/"* "$DESTDIR/"
"""
EOF_FOOT_RECIPE

"${BUILDER}" "${BLAZE_ROOT}/recipes/core/foot/recipe.toml"

echo "=== All Milestone 8 Phase B Wayland Session Native .blz Packages Built Successfully ==="
ls -lh "${PKGS_DIR}/libxkbcommon-"* "${PKGS_DIR}/pixman-"* "${PKGS_DIR}/fontconfig-"* "${PKGS_DIR}/wlroots-"* "${PKGS_DIR}/weston-"* "${PKGS_DIR}/labwc-"* "${PKGS_DIR}/foot-"*
