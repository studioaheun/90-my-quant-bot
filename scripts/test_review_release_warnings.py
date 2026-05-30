#!/usr/bin/env python3
"""Smoke tests for release warning review CLI safety."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.handoff_commands import (
    DOCKER_BACKEND_START_COMMAND,
    LOCAL_BACKEND_START_COMMAND,
    LOCAL_BACKEND_START_NO_RELOAD_COMMAND,
    backend_health_check_command,
)


REVIEW_RELEASE_WARNINGS = PROJECT_ROOT / "scripts" / "review_release_warnings.py"


def expected_backend_guidance() -> dict[str, str]:
    return {
        "backend": "start the backend before applying reviewed warning actions",
        "local_start_command": LOCAL_BACKEND_START_COMMAND,
        "local_start_no_reload_command": LOCAL_BACKEND_START_NO_RELOAD_COMMAND,
        "docker_start_command": DOCKER_BACKEND_START_COMMAND,
        "health_check_command": backend_health_check_command(),
    }


def write_triage(package_dir: Path) -> None:
    package_dir.mkdir(parents=True)
    (package_dir / "release-warning-triage.json").write_text(
        json.dumps(
            {
                "summary": {"live_beta_archive_missing": True},
                "live_beta_archive": {
                    "status": "missing",
                    "recommended_action": "Archive live-beta closeout evidence after the window.",
                },
                "warning_alerts": [
                    {
                        "id": "warning-1",
                        "title": "Paper guardrail warning",
                        "source": "broker_paper_submission",
                        "rule": "paper_only",
                        "symbol": "SPY",
                        "recommended_action": "Confirm this was intentional.",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def write_clear_triage(package_dir: Path) -> None:
    package_dir.mkdir(parents=True)
    (package_dir / "release-warning-triage.json").write_text(
        json.dumps(
            {
                "summary": {"live_beta_archive_missing": False},
                "live_beta_archive": {
                    "status": "present_or_not_required",
                    "recommended_action": "No live-beta archive warning was reported.",
                },
                "warning_alerts": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


class ReviewReleaseWarningsSmokeTests(unittest.TestCase):
    def test_apply_requires_operator_approved_flag(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(REVIEW_RELEASE_WARNINGS),
                "--package-dir",
                "/tmp/does-not-need-to-exist",
                "--apply",
            ],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("--operator-approved is required with --apply", completed.stdout)

    def test_dry_run_outputs_operator_approved_apply_command(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-warning-review-") as tmp:
            package_dir = Path(tmp) / "package with spaces"
            write_triage(package_dir)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(REVIEW_RELEASE_WARNINGS),
                    "--package-dir",
                    str(package_dir),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            checklist = (package_dir / "release-warning-operator-checklist.md").read_text(encoding="utf-8")
            plan = json.loads((package_dir / "release-warning-actions.json").read_text(encoding="utf-8"))
            actions_markdown = (package_dir / "release-warning-actions.md").read_text(encoding="utf-8")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--apply --operator-approved", checklist)
        self.assertIn("package with spaces'", checklist)
        self.assertIn("## Commands", actions_markdown)
        self.assertIn("--json-only --fail-if-action-needed", actions_markdown)
        self.assertIn("--summary-json-only --fail-if-action-needed", actions_markdown)
        self.assertIn("--pre-approval-sequence-only", actions_markdown)
        self.assertIn("--review-artifacts-only", actions_markdown)
        self.assertFalse(plan["operator_approved"])
        self.assertEqual(plan["mode"], "dry_run")

    def test_no_write_prints_plan_without_mutating_package(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-warning-review-") as tmp:
            package_dir = Path(tmp) / "package"
            write_triage(package_dir)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(REVIEW_RELEASE_WARNINGS),
                    "--package-dir",
                    str(package_dir),
                    "--no-write",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertFalse((package_dir / "release-warning-actions.json").exists())
            self.assertFalse((package_dir / "release-warning-actions.md").exists())
            self.assertFalse((package_dir / "release-warning-operator-checklist.md").exists())

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("PLANNED", completed.stdout)
        self.assertIn("Warning action plan: not written (--no-write)", completed.stdout)
        self.assertIn("Operator checklist: not written (--no-write)", completed.stdout)
        self.assertIn("Recommended next action:", completed.stdout)
        self.assertIn("Recommended next command:", completed.stdout)
        self.assertIn("Recommended next requires operator approval: yes", completed.stdout)
        self.assertIn(f"Backend local start: {LOCAL_BACKEND_START_COMMAND}", completed.stdout)
        self.assertIn(
            f"Backend local start no reload: {LOCAL_BACKEND_START_NO_RELOAD_COMMAND}",
            completed.stdout,
        )
        self.assertIn(f"Backend Docker start: {DOCKER_BACKEND_START_COMMAND}", completed.stdout)
        self.assertIn(f"Backend health check: {backend_health_check_command()}", completed.stdout)
        self.assertIn("Apply command after checklist review:", completed.stdout)
        self.assertIn("--apply --operator-approved", completed.stdout)
        self.assertNotIn("Refreshed tarball", completed.stdout)

    def test_json_only_prints_machine_readable_plan_without_mutating_package(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-warning-review-") as tmp:
            package_dir = Path(tmp) / "package"
            write_triage(package_dir)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(REVIEW_RELEASE_WARNINGS),
                    "--package-dir",
                    str(package_dir),
                    "--json-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertFalse((package_dir / "release-warning-actions.json").exists())
            self.assertFalse((package_dir / "release-warning-actions.md").exists())
            self.assertFalse((package_dir / "release-warning-operator-checklist.md").exists())

        self.assertEqual(completed.returncode, 0, completed.stderr)
        plan = json.loads(completed.stdout)
        self.assertEqual(plan["status"], "planned")
        self.assertEqual(plan["mode"], "dry_run")
        self.assertEqual(plan["summary"]["warning_alerts"], 1)
        self.assertEqual(plan["summary"]["planned"], 1)
        self.assertEqual(plan["summary"]["applied"], 0)
        self.assertTrue(plan["summary"]["action_needed"])
        self.assertIn("planned_acknowledgements", plan["summary"]["action_needed_reasons"])
        self.assertIn("live_beta_archive", plan["summary"]["action_needed_reasons"])
        self.assertEqual(
            plan["commands"]["review"],
            f"python3 scripts/review_release_warnings.py --package-dir {package_dir} --no-write",
        )
        self.assertEqual(
            plan["commands"]["json"],
            f"python3 scripts/review_release_warnings.py --package-dir {package_dir} --json-only",
        )
        self.assertEqual(
            plan["commands"]["gate_json"],
            f"python3 scripts/review_release_warnings.py --package-dir {package_dir} --json-only --fail-if-action-needed",
        )
        self.assertEqual(
            plan["commands"]["summary_json"],
            f"python3 scripts/review_release_warnings.py --package-dir {package_dir} --summary-json-only",
        )
        self.assertEqual(
            plan["commands"]["gate_summary_json"],
            f"python3 scripts/review_release_warnings.py --package-dir {package_dir} --summary-json-only --fail-if-action-needed",
        )
        self.assertEqual(
            plan["commands"]["pre_approval_sequence"],
            f"python3 scripts/review_release_warnings.py --package-dir {package_dir} --pre-approval-sequence-only",
        )
        self.assertEqual(
            plan["commands"]["apply"],
            f"python3 scripts/review_release_warnings.py --package-dir {package_dir} --apply --operator-approved",
        )
        self.assertEqual(
            plan["commands"]["next_command_only"],
            f"python3 scripts/review_release_warnings.py --package-dir {package_dir} --next-command-only",
        )
        self.assertEqual(
            plan["commands"]["review_artifacts_only"],
            f"python3 scripts/review_release_warnings.py --package-dir {package_dir} --review-artifacts-only",
        )
        self.assertEqual(plan["recommended_next"]["id"], "apply_reviewed_warning_actions")
        self.assertEqual(plan["recommended_next"]["command"], plan["commands"]["apply"])
        self.assertTrue(plan["recommended_next"]["requires_operator_approval"])
        self.assertEqual(plan["recommended_next"]["backend"], expected_backend_guidance())
        self.assertEqual(plan["backend"], expected_backend_guidance())
        self.assertEqual(
            plan["recommended_next"]["review_artifacts"]["operator_checklist"],
            str(package_dir / "release-warning-operator-checklist.md"),
        )
        self.assertEqual(
            plan["recommended_next"]["review_artifacts"]["action_plan"],
            str(package_dir / "release-warning-actions.md"),
        )
        self.assertIn("release-warning-actions.json", plan["json_path"])
        self.assertNotIn("Warning action plan:", completed.stdout)
        self.assertNotIn("Apply command after checklist review:", completed.stdout)

    def test_summary_json_only_prints_compact_plan_without_mutating_package(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-warning-review-") as tmp:
            package_dir = Path(tmp) / "package"
            write_triage(package_dir)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(REVIEW_RELEASE_WARNINGS),
                    "--package-dir",
                    str(package_dir),
                    "--summary-json-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertFalse((package_dir / "release-warning-actions.json").exists())
            self.assertFalse((package_dir / "release-warning-actions.md").exists())
            self.assertFalse((package_dir / "release-warning-operator-checklist.md").exists())

        self.assertEqual(completed.returncode, 0, completed.stderr)
        summary = json.loads(completed.stdout)
        self.assertEqual(summary["status"], "planned")
        self.assertTrue(summary["action_needed"])
        self.assertEqual(summary["action_needed_reasons"], ["planned_acknowledgements", "live_beta_archive"])
        self.assertEqual(summary["counts"]["warning_alerts"], 1)
        self.assertEqual(summary["counts"]["planned"], 1)
        self.assertEqual(summary["counts"]["failed"], 0)
        self.assertTrue(summary["counts"]["live_beta_archive_missing"])
        self.assertEqual(summary["recommended_next"]["id"], "apply_reviewed_warning_actions")
        self.assertTrue(summary["recommended_next"]["requires_operator_approval"])
        self.assertEqual(summary["recommended_next"]["command"], summary["commands"]["apply"])
        self.assertEqual(summary["recommended_next"]["backend"], expected_backend_guidance())
        self.assertEqual(summary["backend"], expected_backend_guidance())
        self.assertEqual(
            summary["commands"]["gate_summary_json"],
            f"python3 scripts/review_release_warnings.py --package-dir {package_dir} --summary-json-only --fail-if-action-needed",
        )
        self.assertEqual(
            summary["commands"]["pre_approval_sequence"],
            f"python3 scripts/review_release_warnings.py --package-dir {package_dir} --pre-approval-sequence-only",
        )
        self.assertIn("release-warning-operator-checklist.md", summary["operator_checklist_path"])

    def test_clear_triage_status_does_not_require_operator_action(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-warning-review-") as tmp:
            package_dir = Path(tmp) / "package"
            write_clear_triage(package_dir)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(REVIEW_RELEASE_WARNINGS),
                    "--package-dir",
                    str(package_dir),
                    "--summary-json-only",
                    "--fail-if-action-needed",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        summary = json.loads(completed.stdout)
        self.assertEqual(summary["status"], "clear")
        self.assertFalse(summary["action_needed"])
        self.assertEqual(summary["counts"]["warning_alerts"], 0)
        self.assertEqual(summary["counts"]["planned"], 0)
        self.assertEqual(summary["recommended_next"]["id"], "gate_warning_actions_clear")
        self.assertFalse(summary["recommended_next"]["requires_operator_approval"])
        self.assertIn("--json-only --fail-if-action-needed", summary["recommended_next"]["command"])

    def test_pre_approval_sequence_only_prints_apply_free_review_commands(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-warning-review-") as tmp:
            package_dir = Path(tmp) / "package"
            write_triage(package_dir)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(REVIEW_RELEASE_WARNINGS),
                    "--package-dir",
                    str(package_dir),
                    "--pre-approval-sequence-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertFalse((package_dir / "release-warning-actions.json").exists())
            self.assertFalse((package_dir / "release-warning-actions.md").exists())
            self.assertFalse((package_dir / "release-warning-operator-checklist.md").exists())

        self.assertEqual(completed.returncode, 0, completed.stderr)
        lines = completed.stdout.splitlines()
        self.assertEqual(
            lines,
            [
                f"python3 scripts/review_release_warnings.py --package-dir {package_dir} --summary-json-only",
                f"python3 scripts/review_release_warnings.py --package-dir {package_dir} --review-artifacts-only",
            ],
        )
        self.assertNotIn("--apply", completed.stdout)

    def test_next_command_only_prints_recommended_warning_command(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-warning-review-") as tmp:
            package_dir = Path(tmp) / "package"
            write_triage(package_dir)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(REVIEW_RELEASE_WARNINGS),
                    "--package-dir",
                    str(package_dir),
                    "--next-command-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertFalse((package_dir / "release-warning-actions.json").exists())
            self.assertFalse((package_dir / "release-warning-actions.md").exists())
            self.assertFalse((package_dir / "release-warning-operator-checklist.md").exists())

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            completed.stdout.strip(),
            f"python3 scripts/review_release_warnings.py --package-dir {package_dir} --apply --operator-approved",
        )

    def test_review_artifacts_only_prints_existing_artifact_paths(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-warning-review-") as tmp:
            package_dir = Path(tmp) / "package"
            write_triage(package_dir)
            action_path = package_dir / "release-warning-actions.md"
            checklist_path = package_dir / "release-warning-operator-checklist.md"
            action_path.write_text("actions\n", encoding="utf-8")
            checklist_path.write_text("checklist\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(REVIEW_RELEASE_WARNINGS),
                    "--package-dir",
                    str(package_dir),
                    "--review-artifacts-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.splitlines(), [str(action_path), str(checklist_path)])

    def test_review_artifacts_only_fails_when_artifacts_are_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-warning-review-") as tmp:
            package_dir = Path(tmp) / "package"
            write_triage(package_dir)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(REVIEW_RELEASE_WARNINGS),
                    "--package-dir",
                    str(package_dir),
                    "--review-artifacts-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(
            completed.stdout.splitlines(),
            [
                str(package_dir / "release-warning-actions.md"),
                str(package_dir / "release-warning-operator-checklist.md"),
            ],
        )

    def test_next_command_only_can_fail_when_operator_action_is_needed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-warning-review-") as tmp:
            package_dir = Path(tmp) / "package"
            write_triage(package_dir)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(REVIEW_RELEASE_WARNINGS),
                    "--package-dir",
                    str(package_dir),
                    "--next-command-only",
                    "--fail-if-action-needed",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertFalse((package_dir / "release-warning-actions.json").exists())
            self.assertFalse((package_dir / "release-warning-actions.md").exists())
            self.assertFalse((package_dir / "release-warning-operator-checklist.md").exists())

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(
            completed.stdout.strip(),
            f"python3 scripts/review_release_warnings.py --package-dir {package_dir} --apply --operator-approved",
        )

    def test_json_only_can_fail_when_operator_action_is_needed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-warning-review-") as tmp:
            package_dir = Path(tmp) / "package"
            write_triage(package_dir)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(REVIEW_RELEASE_WARNINGS),
                    "--package-dir",
                    str(package_dir),
                    "--json-only",
                    "--fail-if-action-needed",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertFalse((package_dir / "release-warning-actions.json").exists())
            self.assertFalse((package_dir / "release-warning-actions.md").exists())
            self.assertFalse((package_dir / "release-warning-operator-checklist.md").exists())

        self.assertEqual(completed.returncode, 1, completed.stderr)
        plan = json.loads(completed.stdout)
        self.assertTrue(plan["summary"]["action_needed"])
        self.assertEqual(
            plan["summary"]["action_needed_reasons"],
            ["planned_acknowledgements", "live_beta_archive"],
        )
        self.assertEqual(
            plan["commands"]["gate_json"],
            f"python3 scripts/review_release_warnings.py --package-dir {package_dir} --json-only --fail-if-action-needed",
        )

    def test_summary_json_only_can_fail_when_operator_action_is_needed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-warning-review-") as tmp:
            package_dir = Path(tmp) / "package"
            write_triage(package_dir)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(REVIEW_RELEASE_WARNINGS),
                    "--package-dir",
                    str(package_dir),
                    "--summary-json-only",
                    "--fail-if-action-needed",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertFalse((package_dir / "release-warning-actions.json").exists())
            self.assertFalse((package_dir / "release-warning-actions.md").exists())
            self.assertFalse((package_dir / "release-warning-operator-checklist.md").exists())

        self.assertEqual(completed.returncode, 1, completed.stderr)
        summary = json.loads(completed.stdout)
        self.assertTrue(summary["action_needed"])
        self.assertEqual(
            summary["action_needed_reasons"],
            ["planned_acknowledgements", "live_beta_archive"],
        )
        self.assertEqual(
            summary["commands"]["gate_summary_json"],
            f"python3 scripts/review_release_warnings.py --package-dir {package_dir} --summary-json-only --fail-if-action-needed",
        )

    def test_no_write_prints_existing_action_and_checklist_paths(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-warning-review-") as tmp:
            package_dir = Path(tmp) / "package"
            write_triage(package_dir)
            (package_dir / "release-warning-actions.md").write_text("actions\n", encoding="utf-8")
            (package_dir / "release-warning-operator-checklist.md").write_text("checklist\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(REVIEW_RELEASE_WARNINGS),
                    "--package-dir",
                    str(package_dir),
                    "--no-write",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn(f"Existing warning action plan: {package_dir / 'release-warning-actions.md'}", completed.stdout)
        self.assertIn(
            f"Existing operator checklist: {package_dir / 'release-warning-operator-checklist.md'}",
            completed.stdout,
        )

    def test_no_write_rejects_apply(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-warning-review-") as tmp:
            package_dir = Path(tmp) / "package"
            write_triage(package_dir)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(REVIEW_RELEASE_WARNINGS),
                    "--package-dir",
                    str(package_dir),
                    "--no-write",
                    "--apply",
                    "--operator-approved",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("--no-write cannot be combined with --apply", completed.stdout)

    def test_json_only_rejects_apply(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-warning-review-") as tmp:
            package_dir = Path(tmp) / "package"
            write_triage(package_dir)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(REVIEW_RELEASE_WARNINGS),
                    "--package-dir",
                    str(package_dir),
                    "--json-only",
                    "--apply",
                    "--operator-approved",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("--json-only cannot be combined with --apply", completed.stdout)

    def test_json_only_rejects_next_command_only(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-warning-review-") as tmp:
            package_dir = Path(tmp) / "package"
            write_triage(package_dir)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(REVIEW_RELEASE_WARNINGS),
                    "--package-dir",
                    str(package_dir),
                    "--json-only",
                    "--next-command-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("--json-only cannot be combined with --next-command-only", completed.stdout)

    def test_summary_json_only_rejects_next_command_only(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-warning-review-") as tmp:
            package_dir = Path(tmp) / "package"
            write_triage(package_dir)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(REVIEW_RELEASE_WARNINGS),
                    "--package-dir",
                    str(package_dir),
                    "--summary-json-only",
                    "--next-command-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("--summary-json-only cannot be combined with --next-command-only", completed.stdout)

    def test_json_only_rejects_review_artifacts_only(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-warning-review-") as tmp:
            package_dir = Path(tmp) / "package"
            write_triage(package_dir)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(REVIEW_RELEASE_WARNINGS),
                    "--package-dir",
                    str(package_dir),
                    "--json-only",
                    "--review-artifacts-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("--json-only cannot be combined with --review-artifacts-only", completed.stdout)

    def test_json_only_rejects_summary_json_only(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-warning-review-") as tmp:
            package_dir = Path(tmp) / "package"
            write_triage(package_dir)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(REVIEW_RELEASE_WARNINGS),
                    "--package-dir",
                    str(package_dir),
                    "--json-only",
                    "--summary-json-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("--json-only cannot be combined with --summary-json-only", completed.stdout)


if __name__ == "__main__":
    unittest.main()
