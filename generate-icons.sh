#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Mattia Egloff <mattia.egloff@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Generate platform-specific app icons from the 512x512 source PNG.
#
# Usage: ./generate-icons.sh [--install]
#   --install  Copy generated icons into each repo's expected location
#
# Requirements: sips (macOS built-in), iconutil (macOS built-in), png2ico (optional, for .ico)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="$(dirname "$SCRIPT_DIR")"
SOURCE_PNG="$WORKSPACE/docs/docs/assets/logo.png"
SOURCE_SVG="$WORKSPACE/docs/docs/assets/logo.svg"
OUT_DIR="$SCRIPT_DIR/generated"
INSTALL=false

if [[ "${1:-}" == "--install" ]]; then
    INSTALL=true
fi

if [[ ! -f "$SOURCE_PNG" ]]; then
    echo "ERROR: Source PNG not found at $SOURCE_PNG"
    exit 1
fi

echo "Source: $SOURCE_PNG (512x512)"
echo "Output: $OUT_DIR"
echo ""

rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

# ============================================================
# Helper: resize PNG using sips
# ============================================================
resize() {
    local src="$1" size="$2" dest="$3"
    sips --resampleHeightWidth "$size" "$size" "$src" --out "$dest" >/dev/null 2>&1
}

# ============================================================
# 1. macOS — .icns via iconutil
# ============================================================
echo "=== macOS (.icns) ==="
ICONSET="$OUT_DIR/AppIcon.iconset"
mkdir -p "$ICONSET"

resize "$SOURCE_PNG" 16   "$ICONSET/icon_16x16.png"
resize "$SOURCE_PNG" 32   "$ICONSET/icon_16x16@2x.png"
resize "$SOURCE_PNG" 32   "$ICONSET/icon_32x32.png"
resize "$SOURCE_PNG" 64   "$ICONSET/icon_32x32@2x.png"
resize "$SOURCE_PNG" 128  "$ICONSET/icon_128x128.png"
resize "$SOURCE_PNG" 256  "$ICONSET/icon_128x128@2x.png"
resize "$SOURCE_PNG" 256  "$ICONSET/icon_256x256.png"
resize "$SOURCE_PNG" 512  "$ICONSET/icon_256x256@2x.png"
resize "$SOURCE_PNG" 512  "$ICONSET/icon_512x512.png"
cp "$SOURCE_PNG"          "$ICONSET/icon_512x512@2x.png"  # 1024 would be ideal

iconutil --convert icns "$ICONSET" --output "$OUT_DIR/AppIcon.icns"
echo "  Created AppIcon.icns"

# ============================================================
# 2. iOS — Assets.xcassets/AppIcon.appiconset
# ============================================================
echo "=== iOS (AppIcon.appiconset) ==="
IOS_DIR="$OUT_DIR/ios/AppIcon.appiconset"
mkdir -p "$IOS_DIR"

resize "$SOURCE_PNG" 40   "$IOS_DIR/icon-20@2x.png"
resize "$SOURCE_PNG" 60   "$IOS_DIR/icon-20@3x.png"
resize "$SOURCE_PNG" 58   "$IOS_DIR/icon-29@2x.png"
resize "$SOURCE_PNG" 87   "$IOS_DIR/icon-29@3x.png"
resize "$SOURCE_PNG" 80   "$IOS_DIR/icon-40@2x.png"
resize "$SOURCE_PNG" 120  "$IOS_DIR/icon-40@3x.png"
resize "$SOURCE_PNG" 120  "$IOS_DIR/icon-60@2x.png"
resize "$SOURCE_PNG" 180  "$IOS_DIR/icon-60@3x.png"
resize "$SOURCE_PNG" 76   "$IOS_DIR/icon-76.png"
resize "$SOURCE_PNG" 152  "$IOS_DIR/icon-76@2x.png"
resize "$SOURCE_PNG" 167  "$IOS_DIR/icon-83.5@2x.png"
resize "$SOURCE_PNG" 1024 "$IOS_DIR/icon-1024.png"

