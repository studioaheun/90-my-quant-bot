#!/usr/bin/env python3
"""Smoke tests for shared release manifest file lists."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RELEASE_MANIFEST = PROJECT_ROOT / "scripts" / "release_manifest.py"


def load_release_manifest():
    spec = importlib.util.spec_from_file_location("release_manifest", RELEASE_MANIFEST)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {RELEASE_MANIFEST}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReleaseManifestSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_release_manifest()

    def test_manifest_lists_have_no_duplicates(self) -> None:
        for name in (
            "CORE_RELEASE_SCRIPT_FILES",
            "REQUIRED_EVIDENCE_DOC_FILES",
            "EXTRA_RUNBOOK_DOC_FILES",
            "EVIDENCE_RUNBOOK_FILES",
            "REQUIRED_EVIDENCE_DOC_SUFFIXES",
            "HANDOFF_REQUIRED_SOURCE_FILES",
        ):
            values = getattr(self.module, name)
            self.assertEqual(len(values), len(set(values)), f"{name} contains duplicates")

    def test_critical_verification_scripts_are_in_evidence_and_handoff(self) -> None:
        required = {
            "scripts/verify_project.py",
            "scripts/check_completion_audit.py",
            "scripts/test_check_completion_audit.py",
            "scripts/check_frontend_theme.py",
            "scripts/test_check_frontend_theme.py",
            "scripts/check_external_readiness.py",
            "scripts/test_check_external_readiness.py",
            "scripts/run_local_smoke.py",
            "scripts/ops_smoke_check.py",
            "scripts/seed_crypto_drill.py",
            "scripts/write_evidence_checksums.py",
            "scripts/test_write_evidence_checksums.py",
            "scripts/handoff_commands.py",
            "scripts/next_release_step.py",
            "scripts/test_next_release_step.py",
            "scripts/report_release_status.py",
            "scripts/test_report_release_status.py",
            "scripts/connected_runner_contract.py",
            "scripts/test_connected_runner_contract.py",
            "scripts/release_manifest.py",
            "scripts/test_release_manifest.py",
            "scripts/release_gate.py",
            "scripts/test_release_gate.py",
        }

        self.assertTrue(required.issubset(set(self.module.CORE_RELEASE_SCRIPT_FILES)))
        self.assertTrue(required.issubset(set(self.module.EVIDENCE_RUNBOOK_FILES)))
        self.assertTrue(required.issubset(set(self.module.REQUIRED_EVIDENCE_DOC_SUFFIXES)))
        self.assertTrue(required.issubset(set(self.module.HANDOFF_REQUIRED_SOURCE_FILES)))

    def test_required_evidence_docs_are_subset_of_packaged_runbooks(self) -> None:
        self.assertTrue(
            set(self.module.REQUIRED_EVIDENCE_DOC_SUFFIXES).issubset(
                set(self.module.EVIDENCE_RUNBOOK_FILES)
            )
        )


if __name__ == "__main__":
    unittest.main()
