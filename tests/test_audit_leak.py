# -*- coding: utf-8 -*-
"""Tests for audit_leak.py (standard library only)."""

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "audit_leak.py"


def touch_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # The audit only inspects paths, so a non-empty placeholder is enough.
    path.write_bytes(b"not-a-real-image")


class AuditLeakTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "images/base/A").mkdir(parents=True)
        (self.root / "images/base/B").mkdir(parents=True)
        (self.root / "images/novel/A").mkdir(parents=True)
        self.yaml = self.root / "eval_classes.txt"
        self.yaml.write_text("A\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_audit(self, csv_path: Path, extra=None):
        cmd = [
            sys.executable,
            str(SCRIPT),
            "--train-dir", str(self.root / "images/base"),
            "--path-root", str(self.root),
            "--split-csv", str(csv_path),
            "--eval-classes", str(self.yaml),
        ]
        if extra:
            cmd.extend(extra)
        return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")

    def write_csv(self, rows):
        p = self.root / "split.csv"
        with p.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["path", "is_train", "class_id"])
            writer.writerows(rows)
        return p

    def test_leak_returns_2(self):
        touch_image(self.root / "images/base/A/leaked.jpg")
        touch_image(self.root / "images/novel/A/control.jpg")
        csv_path = self.write_csv([
            ["images/base/A/leaked.jpg", 0, "A"],
            ["images/novel/A/control.jpg", 0, "A"],
        ])
        out = self.run_audit(csv_path)
        self.assertEqual(out.returncode, 2, out.stderr)
        self.assertIn("LEAK", out.stdout)

    def test_clean_returns_0(self):
        touch_image(self.root / "images/base/A/train.jpg")
        touch_image(self.root / "images/novel/A/control.jpg")
        csv_path = self.write_csv([
            ["images/novel/A/control.jpg", 0, "A"],
        ])
        out = self.run_audit(csv_path)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("OK", out.stdout)

    def test_training_class_holdout_returns_3(self):
        touch_image(self.root / "images/base/B/train.jpg")
        csv_path = self.write_csv([
            ["images/base/B/train.jpg", 0, "B"],
        ])
        out = self.run_audit(csv_path)
        self.assertEqual(out.returncode, 3, out.stderr)
        self.assertIn("HOLDOUT", out.stdout)

    def test_json_output(self):
        touch_image(self.root / "images/base/A/leaked.jpg")
        csv_path = self.write_csv([
            ["images/base/A/leaked.jpg", 0, "A"],
        ])
        out = self.run_audit(csv_path, ["--json"])
        self.assertEqual(out.returncode, 2, out.stderr)
        data = json.loads(out.stdout)
        self.assertEqual(data["status"], "leak")
        self.assertEqual(data["summary"]["leaked_eval_images"], 1)


if __name__ == "__main__":
    unittest.main()