cat > "$IOS_DIR/Contents.json" << 'CONTENTS'
{
  "images" : [
    { "filename" : "icon-20@2x.png",   "idiom" : "iphone", "scale" : "2x", "size" : "20x20" },
    { "filename" : "icon-20@3x.png",   "idiom" : "iphone", "scale" : "3x", "size" : "20x20" },
    { "filename" : "icon-29@2x.png",   "idiom" : "iphone", "scale" : "2x", "size" : "29x29" },
    { "filename" : "icon-29@3x.png",   "idiom" : "iphone", "scale" : "3x", "size" : "29x29" },
    { "filename" : "icon-40@2x.png",   "idiom" : "iphone", "scale" : "2x", "size" : "40x40" },
    { "filename" : "icon-40@3x.png",   "idiom" : "iphone", "scale" : "3x", "size" : "40x40" },
    { "filename" : "icon-60@2x.png",   "idiom" : "iphone", "scale" : "2x", "size" : "60x60" },
    { "filename" : "icon-60@3x.png",   "idiom" : "iphone", "scale" : "3x", "size" : "60x60" },
    { "filename" : "icon-76.png",      "idiom" : "ipad",   "scale" : "1x", "size" : "76x76" },
    { "filename" : "icon-76@2x.png",   "idiom" : "ipad",   "scale" : "2x", "size" : "76x76" },
    { "filename" : "icon-83.5@2x.png", "idiom" : "ipad",   "scale" : "2x", "size" : "83.5x83.5" },
    { "filename" : "icon-1024.png",    "idiom" : "ios-marketing", "scale" : "1x", "size" : "1024x1024" }
  ],
  "info" : { "author" : "generate-icons.sh", "version" : 1 }
}
CONTENTS
echo "  Created iOS icon set (12 sizes)"

# ============================================================
# 3. Android — mipmap densities
# ============================================================
echo "=== Android (mipmap) ==="
ANDROID_DIR="$OUT_DIR/android"

for density_size in "mdpi:48" "hdpi:72" "xhdpi:96" "xxhdpi:144" "xxxhdpi:192"; do
    density="${density_size%%:*}"
    size="${density_size##*:}"
    mkdir -p "$ANDROID_DIR/mipmap-$density"
    resize "$SOURCE_PNG" "$size" "$ANDROID_DIR/mipmap-$density/ic_launcher.png"
    resize "$SOURCE_PNG" "$size" "$ANDROID_DIR/mipmap-$density/ic_launcher_round.png"
done

# Store icon
resize "$SOURCE_PNG" 512 "$ANDROID_DIR/store-icon-512.png"
echo "  Created Android mipmap icons (5 densities + store)"

# ============================================================
# 4. Linux (freedesktop) — hicolor icon theme
# ============================================================
echo "=== Linux (hicolor) ==="
LINUX_DIR="$OUT_DIR/linux/icons/hicolor"

for size in 16 24 32 48 64 128 256 512; do
    mkdir -p "$LINUX_DIR/${size}x${size}/apps"
    resize "$SOURCE_PNG" "$size" "$LINUX_DIR/${size}x${size}/apps/vauchi.png"
done

# Also copy SVG for scalable
mkdir -p "$LINUX_DIR/scalable/apps"
cp "$SOURCE_SVG" "$LINUX_DIR/scalable/apps/vauchi.svg"
echo "  Created Linux hicolor icons (8 sizes + scalable SVG)"

# ============================================================
# 5. Windows — .ico (multi-resolution)
# ============================================================
echo "=== Windows (.ico) ==="
WIN_DIR="$OUT_DIR/windows"
mkdir -p "$WIN_DIR"

# Generate individual PNGs for ico
for size in 16 32 48 256; do
    resize "$SOURCE_PNG" "$size" "$WIN_DIR/icon-${size}.png"
done

# Try to create .ico using available tools
if command -v png2ico &>/dev/null; then
    png2ico "$WIN_DIR/vauchi.ico" \
        "$WIN_DIR/icon-16.png" "$WIN_DIR/icon-32.png" \
        "$WIN_DIR/icon-48.png" "$WIN_DIR/icon-256.png"
    echo "  Created vauchi.ico (png2ico)"
elif python3 -c "from PIL import Image" 2>/dev/null; then
    python3 -c "
from PIL import Image
imgs = [Image.open('$WIN_DIR/icon-{}.png'.format(s)) for s in [16,32,48,256]]
imgs[0].save('$WIN_DIR/vauchi.ico', format='ICO', sizes=[(16,16),(32,32),(48,48),(256,256)], append_images=imgs[1:])
"
    echo "  Created vauchi.ico (Pillow)"
else
    echo "  WARNING: No ICO converter found. Generated PNGs only."
    echo "  Install: brew install png2ico  OR  pip install Pillow"
fi

# ============================================================
# 6. Web — favicon + PWA icons
# ============================================================
echo "=== Web (favicon + PWA) ==="
WEB_DIR="$OUT_DIR/web"
mkdir -p "$WEB_DIR"

