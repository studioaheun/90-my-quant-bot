#!/usr/bin/env python3
"""Smoke tests for evidence package artifact selection."""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_EVIDENCE = PROJECT_ROOT / "scripts" / "package_evidence.py"


def load_package_evidence():
    spec = importlib.util.spec_from_file_location("package_evidence", PACKAGE_EVIDENCE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {PACKAGE_EVIDENCE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class PackageEvidenceSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_package_evidence()

    def test_latest_path_uses_json_generated_at_before_mtime(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-package-evidence-") as tmp:
            root = Path(tmp)
            older_name = root / "verification-20260523-010000.json"
            newer_name = root / "verification-20260523-020000.json"
            write_json(older_name, {"generated_at": "2026-05-23T01:00:00+00:00"})
            write_json(newer_name, {"generated_at": "2026-05-23T02:00:00+00:00"})
            os.utime(newer_name, (1_700_000_000, 1_700_000_000))
            os.utime(older_name, (1_800_000_000, 1_800_000_000))

            selected = self.module.latest_path(str(root / "verification-*.json"))

        self.assertEqual(selected, newer_name)

    def test_latest_path_uses_directory_child_json_generated_at_before_mtime(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-package-evidence-") as tmp:
            root = Path(tmp)
            older_name = root / "ops-smoke-older"
            newer_name = root / "ops-smoke-newer"
            older_name.mkdir()
            newer_name.mkdir()
            write_json(older_name / "ops-smoke-summary.json", {"generated_at": "2026-05-23T01:00:00+00:00"})
            write_json(newer_name / "ops-smoke-summary.json", {"generated_at": "2026-05-23T02:00:00+00:00"})
            os.utime(newer_name, (1_700_000_000, 1_700_000_000))
            os.utime(older_name, (1_800_000_000, 1_800_000_000))

            selected = self.module.latest_path(str(root / "ops-smoke-*"), dirs=True)

        self.assertEqual(selected, newer_name)

    def test_collect_latest_artifacts_selects_newer_generated_verification(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-package-evidence-") as tmp:
            root = Path(tmp)
            package_dir = root / "package"
            older = root / "artifacts" / "verification" / "verification-20260523-010000.json"
            newer = root / "artifacts" / "verification" / "verification-20260523-020000.json"
            write_json(older, {"generated_at": "2026-05-23T01:00:00+00:00", "status": "fail"})
            write_json(newer, {"generated_at": "2026-05-23T02:00:00+00:00", "status": "pass"})
            os.utime(newer, (1_700_000_000, 1_700_000_000))
            os.utime(older, (1_800_000_000, 1_800_000_000))

            included, _missing = self.module.collect_latest_artifacts(
                root=root,
                package_dir=package_dir,
                symbol="KRW-BTC",
            )

            verification = [item for item in included if item["label"] == "verification_summary"]
            self.assertEqual(len(verification), 1)
            self.assertEqual(Path(verification[0]["source"]), newer)
            self.assertTrue((package_dir / "01-verification" / newer.name).is_file())

    def test_read_latest_verification_status_uses_generated_at_before_filename(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-package-evidence-") as tmp:
            package_dir = Path(tmp)
            older_name = package_dir / "01-verification" / "verification-20260523-020000.json"
            newer_name = package_dir / "01-verification" / "verification-20260523-010000.json"
            write_json(older_name, {"generated_at": "2026-05-23T01:00:00+00:00", "status": "fail"})
            write_json(newer_name, {"generated_at": "2026-05-23T02:00:00+00:00", "status": "pass"})
            os.utime(newer_name, (1_700_000_000, 1_700_000_000))
            os.utime(older_name, (1_800_000_000, 1_800_000_000))

            status = self.module.read_latest_verification_status(package_dir)

        self.assertEqual(status, "pass")


if __name__ == "__main__":
    unittest.main()
