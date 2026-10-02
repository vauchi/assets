#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Mattia Egloff <mattia.egloff@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Derive the per-platform pictogram files from the hand-drawn SVGs.

Shells cannot all read SVG with rects, circles and transforms: Android
needs VectorDrawable path data and Windows needs XAML path geometry. So the
drawn sources are flattened into path-only SVG (every shape a <path>, no
transforms), which every shell can consume, plus Android VectorDrawables.

Usage:
  generate.py            write <group>/generated/
  generate.py --check    fail if generated/ is stale
"""

import json
import math
import pathlib
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET

HERE = pathlib.Path(__file__).resolve().parent
SVG_NS = "http://www.w3.org/2000/svg"
NUM = r"-?\d*\.?\d+(?:e-?\d+)?"
ROOT_STROKE = 1.6


def fmt(value):
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def rect_path(x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    if r <= 0:
        return f"M{x} {y}h{w}v{h}h{-w}z"
    return (
        f"M{x + r} {y}H{x + w - r}A{r} {r} 0 0 1 {x + w} {y + r}V{y + h - r}"
        f"A{r} {r} 0 0 1 {x + w - r} {y + h}H{x + r}A{r} {r} 0 0 1 {x} {y + h - r}"
        f"V{y + r}A{r} {r} 0 0 1 {x + r} {y}z"
    )


def circle_path(cx, cy, r):
    return f"M{cx - r} {cy}A{r} {r} 0 1 0 {cx + r} {cy}A{r} {r} 0 1 0 {cx - r} {cy}z"


def to_absolute(d):
    """Parse path data into absolute commands: [(cmd, [numbers])]."""
    tokens = re.findall(rf"[MmLlHhVvCcSsQqTtAaZz]|{NUM}", d)
    out, i, cmd = [], 0, None
    x = y = sx = sy = 0.0
    arity = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7, "Z": 0}
    while i < len(tokens):
        if re.fullmatch(r"[A-Za-z]", tokens[i]):
            cmd = tokens[i]
            i += 1
            if cmd in "Zz":
                out.append(("Z", []))
                x, y = sx, sy
                continue
        n = arity[cmd.upper()]
        args = [float(t) for t in tokens[i : i + n]]
        i += n
        rel = cmd.islower()
        c = cmd.upper()
        if c == "H":
            x = args[0] + (x if rel else 0)
            out.append(("L", [x, y]))
        elif c == "V":
            y = args[0] + (y if rel else 0)
            out.append(("L", [x, y]))
        elif c == "A":
            ex, ey = args[5] + (x if rel else 0), args[6] + (y if rel else 0)
            out.append(("A", args[:5] + [ex, ey]))
            x, y = ex, ey
        else:
            pts = []
            for k in range(0, n, 2):
                pts += [args[k] + (x if rel else 0), args[k + 1] + (y if rel else 0)]
            out.append((c, pts))
            x, y = pts[-2], pts[-1]
            if c == "M":
                sx, sy = x, y
                cmd = "l" if rel else "L"
    return out


def rotation(transform):
    if not transform:
        return None
    m = re.fullmatch(rf"\s*rotate\(\s*({NUM})(?:[\s,]+({NUM})[\s,]+({NUM}))?\s*\)\s*", transform)
    if not m:
        raise SystemExit(f"unsupported transform: {transform}")
    angle = math.radians(float(m.group(1)))
    cx, cy = float(m.group(2) or 0), float(m.group(3) or 0)
    cos, sin = math.cos(angle), math.sin(angle)
    return lambda px, py: (
        cx + (px - cx) * cos - (py - cy) * sin,
        cy + (px - cx) * sin + (py - cy) * cos,
    )


def serialize(commands, rotate):
    parts = []
    for cmd, args in commands:
        if cmd == "Z":
            parts.append("Z")
            continue
        if cmd == "A":
            rx, ry, rot, large, sweep, ex, ey = args
            if rotate:
                ex, ey = rotate(ex, ey)
            parts.append(f"A{fmt(rx)} {fmt(ry)} {fmt(rot)} {int(large)} {int(sweep)} {fmt(ex)} {fmt(ey)}")
            continue
        pts = list(args)
        if rotate:
            for k in range(0, len(pts), 2):
                pts[k], pts[k + 1] = rotate(pts[k], pts[k + 1])
        parts.append(cmd + " ".join(fmt(p) for p in pts))
    return "".join(parts)


def flatten(source):
    """Yield (path_data, stroke_width, filled) for every shape in a source SVG."""
    root = ET.parse(source).getroot()

    def walk(node, transform):
        for child in node:
            tag = child.tag.replace(f"{{{SVG_NS}}}", "")
            t = child.get("transform") or transform
            if tag == "g":
                yield from walk(child, t)
                continue
            f = lambda k, d=0.0: float(child.get(k, d))
            if tag == "path":
                d = child.get("d")
            elif tag == "rect":
                d = rect_path(f("x"), f("y"), f("width"), f("height"), f("rx"))
            elif tag == "circle":
                d = circle_path(f("cx"), f("cy"), f("r"))
            else:
                raise SystemExit(f"{source.name}: unsupported element <{tag}>")
            filled = child.get("fill") == "currentColor"
            width = 0.0 if filled else float(child.get("stroke-width", ROOT_STROKE))
            yield serialize(to_absolute(d), rotation(t)), width, filled

    yield from walk(root, None)


# REUSE-IgnoreStart
HEADER = (
    "SPDX-FileCopyrightText: 2026 Mattia Egloff <mattia.egloff@pm.me>\n"
    "SPDX-License-Identifier: GPL-3.0-or-later\n"
    "Generated by pictograms/generate.py from ../{name}.svg; do not edit."
)
# REUSE-IgnoreEnd


def flat_svg(name, shapes):
    lines = [f"<!-- {line} -->" for line in HEADER.format(name=name).splitlines()]
    lines.append(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" '
        'fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    )
    for d, width, filled in shapes:
        if filled:
            lines.append(f'  <path d="{d}" fill="currentColor" stroke="none"/>')
        else:
            lines.append(f'  <path d="{d}" stroke-width="{fmt(width)}"/>')
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def vector_drawable(name, shapes):
    lines = ['<?xml version="1.0" encoding="utf-8"?>']
    lines += [f"<!-- {line} -->" for line in HEADER.format(name=name).splitlines()]
    lines.append(
        '<vector xmlns:android="http://schemas.android.com/apk/res/android"\n'
        '    android:width="24dp" android:height="24dp"\n'
        '    android:viewportWidth="24" android:viewportHeight="24">'
    )
    for d, width, filled in shapes:
        if filled:
            lines.append(f'    <path android:fillColor="#FF000000" android:pathData="{d}"/>')
        else:
            lines.append(
                f'    <path android:strokeColor="#FF000000" android:strokeWidth="{fmt(width)}"\n'
                '        android:strokeLineCap="round" android:strokeLineJoin="round"\n'
                f'        android:pathData="{d}"/>'
            )
    lines.append("</vector>")
    return "\n".join(lines) + "\n"


def terminal_glyphs(group, names):
    """The group's glyph table, checked: one glyph per pictogram, each a
    single narrow character (ambiguous-width ones turn double in CJK
    terminals and break column alignment)."""
    table = {}
    for line in (group / "terminal.tsv").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        name, glyph = line.split("\t")
        if len(glyph) != 1 or unicodedata.east_asian_width(glyph) not in ("N", "Na", "H"):
            raise SystemExit(f"{group.name}/terminal.tsv: {name} glyph {glyph!r} is not single-width")
        table[name] = glyph
    if sorted(table) != sorted(names):
        raise SystemExit(f"{group.name}/terminal.tsv must list exactly {sorted(names)}, has {sorted(table)}")
    return table


def outputs():
    for group in sorted(p for p in HERE.iterdir() if p.is_dir()):
        sources = sorted(group.glob("*.svg"))
        glyphs = terminal_glyphs(group, [s.stem for s in sources])
        yield (
            group / "generated" / "terminal.json",
            json.dumps({f"pictogram.{group.name}.{k}": v for k, v in sorted(glyphs.items())}, ensure_ascii=False, indent=2)
            + "\n",
        )
        for source in sources:
            shapes = list(flatten(source))
            base = group / "generated"
            yield base / "svg" / source.name, flat_svg(source.stem, shapes)
            android_name = f"pictogram_{group.name}_{source.stem}.xml"
            yield base / "android" / android_name, vector_drawable(source.stem, shapes)


def main():
    check = "--check" in sys.argv[1:]
    stale = []
    for path, text in outputs():
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                stale.append(path.relative_to(HERE))
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    if stale:
        print("generated pictograms are stale; run pictograms/generate.py:", *stale, sep="\n  ")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