resize "$SOURCE_PNG" 16  "$WEB_DIR/favicon-16x16.png"
resize "$SOURCE_PNG" 32  "$WEB_DIR/favicon-32x32.png"
resize "$SOURCE_PNG" 180 "$WEB_DIR/apple-touch-icon.png"
resize "$SOURCE_PNG" 192 "$WEB_DIR/icon-192.png"
resize "$SOURCE_PNG" 512 "$WEB_DIR/icon-512.png"
cp "$SOURCE_SVG"         "$WEB_DIR/favicon.svg"

# Generate favicon.ico from 16+32 if possible
if command -v png2ico &>/dev/null; then
    png2ico "$WEB_DIR/favicon.ico" "$WEB_DIR/favicon-16x16.png" "$WEB_DIR/favicon-32x32.png"
    echo "  Created favicon.ico (png2ico)"
elif python3 -c "from PIL import Image" 2>/dev/null; then
    python3 -c "
from PIL import Image
imgs = [Image.open('$WEB_DIR/favicon-{}x{}.png'.format(s,s)) for s in [16,32]]
imgs[0].save('$WEB_DIR/favicon.ico', format='ICO', sizes=[(16,16),(32,32)], append_images=imgs[1:])
"
    echo "  Created favicon.ico (Pillow)"
else
    echo "  WARNING: No ICO converter. favicon.svg available as fallback."
fi

cat > "$WEB_DIR/webmanifest.json" << 'MANIFEST'
{
  "icons": [
    { "src": "/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
MANIFEST
echo "  Created PWA icons (favicon, apple-touch, 192, 512)"

# ============================================================
# 7. GitLab avatar
# ============================================================
echo "=== GitLab avatar ==="
resize "$SOURCE_PNG" 192 "$OUT_DIR/gitlab-avatar.png"
echo "  Created gitlab-avatar.png (192x192)"

# ============================================================
# Summary
# ============================================================
echo ""
echo "=== Generated ==="
find "$OUT_DIR" -type f | sort | while read -r f; do
    echo "  ${f#$OUT_DIR/}"
done
echo ""
echo "Total: $(find "$OUT_DIR" -type f | wc -l | tr -d ' ') files"

# ============================================================
# Install into repos (optional)
# ============================================================
if $INSTALL; then
    echo ""
    echo "=== Installing into repos ==="

    # macOS
    if [[ -d "$WORKSPACE/macos" ]]; then
        mkdir -p "$WORKSPACE/macos/Vauchi/Assets.xcassets/AppIcon.appiconset"
        cp "$OUT_DIR/AppIcon.icns" "$WORKSPACE/macos/Vauchi/"
        cp "$IOS_DIR"/* "$WORKSPACE/macos/Vauchi/Assets.xcassets/AppIcon.appiconset/"
        echo "  macOS: installed .icns + asset catalog"
    fi

    # Linux GTK
    if [[ -d "$WORKSPACE/linux-gtk" ]]; then
        cp -r "$LINUX_DIR" "$WORKSPACE/linux-gtk/data/icons/hicolor" 2>/dev/null || \
        { mkdir -p "$WORKSPACE/linux-gtk/data/icons" && cp -r "$OUT_DIR/linux/icons/hicolor" "$WORKSPACE/linux-gtk/data/icons/"; }
        echo "  linux-gtk: installed hicolor icons"
    fi

    # Linux Qt
    if [[ -d "$WORKSPACE/linux-qt" ]]; then
        cp -r "$LINUX_DIR" "$WORKSPACE/linux-qt/data/icons/hicolor" 2>/dev/null || \
        { mkdir -p "$WORKSPACE/linux-qt/data/icons" && cp -r "$OUT_DIR/linux/icons/hicolor" "$WORKSPACE/linux-qt/data/icons/"; }
        echo "  linux-qt: installed hicolor icons"
    fi

    # Windows
    if [[ -d "$WORKSPACE/windows" ]]; then
        mkdir -p "$WORKSPACE/windows/assets"
        cp "$WIN_DIR"/vauchi.ico "$WORKSPACE/windows/assets/" 2>/dev/null || \
        cp "$WIN_DIR"/icon-*.png "$WORKSPACE/windows/assets/"
        echo "  windows: installed icon"
    fi

    # Web demo
    if [[ -d "$WORKSPACE/web-demo" ]]; then
        mkdir -p "$WORKSPACE/web-demo/public"
        cp "$WEB_DIR"/* "$WORKSPACE/web-demo/public/" 2>/dev/null || true
        echo "  web-demo: installed web icons"
    fi

    echo "  Done."
fi
