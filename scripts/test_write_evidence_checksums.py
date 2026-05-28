#!/usr/bin/env python3
"""Smoke tests for evidence checksum JSON automation output."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WRITE_EVIDENCE_CHECKSUMS = PROJECT_ROOT / "scripts" / "write_evidence_checksums.py"


class WriteEvidenceChecksumsSmokeTests(unittest.TestCase):
    def test_cli_json_only_writes_and_verifies_parseable_checksum_payloads(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-checksums-") as tmp:
            package_dir = Path(tmp) / "package"
            package_dir.mkdir()
            (package_dir / "alpha.txt").write_text("alpha\n", encoding="utf-8")

            write_completed = subprocess.run(
                [
                    sys.executable,
                    str(WRITE_EVIDENCE_CHECKSUMS),
                    "--package-dir",
                    str(package_dir),
                    "--no-refresh-tarball",
                    "--json-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(write_completed.returncode, 0, write_completed.stderr)
            write_payload = json.loads(write_completed.stdout)
            self.assertEqual(write_payload["status"], "pass")
            self.assertEqual(write_payload["mode"], "write")
            self.assertEqual(write_payload["file_count"], 1)
            self.assertTrue((package_dir / "evidence-checksums.json").is_file())
            self.assertTrue((package_dir / "evidence-checksums.sha256").is_file())

            verify_completed = subprocess.run(
                [
                    sys.executable,
                    str(WRITE_EVIDENCE_CHECKSUMS),
                    "--package-dir",
                    str(package_dir),
                    "--verify",
                    "--json-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(verify_completed.returncode, 0, verify_completed.stderr)
            verify_payload = json.loads(verify_completed.stdout)
            self.assertEqual(verify_payload["status"], "pass")
            self.assertEqual(verify_payload["mode"], "verify")
            self.assertEqual(verify_payload["file_count"], 1)
            self.assertEqual(verify_payload["failures"], [])
            self.assertNotIn("Checksum verification:", verify_completed.stdout)

    def test_cli_verify_json_only_reports_missing_checksum_file_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-checksums-") as tmp:
            package_dir = Path(tmp) / "package"
            package_dir.mkdir()
            (package_dir / "alpha.txt").write_text("alpha\n", encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(WRITE_EVIDENCE_CHECKSUMS),
                    "--package-dir",
                    str(package_dir),
                    "--verify",
                    "--json-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 1)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "fail")
            self.assertEqual(payload["mode"], "verify")
            self.assertEqual(payload["failures"], [{"path": "evidence-checksums.json", "reason": "missing"}])
            self.assertEqual(completed.stderr, "")


if __name__ == "__main__":
    unittest.main()
