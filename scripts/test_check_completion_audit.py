#!/usr/bin/env python3
"""Smoke tests for completion audit context checks."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHECK_COMPLETION_AUDIT = PROJECT_ROOT / "scripts" / "check_completion_audit.py"


def load_check_completion_audit():
    spec = importlib.util.spec_from_file_location("check_completion_audit", CHECK_COMPLETION_AUDIT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {CHECK_COMPLETION_AUDIT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CompletionAuditCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_check_completion_audit()

    def test_current_completion_audit_contains_required_markers(self) -> None:
        report = self.module.check_completion_audit(PROJECT_ROOT / "docs" / "completion-audit.md")

        self.assertEqual(report["status"], "pass")
        statuses = {check["id"]: check["status"] for check in report["checks"]}
        self.assertEqual(statuses["theme_smoke_command"], "pass")
        self.assertEqual(statuses["script_test_count"], "pass")
        self.assertEqual(statuses["latest_package_default"], "pass")
        self.assertEqual(statuses["handoff_manifest_quickstart"], "pass")
        self.assertEqual(statuses["handoff_manifest_completion_plan"], "pass")
        self.assertEqual(statuses["handoff_manifest_completion_requirements"], "pass")
        self.assertEqual(statuses["handoff_manifest_remaining_ids"], "pass")
        self.assertEqual(statuses["handoff_manifest_next_item"], "pass")
        self.assertEqual(statuses["handoff_manifest_owner_lanes"], "pass")
        self.assertEqual(statuses["handoff_manifest_bundle_commands"], "pass")
        self.assertEqual(statuses["handoff_manifest_bundle_sequence"], "pass")
        self.assertEqual(statuses["handoff_manifest_gate_summary"], "pass")
        self.assertEqual(statuses["handoff_manifest_first_gate_by_owner"], "pass")
        self.assertEqual(statuses["handoff_context_json_command"], "pass")
        self.assertEqual(statuses["handoff_command_sequence_command"], "pass")
        self.assertEqual(statuses["handoff_manifest_handoff_context_json"], "pass")
        self.assertEqual(statuses["handoff_manifest_handoff_command_sequence"], "pass")
        self.assertEqual(statuses["handoff_manifest_completion_context_audit"], "pass")
        self.assertEqual(statuses["handoff_manifest_completion_plan_json"], "pass")
        self.assertEqual(statuses["handoff_manifest_completion_requirements_json"], "pass")
        self.assertEqual(statuses["handoff_manifest_progress_json"], "pass")
        self.assertEqual(statuses["handoff_manifest_verify_bundle_summary"], "pass")
        self.assertEqual(statuses["handoff_manifest_acceptance_summary"], "pass")
        self.assertEqual(statuses["handoff_manifest_operator_review_sequence"], "pass")
        self.assertEqual(statuses["handoff_manifest_warning_summary"], "pass")
        self.assertEqual(statuses["handoff_manifest_warning_artifacts"], "pass")
        self.assertEqual(statuses["handoff_manifest_warning_gate"], "pass")
        self.assertEqual(statuses["completion_audit_bundle_command"], "pass")
        self.assertEqual(statuses["progress_summary_warning_review"], "pass")
        self.assertEqual(statuses["progress_summary_completion_plan_pre_approval_sequence"], "pass")
        self.assertEqual(statuses["progress_summary_warning_review_sequence_command"], "pass")
        self.assertEqual(statuses["progress_summary_warning_review_pre_approval_sequence"], "pass")
        self.assertEqual(statuses["progress_summary_warning_review_pre_approval_command"], "pass")
        self.assertEqual(statuses["progress_summary_handoff_context_json"], "pass")
        self.assertEqual(statuses["progress_summary_handoff_command_sequence"], "pass")
        self.assertEqual(statuses["progress_summary_operator_review_sequence"], "pass")
        self.assertEqual(statuses["operator_review_skip_apply"], "pass")
        self.assertEqual(statuses["local_readiness_setup_sequence_preview"], "pass")
        self.assertEqual(statuses["local_readiness_command_sequence_preview"], "pass")

    def test_missing_marker_fails(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-completion-audit-") as tmp:
            audit_path = Path(tmp) / "completion-audit.md"
            audit_path.write_text("96% complete\n", encoding="utf-8")

            report = self.module.check_completion_audit(audit_path)

        self.assertEqual(report["status"], "fail")
        statuses = {check["id"]: check["status"] for check in report["checks"]}
        self.assertEqual(statuses["completion_percent"], "pass")
        self.assertEqual(statuses["theme_smoke_command"], "fail")

    def test_missing_progress_summary_warning_review_marker_fails(self) -> None:
        markers = [
            marker
            for check_id, marker in self.module.REQUIRED_MARKERS
            if check_id
            not in {
                "progress_summary_warning_review",
                "progress_summary_warning_review_sequence_command",
                "progress_summary_warning_review_pre_approval_sequence",
                "progress_summary_warning_review_pre_approval_command",
            }
        ]
        with tempfile.TemporaryDirectory(prefix="quant-completion-audit-") as tmp:
            audit_path = Path(tmp) / "completion-audit.md"
            audit_path.write_text("\n".join(markers), encoding="utf-8")

            report = self.module.check_completion_audit(audit_path)

        self.assertEqual(report["status"], "fail")
        statuses = {check["id"]: check["status"] for check in report["checks"]}
        self.assertEqual(statuses["progress_summary_warning_review"], "fail")
        self.assertEqual(statuses["progress_summary_warning_review_sequence_command"], "fail")
        self.assertEqual(statuses["progress_summary_warning_review_pre_approval_sequence"], "fail")
        self.assertEqual(statuses["progress_summary_warning_review_pre_approval_command"], "fail")
        passing_checks = [
            status
            for check_id, status in statuses.items()
            if check_id
            not in {
                "progress_summary_warning_review",
                "progress_summary_warning_review_sequence_command",
                "progress_summary_warning_review_pre_approval_sequence",
                "progress_summary_warning_review_pre_approval_command",
            }
        ]
        self.assertTrue(all(status == "pass" for status in passing_checks))

    def test_handoff_bundle_command_marker_coverage_passes_for_known_commands(self) -> None:
        markers = [marker for _, marker in self.module.REQUIRED_MARKERS]
        with tempfile.TemporaryDirectory(prefix="quant-completion-audit-") as tmp:
            tmp_path = Path(tmp)
            audit_path = tmp_path / "completion-audit.md"
            bundle_dir = tmp_path / "bundle"
            bundle_dir.mkdir()
            audit_path.write_text("\n".join(markers), encoding="utf-8")
            (bundle_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "handoff_context": {
                            "bundle_commands": {
                                "show_progress_json": "python3 source/scripts/report_release_status.py --progress-json-only"
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            report = self.module.check_completion_audit(audit_path, handoff_bundle=bundle_dir)

        statuses = {check["id"]: check["status"] for check in report["checks"]}
        self.assertEqual(report["status"], "pass")
        self.assertEqual(statuses["handoff_bundle_commands_present"], "pass")
        self.assertEqual(statuses["handoff_bundle_command_marker_show_progress_json"], "pass")

    def test_handoff_bundle_command_marker_coverage_fails_for_untracked_commands(self) -> None:
        markers = [marker for _, marker in self.module.REQUIRED_MARKERS]
        future_marker = "manifest.json handoff_context.bundle_commands.future_helper_json"
        with tempfile.TemporaryDirectory(prefix="quant-completion-audit-") as tmp:
            tmp_path = Path(tmp)
            audit_path = tmp_path / "completion-audit.md"
            bundle_dir = tmp_path / "bundle"
            bundle_dir.mkdir()
            audit_path.write_text("\n".join([*markers, future_marker]), encoding="utf-8")
            (bundle_dir / "manifest.json").write_text(
                json.dumps({"handoff_context": {"bundle_commands": {"future_helper_json": "python3 helper.py"}}}),
                encoding="utf-8",
            )

            report = self.module.check_completion_audit(audit_path, handoff_bundle=bundle_dir)

        statuses = {check["id"]: check["status"] for check in report["checks"]}
        messages = {check["id"]: check["message"] for check in report["checks"]}
        self.assertEqual(report["status"], "fail")
        self.assertEqual(statuses["handoff_bundle_command_marker_future_helper_json"], "fail")
        self.assertIn("Missing REQUIRED_MARKERS entry", messages["handoff_bundle_command_marker_future_helper_json"])


if __name__ == "__main__":
    unittest.main()
