#!/usr/bin/env python3
"""Smoke tests for release gate command builders."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RELEASE_GATE = PROJECT_ROOT / "scripts" / "release_gate.py"


def load_release_gate():
    spec = importlib.util.spec_from_file_location("release_gate", RELEASE_GATE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {RELEASE_GATE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReleaseGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_release_gate()

    def test_completion_audit_handoff_bundle_command_points_at_bundle(self) -> None:
        bundle = Path("/tmp/quant handoff bundle")

        command = self.module.completion_audit_handoff_bundle_command(bundle)

        self.assertEqual(
            command,
            [
                sys.executable,
                "scripts/check_completion_audit.py",
                "--handoff-bundle",
                str(bundle),
            ],
        )


if __name__ == "__main__":
    unittest.main()
