#!/usr/bin/env python3
"""Smoke tests for the shared connected-runner script contract."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONNECTED_RUNNER_CONTRACT = PROJECT_ROOT / "scripts" / "connected_runner_contract.py"
HANDOFF_COMMANDS = PROJECT_ROOT / "scripts" / "handoff_commands.py"
PACKAGE_CONNECTED_RUNNER_HANDOFF = PROJECT_ROOT / "scripts" / "package_connected_runner_handoff.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ConnectedRunnerContractSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = load_module(CONNECTED_RUNNER_CONTRACT, "connected_runner_contract")
        self.handoff_commands = load_module(HANDOFF_COMMANDS, "handoff_commands")
        self.handoff = load_module(PACKAGE_CONNECTED_RUNNER_HANDOFF, "package_connected_runner_handoff")

    def test_generated_runner_satisfies_shared_contract(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-contract-runner-") as tmp:
            script_path = self.handoff.write_runner_script(Path(tmp))
            script_text = script_path.read_text(encoding="utf-8")

        self.assertEqual(self.contract.missing_runner_script_markers(script_text), [])
        order_ok, order_message, order_details = self.contract.verify_runner_script_order(script_text)
        self.assertTrue(order_ok, order_message)
        order_rules = {rule["id"]: rule for rule in order_details["rules"]}
        self.assertEqual(order_rules["remote_validate_call_before_command_preflight"]["status"], "pass")

        guard_ok, guard_message, guard_details = self.contract.verify_runner_remote_guard(script_text)
        if "bash is unavailable" in guard_message:
            self.skipTest("bash is unavailable")
        self.assertTrue(guard_ok, guard_message)
        self.assertEqual(len(guard_details["cases"]), len(self.contract.RUNNER_REMOTE_GUARD_CASES))

    def test_remote_guard_cases_cover_all_repo_url_placeholders(self) -> None:
        guarded_values = {
            value
            for _, value, _ in self.contract.RUNNER_REMOTE_GUARD_CASES
            if value is not None
        }

        self.assertTrue(set(self.handoff_commands.REPO_URL_PLACEHOLDERS).issubset(guarded_values))

    def test_source_scoped_command_rebases_nested_cd_prefixes(self) -> None:
        command = (
            "cd '/tmp/packaged bundle/source' && "
            "cd '/tmp/older bundle/source' && "
            "python3 -c \"print('keep && inside quotes')\""
        )

        self.assertEqual(
            self.handoff_commands.source_scoped_command(command, Path("/tmp/current bundle/source")),
            "cd '/tmp/current bundle/source' && python3 -c \"print('keep && inside quotes')\"",
        )

    def test_source_scoped_command_handles_commands_without_cd(self) -> None:
        self.assertEqual(
            self.handoff_commands.source_scoped_command(
                "git remote get-url origin",
                Path("/tmp/current bundle/source"),
            ),
            "cd '/tmp/current bundle/source' && git remote get-url origin",
        )

    def test_contract_gitignore_patterns_are_required(self) -> None:
        parsed = self.contract.gitignore_patterns(
            "\n# comment\n.env\n\n node_modules/ \n"
        )
        self.assertEqual(parsed, {".env", "node_modules/"})

        complete_text = "\n".join(self.contract.REQUIRED_GITIGNORE_PATTERNS)
        missing = self.contract.missing_required_gitignore_patterns(complete_text)
        self.assertEqual(missing, [])

        incomplete_text = "\n".join(
            pattern
            for pattern in self.contract.REQUIRED_GITIGNORE_PATTERNS
            if pattern != "artifacts/"
        )
        missing = self.contract.missing_required_gitignore_patterns(incomplete_text)
        self.assertEqual(missing, ["artifacts/"])

        handoff_missing = self.handoff.missing_gitignore_patterns_from_text(incomplete_text)
        self.assertEqual(handoff_missing, ["artifacts/"])

    def test_contract_source_safety_helpers_cover_package_and_acceptance_paths(self) -> None:
        self.assertTrue(
            self.contract.is_packaged_source_excluded(Path("frontend/node_modules/pkg/index.js"))
        )
        self.assertTrue(self.contract.is_packaged_source_excluded(Path("backend/data/prices.parquet")))
        self.assertTrue(self.contract.is_packaged_source_excluded(Path("scripts/__pycache__/x.pyc")))
        self.assertFalse(self.contract.is_packaged_source_excluded(Path("scripts/release_gate.py")))

        self.assertTrue(self.contract.is_forbidden_source_path(Path("backend/data/quant_lab.duckdb")))
        self.assertTrue(self.contract.is_forbidden_source_path(Path("scripts/__pycache__/x.pyc")))
        self.assertFalse(
            self.contract.is_forbidden_source_path(
                Path("frontend/node_modules/pkg/index.js"),
                allowed_prefixes=(Path("frontend/node_modules"),),
            )
        )

    def test_handoff_completion_context_contract_detects_stale_readme(self) -> None:
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
        readme = "\n".join(
            [
                "- Overall status: `warn`",
                "- Approximate completion: `94%`",
                "- Remaining handoff items: `6`",
                "`external_readiness_warnings`: -3 point(s). 3 external readiness warning check(s) remain. Source checks: git_origin_remote, docker_cli, github_cli.",
                "`connected_runner`: 3 items [connected runner] items: git_origin_remote, docker_cli, github_cli",
            ]
        )

        ok, message, details = self.contract.verify_handoff_completion_context(readme, release_status)
        self.assertTrue(ok, message)
        self.assertEqual(details["missing_markers"], [])
        self.assertEqual(
            self.contract.handoff_completion_context_summary_lines(release_status),
            [
                "- Overall status: `warn`",
                "- Approximate completion: `94%`",
                "- Remaining handoff items: `6`",
                "- Completion deductions:",
                "  - `external_readiness_warnings`: -3 point(s). 3 external readiness warning check(s) remain. Source checks: git_origin_remote, docker_cli, github_cli.",
                "- Completion requirements:",
                "  - `connected_runner`: 3 items [connected runner] items: git_origin_remote, docker_cli, github_cli",
            ],
        )

        stale_ok, stale_message, stale_details = self.contract.verify_handoff_completion_context(
            readme.replace("`94%`", "`95%`"),
            release_status,
        )
        self.assertFalse(stale_ok)
        self.assertIn("Approximate completion", stale_message)
        self.assertIn("- Approximate completion: `94%`", stale_details["missing_markers"])

    def test_progress_summary_contract_requires_operator_supporting_commands(self) -> None:
        expected_preflight = "cd /bundle && PREFLIGHT_ONLY=true GIT_ORIGIN_URL=REPLACE_WITH_REPO_URL ./run-connected-runner-handoff.sh"
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
        expected_warning_gate = "python3 scripts/review_release_warnings.py --json-only --fail-if-action-needed"
        expected_warning_summary = "python3 scripts/review_release_warnings.py --summary-json-only"
        expected_warning_gate_summary = (
            "python3 scripts/review_release_warnings.py --summary-json-only --fail-if-action-needed"
        )
        expected_warning_artifacts = "python3 scripts/review_release_warnings.py --review-artifacts-only"
        expected_warning_next_gate = "python3 scripts/review_release_warnings.py --next-command-only --fail-if-action-needed"
        expected_warning_action_plan = "/tmp/quant-evidence/release-warning-actions.md"
        expected_warning_checklist = "/tmp/quant-evidence/release-warning-operator-checklist.md"
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
                            "Show warning summary JSON": expected_warning_summary,
                            "Gate warning summary JSON": expected_warning_gate_summary,
                            "Show warning review artifact paths": expected_warning_artifacts,
                            "Gate warning recommended next command": expected_warning_next_gate,
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
                    "warning_gate_json": expected_warning_gate,
                    "warning_summary_json": expected_warning_summary,
                    "warning_gate_summary_json": expected_warning_gate_summary,
                    "warning_next_command_gate": expected_warning_next_gate,
                    "warning_review_artifacts": expected_warning_artifacts,
                },
                "warning_review": {
                    "summary_json": expected_warning_summary,
                    "review_artifacts_command": expected_warning_artifacts,
                    "review_sequence_command": expected_operator_review_sequence,
                    "pre_approval_review_sequence": [
                        expected_warning_summary,
                        expected_warning_artifacts,
                    ],
                },
            }
        }

        checks: list[dict[str, object]] = []
        self.contract.append_progress_summary_checks(
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
            expected_warning_gate_json=expected_warning_gate,
            expected_warning_summary_json=expected_warning_summary,
            expected_warning_gate_summary_json=expected_warning_gate_summary,
            expected_warning_review_artifacts_only=expected_warning_artifacts,
            expected_warning_review_next_command_gate=expected_warning_next_gate,
            expected_warning_action_plan_path=expected_warning_action_plan,
            expected_warning_operator_checklist_path=expected_warning_checklist,
            expected_operator_command=expected_operator_command,
        )
        checks_by_id = {check["id"]: check for check in checks}
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
            checks_by_id["release_status_json_progress_summary_command_connected_runner_command_only"]["status"],
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
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_operator_review_artifacts"]["status"],
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
            checks_by_id["release_status_json_progress_summary_warning_review_sequence_command"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_warning_review_summary_json"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_warning_review_artifacts_command"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_warning_review_pre_approval_sequence"][
                "status"
            ],
            "pass",
        )

        clear_warning_payload = json.loads(json.dumps(payload))
        clear_warning = clear_warning_payload["progress_summary"]["warning_review"]
        clear_warning["action_needed"] = False
        clear_warning["pre_approval_review_sequence"] = []
        clear_warning_checks: list[dict[str, object]] = []
        self.contract.append_progress_summary_checks(
            clear_warning_checks,
            payload=clear_warning_payload,
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
            expected_warning_gate_json=expected_warning_gate,
            expected_warning_summary_json=expected_warning_summary,
            expected_warning_gate_summary_json=expected_warning_gate_summary,
            expected_warning_review_artifacts_only=expected_warning_artifacts,
            expected_warning_review_next_command_gate=expected_warning_next_gate,
            expected_warning_action_plan_path=expected_warning_action_plan,
            expected_warning_operator_checklist_path=expected_warning_checklist,
            expected_operator_command=expected_operator_command,
        )
        clear_warning_by_id = {check["id"]: check for check in clear_warning_checks}
        self.assertEqual(
            clear_warning_by_id[
                "release_status_json_progress_summary_warning_review_pre_approval_sequence"
            ]["status"],
            "pass",
        )

        live_beta_payload = json.loads(json.dumps(payload))
        live_beta_payload["progress_summary"]["next_commands_by_owner"]["operator"] = {
            "id": "live_beta_archive",
            "command": "python3 scripts/archive_live_beta_closeout.py --preflight",
        }
        live_beta_checks: list[dict[str, object]] = []
        self.contract.append_progress_summary_checks(
            live_beta_checks,
            payload=live_beta_payload,
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
            expected_warning_gate_json=expected_warning_gate,
            expected_warning_summary_json=expected_warning_summary,
            expected_warning_gate_summary_json=expected_warning_gate_summary,
            expected_warning_review_artifacts_only=expected_warning_artifacts,
            expected_warning_review_next_command_gate=expected_warning_next_gate,
            expected_warning_action_plan_path=expected_warning_action_plan,
            expected_warning_operator_checklist_path=expected_warning_checklist,
            expected_operator_command=expected_operator_command,
        )
        live_beta_by_id = {check["id"]: check for check in live_beta_checks}
        self.assertEqual(
            live_beta_by_id["release_status_json_progress_summary_operator_next"]["status"],
            "skipped",
        )
        self.assertFalse([check for check in live_beta_checks if check["status"] == "fail"])

        payload["progress_summary"]["next_commands_by_owner"]["operator"].pop("supporting_commands")
        failing_checks: list[dict[str, object]] = []
        self.contract.append_progress_summary_checks(
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
            expected_warning_gate_json=expected_warning_gate,
            expected_warning_summary_json=expected_warning_summary,
            expected_warning_gate_summary_json=expected_warning_gate_summary,
            expected_warning_review_artifacts_only=expected_warning_artifacts,
            expected_warning_review_next_command_gate=expected_warning_next_gate,
            expected_warning_action_plan_path=expected_warning_action_plan,
            expected_warning_operator_checklist_path=expected_warning_checklist,
            expected_operator_command=expected_operator_command,
        )
        failing_by_id = {check["id"]: check for check in failing_checks}
        self.assertEqual(
            failing_by_id["release_status_json_progress_summary_operator_supporting_commands"]["status"],
            "fail",
        )


if __name__ == "__main__":
    unittest.main()
