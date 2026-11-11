#!/usr/bin/env python3
"""
Generate Authentic ColorOS 17 'Living Flow Design' (Non-Neon Obsidian Satin & Condensed Light)
Icon Suite, Official 4-Petal Blaze Universe Cutout & Numeric Fastfetch Logo,
Settings Category Squircle Badges, and Complete Solar GameZone Artwork Suite.
"""

import os
import shutil
import subprocess
import numpy as np
from PIL import Image

BLAZE_ROOT = "/home/darkmorpheus/Projeler/blaze_base"
SOLAR_ROOT = "/home/darkmorpheus/SolarUI"
ICONS_BASE = os.path.join(SOLAR_ROOT, "data", "icons")
OUT_DIR = os.path.join(ICONS_BASE, "living-flow")
GZ_ICONS_DIR = os.path.join(ICONS_BASE, "gamezone")
COVERS_DIR = os.path.join(SOLAR_ROOT, "data", "covers")
FASTFETCH_DIR = os.path.join(SOLAR_ROOT, "data", "fastfetch")

# Continuous ColorOS 17 Superellipse Squircle path inside 128x128 viewBox
SQUIRCLE_SHADOW_PATH = (
    "M 64,12.5 "
    "C 103,12.5 119,28.5 119,66.5 "
    "C 119,104.5 103,120.5 64,120.5 "
    "C 25,120.5 9,104.5 9,66.5 "
    "C 9,28.5 25,12.5 64,12.5 Z"
)

SQUIRCLE_PATH = (
    "M 64,9 "
    "C 103,9 119,25 119,64 "
    "C 119,103 103,119 64,119 "
    "C 25,119 9,103 9,64 "
    "C 9,25 25,9 64,9 Z"
)

INNER_HIGHLIGHT_PATH = (
    "M 64,10.5 "
    "C 101.6,10.5 117.5,26.4 117.5,64 "
    "C 117.5,101.6 101.6,117.5 64,117.5 "
    "C 26.4,117.5 10.5,101.6 10.5,64 "
    "C 10.5,26.4 26.4,10.5 64,10.5 Z"
)

# Official 4-Petal Blaze Universe Vector Emblem (inside 128x128 viewBox)
BLAZE_4PETAL_SVG = """
  <defs>
    <radialGradient id="petalGlowTL" cx="62%" cy="58%" r="58%">
      <stop offset="0%" stop-color="#ff4d1f"/>
      <stop offset="68%" stop-color="#df2911"/>
      <stop offset="100%" stop-color="#991408"/>
    </radialGradient>
    <radialGradient id="petalGlowTR" cx="38%" cy="58%" r="58%">
      <stop offset="0%" stop-color="#ff4d1f"/>
      <stop offset="68%" stop-color="#df2911"/>
      <stop offset="100%" stop-color="#991408"/>
    </radialGradient>
    <radialGradient id="petalGlowBL" cx="60%" cy="56%" r="60%">
      <stop offset="0%" stop-color="#ff5122"/>
      <stop offset="68%" stop-color="#e02b12"/>
      <stop offset="100%" stop-color="#961307"/>
    </radialGradient>
    <radialGradient id="petalGlowBR" cx="40%" cy="56%" r="60%">
      <stop offset="0%" stop-color="#ff5122"/>
      <stop offset="68%" stop-color="#e02b12"/>
      <stop offset="100%" stop-color="#961307"/>
    </radialGradient>
  </defs>
  <!-- Upper-Left Petal -->
  <path d="M 35,38 L 48,38 C 56,38 61.8,44 61.8,56 L 50,56 C 41,56 35,49 35,38 Z" fill="url(#petalGlowTL)"/>
  <!-- Upper-Right Petal -->
  <path d="M 93,38 L 80,38 C 72,38 66.2,44 66.2,56 L 78,56 C 87,56 93,49 93,38 Z" fill="url(#petalGlowTR)"/>
  <!-- Lower-Left Petal -->
  <path d="M 22,60 L 42,60 C 54,60 61.8,69 61.8,88 L 44,88 C 30,88 22,77 22,60 Z" fill="url(#petalGlowBL)"/>
  <!-- Lower-Right Petal -->
  <path d="M 106,60 L 86,60 C 74,60 66.2,69 66.2,88 L 84,88 C 98,88 106,77 106,60 Z" fill="url(#petalGlowBR)"/>
"""


