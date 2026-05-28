#!/usr/bin/env python3
"""Smoke tests for connected-runner acceptance helpers."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONNECTED_RUNNER_ACCEPTANCE = PROJECT_ROOT / "scripts" / "connected_runner_acceptance.py"
PACKAGE_CONNECTED_RUNNER_HANDOFF = PROJECT_ROOT / "scripts" / "package_connected_runner_handoff.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ConnectedRunnerAcceptanceSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.acceptance = load_module(CONNECTED_RUNNER_ACCEPTANCE, "connected_runner_acceptance")
        self.handoff = load_module(PACKAGE_CONNECTED_RUNNER_HANDOFF, "package_connected_runner_handoff")

    def test_acceptance_remote_guard_rejects_literal_placeholders(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-acceptance-runner-") as tmp:
            script_path = self.handoff.write_runner_script(Path(tmp))
            script_text = script_path.read_text(encoding="utf-8")
            guard_ok, guard_message, guard_details = self.acceptance.verify_runner_remote_guard(script_text)
            order_ok, order_message, order_details = self.acceptance.verify_runner_script_order(script_text)

        if "bash is unavailable" in guard_message:
            self.skipTest("bash is unavailable")

        self.assertTrue(guard_ok, guard_message)
        self.assertTrue(order_ok, order_message)
        order_rules = {rule["id"]: rule for rule in order_details["rules"]}
        self.assertEqual(
            order_rules["remote_validate_call_before_command_preflight"]["status"],
            "pass",
        )
        missing_markers = [
            marker for marker in self.acceptance.RUNNER_SCRIPT_MARKERS if marker not in script_text
        ]
        self.assertEqual(missing_markers, [])
        cases = {case["case"]: case for case in guard_details["cases"]}
        self.assertIn("placeholder", cases)
        self.assertIn("legacy_placeholder", cases)
        self.assertIn("placeholder_repo_url", cases)
        self.assertIn("placeholder_env_name", cases)
        self.assertIn("missing_https_host", cases)
        self.assertIn("missing_ssh_host", cases)
        self.assertIn("missing_scp_host", cases)
        self.assertIn("missing_remote_path", cases)
        self.assertIn("not a placeholder value", cases["placeholder"]["output"])
        self.assertTrue(cases["placeholder"]["preflight_only"])
        self.assertIn("not a placeholder value", cases["legacy_placeholder"]["output"])
        self.assertIn("not a placeholder value", cases["placeholder_repo_url"]["output"])
        self.assertIn("not a placeholder value", cases["placeholder_env_name"]["output"])
        self.assertIn("HTTPS, SSH, or scp-style", cases["missing_https_host"]["output"])
        self.assertIn("HTTPS, SSH, or scp-style", cases["missing_ssh_host"]["output"])
        self.assertIn("HTTPS, SSH, or scp-style", cases["missing_scp_host"]["output"])
        self.assertIn("HTTPS, SSH, or scp-style", cases["missing_remote_path"]["output"])

    def test_acceptance_order_fails_when_remote_validate_call_is_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-acceptance-runner-") as tmp:
            script_path = self.handoff.write_runner_script(Path(tmp))
            script_text = script_path.read_text(encoding="utf-8")

        mutated_script = script_text.replace(
            self.acceptance.RUNNER_REMOTE_VALIDATE_CALL_MARKER,
            "\nBRANCH_NAME=",
        )
        order_ok, order_message, order_details = self.acceptance.verify_runner_script_order(mutated_script)
        order_rules = {rule["id"]: rule for rule in order_details["rules"]}

        self.assertFalse(order_ok)
        self.assertIn("remote_validate_call_before_command_preflight", order_message)
        self.assertEqual(order_rules["remote_validate_call_before_command_preflight"]["status"], "fail")

    def test_cli_json_only_prints_parseable_failure_report(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-acceptance-json-") as tmp:
            source_root = Path(tmp) / "source"
            output_dir = Path(tmp) / "acceptance"
            (source_root / "scripts").mkdir(parents=True)
            (source_root / "scripts" / "release_gate.py").write_text("", encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(CONNECTED_RUNNER_ACCEPTANCE),
                    "--source-root",
                    str(source_root),
                    "--output-dir",
                    str(output_dir),
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
            self.assertEqual(payload["source_root"], str(source_root.absolute()))
            self.assertTrue(Path(payload["json_path"]).is_file())
            self.assertTrue(Path(payload["markdown_path"]).is_file())
            self.assertNotIn("Connected-runner acceptance:", completed.stdout)

    def test_cli_summary_json_only_omits_verbose_check_details(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-acceptance-summary-json-") as tmp:
            source_root = Path(tmp) / "source"
            output_dir = Path(tmp) / "acceptance"
            (source_root / "scripts").mkdir(parents=True)
            (source_root / "scripts" / "release_gate.py").write_text("", encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(CONNECTED_RUNNER_ACCEPTANCE),
                    "--source-root",
                    str(source_root),
                    "--output-dir",
                    str(output_dir),
                    "--summary-json-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 1)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "fail")
            self.assertEqual(payload["source_root"], str(source_root.absolute()))
            self.assertGreater(payload["check_summary"]["counts"]["fail"], 0)
            self.assertIn("failures", payload["check_summary"])
            self.assertNotIn("checks", payload)
            self.assertTrue(Path(payload["json_path"]).is_file())
            self.assertNotIn("Connected-runner acceptance:", completed.stdout)

    def test_expected_handoff_commands_quote_paths(self) -> None:
        bundle_dir = Path("/tmp/quant handoff bundle")
        package_dir = Path("/tmp/quant evidence package")

        self.assertEqual(
            self.acceptance.connected_runner_preflight_command(bundle_dir),
            "cd '/tmp/quant handoff bundle' && "
            "PREFLIGHT_ONLY=true GIT_ORIGIN_URL=REPLACE_WITH_REPO_URL ./run-connected-runner-handoff.sh",
        )
        self.assertEqual(
            self.acceptance.connected_runner_verify_command(bundle_dir),
            "python3 scripts/package_connected_runner_handoff.py --verify '/tmp/quant handoff bundle'",
        )
        self.assertEqual(
            self.acceptance.connected_runner_verify_json_command(bundle_dir),
            "python3 scripts/package_connected_runner_handoff.py --verify '/tmp/quant handoff bundle' --json-only",
        )
        self.assertEqual(
            self.acceptance.connected_runner_verify_summary_json_command(bundle_dir),
            "python3 scripts/package_connected_runner_handoff.py --verify "
            "'/tmp/quant handoff bundle' --summary-json-only",
        )
        self.assertEqual(
            self.acceptance.connected_runner_acceptance_command(),
            "python3 scripts/connected_runner_acceptance.py --handoff-root .. --require-external --check-gh-auth",
        )
        self.assertEqual(
            self.acceptance.connected_runner_acceptance_json_command(),
            "python3 scripts/connected_runner_acceptance.py --handoff-root .. --require-external --check-gh-auth --json-only",
        )
        self.assertEqual(
            self.acceptance.connected_runner_acceptance_summary_json_command(),
            "python3 scripts/connected_runner_acceptance.py --handoff-root .. "
            "--require-external --check-gh-auth --summary-json-only",
        )
        self.assertEqual(
            self.acceptance.read_only_evidence_check_command(package_dir),
            "python3 scripts/check_release_evidence.py --package-dir '/tmp/quant evidence package' --no-write",
        )
        self.assertEqual(
            self.acceptance.verify_evidence_checksums_json_command(package_dir),
            "python3 scripts/write_evidence_checksums.py --package-dir '/tmp/quant evidence package' --verify --json-only",
        )
        self.assertEqual(
            self.acceptance.release_status_progress_command(package_dir),
            "python3 scripts/report_release_status.py --package-dir '/tmp/quant evidence package' --progress-only",
        )
        self.assertEqual(
            self.acceptance.release_status_progress_json_command(package_dir),
            "python3 scripts/report_release_status.py --package-dir '/tmp/quant evidence package' --progress-json-only",
        )
        self.assertEqual(
            self.acceptance.read_only_warning_review_command(package_dir),
            "python3 scripts/review_release_warnings.py --package-dir '/tmp/quant evidence package' --no-write",
        )
        self.assertEqual(
            self.acceptance.warning_review_json_command(package_dir),
            "python3 scripts/review_release_warnings.py --package-dir '/tmp/quant evidence package' --json-only",
        )
        self.assertEqual(
            self.acceptance.warning_review_gate_json_command(package_dir),
            "python3 scripts/review_release_warnings.py --package-dir '/tmp/quant evidence package' --json-only --fail-if-action-needed",
        )
        self.assertEqual(
            self.acceptance.warning_review_artifacts_only_command(package_dir),
            "python3 scripts/review_release_warnings.py --package-dir '/tmp/quant evidence package' --review-artifacts-only",
        )
        self.assertEqual(
            self.acceptance.warning_review_next_command_only_command(package_dir),
            "python3 scripts/review_release_warnings.py --package-dir '/tmp/quant evidence package' --next-command-only",
        )
        self.assertEqual(
            self.acceptance.warning_review_next_command_gate_command(package_dir),
            (
                "python3 scripts/review_release_warnings.py --package-dir "
                "'/tmp/quant evidence package' --next-command-only --fail-if-action-needed"
            ),
        )
        self.assertEqual(
            self.acceptance.warning_review_apply_command(package_dir),
            "python3 scripts/review_release_warnings.py --package-dir '/tmp/quant evidence package' --apply --operator-approved",
        )
        self.assertEqual(
            self.acceptance.next_release_local_readiness_command_only_env_command(package_dir),
            (
                "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
                '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --command-only '
                "--fail-if-repo-url-required --local-readiness --fail-if-local-readiness-not-pass"
            ),
        )
        self.assertEqual(
            self.acceptance.LIVE_BETA_PREFLIGHT_COMMAND,
            "python3 scripts/archive_live_beta_closeout.py --api-base http://localhost:8000 "
            "--symbol KRW-BTC --backup-reference /backups/quant-lab.sqlite3 --preflight",
        )
        self.assertEqual(
            self.acceptance.LIVE_BETA_PREFLIGHT_JSON_COMMAND,
            self.acceptance.LIVE_BETA_PREFLIGHT_COMMAND + " --json",
        )
        self.assertEqual(
            self.acceptance.LIVE_BETA_NEXT_COMMAND_ONLY_COMMAND,
            self.acceptance.LIVE_BETA_PREFLIGHT_COMMAND + " --next-command-only",
        )
        self.assertEqual(
            self.acceptance.LIVE_BETA_CLOSEOUT_COMMAND,
            "python3 scripts/archive_live_beta_closeout.py --api-base http://localhost:8000 "
            "--symbol KRW-BTC --backup-reference /backups/quant-lab.sqlite3",
        )
        self.assertEqual(
            self.acceptance.CONNECTED_STRICT_GATE_COMMAND,
            "python3 scripts/release_gate.py --run-smoke --strict-external --check-gh-auth",
        )
        self.assertEqual(
            self.acceptance.LIVE_BETA_FINAL_GATE_COMMAND,
            "python3 scripts/release_gate.py --run-smoke --strict-external --check-gh-auth --require-live-beta",
        )
        self.assertEqual(
            self.acceptance.LOCAL_BACKEND_START_COMMAND,
            "cd backend && . .venv/bin/activate && uvicorn app.main:app --reload",
        )
        self.assertEqual(
            self.acceptance.LOCAL_BACKEND_START_NO_RELOAD_COMMAND,
            "cd backend && . .venv/bin/activate && uvicorn app.main:app",
        )
        self.assertEqual(self.acceptance.DOCKER_BACKEND_START_COMMAND, "docker compose start backend")
        self.assertEqual(
            self.acceptance.backend_health_check_command(),
            "curl -fsS http://localhost:8000/api/health",
        )
        self.assertEqual(
            self.acceptance.next_release_step_command(package_dir),
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package'",
        )
        self.assertEqual(
            self.acceptance.next_release_operator_sequence_command(package_dir),
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            "--owner operator --show-sequence --no-write",
        )
        self.assertEqual(
            self.acceptance.next_release_step_origin_command(package_dir),
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            "--repo-url-from-origin --no-write",
        )
        self.assertEqual(
            self.acceptance.next_release_step_env_command(package_dir),
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            "--repo-url-from-env GIT_ORIGIN_URL --no-write",
        )
        self.assertEqual(
            self.acceptance.next_release_command_only_env_command(package_dir),
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            "--repo-url-from-env GIT_ORIGIN_URL --command-only --fail-if-repo-url-required",
        )
        self.assertEqual(
            self.acceptance.next_release_connected_json_only_env_command(package_dir),
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --json-only '
            "--fail-if-repo-url-required",
        )
        self.assertEqual(
            self.acceptance.next_release_json_only_env_command(package_dir),
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            "--repo-url-from-env GIT_ORIGIN_URL --json-only --fail-if-repo-url-required",
        )
        self.assertEqual(
            self.acceptance.next_release_operator_command_only_command(package_dir),
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            "--owner operator --command-only --fail-if-repo-url-required",
        )
        self.assertEqual(
            self.acceptance.next_release_operator_json_only_command(package_dir),
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            "--owner operator --json-only --fail-if-repo-url-required",
        )
        self.assertEqual(
            self.acceptance.next_release_connected_sequence_origin_command(package_dir),
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            '--owner "connected runner" --repo-url-from-origin --show-sequence --no-write',
        )
        self.assertEqual(
            self.acceptance.next_release_connected_sequence_env_command(package_dir),
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --show-sequence --no-write',
        )
        self.assertEqual(
            self.acceptance.next_release_local_readiness_command(package_dir),
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            '--owner "connected runner" --summary-by-owner --show-sequence '
            "--local-readiness --no-write",
        )
        self.assertEqual(
            self.acceptance.next_release_local_readiness_json_env_command(package_dir),
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --json-only '
            "--fail-if-repo-url-required --local-readiness",
        )
        self.assertEqual(
            self.acceptance.next_release_local_readiness_gate_json_env_command(package_dir),
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --json-only '
            "--fail-if-repo-url-required --local-readiness --fail-if-local-readiness-not-pass",
        )
        self.assertEqual(
            self.acceptance.next_release_local_readiness_setup_sequence_env_command(package_dir),
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL '
            "--local-readiness-setup-sequence-only --fail-if-local-readiness-not-pass",
        )
        self.assertEqual(
            self.acceptance.next_release_local_readiness_command_sequence_env_command(package_dir),
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL '
            "--local-readiness-command-sequence-only --fail-if-local-readiness-not-pass",
        )
        self.assertEqual(
            self.acceptance.next_release_local_readiness_setup_sequence_preview_command(package_dir),
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            '--owner "connected runner" --local-readiness-setup-sequence-only',
        )
        self.assertEqual(
            self.acceptance.next_release_local_readiness_command_sequence_preview_command(package_dir),
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            '--owner "connected runner" --local-readiness-command-sequence-only',
        )

    def test_copied_evidence_commands_accept_release_status_package_dir_string(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-acceptance-copied-evidence-") as tmp:
            root = Path(tmp)
            package_dir = root / "evidence-package"
            package_dir.mkdir()
            handoff_root = root / "handoff"
            handoff_root.mkdir()
            expected_preflight = self.acceptance.connected_runner_preflight_command(handoff_root)
            expected_full = self.acceptance.connected_runner_full_command(handoff_root)
            expected_verify = self.acceptance.connected_runner_verify_command(handoff_root)

            (package_dir / "release-status.md").write_text(
                "\n".join([expected_preflight, expected_full, expected_verify]),
                encoding="utf-8",
            )
            (package_dir / "next-release-step.md").write_text(
                "\n".join([expected_preflight, expected_full]),
                encoding="utf-8",
            )
            (package_dir / "release-status.json").write_text(
                json.dumps(
                    {
                        "connected_runner_handoff_bundle": str(handoff_root),
                        "connected_runner_preflight_command": expected_preflight,
                        "connected_runner_full_command": expected_full,
                        "package_dir": str(package_dir),
                        "remaining_items": [],
                    }
                ),
                encoding="utf-8",
            )
            (package_dir / "next-release-step.json").write_text(
                json.dumps({"next_command": expected_preflight}),
                encoding="utf-8",
            )

            _, _, details, _ = self.acceptance.verify_copied_evidence_handoff_commands(
                handoff_root=handoff_root,
                package_dir=package_dir,
            )

        self.assertEqual(
            details["expected_warning_action_plan_path"],
            str(package_dir / "release-warning-actions.md"),
        )
        self.assertEqual(
            details["expected_warning_operator_checklist_path"],
            str(package_dir / "release-warning-operator-checklist.md"),
        )

    def test_copied_evidence_commands_skip_runner_checks_after_runner_work_clears(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-acceptance-copied-evidence-cleared-") as tmp:
            root = Path(tmp)
            package_dir = root / "evidence-package"
            package_dir.mkdir()
            handoff_root = root / "handoff"
            handoff_root.mkdir()
            expected_preflight = self.acceptance.connected_runner_preflight_command(handoff_root)
            expected_full = self.acceptance.connected_runner_full_command(handoff_root)
            expected_verify = self.acceptance.connected_runner_verify_command(handoff_root)

            (package_dir / "release-status.md").write_text(
                "\n".join([expected_preflight, expected_full, expected_verify]),
                encoding="utf-8",
            )
            (package_dir / "next-release-step.md").write_text(
                "python3 scripts/review_release_warnings.py --no-write",
                encoding="utf-8",
            )
            (package_dir / "release-status.json").write_text(
                json.dumps(
                    {
                        "connected_runner_handoff_bundle": str(handoff_root),
                        "connected_runner_preflight_command": expected_preflight,
                        "connected_runner_full_command": expected_full,
                        "remaining_items": [{"id": "warning_alerts", "owner": "operator"}],
                    }
                ),
                encoding="utf-8",
            )
            (package_dir / "next-release-step.json").write_text(
                json.dumps({"next_command": "python3 scripts/review_release_warnings.py --no-write"}),
                encoding="utf-8",
            )

            status, message, details, _ = self.acceptance.verify_copied_evidence_handoff_commands(
                handoff_root=handoff_root,
                package_dir=package_dir,
            )

        self.assertEqual(status, "pass", message)
        checks = {check["id"]: check for check in details["checks"]}
        self.assertEqual(checks["release_status_connected_runner_items"]["status"], "skipped")
        self.assertEqual(checks["next_release_step_md_preflight_command"]["status"], "skipped")
        self.assertEqual(checks["next_release_step_md_full_command"]["status"], "skipped")
        self.assertEqual(checks["next_release_step_json_preflight_command"]["status"], "skipped")
        self.assertEqual(checks["next_release_step_json_full_command"]["status"], "skipped")

    def test_gitignore_guard_patterns_are_required(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-acceptance-gitignore-") as tmp:
            source_root = Path(tmp)
            (source_root / ".gitignore").write_text(
                "\n".join(self.acceptance.REQUIRED_GITIGNORE_PATTERNS) + "\n",
                encoding="utf-8",
            )
            missing, error = self.acceptance.missing_gitignore_patterns(source_root)
            self.assertEqual(missing, [])
            self.assertIsNone(error)

            (source_root / ".gitignore").write_text(
                "\n".join(
                    pattern
                    for pattern in self.acceptance.REQUIRED_GITIGNORE_PATTERNS
                    if pattern != "artifacts/"
                )
                + "\n",
                encoding="utf-8",
            )
            missing, error = self.acceptance.missing_gitignore_patterns(source_root)
            self.assertEqual(missing, ["artifacts/"])
            self.assertIsNone(error)

    def test_progress_summary_checks_require_resume_commands(self) -> None:
        expected_preflight = "cd /tmp/handoff && PREFLIGHT_ONLY=true GIT_ORIGIN_URL=REPO ./run-connected-runner-handoff.sh"
        expected_next_command_only = "python3 scripts/next_release_step.py --command-only"
        expected_next_json_only = "python3 scripts/next_release_step.py --json-only"
        expected_connected_command_only = "python3 scripts/next_release_step.py --owner connected --command-only"
        expected_connected_sequence = "python3 scripts/next_release_step.py --owner connected --command-sequence-only"
        expected_operator_command_only = "python3 scripts/next_release_step.py --owner operator --command-only"
        expected_operator_sequence = "python3 scripts/next_release_step.py --owner operator --command-sequence-only"
        expected_operator_review_sequence = (
            "python3 scripts/next_release_step.py --owner operator --command-sequence-only --skip-operator-approved"
        )
        expected_operator_json_only = "python3 scripts/next_release_step.py --owner operator --json-only"
        expected_remaining_sequence = "python3 scripts/next_release_step.py --command-sequence-only"
        expected_progress_json = "python3 scripts/report_release_status.py --progress-json-only"
        expected_completion_plan = "python3 scripts/report_release_status.py --completion-plan-only"
        expected_completion_plan_json = "python3 scripts/report_release_status.py --completion-plan-json-only"
        expected_completion_requirements = "python3 scripts/report_release_status.py --completion-requirements-only"
        expected_completion_requirements_json = (
            "python3 scripts/report_release_status.py --completion-requirements-json-only"
        )
        expected_owner_lanes = "python3 scripts/report_release_status.py --owner-lanes-only"
        expected_owner_lanes_json = "python3 scripts/report_release_status.py --owner-lanes-json-only"
        expected_handoff_context_json = "python3 scripts/package_connected_runner_handoff.py --handoff-context-json-only"
        expected_handoff_command_sequence = (
            "python3 scripts/package_connected_runner_handoff.py --handoff-command-sequence-only"
        )
        expected_local_readiness_setup = "python3 scripts/next_release_step.py --local-readiness-setup-sequence-only"
        expected_local_readiness_sequence = "python3 scripts/next_release_step.py --local-readiness-command-sequence-only"
        expected_local_readiness_setup_preview = (
            "python3 scripts/next_release_step.py --local-readiness-setup-sequence-only --preview"
        )
        expected_local_readiness_sequence_preview = (
            "python3 scripts/next_release_step.py --local-readiness-command-sequence-only --preview"
        )
        expected_external_readiness_summary = "python3 scripts/check_external_readiness.py --summary-json-only"
        expected_external_readiness_strict_summary = (
            "python3 scripts/check_external_readiness.py "
            "--require-git-remote --require-docker --require-gh --check-gh-auth --summary-json-only"
        )
        expected_warning_gate_json = "python3 scripts/review_release_warnings.py --json-only --fail-if-action-needed"
        expected_warning_summary_json = "python3 scripts/review_release_warnings.py --summary-json-only"
        expected_warning_gate_summary_json = (
            "python3 scripts/review_release_warnings.py --summary-json-only --fail-if-action-needed"
        )
        expected_warning_review_artifacts_only = "python3 scripts/review_release_warnings.py --review-artifacts-only"
        expected_warning_review_next_command_gate = (
            "python3 scripts/review_release_warnings.py --next-command-only --fail-if-action-needed"
        )
        expected_warning_action_plan = "/tmp/package/release-warning-actions.md"
        expected_warning_checklist = "/tmp/package/release-warning-operator-checklist.md"
        expected_operator_command = "python3 scripts/review_release_warnings.py --no-write"
        payload = {
            "progress_summary": {
                "next_command": expected_preflight,
                "next_item_id": "git_origin_remote",
                "next_item_owner": "connected runner",
                "owner_lanes": {},
                "next_commands_by_owner": {
                    "connected runner": {
                        "id": "git_origin_remote",
                        "command": expected_preflight,
                        "supporting_commands": {
                            "Show connected-runner command only from env": expected_connected_command_only,
                            "Show external readiness summary JSON": expected_external_readiness_summary,
                            "Gate external readiness summary JSON": expected_external_readiness_strict_summary,
                            "Show local readiness setup sequence": expected_local_readiness_setup,
                            "Show local readiness command sequence": expected_local_readiness_sequence,
                            "Preview local readiness setup sequence": expected_local_readiness_setup_preview,
                            "Preview local readiness command sequence": expected_local_readiness_sequence_preview,
                        },
                    },
                    "operator": {
                        "id": "warning_alerts",
                        "command": expected_operator_command,
                        "supporting_commands": {
                            "Show warning summary JSON": expected_warning_summary_json,
                            "Gate warning summary JSON": expected_warning_gate_summary_json,
                            "Show warning review artifact paths": expected_warning_review_artifacts_only,
                            "Gate warning recommended next command": expected_warning_review_next_command_gate,
                        },
                        "review_artifacts": {
                            "action_plan": expected_warning_action_plan,
                            "operator_checklist": expected_warning_checklist,
                        },
                    },
                },
                "commands": {
                    "next_command_only": expected_next_command_only,
                    "next_json_only": expected_next_json_only,
                    "connected_runner_command_only": expected_connected_command_only,
                    "connected_runner_command_sequence": expected_connected_sequence,
                    "operator_command_only": expected_operator_command_only,
                    "operator_command_sequence": expected_operator_sequence,
                    "operator_review_sequence": expected_operator_review_sequence,
                    "operator_json_only": expected_operator_json_only,
                    "remaining_sequence": expected_remaining_sequence,
                    "show_progress_json": expected_progress_json,
                    "show_completion_plan": expected_completion_plan,
                    "show_completion_plan_json": expected_completion_plan_json,
                    "show_completion_requirements": expected_completion_requirements,
                    "show_completion_requirements_json": expected_completion_requirements_json,
                    "show_owner_lanes": expected_owner_lanes,
                    "show_owner_lanes_json": expected_owner_lanes_json,
                    "handoff_context_json": expected_handoff_context_json,
                    "handoff_command_sequence": expected_handoff_command_sequence,
                    "local_readiness_setup_sequence": expected_local_readiness_setup,
                    "local_readiness_command_sequence": expected_local_readiness_sequence,
                    "local_readiness_setup_sequence_preview": expected_local_readiness_setup_preview,
                    "local_readiness_command_sequence_preview": expected_local_readiness_sequence_preview,
                    "external_readiness_summary_json": expected_external_readiness_summary,
                    "external_readiness_strict_summary_json": expected_external_readiness_strict_summary,
                    "warning_gate_json": expected_warning_gate_json,
                    "warning_summary_json": expected_warning_summary_json,
                    "warning_gate_summary_json": expected_warning_gate_summary_json,
                    "warning_next_command_gate": expected_warning_review_next_command_gate,
                    "warning_review_artifacts": expected_warning_review_artifacts_only,
                },
                "warning_review": {
                    "summary_json": expected_warning_summary_json,
                    "review_artifacts_command": expected_warning_review_artifacts_only,
                    "review_sequence_command": expected_operator_review_sequence,
                    "pre_approval_review_sequence": [
                        expected_warning_summary_json,
                        expected_warning_review_artifacts_only,
                    ],
                },
            }
        }

        checks: list[dict[str, object]] = []
        self.acceptance.progress_summary_checks(
            checks,
            payload=payload,
            expected_preflight=expected_preflight,
            expected_next_command_only=expected_next_command_only,
            expected_next_json_only=expected_next_json_only,
            expected_connected_command_only=expected_connected_command_only,
            expected_connected_command_sequence=expected_connected_sequence,
            expected_operator_command_only=expected_operator_command_only,
            expected_operator_command_sequence=expected_operator_sequence,
            expected_operator_review_sequence=expected_operator_review_sequence,
            expected_operator_json_only=expected_operator_json_only,
            expected_remaining_sequence=expected_remaining_sequence,
            expected_progress_json=expected_progress_json,
            expected_completion_plan=expected_completion_plan,
            expected_completion_plan_json=expected_completion_plan_json,
            expected_completion_requirements=expected_completion_requirements,
            expected_completion_requirements_json=expected_completion_requirements_json,
            expected_owner_lanes=expected_owner_lanes,
            expected_owner_lanes_json=expected_owner_lanes_json,
            expected_handoff_context_json=expected_handoff_context_json,
            expected_handoff_command_sequence=expected_handoff_command_sequence,
            expected_local_readiness_setup_sequence=expected_local_readiness_setup,
            expected_local_readiness_command_sequence=expected_local_readiness_sequence,
            expected_local_readiness_setup_sequence_preview=expected_local_readiness_setup_preview,
            expected_local_readiness_command_sequence_preview=expected_local_readiness_sequence_preview,
            expected_external_readiness_summary_json=expected_external_readiness_summary,
            expected_external_readiness_strict_summary_json=expected_external_readiness_strict_summary,
            expected_warning_gate_json=expected_warning_gate_json,
            expected_warning_summary_json=expected_warning_summary_json,
            expected_warning_gate_summary_json=expected_warning_gate_summary_json,
            expected_warning_review_artifacts_only=expected_warning_review_artifacts_only,
            expected_warning_review_next_command_gate=expected_warning_review_next_command_gate,
            expected_warning_action_plan_path=expected_warning_action_plan,
            expected_warning_operator_checklist_path=expected_warning_checklist,
            expected_operator_command=expected_operator_command,
        )
        checks_by_id = {check["id"]: check for check in checks}

        self.assertEqual(checks_by_id["release_status_json_progress_summary_next_command"]["status"], "pass")
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_connected_runner_next"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_connected_runner_command_only"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id[
                "release_status_json_progress_summary_connected_runner_external_readiness_summary_json"
            ]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id[
                "release_status_json_progress_summary_connected_runner_external_readiness_strict_summary_json"
            ]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_connected_runner_local_readiness_setup_sequence"][
                "status"
            ],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_connected_runner_local_readiness_command_sequence"][
                "status"
            ],
            "pass",
        )
        self.assertEqual(
            checks_by_id[
                "release_status_json_progress_summary_connected_runner_local_readiness_setup_sequence_preview"
            ]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id[
                "release_status_json_progress_summary_connected_runner_local_readiness_command_sequence_preview"
            ]["status"],
            "pass",
        )
        self.assertEqual(checks_by_id["release_status_json_progress_summary_operator_next"]["status"], "pass")
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_operator_review_artifacts"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_operator_next_command_gate"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_operator_action_plan_path"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_operator_checklist_path"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_command_connected_runner_command_only"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_command_next_command_only"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_command_next_json_only"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_command_show_completion_plan"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_command_show_completion_plan_json"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_command_show_completion_requirements"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_command_show_completion_requirements_json"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_command_show_owner_lanes"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_command_show_owner_lanes_json"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_owner_lanes_object"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_command_connected_runner_command_sequence"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_command_operator_command_only"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_command_operator_json_only"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_command_external_readiness_summary_json"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id[
                "release_status_json_progress_summary_command_external_readiness_strict_summary_json"
            ]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_command_warning_summary_json"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_command_warning_gate_summary_json"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_operator_summary_json"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_operator_summary_json_gate"]["status"],
            "pass",
        )

        payload["progress_summary"]["commands"]["warning_gate_json"] = "stale command"
        failing_checks: list[dict[str, object]] = []
        self.acceptance.progress_summary_checks(
            failing_checks,
            payload=payload,
            expected_preflight=expected_preflight,
            expected_next_command_only=expected_next_command_only,
            expected_next_json_only=expected_next_json_only,
            expected_connected_command_only=expected_connected_command_only,
            expected_connected_command_sequence=expected_connected_sequence,
            expected_operator_command_only=expected_operator_command_only,
            expected_operator_command_sequence=expected_operator_sequence,
            expected_operator_review_sequence=expected_operator_review_sequence,
            expected_operator_json_only=expected_operator_json_only,
            expected_remaining_sequence=expected_remaining_sequence,
            expected_progress_json=expected_progress_json,
            expected_completion_plan=expected_completion_plan,
            expected_completion_plan_json=expected_completion_plan_json,
            expected_completion_requirements=expected_completion_requirements,
            expected_completion_requirements_json=expected_completion_requirements_json,
            expected_owner_lanes=expected_owner_lanes,
            expected_owner_lanes_json=expected_owner_lanes_json,
            expected_handoff_context_json=expected_handoff_context_json,
            expected_handoff_command_sequence=expected_handoff_command_sequence,
            expected_local_readiness_setup_sequence=expected_local_readiness_setup,
            expected_local_readiness_command_sequence=expected_local_readiness_sequence,
            expected_local_readiness_setup_sequence_preview=expected_local_readiness_setup_preview,
            expected_local_readiness_command_sequence_preview=expected_local_readiness_sequence_preview,
            expected_external_readiness_summary_json=expected_external_readiness_summary,
            expected_external_readiness_strict_summary_json=expected_external_readiness_strict_summary,
            expected_warning_gate_json=expected_warning_gate_json,
            expected_warning_summary_json=expected_warning_summary_json,
            expected_warning_gate_summary_json=expected_warning_gate_summary_json,
            expected_warning_review_artifacts_only=expected_warning_review_artifacts_only,
            expected_warning_review_next_command_gate=expected_warning_review_next_command_gate,
            expected_warning_action_plan_path=expected_warning_action_plan,
            expected_warning_operator_checklist_path=expected_warning_checklist,
            expected_operator_command=expected_operator_command,
        )
        failing_by_id = {check["id"]: check for check in failing_checks}
        self.assertEqual(
            failing_by_id["release_status_json_progress_summary_command_warning_gate_json"]["status"],
            "fail",
        )

    def test_handoff_readme_completion_context_is_checked_against_release_status(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-acceptance-handoff-") as tmp:
            root = Path(tmp)
            handoff_root = root / "handoff"
            package_dir = handoff_root / "evidence" / "package"
            package_dir.mkdir(parents=True)
            release_status = {
                "status": "warn",
                "readiness_estimate": {
                    "percent": 94,
                    "remaining_items": 6,
                    "deductions": [
                        {
                            "id": "external_readiness_warnings",
                            "points": 3,
                            "detail": "3 external readiness warning check(s) remain.",
                            "check_ids": ["git_origin_remote", "docker_cli", "github_cli"],
                        }
                    ],
                },
                "progress_summary": {
                    "completion_requirements": [
                        {
                            "requirement": "connected_runner",
                            "item_ids": ["git_origin_remote", "docker_cli", "github_cli"],
                            "owners": ["connected runner"],
                            "count": 3,
                        }
                    ]
                },
            }
            (package_dir / "release-status.json").write_text(
                json.dumps(release_status) + "\n",
                encoding="utf-8",
            )
            (handoff_root / "HANDOFF.md").write_text(
                "\n".join(
                    [
                        "- Overall status: `warn`",
                        "- Approximate completion: `94%`",
                        "- Remaining handoff items: `6`",
                        "`external_readiness_warnings`: -3 point(s). 3 external readiness warning check(s) remain. Source checks: git_origin_remote, docker_cli, github_cli.",
                        "`connected_runner`: 3 items [connected runner] items: git_origin_remote, docker_cli, github_cli",
                    ]
                ),
                encoding="utf-8",
            )

            status, message, details, evidence = self.acceptance.verify_handoff_readme_completion_context(
                handoff_root=handoff_root,
                package_dir=package_dir,
            )
            self.assertEqual(status, "pass", message)
            self.assertEqual(details["missing_markers"], [])
            self.assertEqual(evidence, str(handoff_root / "HANDOFF.md"))

            (handoff_root / "HANDOFF.md").write_text(
                (handoff_root / "HANDOFF.md").read_text(encoding="utf-8").replace("`94%`", "`95%`"),
                encoding="utf-8",
            )
            stale_status, stale_message, stale_details, _ = self.acceptance.verify_handoff_readme_completion_context(
                handoff_root=handoff_root,
                package_dir=package_dir,
            )
            self.assertEqual(stale_status, "fail")
            self.assertIn("Approximate completion", stale_message)
            self.assertIn("- Approximate completion: `94%`", stale_details["missing_markers"])

    def test_handoff_root_source_is_preferred_when_source_root_is_omitted(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-acceptance-source-") as tmp:
            root = Path(tmp)
            handoff_source = root / "handoff" / "source"
            local_source = root / "local"
            (handoff_source / "scripts").mkdir(parents=True)
            (local_source / "scripts").mkdir(parents=True)
            (handoff_source / "scripts" / "release_gate.py").write_text("", encoding="utf-8")
            (local_source / "scripts" / "release_gate.py").write_text("", encoding="utf-8")
            args = type(
                "Args",
                (),
                {
                    "source_root": None,
                    "handoff_root": str(root / "handoff"),
                },
            )()
            previous_cwd = Path.cwd()
            try:
                import os

                os.chdir(local_source)
                source_root = self.acceptance.detect_source_root(args)
            finally:
                os.chdir(previous_cwd)

        self.assertEqual(source_root, handoff_source.absolute())

    def test_verify_evidence_archive_accepts_sibling_package_archive(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-acceptance-archive-") as tmp:
            root = Path(tmp)
            package_dir = root / "package"
            archive_source = root / "archive-source" / package_dir.name
            archive_source.mkdir(parents=True)
            package_dir.mkdir()
            for filename in ("manifest.json", "release-status.md", "evidence-checksums.json"):
                (archive_source / filename).write_text(f"{filename}\n", encoding="utf-8")

            archive = package_dir.with_name(f"{package_dir.name}.tgz")
            with tarfile.open(archive, "w:gz") as tar:
                tar.add(archive_source, arcname=package_dir.name)
            sidecar = archive.with_suffix(archive.suffix + ".sha256")
            sidecar.write_text(f"{self.acceptance.sha256_file(archive)}  {archive.name}\n", encoding="utf-8")

            status, message = self.acceptance.verify_evidence_archive(package_dir)

        self.assertEqual(status, "pass", message)
        self.assertIn(str(archive), message)


if __name__ == "__main__":
    unittest.main()
