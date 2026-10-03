# SPDX-FileCopyrightText: 2026 Mattia Egloff <mattia.egloff@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""check-copies.py: a shell's pictogram copies match the generated ones at
the assets revision the shell records (#476)."""

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "check-copies.py"

SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="1.6">\n'
    '  <path d="M1 2L3 4" stroke-width="1.6"/>\n'
    '  <path d="M5 5A1 1 0 1 0 6 5Z" fill="currentColor" stroke="none"/>\n'
    "</svg>\n"
)
ANDROID = (
    '<vector xmlns:android="http://schemas.android.com/apk/res/android">\n'
    '  <path android:strokeColor="#FF000000" android:strokeWidth="1.6" android:pathData="M1 2L3 4"/>\n'
    '  <path android:fillColor="#FF000000" android:pathData="M5 5A1 1 0 1 0 6 5Z"/>\n'
    "</vector>\n"
)


def git(cwd, *args):
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


class CheckCopies(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.assets = self.tmp / "assets"
        generated = self.assets / "pictograms" / "exchange" / "generated"
        (generated / "svg").mkdir(parents=True)
        (generated / "android").mkdir()
        (generated / "svg" / "hover.svg").write_text(SVG)
        (generated / "android" / "pictogram_exchange_hover.xml").write_text(ANDROID)
        (generated / "terminal.json").write_text(json.dumps({"pictogram.exchange.hover": "⧉"}))
        self.shell = self.tmp / "shell"
        (self.shell / "icons").mkdir(parents=True)

    def run_check(self, fmt, template, *extra):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--assets", str(self.assets), "--format", fmt,
             "--copies", str(self.shell / template), *extra],
            capture_output=True,
            text=True,
        )

    def test_a_copy_differing_only_in_colour_and_comments_matches(self):
        copy = "<!-- copied by hand -->\n" + SVG.replace("currentColor", "#000000")
        (self.shell / "icons" / "hover.svg").write_text(copy)
        result = self.run_check("svg", "icons/{name}.svg")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_changed_drawing_fails(self):
        (self.shell / "icons" / "hover.svg").write_text(SVG.replace("M1 2L3 4", "M1 2L3 5"))
        result = self.run_check("svg", "icons/{name}.svg")
        self.assertEqual(result.returncode, 1)
        self.assertIn("hover", result.stdout)

    def test_a_changed_stroke_width_fails(self):
        (self.shell / "icons" / "hover.svg").write_text(SVG.replace('stroke-width="1.6"/>', 'stroke-width="2"/>'))
        self.assertEqual(self.run_check("svg", "icons/{name}.svg").returncode, 1)

    def test_a_missing_copy_fails(self):
        result = self.run_check("svg", "icons/{name}.svg")
        self.assertEqual(result.returncode, 1)
        self.assertIn("missing", result.stdout)

    def test_android_copies_are_compared_by_geometry(self):
        (self.shell / "icons" / "pictogram_exchange_hover.xml").write_text(ANDROID.replace("FF000000", "FF222222"))
        self.assertEqual(self.run_check("android", "icons/pictogram_{group}_{name}.xml").returncode, 0)
        (self.shell / "icons" / "pictogram_exchange_hover.xml").write_text(ANDROID.replace("M1 2L3 4", "M1 2L9 9"))
        self.assertEqual(self.run_check("android", "icons/pictogram_{group}_{name}.xml").returncode, 1)

    def test_terminal_glyphs_must_match_exactly(self):
        (self.shell / "icons" / "glyphs.json").write_text(json.dumps({"pictogram.exchange.hover": "⧉"}))
        self.assertEqual(self.run_check("terminal", "icons/glyphs.json").returncode, 0)
        (self.shell / "icons" / "glyphs.json").write_text(json.dumps({"pictogram.exchange.hover": "#"}))
        self.assertEqual(self.run_check("terminal", "icons/glyphs.json").returncode, 1)

    def test_behind_reports_when_the_recorded_revision_is_older_than_main(self):
        git(self.assets, "init", "-q", "-b", "main")
        git(self.assets, "add", "-A")
        git(self.assets, "commit", "-q", "-m", "first")
        first = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.assets, capture_output=True, text=True).stdout.strip()
        generated = self.assets / "pictograms" / "exchange" / "generated" / "svg" / "hover.svg"
        generated.write_text(SVG.replace("M1 2L3 4", "M1 2L3 6"))
        git(self.assets, "commit", "-q", "-am", "second")

        behind = self.run_check("svg", "icons/{name}.svg", "--behind", first)
        current = self.run_check("svg", "icons/{name}.svg", "--behind", "HEAD")

        self.assertEqual(behind.returncode, 1)
        self.assertIn("behind", behind.stdout)
        self.assertEqual(current.returncode, 0, current.stdout + current.stderr)


if __name__ == "__main__":
    unittest.main()