def wrap_squircle_svg(grad_start: str, grad_end: str, condensed_light: str, inner_svg: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" width="128" height="128">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{grad_start}"/>
      <stop offset="100%" stop-color="{grad_end}"/>
    </linearGradient>
    <radialGradient id="luminousGlow" cx="28%" cy="18%" r="72%">
      <stop offset="0%" stop-color="{condensed_light}" stop-opacity="0.24"/>
      <stop offset="100%" stop-color="{condensed_light}" stop-opacity="0.0"/>
    </radialGradient>
    <linearGradient id="contourBorder" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#ffffff" stop-opacity="0.34"/>
      <stop offset="50%" stop-color="#ffffff" stop-opacity="0.11"/>
      <stop offset="100%" stop-color="#ffffff" stop-opacity="0.05"/>
    </linearGradient>
  </defs>
  <path d="{SQUIRCLE_SHADOW_PATH}" fill="#050507" fill-opacity="0.46"/>
  <path d="{SQUIRCLE_PATH}" fill="url(#bgGrad)"/>
  <path d="{SQUIRCLE_PATH}" fill="url(#luminousGlow)"/>
  <path d="{INNER_HIGHLIGHT_PATH}" fill="none" stroke="url(#contourBorder)" stroke-width="1.8"/>
  <g>
    {inner_svg}
  </g>
</svg>
"""


# Non-Neon ColorOS 17 Industrial Satin Squircle Icon Families
ICONS = {
    # 1. Alacritty / Terminal (Smoked Obsidian Titanium)
    "alacritty": (
        "#23252c",
        "#141519",
        "#e4e4e7",
        """
        <rect x="27" y="31" width="74" height="66" rx="14" fill="#0d0e11" fill-opacity="0.82" stroke="#ffffff" stroke-opacity="0.16" stroke-width="1.8"/>
        <path d="M 41,52 L 56,64 L 41,76" fill="none" stroke="#f4f4f5" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
        <line x1="62" y1="76" x2="83" y2="76" stroke="#e04828" stroke-width="6" stroke-linecap="round"/>
        """,
        ["utilities-terminal", "org.Alacritty", "Alacritty", "terminal"],
    ),
    # 2. BlazeOS / Solar Installer (Satin Terracotta Vermilion)
    "solar-installer": (
        "#c23b22",
        "#7c2012",
        "#fca5a5",
        """
        <rect x="30" y="72" width="68" height="24" rx="9" fill="#ffffff" fill-opacity="0.16" stroke="#f8fafc" stroke-width="3"/>
        <circle cx="84" cy="84" r="3.6" fill="#fde68a"/>
        <circle cx="72" cy="84" r="3.6" fill="#ffffff"/>
        <path d="M 64,29 L 64,65" stroke="#ffffff" stroke-width="6.5" stroke-linecap="round"/>
        <path d="M 49,51 L 64,66 L 79,51" fill="none" stroke="#ffffff" stroke-width="6.5" stroke-linecap="round" stroke-linejoin="round"/>
        """,
        ["solar-installer-gui", "system-software-install", "drive-harddisk", "drive-harddisk-system"],
    ),
    # 3. Noctalia Shell (Deep Smoked Plum-Graphite)
    "noctalia": (
        "#2e293d",
        "#181622",
        "#d8b4fe",
        """
        <path d="M 74,31 C 53,33 39,50 41,70 C 43,88 59,101 78,97 C 66,93 58,81 58,67 C 58,51 67,38 78,32 C 76.5,31.5 75,31 74,31 Z" fill="#f4f4f5"/>
        <circle cx="84" cy="48" r="4" fill="#fde68a"/>
        <circle cx="91" cy="64" r="2.5" fill="#d4d4d8"/>
        """,
        ["dev.noctalia.Noctalia"],
    ),
    # 4. Caelestia Shell (Satin Slate-Steel)
    "caelestia": (
        "#293242",
        "#161b24",
        "#cbd5e1",
        """
        <ellipse cx="64" cy="64" rx="37" ry="15.5" transform="rotate(-28 64 64)" fill="none" stroke="#e2e8f0" stroke-width="4"/>
        <ellipse cx="64" cy="64" rx="37" ry="15.5" transform="rotate(32 64 64)" fill="none" stroke="#94a3b8" stroke-width="3.2"/>
        <circle cx="64" cy="64" r="12" fill="#f8fafc"/>
        """,
        [],
    ),
    # 5. Solar GameZone (Smoked Mineral Jade & Obsidian)
    "solar-gamezone": (
        "#1f3b34",
        "#121918",
        "#a7f3d0",
        """
        <path d="M 38,48 L 90,48 C 99,48 104,56 101,69 L 97,83 C 95,90 87,92 82,86 L 74,77 L 54,77 L 46,86 C 41,92 33,90 31,83 L 27,69 C 24,56 29,48 38,48 Z" fill="#f4f4f5"/>
        <line x1="45" y1="58" x2="45" y2="70" stroke="#18181b" stroke-width="4.5" stroke-linecap="round"/>
        <line x1="39" y1="64" x2="51" y2="64" stroke="#18181b" stroke-width="4.5" stroke-linecap="round"/>
        <circle cx="80" cy="60" r="3.4" fill="#1f3b34"/>
        <circle cx="87" cy="66" r="3.4" fill="#c23b22"/>
        <circle cx="73" cy="66" r="3.4" fill="#52525b"/>
        """,
        ["applications-games", "input-gaming", "blaze-gamezone"],
    ),
    # 6. SolarUI Settings (ColorOS 17 Brushed Titanium Sliders)
    "solar-settings": (
        "#2d3139",
        "#181a20",
        "#f4f4f5",
        """
        <line x1="34" y1="44" x2="94" y2="44" stroke="#a1a1aa" stroke-width="5" stroke-linecap="round" stroke-opacity="0.55"/>
        <circle cx="52" cy="44" r="9" fill="#f4f4f5"/>
        <line x1="34" y1="64" x2="94" y2="64" stroke="#a1a1aa" stroke-width="5" stroke-linecap="round" stroke-opacity="0.55"/>
        <circle cx="77" cy="64" r="9" fill="#e04828"/>
        <line x1="34" y1="84" x2="94" y2="84" stroke="#a1a1aa" stroke-width="5" stroke-linecap="round" stroke-opacity="0.55"/>
        <circle cx="57" cy="84" r="9" fill="#f4f4f5"/>
        """,
        [
            "solarui",
            "preferences-system",
            "preferences-desktop-theme",
            "preferences-desktop-wallpaper",
            "video-display",
            "solar-omnibar",
        ],
    ),
    # 7. SolarUI Welcome & Official Blaze Universe 4-Petal Emblem
    "solar-welcome": (
        "#1b1c21",
        "#101114",
        "#ff6b4a",
        BLAZE_4PETAL_SVG,
        ["blazeos", "system-help"],
    ),
    # 8. Blaze Recovery / Sentinel Shield (Satin Crimson)
    "blaze-recovery": (
        "#99231b",
        "#4c110d",
        "#fca5a5",
        """
        <path d="M 64,27 L 93,38.5 L 93,63 C 93,81.5 79.5,95.5 64,101.5 C 48.5,95.5 35,81.5 35,63 L 35,38.5 Z" fill="#ffffff" fill-opacity="0.14" stroke="#f4f4f5" stroke-width="4.2" stroke-linejoin="round"/>
        <path d="M 50,64 L 60,74 L 78,54" fill="none" stroke="#ffffff" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
        """,
        ["system-error", "security-high"],
    ),
    # 9. Clipboard / Paste (Smoked Pewter)
    "edit-paste": (
        "#2a3338",
        "#171c1f",
        "#cbd5e1",
        """
        <rect x="37" y="36" width="54" height="63" rx="10" fill="#ffffff" fill-opacity="0.12" stroke="#f4f4f5" stroke-width="3.8"/>
        <rect x="50" y="28" width="28" height="13" rx="6" fill="#f4f4f5"/>
        <line x1="48" y1="58" x2="80" y2="58" stroke="#e4e4e7" stroke-width="4.2" stroke-linecap="round"/>
        <line x1="48" y1="72" x2="80" y2="72" stroke="#e4e4e7" stroke-width="4.2" stroke-linecap="round"/>
        <line x1="48" y1="86" x2="68" y2="86" stroke="#a1a1aa" stroke-width="4.2" stroke-linecap="round"/>
        """,
        [],
    ),
    # 10. Web / Internet (Smoked Graphite Globe)
    "applications-internet": (
        "#27303f",
        "#151922",
        "#cbd5e1",
        """
        <circle cx="64" cy="64" r="33" fill="none" stroke="#f4f4f5" stroke-width="4"/>
        <ellipse cx="64" cy="64" rx="15.5" ry="33" fill="none" stroke="#a1a1aa" stroke-width="3.2"/>
        <line x1="31" y1="64" x2="97" y2="64" stroke="#f4f4f5" stroke-width="3.2"/>
        <line x1="37" y1="47" x2="91" y2="47" stroke="#a1a1aa" stroke-width="2.8"/>
        <line x1="37" y1="81" x2="91" y2="81" stroke="#a1a1aa" stroke-width="2.8"/>
        """,
        ["web-browser"],
    ),
    # 11. System Lock / Reboot / Shutdown / App Grid
    "system-lock-screen": (
        "#2c2d35",
        "#18191e",
        "#e4e4e7",
        """
        <rect x="39" y="58" width="50" height="39" rx="10" fill="#f4f4f5"/>
        <path d="M 48,58 L 48,45 C 48,35.5 55,28.5 64,28.5 C 73,28.5 80,35.5 80,45 L 80,58" fill="none" stroke="#f4f4f5" stroke-width="6" stroke-linecap="round"/>
        <circle cx="64" cy="77" r="5" fill="#18191e"/>
        """,
        [],
    ),
    "system-reboot": (
        "#243832",
        "#141f1c",
        "#a7f3d0",
        """
        <path d="M 87,52 A 27,27 0 1 0 89,74" fill="none" stroke="#f4f4f5" stroke-width="6" stroke-linecap="round"/>
        <polygon points="91,36 93,56 74,52" fill="#f4f4f5"/>
        """,
        [],
    ),
    "system-shutdown": (
        "#881d1d",
        "#451010",
        "#fecaca",
        """
        <line x1="64" y1="31" x2="64" y2="61" stroke="#ffffff" stroke-width="6.5" stroke-linecap="round"/>
        <path d="M 44,44 A 27,27 0 1 0 84,44" fill="none" stroke="#ffffff" stroke-width="6" stroke-linecap="round"/>
        """,
        [],
    ),
    "application-x-executable": (
        "#272930",
        "#15161a",
        "#d4d4d8",
        """
        <rect x="35" y="35" width="25" height="25" rx="7" fill="#e4e4e7"/>
        <rect x="68" y="35" width="25" height="25" rx="7" fill="#d94226"/>
        <rect x="35" y="68" width="25" height="25" rx="7" fill="#71717a"/>
        <rect x="68" y="68" width="25" height="25" rx="7" fill="#a1a1aa"/>
        """,
        ["image-missing", "application-generic"],
    ),
}

# 11 ColorOS 17 Settings Navigation Category Squircle Badges (56x56 retina for crisp 24x24 display)
SETTINGS_NAV_ICONS = {
    "nav-clock": (
        "#3a2d22", "#221b15", "#fdba74",
        """
        <circle cx="64" cy="64" r="32" fill="none" stroke="#f4f4f5" stroke-width="6"/>
        <path d="M 64,45 L 64,64 L 78,73" fill="none" stroke="#fb923c" stroke-width="6.5" stroke-linecap="round" stroke-linejoin="round"/>
        """,
    ),
    "nav-taskbar": (
        "#2b303a", "#191c22", "#e2e8f0",
        """
        <rect x="26" y="72" width="76" height="22" rx="11" fill="#f4f4f5"/>
        <circle cx="44" cy="50" r="7" fill="#a1a1aa"/>
        <circle cx="64" cy="50" r="7" fill="#e04828"/>
        <circle cx="84" cy="50" r="7" fill="#a1a1aa"/>
        """,
    ),
    "nav-display": (
        "#26313f", "#161d26", "#cbd5e1",
        """
        <rect x="27" y="34" width="74" height="48" rx="9" fill="none" stroke="#f4f4f5" stroke-width="6"/>
        <line x1="48" y1="94" x2="80" y2="94" stroke="#a1a1aa" stroke-width="6" stroke-linecap="round"/>
        <line x1="64" y1="82" x2="64" y2="94" stroke="#a1a1aa" stroke-width="6"/>
        """,
    ),
    "nav-shell": (
        "#3b2622", "#211614", "#fca5a5",
        """
        <polygon points="64,30 98,48 64,66 30,48" fill="#f4f4f5"/>
        <polyline points="30,64 64,82 98,64" fill="none" stroke="#e04828" stroke-width="6.5" stroke-linecap="round" stroke-linejoin="round"/>
        <polyline points="30,79 64,97 98,79" fill="none" stroke="#a1a1aa" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
        """,
    ),
    "nav-caelestia": (
        "#2e2a3b", "#1a1822", "#d8b4fe",
        """
        <ellipse cx="64" cy="64" rx="34" ry="14" transform="rotate(-28 64 64)" fill="none" stroke="#f4f4f5" stroke-width="5.5"/>
        <circle cx="64" cy="64" r="11" fill="#e4e4e7"/>
        """,
    ),
    "nav-noctalia": (
        "#282736", "#171620", "#cbd5e1",
        """
        <path d="M 74,32 C 54,34 40,50 42,70 C 44,87 60,99 78,95 C 66,91 58,80 58,66 C 58,51 67,39 78,33 Z" fill="#f4f4f5"/>
        """,
    ),
    "nav-perf": (
        "#3b2e1e", "#211a12", "#fcd34d",
        """
        <polygon points="69,26 40,68 62,68 57,102 88,58 66,58" fill="#f59e0b"/>
        """,
    ),
    "nav-health": (
        "#1f362d", "#13211c", "#86efac",
        """
        <path d="M 64,28 L 92,39 L 92,63 C 92,81 79,94 64,100 C 49,94 36,81 36,63 L 36,39 Z" fill="none" stroke="#f4f4f5" stroke-width="6" stroke-linejoin="round"/>
        <path d="M 51,64 L 60,73 L 77,54" fill="none" stroke="#4ade80" stroke-width="6.5" stroke-linecap="round" stroke-linejoin="round"/>
        """,
    ),
    "nav-omnibar": (
        "#2c2e36", "#191a1f", "#e4e4e7",
        """
        <circle cx="58" cy="58" r="23" fill="none" stroke="#f4f4f5" stroke-width="6.5"/>
        <line x1="75" y1="75" x2="94" y2="94" stroke="#e04828" stroke-width="7" stroke-linecap="round"/>
        """,
    ),
    "nav-hud": (
        "#2d3036", "#191b1f", "#d4d4d8",
        """
        <rect x="26" y="38" width="76" height="52" rx="11" fill="none" stroke="#f4f4f5" stroke-width="5.5"/>
        <rect x="38" y="50" width="12" height="10" rx="3" fill="#e4e4e7"/>
        <rect x="58" y="50" width="12" height="10" rx="3" fill="#e4e4e7"/>
        <rect x="78" y="50" width="12" height="10" rx="3" fill="#e4e4e7"/>
        <rect x="44" y="68" width="40" height="9" rx="4" fill="#e04828"/>
        """,
    ),
    "nav-about": (
        "#1e1f24", "#111215", "#ff5722",
        BLAZE_4PETAL_SVG,
    ),
}


def render_svg_to_png(svg_path: str, png_path: str, width: int, height: int | None = None) -> None:
    h = height if height is not None else width
    subprocess.run(
        ["rsvg-convert", "-w", str(width), "-h", str(h), svg_path, "-o", png_path],
        check=True,
    )


def build_official_logo_and_fastfetch() -> None:
    src_jpg = os.path.join(ICONS_BASE, "blaze-source-logo.jpg")
    if not os.path.exists(src_jpg):
        return
    src = Image.open(src_jpg).convert("RGB")
    arr = np.array(src, dtype=np.float32)
    mask_rough = arr[:, :, 0] > 28
    ys, xs = np.where(mask_rough)
    crop = arr[ys.min():ys.max() + 1, xs.min():xs.max() + 1]

    r, g, b = crop[:, :, 0], crop[:, :, 1], crop[:, :, 2]
    alpha = np.power(np.clip((r - 22.0) / 68.0, 0.0, 1.0), 0.85)
    r_clean = np.where(alpha > 0.01, np.clip(r / np.maximum(alpha, 0.35), 0, 255), 0)
    g_clean = np.where(alpha > 0.01, np.clip(g / np.maximum(alpha, 0.55), 0, 255), 0)
    b_clean = np.where(alpha > 0.01, np.clip(b / np.maximum(alpha, 0.65), 0, 255), 0)

    rgba_crop = np.stack([r_clean, g_clean, b_clean, alpha * 255.0], axis=-1).astype(np.uint8)
    petal_img = Image.fromarray(rgba_crop, mode="RGBA")

    canvas = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    scale = 448.0 / max(petal_img.width, petal_img.height)
    nw, nh = int(round(petal_img.width * scale)), int(round(petal_img.height * scale))
    resized = petal_img.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas.paste(resized, ((512 - nw) // 2, (512 - nh) // 2), resized)

    for sz, out_name in [
        (256, "blaze-logo-256.png"),
        (256, "solar-logo-256.png"),
        (48, "solar-logo-48.png"),
    ]:
        canvas.resize((sz, sz), Image.Resampling.LANCZOS).save(os.path.join(ICONS_BASE, out_name))

    # Symmetrical 40x15 numeric ASCII art ("rakamlarla") with TrueColor crimson-vermilion shading
    os.makedirs(FASTFETCH_DIR, exist_ok=True)
    cols, rows = 40, 15
    grid = petal_img.resize((cols, rows), Image.Resampling.LANCZOS)
    g_arr = np.array(grid, dtype=np.float32)
    digits = "1234567890"
    raw_lines = []
    for y in range(rows):
        r_line = ""
        for x in range(cols):
            mx = cols - 1 - x
            pr = 0.5 * (g_arr[y, x, 0] + g_arr[y, mx, 0])
            pg = 0.5 * (g_arr[y, x, 1] + g_arr[y, mx, 1])
            pb = 0.5 * (g_arr[y, x, 2] + g_arr[y, mx, 2])
            pa = 0.5 * (g_arr[y, x, 3] + g_arr[y, mx, 3])
            if y == 5 or x in (19, 20) or pa < 105:
                r_line += " "
            else:
                lum = np.clip((pr - 115.0) / 140.0, 0.0, 0.999)
                d_ch = digits[int(lum * len(digits))]
                ri = int(np.clip(pr * 1.02, 135, 255))
                gi = int(np.clip(pg * 1.05, 20, 68))
                bi = int(np.clip(pb, 10, 28))
                r_line += f"\x1b[38;2;{ri};{gi};{bi}m{d_ch}\x1b[0m"
        raw_lines.append(r_line.rstrip())

    with open(os.path.join(FASTFETCH_DIR, "blaze-logo.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(raw_lines) + "\n")


def generate_gamezone_assets() -> None:
    os.makedirs(COVERS_DIR, exist_ok=True)
    os.makedirs(GZ_ICONS_DIR, exist_ok=True)

    # 1. User Avatar (128x128 Obsidian Circle + Official 4-Petal Blaze Emblem)
    avatar_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" width="128" height="128">
      <circle cx="64" cy="64" r="62" fill="#18191e" stroke="#ffffff" stroke-opacity="0.22" stroke-width="3"/>
      <g transform="translate(6, 4) scale(0.90)">{BLAZE_4PETAL_SVG}</g>
    </svg>"""
    av_svg_p = os.path.join(COVERS_DIR, "_avatar.svg")
    with open(av_svg_p, "w", encoding="utf-8") as f:
        f.write(avatar_svg)
    render_svg_to_png(av_svg_p, os.path.join(COVERS_DIR, "user_avatar.png"), 128)
    os.remove(av_svg_p)

    # 2. 5 Top Capsule Bar Nav Icons (36x36 crisp platinum)
    nav_svgs = {
        "xbox_nav_library": """<rect x="6" y="6" width="10" height="10" rx="2.5" fill="#f4f4f5"/><rect x="20" y="6" width="10" height="10" rx="2.5" fill="#f4f4f5"/><rect x="6" y="20" width="10" height="10" rx="2.5" fill="#f4f4f5"/><rect x="20" y="20" width="10" height="10" rx="2.5" fill="#e04828"/>""",
        "xbox_nav_store": """<path d="M 8,13 L 28,13 L 26,29 C 26,30.5 25,31 23.5,31 L 12.5,31 C 11,31 10,30.5 10,29 Z" fill="none" stroke="#f4f4f5" stroke-width="2.6"/><path d="M 13,13 L 13,10 C 13,7.2 15.2,5 18,5 C 20.8,5 23,7.2 23,10 L 23,13" fill="none" stroke="#f4f4f5" stroke-width="2.6"/>""",
        "xbox_nav_gamepass": """<path d="M 10,12 L 26,12 C 29,12 31,15 30,20 L 28.5,25 C 27.8,27.5 25,28 23.5,26 L 21,23 L 15,23 L 12.5,26 C 11,28 8.2,27.5 7.5,25 L 6,20 C 5,15 7,12 10,12 Z" fill="none" stroke="#f4f4f5" stroke-width="2.5"/>""",
        "xbox_nav_search": """<circle cx="16" cy="16" r="8.5" fill="none" stroke="#f4f4f5" stroke-width="2.8"/><line x1="22.5" y1="22.5" x2="30" y2="30" stroke="#f4f4f5" stroke-width="3" stroke-linecap="round"/>""",
        "xbox_nav_settings": """<line x1="7" y1="11" x2="29" y2="11" stroke="#a1a1aa" stroke-width="2.5" stroke-linecap="round"/><circle cx="14" cy="11" r="3.5" fill="#f4f4f5"/><line x1="7" y1="18" x2="29" y2="18" stroke="#a1a1aa" stroke-width="2.5" stroke-linecap="round"/><circle cx="23" cy="18" r="3.5" fill="#e04828"/><line x1="7" y1="25" x2="29" y2="25" stroke="#a1a1aa" stroke-width="2.5" stroke-linecap="round"/><circle cx="15" cy="25" r="3.5" fill="#f4f4f5"/>""",
    }
    for nav_name, body in nav_svgs.items():
        svg_full = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 36 36" width="36" height="36">{body}</svg>'
        svg_p = os.path.join(GZ_ICONS_DIR, f"{nav_name}.svg")
        png_p = os.path.join(GZ_ICONS_DIR, f"{nav_name}.png")
        with open(svg_p, "w", encoding="utf-8") as f:
            f.write(svg_full)
        render_svg_to_png(svg_p, png_p, 36)

    # 3. Ambient Architectural Hero Backdrop (1280x800 Obsidian + Subdued Warm Blaze Light Sweep)
    hero_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 800" width="1280" height="800">
      <defs>
        <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#111216"/>
          <stop offset="55%" stop-color="#17161b"/>
          <stop offset="100%" stop-color="#0d0e11"/>
        </linearGradient>
        <radialGradient id="emberAmbient" cx="76%" cy="32%" r="54%">
          <stop offset="0%" stop-color="#c9381e" stop-opacity="0.30"/>
          <stop offset="55%" stop-color="#7c1f10" stop-opacity="0.11"/>
          <stop offset="100%" stop-color="#0d0e11" stop-opacity="0.0"/>
        </radialGradient>
        <radialGradient id="platinumSweep" cx="22%" cy="18%" r="48%">
          <stop offset="0%" stop-color="#ffffff" stop-opacity="0.06"/>
          <stop offset="100%" stop-color="#ffffff" stop-opacity="0.0"/>
        </radialGradient>
      </defs>
      <rect width="1280" height="800" fill="url(#bg)"/>
      <rect width="1280" height="800" fill="url(#emberAmbient)"/>
      <rect width="1280" height="800" fill="url(#platinumSweep)"/>
      <path d="M 620,-40 C 860,120 1060,260 1340,210 L 1340,800 L 520,800 Z" fill="#ffffff" fill-opacity="0.018"/>
      <g transform="translate(835, 75) scale(2.45)" opacity="0.24">{BLAZE_4PETAL_SVG}</g>
    </svg>"""
    h_svg_p = os.path.join(COVERS_DIR, "_hero.svg")
    with open(h_svg_p, "w", encoding="utf-8") as f:
        f.write(hero_svg)
    render_svg_to_png(h_svg_p, os.path.join(COVERS_DIR, "xbox_dynamic.png"), 1280, 800)
    os.remove(h_svg_p)

    # 4. 7 Distinct Bespoke Game Cover Artworks (420x420 each, non-neon satin luxury)
    covers_spec = {
        "steam-deck": (
            "#1b1c22", "#101115", "#d94226", "BLAZE CONSOLE",
            f'<g transform="translate(82, 58) scale(2.0)">{BLAZE_4PETAL_SVG}</g>',
        ),
        "beamng": (
            "#2a211b", "#141210", "#ea580c", "PHYSICS SIM",
            """<circle cx="210" cy="182" r="74" fill="none" stroke="#e4e4e7" stroke-opacity="0.22" stroke-width="10"/>
               <path d="M 152,226 A 74,74 0 1 1 268,226" fill="none" stroke="#ea580c" stroke-width="10" stroke-linecap="round"/>
               <line x1="210" y1="182" x2="252" y2="146" stroke="#f8fafc" stroke-width="8" stroke-linecap="round"/>
               <circle cx="210" cy="182" r="11" fill="#f8fafc"/>""",
        ),
        "dota-2": (
            "#2d1917", "#140d0c", "#dc2626", "COMPETITIVE MOBA",
            """<rect x="142" y="114" width="136" height="136" rx="22" fill="none" stroke="#dc2626" stroke-width="9"/>
               <line x1="160" y1="132" x2="260" y2="232" stroke="#f8fafc" stroke-width="14" stroke-linecap="round"/>
               <polygon points="162,216 190,232 162,232" fill="#dc2626"/>
               <polygon points="258,148 230,132 258,132" fill="#dc2626"/>""",
        ),
        "cyberpunk-2077": (
            "#2b2616", "#14130e", "#eab308", "NIGHT CITY RPG",
            """<polygon points="135,235 135,155 168,135 168,235" fill="#eab308" fill-opacity="0.85"/>
               <polygon points="182,235 182,112 228,96 228,235" fill="#f4f4f5" fill-opacity="0.92"/>
               <polygon points="242,235 242,142 285,158 285,235" fill="#ca8a04" fill-opacity="0.82"/>
               <line x1="118" y1="236" x2="302" y2="236" stroke="#eab308" stroke-width="5"/>""",
        ),
        "stardew-valley": (
            "#1e2d24", "#111714", "#4ade80", "VALLEY SIM",
            """<polygon points="122,232 184,142 238,232" fill="#3f6212"/>
               <polygon points="188,232 248,128 304,232" fill="#4d7c0f"/>
               <circle cx="164" cy="126" r="20" fill="#fde68a"/>""",
        ),
        "mechanicus": (
            "#282220", "#141211", "#b91c1c", "TACTICS 40K",
            """<circle cx="210" cy="180" r="56" fill="none" stroke="#d4d4d8" stroke-width="12" stroke-dasharray="18 11"/>
               <circle cx="210" cy="180" r="34" fill="#18181b" stroke="#dc2626" stroke-width="6"/>
               <circle cx="210" cy="180" r="12" fill="#f4f4f5"/>""",
        ),
        "xbox-cloud": (
            "#1d2c24", "#101613", "#22c55e", "CLOUD PLAY",
            """<path d="M 156,214 L 266,214 C 286,214 298,200 296,182 C 294,166 281,155 265,155 C 259,131 237,116 212,118 C 188,120 170,138 167,161 C 149,163 136,177 138,195 C 140,206 147,214 156,214 Z" fill="#f4f4f5"/>""",
        ),
    }

    for slug, (c1, c2, acc, tag, art) in covers_spec.items():
        svg_c = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 420 420" width="420" height="420">
          <defs>
            <linearGradient id="cg" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="{c1}"/>
              <stop offset="100%" stop-color="{c2}"/>
            </linearGradient>
            <radialGradient id="cr" cx="50%" cy="38%" r="58%">
              <stop offset="0%" stop-color="{acc}" stop-opacity="0.26"/>
              <stop offset="100%" stop-color="{acc}" stop-opacity="0.0"/>
            </radialGradient>
          </defs>
          <rect width="420" height="420" fill="url(#cg)"/>
          <rect width="420" height="420" fill="url(#cr)"/>
          {art}
          <text x="210" y="302" text-anchor="middle" fill="#a1a1aa" font-family="Sans" font-size="14" font-weight="bold" letter-spacing="2.5">{tag}</text>
        </svg>"""
        s_tmp = os.path.join(COVERS_DIR, f"_{slug}.svg")
        p_tmp = os.path.join(COVERS_DIR, f"{slug}.png")
        j_out = os.path.join(COVERS_DIR, f"{slug}.jpg")
        with open(s_tmp, "w", encoding="utf-8") as f:
            f.write(svg_c)
        render_svg_to_png(s_tmp, p_tmp, 420)
        Image.open(p_tmp).convert("RGB").save(j_out, quality=93)
        os.remove(s_tmp)
        if slug != "steam-deck":
            os.remove(p_tmp)

    # 5. 4 Bottom Bento Action Cards (550x310 smoked titanium + crisp emblem in upper-right)
    bento_specs = {
        "bento_browse": (
            "#202229", "#15161b", "#d94226",
            """<g transform="translate(385, 34)">
                 <rect x="0" y="0" width="38" height="38" rx="9" fill="#f4f4f5" fill-opacity="0.9"/>
                 <rect x="48" y="0" width="38" height="38" rx="9" fill="#d94226" fill-opacity="0.9"/>
                 <rect x="0" y="48" width="38" height="38" rx="9" fill="#71717a" fill-opacity="0.8"/>
                 <rect x="48" y="48" width="38" height="38" rx="9" fill="#a1a1aa" fill-opacity="0.85"/>
               </g>""",
        ),
        "bento_performance": (
            "#24201c", "#151412", "#f59e0b",
            """<polyline points="330,96 368,96 386,52 410,118 432,70 452,96 496,96" fill="none" stroke="#f59e0b" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
               <circle cx="496" cy="96" r="6" fill="#f4f4f5"/>""",
        ),
        "bento_store": (
            "#241d22", "#151215", "#e04828",
            """<g transform="translate(396, 30)">
                 <rect x="8" y="24" width="72" height="62" rx="12" fill="none" stroke="#f4f4f5" stroke-opacity="0.88" stroke-width="6"/>
                 <path d="M 26,24 L 26,16 C 26,6 34,0 44,0 C 54,0 62,6 62,16 L 62,24" fill="none" stroke="#e04828" stroke-width="6"/>
               </g>""",
        ),
        "bento_settings": (
            "#1e2428", "#131619", "#94a3b8",
            """<g transform="translate(390, 32)">
                 <line x1="8" y1="20" x2="86" y2="20" stroke="#71717a" stroke-width="6" stroke-linecap="round"/>
                 <circle cx="32" cy="20" r="10" fill="#f4f4f5"/>
                 <line x1="8" y1="52" x2="86" y2="52" stroke="#71717a" stroke-width="6" stroke-linecap="round"/>
                 <circle cx="62" cy="52" r="10" fill="#e04828"/>
               </g>""",
        ),
    }
    for b_name, (c1, c2, acc, graphic) in bento_specs.items():
        b_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 550 310" width="550" height="310">
          <defs>
            <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="{c1}"/>
              <stop offset="100%" stop-color="{c2}"/>
            </linearGradient>
            <radialGradient id="gl" cx="80%" cy="28%" r="55%">
              <stop offset="0%" stop-color="{acc}" stop-opacity="0.22"/>
              <stop offset="100%" stop-color="{acc}" stop-opacity="0.0"/>
            </radialGradient>
          </defs>
          <rect width="550" height="310" fill="url(#bg)"/>
          <rect width="550" height="310" fill="url(#gl)"/>
          {graphic}
        </svg>"""
        s_tmp = os.path.join(COVERS_DIR, f"_{b_name}.svg")
        p_out = os.path.join(COVERS_DIR, f"{b_name}.png")
        with open(s_tmp, "w", encoding="utf-8") as f:
            f.write(b_svg)
        render_svg_to_png(s_tmp, p_out, 550, 310)
        os.remove(s_tmp)


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

    # Install transparent official Blaze 4-petal logo into pixmaps & blazeos share
    blaze_cutout = os.path.join(ICONS_BASE, "blaze-logo-256.png")
    if os.path.exists(blaze_cutout):
        shutil.copy2(blaze_cutout, os.path.join(pixmaps, "blaze-logo.png"))
        blaze_share = os.path.join(rootfs_dir, "usr", "share", "blazeos")
        os.makedirs(blaze_share, exist_ok=True)
        shutil.copy2(blaze_cutout, os.path.join(blaze_share, "logo.png"))

    # Ensure FireHub PNG is registered across all hicolor sizes
    firehub_png = os.path.join(pixmaps, "firehub.png")
    if os.path.exists(firehub_png):
        img = Image.open(firehub_png).convert("RGBA")
        for sz in sizes:
            resized = img.resize((sz, sz), Image.Resampling.LANCZOS)
            resized.save(os.path.join(hicolor, f"{sz}x{sz}", "apps", "firehub.png"))

    # Copy GameZone covers, Bento graphics, and user_avatar into rootfs
    covers_dst = os.path.join(rootfs_dir, "usr", "share", "solarui", "covers")
    os.makedirs(covers_dst, exist_ok=True)
    for fn in os.listdir(COVERS_DIR):
        shutil.copy2(os.path.join(COVERS_DIR, fn), os.path.join(covers_dst, fn))

    # Copy GameZone nav icons & Settings nav icons into /usr/share/solarui/icons
    solar_icons_dst = os.path.join(rootfs_dir, "usr", "share", "solarui", "icons")
    os.makedirs(solar_icons_dst, exist_ok=True)
    for fn in os.listdir(GZ_ICONS_DIR):
        shutil.copy2(os.path.join(GZ_ICONS_DIR, fn), os.path.join(solar_icons_dst, fn))
    for nav_key in SETTINGS_NAV_ICONS:
        shutil.copy2(
            os.path.join(OUT_DIR, f"{nav_key}.png"),
            os.path.join(solar_icons_dst, f"{nav_key}.png"),
        )

    # Copy GameZone dynamic hero wallpaper into /usr/share/blazeos/wallpapers
    wp_dst = os.path.join(rootfs_dir, "usr", "share", "blazeos", "wallpapers")
    os.makedirs(wp_dst, exist_ok=True)
    hero_p = os.path.join(COVERS_DIR, "xbox_dynamic.png")
    if os.path.exists(hero_p):
        shutil.copy2(hero_p, os.path.join(wp_dst, "xbox_dynamic.png"))

    subprocess.run(["gtk-update-icon-cache", "-f", "-t", hicolor], check=False)


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    build_official_logo_and_fastfetch()
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

    for nav_name, (g1, g2, glow, inner) in SETTINGS_NAV_ICONS.items():
        svg_content = wrap_squircle_svg(g1, g2, glow, inner)
        svg_path = os.path.join(OUT_DIR, f"{nav_name}.svg")
        png_path = os.path.join(OUT_DIR, f"{nav_name}.png")
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(svg_content)
        render_svg_to_png(svg_path, png_path, 56)

    generate_gamezone_assets()

    cols = 7
    rows = (len(preview_tiles) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * 148 + 20, rows * 148 + 20), (16, 17, 20, 255))
    for idx, (_name, p_path) in enumerate(preview_tiles):
        r, c = divmod(idx, cols)
        tile = Image.open(p_path).convert("RGBA")
        sheet.paste(tile, (20 + c * 148, 20 + r * 148), tile)
    sheet.save("/home/darkmorpheus/.gemini/antigravity/brain/37ca2892-cb0d-42ae-993a-ad5a089c6364/lf_00_icon_suite.png")
    print(f"Generated {len(ICONS)} Living Flow app icons, {len(SETTINGS_NAV_ICONS)} Settings badges & GameZone suite")

    rootfs_dir = os.path.join(BLAZE_ROOT, "build", "rootfs")
    if os.path.exists(rootfs_dir):
        install_into_rootfs(rootfs_dir)
        print(f"Installed Living Flow icons & GameZone assets into {rootfs_dir}")


if __name__ == "__main__":
    main()
