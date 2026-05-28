#!/usr/bin/env python3
"""Smoke tests for release artifact selection helpers."""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RELEASE_ARTIFACTS = PROJECT_ROOT / "scripts" / "release_artifacts.py"


def load_release_artifacts():
    spec = importlib.util.spec_from_file_location("release_artifacts", RELEASE_ARTIFACTS)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {RELEASE_ARTIFACTS}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class ReleaseArtifactSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_release_artifacts()

    def test_latest_package_uses_manifest_timestamp_before_mtime(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-release-artifacts-") as tmp:
            packages_dir = Path(tmp)
            older = packages_dir / "20260523-KRW-BTC-beta-001"
            newer = packages_dir / "20260523-KRW-BTC-beta-002"
            older.mkdir()
            newer.mkdir()
            write_json(older / "manifest.json", {"generated_at": "2026-05-23T00:00:00+00:00"})
            write_json(newer / "manifest.json", {"generated_at": "2026-05-23T01:00:00+00:00"})
            os.utime(newer, (1_700_000_000, 1_700_000_000))
            os.utime(older, (1_800_000_000, 1_800_000_000))

            selected = self.module.latest_package_dir(packages_dir, marker_file="manifest.json")

        self.assertEqual(selected.name, "20260523-KRW-BTC-beta-002")

    def test_latest_package_falls_back_to_beta_sequence_before_mtime(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-release-artifacts-") as tmp:
            packages_dir = Path(tmp)
            older = packages_dir / "20260523-KRW-BTC-beta-009"
            newer = packages_dir / "20260523-KRW-BTC-beta-010"
            older.mkdir()
            newer.mkdir()
            write_json(older / "manifest.json", {"generated_at": "not-a-timestamp"})
            write_json(newer / "manifest.json", {"generated_at": "not-a-timestamp"})
            os.utime(newer, (1_700_000_000, 1_700_000_000))
            os.utime(older, (1_800_000_000, 1_800_000_000))

            selected = self.module.latest_package_dir(packages_dir, marker_file="manifest.json")

        self.assertEqual(selected.name, "20260523-KRW-BTC-beta-010")

    def test_latest_package_can_use_release_status_when_manifest_is_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-release-artifacts-") as tmp:
            packages_dir = Path(tmp)
            older = packages_dir / "package-old"
            newer = packages_dir / "package-new"
            older.mkdir()
            newer.mkdir()
            write_json(older / "release-status.json", {"generated_at": "2026-05-23T00:00:00Z"})
            write_json(newer / "release-status.json", {"generated_at": "2026-05-23T01:00:00Z"})
            os.utime(newer, (1_700_000_000, 1_700_000_000))
            os.utime(older, (1_800_000_000, 1_800_000_000))

            selected = self.module.latest_package_dir(
                packages_dir,
                marker_file="release-status.json",
                metadata_files=("manifest.json", "release-status.json"),
            )

        self.assertEqual(selected.name, "package-new")

    def test_latest_package_requires_marker_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-release-artifacts-") as tmp:
            packages_dir = Path(tmp)
            package_dir = packages_dir / "20260523-KRW-BTC-beta-001"
            package_dir.mkdir()
            write_json(package_dir / "manifest.json", {"generated_at": "2026-05-23T00:00:00+00:00"})

            with self.assertRaisesRegex(FileNotFoundError, "release-status.json"):
                self.module.latest_package_dir(packages_dir, marker_file="release-status.json")

    def test_named_latest_package_helpers_use_expected_markers(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-release-artifacts-") as tmp:
            packages_dir = Path(tmp)
            manifest_package = packages_dir / "20260523-KRW-BTC-beta-001"
            status_package = packages_dir / "20260523-KRW-BTC-beta-002"
            warning_package = packages_dir / "20260523-KRW-BTC-beta-003"
            manifest_package.mkdir()
            status_package.mkdir()
            warning_package.mkdir()
            write_json(manifest_package / "manifest.json", {"generated_at": "2026-05-23T00:00:00Z"})
            write_json(status_package / "release-status.json", {"generated_at": "2026-05-23T01:00:00Z"})
            write_json(warning_package / "release-warning-triage.json", {"generated_at": "2026-05-23T02:00:00Z"})

            manifest_selected = self.module.latest_manifest_package_dir(packages_dir)
            status_selected = self.module.latest_release_status_package_dir(packages_dir)
            warning_selected = self.module.latest_warning_triage_package_dir(packages_dir)

        self.assertEqual(manifest_selected, manifest_package)
        self.assertEqual(status_selected, status_package)
        self.assertEqual(warning_selected, warning_package)

    def test_latest_json_artifact_uses_generated_at_before_mtime(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-release-artifacts-") as tmp:
            root = Path(tmp)
            older = root / "release-gate-20260523-010000.json"
            newer = root / "release-gate-20260523-020000.json"
            write_json(older, {"generated_at": "2026-05-23T01:00:00+00:00"})
            write_json(newer, {"generated_at": "2026-05-23T02:00:00+00:00"})
            os.utime(newer, (1_700_000_000, 1_700_000_000))
            os.utime(older, (1_800_000_000, 1_800_000_000))

            selected = self.module.latest_json_file(root, "release-gate-*.json")

        self.assertEqual(selected.name, "release-gate-20260523-020000.json")

    def test_latest_json_artifact_falls_back_to_path_timestamp_before_mtime(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-release-artifacts-") as tmp:
            root = Path(tmp)
            older_dir = root / "20260523-010000"
            newer_dir = root / "20260523-020000"
            older_dir.mkdir()
            newer_dir.mkdir()
            older = older_dir / "external-readiness.json"
            newer = newer_dir / "external-readiness.json"
            write_json(older, {"generated_at": "not-a-timestamp"})
            write_json(newer, {"generated_at": "not-a-timestamp"})
            os.utime(newer, (1_700_000_000, 1_700_000_000))
            os.utime(older, (1_800_000_000, 1_800_000_000))

            selected = self.module.latest_json_file(root, "*/external-readiness.json")

        self.assertEqual(selected, newer)

    def test_latest_artifact_path_uses_child_json_generated_at_for_directories(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-release-artifacts-") as tmp:
            root = Path(tmp)
            older = root / "ops-smoke-old"
            newer = root / "ops-smoke-new"
            older.mkdir()
            newer.mkdir()
            write_json(older / "ops-smoke-summary.json", {"generated_at": "2026-05-23T01:00:00+00:00"})
            write_json(newer / "ops-smoke-summary.json", {"generated_at": "2026-05-23T02:00:00+00:00"})
            os.utime(newer, (1_700_000_000, 1_700_000_000))
            os.utime(older, (1_800_000_000, 1_800_000_000))

            selected = self.module.latest_artifact_path([older, newer])

        self.assertEqual(selected, newer)

    def test_latest_artifact_path_falls_back_to_directory_timestamp(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-release-artifacts-") as tmp:
            root = Path(tmp)
            older = root / "20260523-010000"
            newer = root / "20260523-020000"
            older.mkdir()
            newer.mkdir()
            os.utime(newer, (1_700_000_000, 1_700_000_000))
            os.utime(older, (1_800_000_000, 1_800_000_000))

            selected = self.module.latest_artifact_path([older, newer])

        self.assertEqual(selected, newer)


if __name__ == "__main__":
    unittest.main()
