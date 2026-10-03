#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Mattia Egloff <mattia.egloff@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Check a shell's pictogram copies against the generated ones (#476).

Each shell keeps its own copies and records, in a REVISION file, the
assets commit they came from. Its CI checks out vauchi/assets at that
commit and runs this script, so a copy edited by hand, or only half
updated, fails the shell's MR without assets moving ever turning an
unrelated MR red. `--behind <rev>` instead reports whether that revision
is older than the checked-out assets, for main and nightly pipelines.

Copies compare by what they draw (path data, fill or stroke, stroke
width), not byte for byte: shells legitimately change colours and
comments (iOS and macOS swap currentColor for black).

Usage:
  check-copies.py --assets DIR --format svg|gtk|android|terminal \\
                  --copies 'path/with/{group}/and/{name}' [--group exchange]
  ... --behind REV   exit 1 if the generated files changed since REV
"""

import argparse
import json
import pathlib
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

NUM = r"-?\d*\.?\d+(?:e-?\d+)?"
ANDROID_NS = "{http://schemas.android.com/apk/res/android}"

# Where each format lives under pictograms/<group>/generated/, and the
# generated file name for a pictogram.
LAYOUT = {
    "svg": ("svg", "{name}.svg"),
    "gtk": ("gtk", "pictogram-{group}-{name}-symbolic.svg"),
    "android": ("android", "pictogram_{group}_{name}.xml"),
}


def normalise(d):
    tokens = re.findall(rf"[A-Za-z]|{NUM}", d)
    return " ".join(t if t.isalpha() else f"{float(t):.3f}" for t in tokens)


def svg_geometry(text):
    root = ET.fromstring(re.sub(r"<!--.*?-->", "", text, flags=re.S))
    default_width = root.get("stroke-width", "1")
    shapes = []
    for node in root.iter():
        if not node.tag.endswith("path"):
            continue
        filled = node.get("fill") not in (None, "none")
        width = None if filled else float(node.get("stroke-width", default_width))
        shapes.append((normalise(node.get("d", "")), "fill" if filled else "stroke", width))
    return shapes


def android_geometry(text):
    root = ET.fromstring(re.sub(r"<!--.*?-->", "", text, flags=re.S))
    shapes = []
    for node in root.iter("path"):
        filled = node.get(f"{ANDROID_NS}fillColor") is not None
        width = None if filled else float(node.get(f"{ANDROID_NS}strokeWidth", "1"))
        shapes.append((normalise(node.get(f"{ANDROID_NS}pathData", "")), "fill" if filled else "stroke", width))
    return shapes


def geometry(fmt, text):
    return android_geometry(text) if fmt == "android" else svg_geometry(text)


def check(assets, fmt, copies, group):
    generated = assets / "pictograms" / group / "generated"
    problems = []
    if fmt == "terminal":
        expected = json.loads((generated / "terminal.json").read_text(encoding="utf-8"))
        copy = pathlib.Path(copies)
        if not copy.exists():
            return [f"missing {copy}"]
        if json.loads(copy.read_text(encoding="utf-8")) != expected:
            problems.append(f"{copy}: glyphs differ from {generated / 'terminal.json'}")
        return problems
    subdir, pattern = LAYOUT[fmt]
    names = sorted(p.stem for p in (generated / "svg").glob("*.svg"))
    for name in names:
        source = generated / subdir / pattern.format(group=group, name=name)
        copy = pathlib.Path(copies.format(group=group, name=name))
        if not copy.exists():
            problems.append(f"missing {copy} (copy of {source.name})")
            continue
        if geometry(fmt, copy.read_text(encoding="utf-8")) != geometry(fmt, source.read_text(encoding="utf-8")):
            problems.append(f"{copy}: draws something other than {source.name} ({name})")
    return problems


def behind(assets, fmt, group, revision):
    subdir = "" if fmt == "terminal" else LAYOUT[fmt][0]
    path = f"pictograms/{group}/generated/{subdir or 'terminal.json'}"
    result = subprocess.run(
        ["git", "-C", str(assets), "diff", "--quiet", revision, "HEAD", "--", path],
        capture_output=True,
        text=True,
    )
    if result.returncode > 1:
        raise SystemExit(f"cannot compare {revision} with HEAD: {result.stderr.strip()}")
    return result.returncode == 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets", required=True, type=pathlib.Path)
    parser.add_argument("--format", required=True, choices=["svg", "gtk", "android", "terminal"])
    parser.add_argument("--copies", required=True)
    parser.add_argument("--group", default="exchange")
    parser.add_argument("--behind", metavar="REV")
    args = parser.parse_args()

    if args.behind:
        if behind(args.assets, args.format, args.group, args.behind):
            print(f"pictogram copies are behind vauchi/assets: generated {args.format} files changed since {args.behind}")
            return 1
        print(f"pictogram copies are current with vauchi/assets ({args.behind})")
        return 0

    problems = check(args.assets, args.format, args.copies, args.group)
    for problem in problems:
        print(problem)
    if problems:
        print("copy the generated files from vauchi/assets at the recorded REVISION")
        return 1
    print("pictogram copies match vauchi/assets")
    return 0


if __name__ == "__main__":
    sys.exit(main())
