#!/usr/bin/env python3
"""
Generate ColorOS 17 'Living Flow Design' Squircle Vector (SVG) & Raster (PNG) Icon Suite
for Blaze Universe & SolarUI.

Installs crisp, luminous squircle icons with Contour Glow borders into:
  - SolarUI/data/icons/living-flow/
  - ROOTFS/usr/share/icons/hicolor/{24x24,32x32,48x48,64x64,128x128,256x256,scalable}/apps/
  - ROOTFS/usr/share/pixmaps/
so Qt6/Quickshell (Caelestia, Noctalia) and GTK4 (SolarUI, OmniBar, Taskbar) resolve 100% of icons
with zero missing-texture checkerboards.
"""

import os
import shutil
import subprocess
from PIL import Image

BLAZE_ROOT = "/home/darkmorpheus/Projeler/blaze_base"
SOLAR_ROOT = "/home/darkmorpheus/SolarUI"
OUT_DIR = os.path.join(SOLAR_ROOT, "data", "icons", "living-flow")
COVERS_DIR = os.path.join(SOLAR_ROOT, "data", "covers")

# Continuous ColorOS 17 Superellipse Squircle path inside 128x128 viewBox
SQUIRCLE_SHADOW_PATH = (
    "M 64,13 "
    "C 103,13 119,29 119,67 "
    "C 119,105 103,121 64,121 "
    "C 25,121 9,105 9,67 "
    "C 9,29 25,13 64,13 Z"
)

SQUIRCLE_PATH = (
    "M 64,9 "
    "C 103,9 119,25 119,64 "
    "C 119,103 103,119 64,119 "
    "C 25,119 9,103 9,64 "
    "C 9,25 25,9 64,9 Z"
)

INNER_HIGHLIGHT_PATH = (
    "M 64,10.8 "
    "C 101.5,10.8 117.2,26.5 117.2,64 "
    "C 117.2,101.5 101.5,117.2 64,117.2 "
    "C 26.5,117.2 10.8,101.5 10.8,64 "
    "C 10.8,26.5 26.5,10.8 64,10.8 Z"
)


def wrap_squircle_svg(grad_start: str, grad_end: str, accent_glow: str, inner_svg: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" width="128" height="128">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{grad_start}"/>
      <stop offset="100%" stop-color="{grad_end}"/>
    </linearGradient>
    <radialGradient id="luminousGlow" cx="26%" cy="20%" r="74%">
      <stop offset="0%" stop-color="{accent_glow}" stop-opacity="0.46"/>
      <stop offset="100%" stop-color="{accent_glow}" stop-opacity="0.0"/>
    </radialGradient>
    <linearGradient id="contourBorder" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#ffffff" stop-opacity="0.55"/>
      <stop offset="45%" stop-color="#ffffff" stop-opacity="0.18"/>
      <stop offset="100%" stop-color="#ffffff" stop-opacity="0.08"/>
    </linearGradient>
  </defs>
  <path d="{SQUIRCLE_SHADOW_PATH}" fill="#020617" fill-opacity="0.42"/>
  <path d="{SQUIRCLE_PATH}" fill="url(#bgGrad)"/>
  <path d="{SQUIRCLE_PATH}" fill="url(#luminousGlow)"/>
  <path d="{INNER_HIGHLIGHT_PATH}" fill="none" stroke="url(#contourBorder)" stroke-width="2.2"/>
  <g>
    {inner_svg}
  </g>
</svg>
"""


ICONS = {
    # 1. Alacritty / Terminal
    "alacritty": (
        "#0f172a",
        "#1e293b",
        "#38bdf8",
        """
        <rect x="26" y="30" width="76" height="68" rx="14" fill="#090d16" fill-opacity="0.72" stroke="#38bdf8" stroke-opacity="0.45" stroke-width="2"/>
        <path d="M 40,51 L 56,64 L 40,77" fill="none" stroke="#38bdf8" stroke-width="6.5" stroke-linecap="round" stroke-linejoin="round"/>
        <line x1="62" y1="77" x2="84" y2="77" stroke="#34d399" stroke-width="6.5" stroke-linecap="round"/>
        """,
        ["utilities-terminal", "org.Alacritty", "Alacritty", "terminal"],
    ),
    # 2. BlazeOS / Solar Installer
    "solar-installer": (
        "#ea580c",
        "#9a3412",
        "#fde047",
        """
        <rect x="30" y="72" width="68" height="24" rx="9" fill="#ffffff" fill-opacity="0.22" stroke="#ffffff" stroke-width="3.2"/>
        <circle cx="84" cy="84" r="3.8" fill="#fde047"/>
        <circle cx="72" cy="84" r="3.8" fill="#ffffff"/>
        <path d="M 64,28 L 64,65" stroke="#ffffff" stroke-width="7" stroke-linecap="round"/>
        <path d="M 48,51 L 64,67 L 80,51" fill="none" stroke="#ffffff" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
        """,
        ["solar-installer-gui", "system-software-install", "drive-harddisk", "drive-harddisk-system"],
    ),
    # 3. Noctalia Shell
    "noctalia": (
        "#312e81",
        "#1e1b4b",
        "#c084fc",
        """
        <path d="M 74,30 C 53,32 38,49 40,70 C 42,89 59,102 79,98 C 66,94 58,82 58,67 C 58,50 67,37 79,31 C 77,30.5 75.5,30 74,30 Z" fill="#f8fafc"/>
        <circle cx="84" cy="46" r="4.5" fill="#fde047"/>
        <circle cx="92" cy="64" r="2.8" fill="#38bdf8"/>
        <circle cx="76" cy="60" r="2.4" fill="#e879f9"/>
        """,
        ["dev.noctalia.Noctalia"],
    ),
    # 4. Caelestia Shell
    "caelestia": (
        "#0369a1",
        "#312e81",
        "#7dd3fc",
        """
        <ellipse cx="64" cy="64" rx="38" ry="16" transform="rotate(-28 64 64)" fill="none" stroke="#bae6fd" stroke-width="4.5"/>
        <ellipse cx="64" cy="64" rx="38" ry="16" transform="rotate(32 64 64)" fill="none" stroke="#c4b5fd" stroke-width="3.5" stroke-opacity="0.8"/>
        <circle cx="64" cy="64" r="13" fill="#ffffff"/>
        """,
        [],
    ),
    # 5. Solar GameZone
    "solar-gamezone": (
        "#059669",
        "#0f172a",
        "#34d399",
        """
        <path d="M 38,48 L 90,48 C 99,48 104,56 101,69 L 97,83 C 95,90 87,92 82,86 L 74,77 L 54,77 L 46,86 C 41,92 33,90 31,83 L 27,69 C 24,56 29,48 38,48 Z" fill="#f8fafc" fill-opacity="0.95"/>
        <line x1="45" y1="58" x2="45" y2="70" stroke="#0f172a" stroke-width="4.5" stroke-linecap="round"/>
        <line x1="39" y1="64" x2="51" y2="64" stroke="#0f172a" stroke-width="4.5" stroke-linecap="round"/>
        <circle cx="80" cy="60" r="3.6" fill="#10b981"/>
        <circle cx="87" cy="66" r="3.6" fill="#0ea5e9"/>
        <circle cx="73" cy="66" r="3.6" fill="#f97316"/>
        """,
        ["applications-games", "input-gaming", "blaze-gamezone"],
    ),
    # 6. SolarUI Settings
    "solar-settings": (
        "#0284c7",
        "#1d4ed8",
        "#7dd3fc",
        """
        <line x1="34" y1="44" x2="94" y2="44" stroke="#bae6fd" stroke-width="5.5" stroke-linecap="round" stroke-opacity="0.55"/>
        <circle cx="52" cy="44" r="9.5" fill="#ffffff"/>
        <line x1="34" y1="64" x2="94" y2="64" stroke="#bae6fd" stroke-width="5.5" stroke-linecap="round" stroke-opacity="0.55"/>
        <circle cx="78" cy="64" r="9.5" fill="#fde047"/>
        <line x1="34" y1="84" x2="94" y2="84" stroke="#bae6fd" stroke-width="5.5" stroke-linecap="round" stroke-opacity="0.55"/>
        <circle cx="58" cy="84" r="9.5" fill="#ffffff"/>
        """,
        [
            "solarui",
            "preferences-system",
            "preferences-desktop-theme",
            "preferences-desktop-wallpaper",
            "video-display",
        ],
    ),
    # 7. SolarUI Welcome & Guide + BlazeOS Emblem
    "solar-welcome": (
        "#f97316",
        "#2563eb",
        "#fde047",
        """
        <path d="M 64,26 C 76,42 88,54 86,73 C 84,89 74,100 64,100 C 54,100 44,89 42,73 C 40,58 51,48 55,40 C 54,51 60,55 64,51 C 62,41 60,33 64,26 Z" fill="#ffffff"/>
        <circle cx="64" cy="77" r="9.5" fill="#38bdf8"/>
        """,
        ["blazeos", "system-help"],
    ),
    # 8. Blaze Recovery / Sentinel Shield
    "blaze-recovery": (
        "#dc2626",
        "#7f1d1d",
        "#fb923c",
        """
        <path d="M 64,26 L 94,38 L 94,63 C 94,82 80,96 64,102 C 48,96 34,82 34,63 L 34,38 Z" fill="#ffffff" fill-opacity="0.20" stroke="#ffffff" stroke-width="4.5" stroke-linejoin="round"/>
        <path d="M 50,64 L 60,74 L 79,53" fill="none" stroke="#ffffff" stroke-width="6.5" stroke-linecap="round" stroke-linejoin="round"/>
        """,
        ["system-error", "security-high"],
    ),
    # 9. Clipboard / Paste
    "edit-paste": (
        "#0d9488",
        "#115e59",
        "#5eead4",
        """
        <rect x="36" y="36" width="56" height="64" rx="10" fill="#ffffff" fill-opacity="0.20" stroke="#ffffff" stroke-width="4"/>
        <rect x="50" y="28" width="28" height="14" rx="6" fill="#ffffff"/>
        <line x1="48" y1="58" x2="80" y2="58" stroke="#ffffff" stroke-width="4.5" stroke-linecap="round"/>
        <line x1="48" y1="72" x2="80" y2="72" stroke="#ffffff" stroke-width="4.5" stroke-linecap="round"/>
        <line x1="48" y1="86" x2="68" y2="86" stroke="#ffffff" stroke-width="4.5" stroke-linecap="round"/>
        """,
        [],
    ),
    # 10. Web / Internet
    "applications-internet": (
        "#0284c7",
        "#0f172a",
        "#38bdf8",
        """
        <circle cx="64" cy="64" r="34" fill="none" stroke="#ffffff" stroke-width="4.5"/>
        <ellipse cx="64" cy="64" rx="16" ry="34" fill="none" stroke="#7dd3fc" stroke-width="3.5"/>
        <line x1="30" y1="64" x2="98" y2="64" stroke="#ffffff" stroke-width="3.5"/>
        <line x1="36" y1="47" x2="92" y2="47" stroke="#7dd3fc" stroke-width="3"/>
        <line x1="36" y1="81" x2="92" y2="81" stroke="#7dd3fc" stroke-width="3"/>
        """,
        ["web-browser"],
    ),
    # 11. Lock / Reboot / Power / Generic App
    "system-lock-screen": (
        "#4338ca",
        "#1e1b4b",
        "#818cf8",
        """
        <rect x="38" y="58" width="52" height="40" rx="10" fill="#ffffff"/>
        <path d="M 48,58 L 48,45 C 48,35 55,28 64,28 C 73,28 80,35 80,45 L 80,58" fill="none" stroke="#ffffff" stroke-width="6.5" stroke-linecap="round"/>
        <circle cx="64" cy="78" r="5.5" fill="#312e81"/>
        """,
        [],
    ),
    "system-reboot": (
        "#059669",
        "#065f46",
        "#6ee7b7",
        """
        <path d="M 88,52 A 28,28 0 1 0 90,74" fill="none" stroke="#ffffff" stroke-width="6.5" stroke-linecap="round"/>
        <polygon points="92,36 94,57 74,53" fill="#ffffff"/>
        """,
        [],
    ),
    "system-shutdown": (
        "#e11d48",
        "#881337",
        "#fda4af",
        """
        <line x1="64" y1="30" x2="64" y2="62" stroke="#ffffff" stroke-width="7" stroke-linecap="round"/>
        <path d="M 44,44 A 28,28 0 1 0 84,44" fill="none" stroke="#ffffff" stroke-width="6.5" stroke-linecap="round"/>
        """,
        [],
    ),
    "application-x-executable": (
        "#334155",
        "#0f172a",
        "#94a3b8",
        """
        <rect x="34" y="34" width="26" height="26" rx="7" fill="#38bdf8"/>
        <rect x="68" y="34" width="26" height="26" rx="7" fill="#f97316"/>
        <rect x="34" y="68" width="26" height="26" rx="7" fill="#a78bfa"/>
        <rect x="68" y="68" width="26" height="26" rx="7" fill="#34d399"/>
        """,
        ["image-missing"],
    ),
}


def render_svg_to_png(svg_path: str, png_path: str, size: int) -> None:
    subprocess.run(
        ["rsvg-convert", "-w", str(size), "-h", str(size), svg_path, "-o", png_path],
        check=True,
    )


def generate_offline_game_cover() -> None:
    os.makedirs(COVERS_DIR, exist_ok=True)
    cover_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
      <defs>
        <linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#0f172a"/>
          <stop offset="50%" stop-color="#1e293b"/>
          <stop offset="100%" stop-color="#0c4a6e"/>
        </linearGradient>
        <radialGradient id="r" cx="30%" cy="25%" r="75%">
          <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.38"/>
          <stop offset="100%" stop-color="#f97316" stop-opacity="0.08"/>
        </radialGradient>
      </defs>
      <rect width="512" height="512" fill="url(#g)"/>
      <rect width="512" height="512" fill="url(#r)"/>
      <circle cx="256" cy="220" r="88" fill="none" stroke="#38bdf8" stroke-opacity="0.35" stroke-width="6"/>
      <path d="M 192,202 L 320,202 C 342,202 356,220 348,252 L 338,286 C 333,303 314,308 302,293 L 282,271 L 230,271 L 210,293 C 198,308 179,303 174,286 L 164,252 C 156,220 170,202 192,202 Z" fill="#f8fafc" fill-opacity="0.92"/>
      <text x="256" y="388" text-anchor="middle" fill="#7dd3fc" font-family="Sans" font-size="24" font-weight="bold" letter-spacing="3">BLAZE GAMEZONE</text>
      <text x="256" y="422" text-anchor="middle" fill="#94a3b8" font-family="Sans" font-size="17">SCHED_EXT • NTSYNC • PROTON</text>
    </svg>"""
    svg_tmp = os.path.join(COVERS_DIR, "steam-deck.svg")
    png_tmp = os.path.join(COVERS_DIR, "steam-deck.png")
    jpg_out = os.path.join(COVERS_DIR, "steam-deck.jpg")
    with open(svg_tmp, "w", encoding="utf-8") as f:
        f.write(cover_svg)
    render_svg_to_png(svg_tmp, png_tmp, 512)
    img = Image.open(png_tmp).convert("RGB")
    img.save(jpg_out, quality=92)
    os.remove(svg_tmp)


def install_into_rootfs(rootfs_dir: str) -> None:
    hicolor = os.path.join(rootfs_dir, "usr", "share", "icons", "hicolor")
    pixmaps = os.path.join(rootfs_dir, "usr", "share", "pixmaps")
    os.makedirs(pixmaps, exist_ok=True)
    sizes = [24, 32, 48, 64, 128, 256]

    for sz in sizes:
        os.makedirs(os.path.join(hicolor, f"{sz}x{sz}", "apps"), exist_ok=True)
    os.makedirs(os.path.join(hicolor, "scalable", "apps"), exist_ok=True)

    for primary_name, (_, _, _, _, aliases) in ICONS.items():
        all_names = [primary_name] + aliases
        src_svg = os.path.join(OUT_DIR, f"{primary_name}.svg")
        for target_name in all_names:
            shutil.copy2(src_svg, os.path.join(hicolor, "scalable", "apps", f"{target_name}.svg"))
            shutil.copy2(src_svg, os.path.join(pixmaps, f"{target_name}.svg"))
            for sz in sizes:
                src_png = os.path.join(OUT_DIR, f"{primary_name}-{sz}.png")
                shutil.copy2(src_png, os.path.join(hicolor, f"{sz}x{sz}", "apps", f"{target_name}.png"))
            shutil.copy2(
                os.path.join(OUT_DIR, f"{primary_name}-128.png"),
                os.path.join(pixmaps, f"{target_name}.png"),
            )

    # Ensure FireHub PNG is also registered across all hicolor sizes
    firehub_png = os.path.join(pixmaps, "firehub.png")
    if os.path.exists(firehub_png):
        img = Image.open(firehub_png).convert("RGBA")
        for sz in sizes:
            resized = img.resize((sz, sz), Image.Resampling.LANCZOS)
            resized.save(os.path.join(hicolor, f"{sz}x{sz}", "apps", "firehub.png"))

    # Copy GameZone fallback cover into rootfs
    covers_dst = os.path.join(rootfs_dir, "usr", "share", "solarui", "covers")
    os.makedirs(covers_dst, exist_ok=True)
    for fn in os.listdir(COVERS_DIR):
        shutil.copy2(os.path.join(COVERS_DIR, fn), os.path.join(covers_dst, fn))

    subprocess.run(["gtk-update-icon-cache", "-f", "-t", hicolor], check=False)


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    sizes = [24, 32, 48, 64, 128, 256]

    preview_tiles = []
    for name, (g1, g2, glow, inner, _aliases) in ICONS.items():
        svg_content = wrap_squircle_svg(g1, g2, glow, inner)
        svg_path = os.path.join(OUT_DIR, f"{name}.svg")
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(svg_content)
        for sz in sizes:
            png_path = os.path.join(OUT_DIR, f"{name}-{sz}.png")
            render_svg_to_png(svg_path, png_path, sz)
        preview_tiles.append((name, os.path.join(OUT_DIR, f"{name}-128.png")))

    generate_offline_game_cover()

    # Build a contact sheet preview to verify visual quality
    cols = 7
    rows = (len(preview_tiles) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * 148 + 20, rows * 148 + 20), (11, 15, 25, 255))
    for idx, (_name, p_path) in enumerate(preview_tiles):
        r, c = divmod(idx, cols)
        tile = Image.open(p_path).convert("RGBA")
        sheet.paste(tile, (20 + c * 148, 20 + r * 148), tile)
    sheet_path = "/tmp/living_flow_icons_preview.png"
    sheet.save(sheet_path)
    print(f"Generated {len(ICONS)} Living Flow icon families -> {OUT_DIR}")

    rootfs_dir = os.path.join(BLAZE_ROOT, "build", "rootfs")
    if os.path.exists(rootfs_dir):
        install_into_rootfs(rootfs_dir)
        print(f"Installed Living Flow icons into {rootfs_dir}")


if __name__ == "__main__":
    main()
