#!/usr/bin/env python3
"""Smoke tests for release status report helpers."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_RELEASE_STATUS = PROJECT_ROOT / "scripts" / "report_release_status.py"


def load_report_release_status():
    spec = importlib.util.spec_from_file_location("report_release_status", REPORT_RELEASE_STATUS)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {REPORT_RELEASE_STATUS}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReportReleaseStatusSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_report_release_status()

    def test_live_beta_closeout_command_uses_realistic_backup_reference(self) -> None:
        self.assertNotIn("PATH_TO_BACKUP", self.module.LIVE_BETA_CLOSEOUT_COMMAND)
        self.assertIn("--backup-reference /backups/quant-lab.sqlite3", self.module.LIVE_BETA_CLOSEOUT_COMMAND)
        self.assertEqual(
            self.module.LIVE_BETA_PREFLIGHT_COMMAND,
            f"{self.module.LIVE_BETA_CLOSEOUT_COMMAND} --preflight",
        )
        self.assertEqual(
            self.module.LIVE_BETA_PREFLIGHT_JSON_COMMAND,
            f"{self.module.LIVE_BETA_PREFLIGHT_COMMAND} --json",
        )
        self.assertEqual(
            self.module.LIVE_BETA_NEXT_COMMAND_ONLY_COMMAND,
            f"{self.module.LIVE_BETA_PREFLIGHT_COMMAND} --next-command-only",
        )

    def test_remaining_items_use_non_placeholder_live_beta_command(self) -> None:
        items = self.module.build_remaining_items(
            package_dir=Path("/tmp/quant-evidence"),
            evidence={"checks": [{"id": "live_beta_archive", "status": "warn", "message": "missing"}]},
            external={"checks": []},
            actions={},
        )

        live_beta_items = [item for item in items if item.get("id") == "live_beta_archive"]
        self.assertEqual(len(live_beta_items), 1)
        self.assertNotIn("PATH_TO_BACKUP", live_beta_items[0]["command"])
        self.assertIn("--backup-reference /backups/quant-lab.sqlite3", live_beta_items[0]["command"])
        self.assertEqual(live_beta_items[0]["preferred_command"], self.module.LIVE_BETA_PREFLIGHT_COMMAND)
        self.assertEqual(live_beta_items[0]["automation_command"], self.module.LIVE_BETA_PREFLIGHT_JSON_COMMAND)
        self.assertEqual(live_beta_items[0]["full_flow_command"], self.module.LIVE_BETA_CLOSEOUT_COMMAND)
        self.assertEqual(
            live_beta_items[0]["supporting_commands"]["Start local backend"],
            self.module.LOCAL_BACKEND_START_COMMAND,
        )
        self.assertEqual(
            live_beta_items[0]["supporting_commands"]["Start local backend without reload"],
            self.module.LOCAL_BACKEND_START_NO_RELOAD_COMMAND,
        )
        self.assertEqual(
            live_beta_items[0]["supporting_commands"]["Start Docker backend"],
            self.module.DOCKER_BACKEND_START_COMMAND,
        )
        self.assertEqual(
            live_beta_items[0]["supporting_commands"]["Check backend health"],
            "curl -fsS http://localhost:8000/api/health",
        )

    def test_warning_items_include_review_artifact_and_recommended_next_helpers(self) -> None:
        package_dir = Path("/tmp/quant-evidence")
        items = self.module.build_remaining_items(
            package_dir=package_dir,
            evidence={"checks": [{"id": "warning_alerts", "status": "warn", "message": "review"}]},
            external={"checks": []},
            actions={"status": "planned"},
        )

        warning_items = {
            item["id"]: item for item in items if item.get("id") in {"warning_alerts", "warning_actions"}
        }
        expected_artifacts = self.module.warning_review_artifacts_only_command(package_dir)
        expected_pre_approval_sequence = self.module.warning_review_pre_approval_sequence_command(package_dir)
        expected = self.module.warning_review_next_command_only_command(package_dir)
        expected_gate = self.module.warning_review_next_command_gate_command(package_dir)
        expected_summary = self.module.warning_review_summary_json_command(package_dir)
        expected_summary_gate = self.module.warning_review_gate_summary_json_command(package_dir)
        self.assertEqual(
            warning_items["warning_alerts"]["supporting_commands"]["Show warning pre-approval sequence"],
            expected_pre_approval_sequence,
        )
        self.assertEqual(
            warning_items["warning_alerts"]["supporting_commands"]["Show warning summary JSON"],
            expected_summary,
        )
        self.assertEqual(
            warning_items["warning_alerts"]["supporting_commands"]["Gate warning summary JSON"],
            expected_summary_gate,
        )
        self.assertEqual(
            warning_items["warning_alerts"]["supporting_commands"]["Show warning review artifact paths"],
            expected_artifacts,
        )
        self.assertEqual(
            warning_items["warning_alerts"]["supporting_commands"]["Show warning recommended next command"],
            expected,
        )
        self.assertEqual(
            warning_items["warning_alerts"]["supporting_commands"]["Gate warning recommended next command"],
            expected_gate,
        )
        self.assertEqual(
            warning_items["warning_actions"]["supporting_commands"]["Show warning pre-approval sequence"],
            expected_pre_approval_sequence,
        )
        self.assertEqual(
            warning_items["warning_actions"]["supporting_commands"]["Show warning review artifact paths"],
            expected_artifacts,
        )
        self.assertEqual(
            warning_items["warning_actions"]["supporting_commands"]["Show warning summary JSON"],
            expected_summary,
        )
        self.assertEqual(
            warning_items["warning_actions"]["supporting_commands"]["Gate warning summary JSON"],
            expected_summary_gate,
        )
        self.assertEqual(
            warning_items["warning_actions"]["supporting_commands"]["Show warning recommended next command"],
            expected,
        )
        self.assertEqual(
            warning_items["warning_actions"]["supporting_commands"]["Gate warning recommended next command"],
            expected_gate,
        )
        expected_review_artifacts = self.module.warning_review_artifacts(package_dir)
        self.assertEqual(warning_items["warning_alerts"]["review_artifacts"], expected_review_artifacts)
        self.assertEqual(warning_items["warning_actions"]["review_artifacts"], expected_review_artifacts)

    def test_completion_plan_marks_operator_approval_sequence(self) -> None:
        package_dir = Path("/tmp/quant-evidence")
        items = self.module.build_remaining_items(
            package_dir=package_dir,
            evidence={"checks": [{"id": "warning_alerts", "status": "warn", "message": "review"}]},
            external={"checks": []},
            actions={"status": "planned"},
        )

        plan = self.module.completion_plan_entries(items, {})
        actions_entry = next(item for item in plan if item["id"] == "warning_actions")
        alerts_entry = next(item for item in plan if item["id"] == "warning_alerts")
        self.assertEqual(alerts_entry["mode"], "operator_review")
        self.assertEqual(alerts_entry["requirements"], ["operator_review"])
        self.assertEqual(actions_entry["mode"], "operator_approval")
        self.assertEqual(
            actions_entry["requirements"],
            ["operator_checklist_review", "operator_approval", "running_backend"],
        )
        self.assertEqual(actions_entry["backend"], self.module.backend_requirement_guidance_payload())
        self.assertTrue(actions_entry["requires_operator_approval"])
        expected_pre_approval_sequence = [
            self.module.warning_review_summary_json_command(package_dir),
            self.module.warning_review_artifacts_only_command(package_dir),
        ]
        self.assertEqual(alerts_entry["pre_approval_review_sequence"], expected_pre_approval_sequence)
        self.assertEqual(actions_entry["pre_approval_review_sequence"], expected_pre_approval_sequence)
        self.assertEqual(
            actions_entry["review_sequence"],
            [
                self.module.warning_review_summary_json_command(package_dir),
                self.module.warning_review_artifacts_only_command(package_dir),
                self.module.warning_review_apply_command(package_dir),
            ],
        )

    def test_completion_plan_lines_print_operator_approval_before_apply_command(self) -> None:
        package_dir = Path("/tmp/quant-evidence")
        report = {
            "progress_summary": {
                "percent": 96,
                "status": "warn",
                "remaining_items": 1,
                "completion_plan": [
                    {
                        "id": "warning_actions",
                        "owner": "operator",
                        "status": "planned",
                        "mode": "operator_approval",
                        "requirements": [
                            "operator_checklist_review",
                            "operator_approval",
                            "running_backend",
                        ],
                        "command": self.module.warning_review_apply_command(package_dir),
                        "requires_operator_approval": True,
                    }
                ],
            }
        }

        lines = self.module.completion_plan_lines(report)
        approval_index = lines.index("   approval: operator approval required after checklist review")
        note_index = next(index for index, line in enumerate(lines) if line.startswith("   note: Required"))
        backend_index = lines.index(f"   local_start_command: {self.module.LOCAL_BACKEND_START_COMMAND}")
        command_index = next(index for index, line in enumerate(lines) if line.startswith("   command:"))

        self.assertLess(approval_index, command_index)
        self.assertLess(note_index, command_index)
        self.assertLess(approval_index, backend_index)
        self.assertLess(backend_index, command_index)
        self.assertIn(
            f"   health_check_command: {self.module.backend_health_check_command()}",
            lines,
        )

    def test_completion_requirements_guidance_includes_operator_review_artifacts(self) -> None:
        package_dir = Path("/tmp/quant-evidence")
        review_artifacts = self.module.warning_review_artifacts(package_dir)
        progress = {
            "percent": 96,
            "status": "warn",
            "completion_requirements": [
                {
                    "requirement": "operator_review",
                    "item_ids": ["warning_alerts"],
                    "owners": ["operator"],
                    "count": 1,
                },
                {
                    "requirement": "operator_checklist_review",
                    "item_ids": ["warning_actions"],
                    "owners": ["operator"],
                    "count": 1,
                },
                {
                    "requirement": "operator_approval",
                    "item_ids": ["warning_actions"],
                    "owners": ["operator"],
                    "count": 1,
                },
            ],
            "completion_plan": [
                {
                    "id": "warning_alerts",
                    "owner": "operator",
                    "status": "warn",
                    "requirements": ["operator_review"],
                    "command": self.module.read_only_warning_review_command(package_dir),
                    "review_artifacts": review_artifacts,
                },
                {
                    "id": "warning_actions",
                    "owner": "operator",
                    "status": "planned",
                    "requirements": [
                        "operator_checklist_review",
                        "operator_approval",
                        "running_backend",
                    ],
                    "command": self.module.warning_review_apply_command(package_dir),
                    "requires_operator_approval": True,
                    "review_artifacts": review_artifacts,
                },
            ],
            "warning_review": {
                "pre_approval_sequence_command": (
                    self.module.warning_review_pre_approval_sequence_command(package_dir)
                ),
                "review_artifacts": review_artifacts,
            },
        }

        payload = self.module.completion_requirements_json_payload({"progress_summary": progress})
        operator_review = next(item for item in payload if item["requirement"] == "operator_review")
        checklist_review = next(
            item for item in payload if item["requirement"] == "operator_checklist_review"
        )
        operator_approval = next(item for item in payload if item["requirement"] == "operator_approval")
        self.assertEqual(operator_review["guidance"]["review_artifacts"], review_artifacts)
        self.assertEqual(checklist_review["guidance"]["review_artifacts"], review_artifacts)
        self.assertEqual(operator_approval["guidance"]["review_artifacts"], review_artifacts)

        lines = self.module.completion_requirements_lines({"progress_summary": progress})
        self.assertIn("   review_artifacts:", lines)
        self.assertIn(f"   - action_plan: {review_artifacts['action_plan']}", lines)
        self.assertIn(
            f"   - operator_checklist: {review_artifacts['operator_checklist']}",
            lines,
        )

    def test_completion_requirements_guidance_includes_running_backend_commands(self) -> None:
        progress = {
            "percent": 96,
            "status": "warn",
            "completion_requirements": [
                {
                    "requirement": "running_backend",
                    "item_ids": ["warning_actions"],
                    "owners": ["operator"],
                    "count": 1,
                },
            ],
            "completion_plan": [
                {
                    "id": "warning_actions",
                    "owner": "operator",
                    "status": "planned",
                    "requirements": ["running_backend"],
                },
            ],
        }

        payload = self.module.completion_requirements_json_payload({"progress_summary": progress})
        running_backend = next(item for item in payload if item["requirement"] == "running_backend")
        guidance = running_backend["guidance"]
        self.assertEqual(
            guidance["backend"],
            "start the backend before applying reviewed warning actions",
        )
        self.assertEqual(guidance["local_start_command"], self.module.LOCAL_BACKEND_START_COMMAND)
        self.assertEqual(
            guidance["local_start_no_reload_command"],
            self.module.LOCAL_BACKEND_START_NO_RELOAD_COMMAND,
        )
        self.assertEqual(guidance["docker_start_command"], self.module.DOCKER_BACKEND_START_COMMAND)
        self.assertEqual(guidance["health_check_command"], self.module.backend_health_check_command())

        lines = self.module.completion_requirements_lines({"progress_summary": progress})
        self.assertIn(f"   local_start_command: {self.module.LOCAL_BACKEND_START_COMMAND}", lines)
        self.assertIn(
            f"   local_start_no_reload_command: {self.module.LOCAL_BACKEND_START_NO_RELOAD_COMMAND}",
            lines,
        )
        self.assertIn(f"   docker_start_command: {self.module.DOCKER_BACKEND_START_COMMAND}", lines)
        self.assertIn(
            f"   health_check_command: {self.module.backend_health_check_command()}",
            lines,
        )

    def test_completion_plan_lines_fold_repeated_commands(self) -> None:
        repeated = "python3 scripts/release_gate.py --run-smoke"
        report = {
            "progress_summary": {
                "percent": 96,
                "status": "warn",
                "remaining_items": 2,
                "completion_plan": [
                    {
                        "id": "git_origin_remote",
                        "owner": "connected runner",
                        "status": "warn",
                        "command": repeated,
                    },
                    {
                        "id": "docker_cli",
                        "owner": "connected runner",
                        "status": "warn",
                        "command": repeated,
                    },
                ],
            }
        }

        lines = self.module.completion_plan_lines(report)

        self.assertEqual(lines.count(f"   command: {repeated}"), 1)
        self.assertIn("   command: same as earlier in plan.", lines)

    def test_owner_lanes_lines_distinguish_later_operator_approval_from_next_command(self) -> None:
        report = {
            "progress_summary": {
                "percent": 96,
                "status": "warn",
                "owner_lanes": {
                    "operator": {
                        "remaining_items": 2,
                        "remaining_ids": ["warning_alerts", "warning_actions"],
                        "next_item_id": "warning_alerts",
                        "requires_operator_approval": True,
                        "next_requires_operator_approval": False,
                        "commands": {
                            "next": "python3 scripts/review_release_warnings.py --no-write",
                        },
                        "review_artifacts": {
                            "action_plan": "/tmp/release-warning-actions.md",
                            "operator_checklist": "/tmp/release-warning-operator-checklist.md",
                        },
                        "review": {
                            "next_command": "python3 scripts/review_release_warnings.py --no-write",
                        },
                    }
                },
            }
        }

        lines = self.module.owner_lanes_lines(report)
        approval_index = lines.index("   approval: later operator approval required after checklist review")
        command_index = next(index for index, line in enumerate(lines) if line.startswith("   command:"))

        self.assertLess(approval_index, command_index)
        self.assertIn("   review_artifacts:", lines)
        self.assertIn("   - action_plan: /tmp/release-warning-actions.md", lines)
        self.assertIn("   - operator_checklist: /tmp/release-warning-operator-checklist.md", lines)
        self.assertIn("   review_next: same as command above.", lines)

    def test_progress_summary_owner_next_includes_supporting_commands(self) -> None:
        package_dir = Path("/tmp/quant-evidence")
        items = self.module.build_remaining_items(
            package_dir=package_dir,
            evidence={"checks": [{"id": "warning_alerts", "status": "warn", "message": "review"}]},
            external={"checks": []},
            actions={"status": "planned"},
        )
        payload = self.module.progress_summary_payload(
            {
                "status": "warn",
                "readiness_estimate": {"percent": 96, "remaining_items": len(items), "deductions": []},
                "remaining_items": items,
                "handoff_commands": [],
                "package_dir": str(package_dir),
            }
        )

        operator_next = payload["next_commands_by_owner"]["operator"]
        self.assertEqual(operator_next["id"], "warning_alerts")
        self.assertEqual(
            operator_next["automation_command"],
            self.module.warning_review_gate_json_command(package_dir),
        )
        self.assertEqual(
            operator_next["supporting_commands"]["Show warning summary JSON"],
            self.module.warning_review_summary_json_command(package_dir),
        )
        self.assertEqual(
            operator_next["supporting_commands"]["Gate warning summary JSON"],
            self.module.warning_review_gate_summary_json_command(package_dir),
        )
        self.assertEqual(
            operator_next["supporting_commands"]["Show warning review artifact paths"],
            self.module.warning_review_artifacts_only_command(package_dir),
        )
        self.assertEqual(
            operator_next["supporting_commands"]["Gate warning recommended next command"],
            self.module.warning_review_next_command_gate_command(package_dir),
        )
        self.assertEqual(
            operator_next["review_artifacts"],
            self.module.warning_review_artifacts(package_dir),
        )
        self.assertEqual(payload["warning_review"]["status"], "planned")
        self.assertEqual(payload["completion_impacts"], {})
        self.assertEqual(
            payload["owner_lanes"]["operator"]["supporting_command_labels"],
            [
                "Show warning pre-approval sequence",
                "Show warning summary JSON",
                "Show warning review artifact paths",
                "Show warning recommended next command",
                "Gate warning summary JSON",
                "Gate warning recommended next command",
            ],
        )
        self.assertTrue(payload["warning_review"]["action_needed"])
        self.assertTrue(payload["warning_review"]["requires_operator_approval"])
        self.assertEqual(payload["warning_review"]["issue_ids"], ["warning_alerts", "warning_actions"])
        self.assertEqual(
            payload["warning_review"]["summary_json"],
            self.module.warning_review_summary_json_command(package_dir),
        )
        self.assertEqual(
            payload["warning_review"]["gate_summary_json"],
            self.module.warning_review_gate_summary_json_command(package_dir),
        )
        self.assertEqual(
            payload["warning_review"]["pre_approval_sequence_command"],
            self.module.warning_review_pre_approval_sequence_command(package_dir),
        )
        self.assertEqual(
            payload["warning_review"]["gate_json"],
            self.module.warning_review_gate_json_command(package_dir),
        )
        self.assertEqual(
            payload["warning_review"]["next_command_gate"],
            self.module.warning_review_next_command_gate_command(package_dir),
        )
        self.assertEqual(
            payload["warning_review"]["review_artifacts_command"],
            self.module.warning_review_artifacts_only_command(package_dir),
        )
        self.assertEqual(
            payload["warning_review"]["apply_command"],
            self.module.warning_review_apply_command(package_dir),
        )
        self.assertIsNone(payload["warning_review"]["review_sequence_command"])
        self.assertEqual(
            payload["warning_review"]["review_artifacts"],
            self.module.warning_review_artifacts(package_dir),
        )
        self.assertEqual(
            payload["warning_review"]["pre_approval_review_sequence"],
            [
                self.module.warning_review_summary_json_command(package_dir),
                self.module.warning_review_artifacts_only_command(package_dir),
            ],
        )
        self.assertEqual(
            payload["warning_review"]["review_sequence"],
            [
                self.module.warning_review_summary_json_command(package_dir),
                self.module.warning_review_artifacts_only_command(package_dir),
                self.module.warning_review_apply_command(package_dir),
            ],
        )
        expected_backend = self.module.backend_requirement_guidance_payload()
        self.assertEqual(payload["warning_review"]["backend"], expected_backend)
        self.assertEqual(payload["owner_lanes"]["operator"]["review"]["backend"], expected_backend)

        owner_lane_lines = self.module.owner_lanes_lines({"progress_summary": payload})
        self.assertIn(f"   local_start_command: {self.module.LOCAL_BACKEND_START_COMMAND}", owner_lane_lines)
        self.assertIn(
            f"   local_start_no_reload_command: {self.module.LOCAL_BACKEND_START_NO_RELOAD_COMMAND}",
            owner_lane_lines,
        )
        self.assertIn(f"   docker_start_command: {self.module.DOCKER_BACKEND_START_COMMAND}", owner_lane_lines)
        self.assertIn(
            f"   health_check_command: {self.module.backend_health_check_command()}",
            owner_lane_lines,
        )

    def test_progress_summary_connected_runner_next_includes_local_readiness_helpers(self) -> None:
        package_dir = Path("/tmp/quant-evidence")
        bundle_dir = Path("/tmp/quant-handoff")
        items = self.module.build_remaining_items(
            package_dir=package_dir,
            evidence={"checks": []},
            external={
                "checks": [
                    {
                        "id": "docker_cli",
                        "status": "warn",
                        "message": "Docker is missing.",
                        "setup_command": "brew install --cask docker && open -a Docker && docker compose version",
                        "verify_command": "docker compose version",
                    }
                ]
            },
            actions={"status": "pass"},
        )
        items = self.module.with_connected_runner_preferred_commands(
            items,
            preflight_command=self.module.connected_runner_preflight_command(bundle_dir),
            full_command=self.module.connected_runner_full_command(bundle_dir),
            automation_command=self.module.next_release_connected_json_only_env_command(package_dir),
            package_dir=package_dir,
            source_dir=bundle_dir / "source",
        )
        deductions = [
            {
                "id": "external_readiness_warnings",
                "points": 1,
                "check_ids": ["docker_cli"],
                "detail": "Docker is missing.",
            }
        ]
        payload = self.module.progress_summary_payload(
            {
                "status": "warn",
                "readiness_estimate": {
                    "percent": 97,
                    "remaining_items": len(items),
                    "deductions": deductions,
                },
                "remaining_items": items,
                "handoff_commands": self.module.build_handoff_commands(package_dir, None, str(bundle_dir)),
                "package_dir": str(package_dir),
            }
        )

        connected_runner_next = payload["next_commands_by_owner"]["connected runner"]
        self.assertEqual(connected_runner_next["id"], "docker_cli")
        self.assertEqual(
            connected_runner_next["supporting_commands"]["Show external readiness summary JSON"],
            self.module.external_readiness_summary_json_command(),
        )
        self.assertEqual(
            connected_runner_next["supporting_commands"]["Gate external readiness summary JSON"],
            self.module.external_readiness_strict_summary_json_command(),
        )
        self.assertEqual(
            connected_runner_next["supporting_commands"]["Show connected-runner command only from env"],
            self.module.next_release_connected_command_only_env_command(package_dir),
        )
        self.assertEqual(
            connected_runner_next["supporting_commands"]["Show local readiness setup sequence"],
            self.module.next_release_local_readiness_setup_sequence_env_command(package_dir),
        )
        self.assertEqual(
            connected_runner_next["supporting_commands"]["Show local readiness command sequence"],
            self.module.next_release_local_readiness_command_sequence_env_command(package_dir),
        )
        self.assertEqual(
            connected_runner_next["supporting_commands"]["Preview local readiness setup sequence"],
            self.module.next_release_local_readiness_setup_sequence_preview_command(package_dir),
        )
        self.assertEqual(
            connected_runner_next["supporting_commands"]["Preview local readiness command sequence"],
            self.module.next_release_local_readiness_command_sequence_preview_command(package_dir),
        )
        self.assertEqual(
            payload["commands"]["connected_runner_acceptance_summary_json"],
            self.module.connected_runner_acceptance_summary_json_command(),
        )
        self.assertEqual(
            payload["commands"]["handoff_bundle_verify_summary_json"],
            self.module.connected_runner_verify_summary_json_command(bundle_dir),
        )
        self.assertEqual(
            payload["commands"]["handoff_context_json"],
            self.module.connected_runner_handoff_context_json_command(bundle_dir),
        )
        self.assertEqual(
            payload["commands"]["handoff_command_sequence"],
            self.module.connected_runner_handoff_command_sequence_command(bundle_dir),
        )
        self.assertEqual(
            payload["commands"]["external_readiness_summary_json"],
            self.module.external_readiness_summary_json_command(),
        )
        self.assertEqual(
            payload["commands"]["external_readiness_strict_summary_json"],
            self.module.external_readiness_strict_summary_json_command(),
        )
        self.assertEqual(
            payload["completion_impacts"]["docker_cli"]["completion_impact_points"],
            1,
        )
        self.assertEqual(
            payload["completion_impacts"]["docker_cli"]["completion_source_checks"],
            ["docker_cli"],
        )
        self.assertEqual(
            connected_runner_next["completion_impact_points"],
            1,
        )
        self.assertEqual(
            connected_runner_next["completion_source_checks"],
            ["docker_cli"],
        )
        self.assertEqual(payload["completion_plan"][0]["id"], "docker_cli")
        self.assertEqual(payload["completion_plan"][0]["owner"], "connected runner")
        self.assertEqual(payload["completion_plan"][0]["mode"], "connected_runner_preflight")
        self.assertEqual(
            payload["completion_plan"][0]["requirements"],
            ["connected_runner", "real_git_remote_url", "docker_cli", "github_cli_auth"],
        )
        self.assertEqual(payload["completion_plan"][0]["completion_impact_points"], 1)
        self.assertEqual(
            payload["completion_plan"][0]["command"],
            self.module.connected_runner_preflight_command(bundle_dir),
        )
        self.assertEqual(
            payload["completion_requirements"],
            [
                {
                    "requirement": "connected_runner",
                    "item_ids": ["docker_cli"],
                    "owners": ["connected runner"],
                    "count": 1,
                },
                {
                    "requirement": "real_git_remote_url",
                    "item_ids": ["docker_cli"],
                    "owners": ["connected runner"],
                    "count": 1,
                },
                {
                    "requirement": "docker_cli",
                    "item_ids": ["docker_cli"],
                    "owners": ["connected runner"],
                    "count": 1,
                },
                {
                    "requirement": "github_cli_auth",
                    "item_ids": ["docker_cli"],
                    "owners": ["connected runner"],
                    "count": 1,
                },
            ],
        )
        self.assertEqual(payload["local_readiness"]["status"], "warn")
        self.assertEqual(payload["local_readiness"]["issue_ids"], ["docker_cli"])
        self.assertEqual(payload["local_readiness"]["next_setup"]["id"], "docker_cli")
        self.assertEqual(
            payload["local_readiness"]["next_setup_command"],
            f"cd {bundle_dir / 'source'} && brew install --cask docker && open -a Docker && docker compose version",
        )
        self.assertEqual(
            payload["local_readiness"]["setup_sequence"],
            [
                f"cd {bundle_dir / 'source'} && brew install --cask docker && open -a Docker && docker compose version"
            ],
        )
        self.assertEqual(
            payload["local_readiness"]["verify_sequence"],
            [f"cd {bundle_dir / 'source'} && docker compose version"],
        )
        self.assertEqual(
            payload["local_readiness"]["command_sequence"],
            [
                f"cd {bundle_dir / 'source'} && brew install --cask docker && open -a Docker && docker compose version",
                f"cd {bundle_dir / 'source'} && docker compose version",
            ],
        )
        self.assertEqual(
            payload["local_readiness"]["json_command"],
            self.module.next_release_local_readiness_json_env_command(package_dir),
        )
        self.assertEqual(
            payload["local_readiness"]["command_only_gate"],
            self.module.next_release_local_readiness_command_only_env_command(package_dir),
        )
        self.assertEqual(
            payload["local_readiness"]["json_gate"],
            self.module.next_release_local_readiness_gate_json_env_command(package_dir),
        )
        self.assertTrue(payload["repo_url"]["required"])
        self.assertEqual(payload["repo_url"]["placeholder"], self.module.REPO_URL_PLACEHOLDER)
        self.assertEqual(
            payload["repo_url"]["export_command"],
            self.module.repo_url_export_example_command(),
        )
        self.assertEqual(
            payload["repo_url"]["command_gate"],
            self.module.next_release_command_only_env_command(package_dir),
        )
        self.assertEqual(
            payload["repo_url"]["json_gate"],
            self.module.next_release_json_only_env_command(package_dir),
        )
        connected_lane = payload["owner_lanes"]["connected runner"]
        self.assertTrue(connected_lane["repo_url"]["required"])
        self.assertEqual(connected_lane["repo_url"]["placeholder"], self.module.REPO_URL_PLACEHOLDER)
        self.assertEqual(
            connected_lane["repo_url"]["export_command"],
            self.module.repo_url_export_example_command(),
        )
        self.assertEqual(
            connected_lane["repo_url"]["command_gate"],
            self.module.next_release_connected_command_only_env_command(package_dir),
        )
        self.assertEqual(
            connected_lane["repo_url"]["json_gate"],
            self.module.next_release_connected_json_only_env_command(package_dir),
        )
        owner_lane_lines = self.module.owner_lanes_lines({"progress_summary": payload})
        self.assertIn(
            (
                f"   repo_url: Replace {self.module.REPO_URL_PLACEHOLDER} with a real HTTPS, "
                "SSH, or scp-style git remote URL before running connected-runner commands."
            ),
            owner_lane_lines,
        )
        self.assertIn(
            f"   repo_url_export: {self.module.repo_url_export_example_command()}",
            owner_lane_lines,
        )
        self.assertIn(
            f"   repo_url_command_gate: {self.module.next_release_connected_command_only_env_command(package_dir)}",
            owner_lane_lines,
        )
        self.assertIn(
            f"   repo_url_json_gate: {self.module.next_release_connected_json_only_env_command(package_dir)}",
            owner_lane_lines,
        )
        completion_requirements_json = self.module.completion_requirements_json_payload(
            {"progress_summary": payload}
        )
        connected_requirement = next(
            item
            for item in completion_requirements_json
            if item["requirement"] == "connected_runner"
        )
        self.assertEqual(
            connected_requirement["guidance"]["repo_url"],
            connected_lane["repo_url"],
        )
        self.assertEqual(
            connected_requirement["guidance"]["next_command"],
            self.module.connected_runner_preflight_command(bundle_dir),
        )
        completion_requirements_lines = self.module.completion_requirements_lines(
            {"progress_summary": payload}
        )
        self.assertIn(
            f"   repo_url_command_gate: {self.module.next_release_connected_command_only_env_command(package_dir)}",
            completion_requirements_lines,
        )
        completion_plan_lines = self.module.completion_plan_lines({"progress_summary": payload})
        self.assertIn(
            f"   repo_url_command_gate: {self.module.next_release_connected_command_only_env_command(package_dir)}",
            completion_plan_lines,
        )
        self.assertIn(
            f"   repo_url_json_gate: {self.module.next_release_connected_json_only_env_command(package_dir)}",
            completion_plan_lines,
        )
        self.assertEqual(
            completion_plan_lines.count(
                f"   repo_url_command_gate: {self.module.next_release_connected_command_only_env_command(package_dir)}"
            ),
            1,
        )

    def test_readiness_estimate_records_warning_deductions(self) -> None:
        estimate = self.module.readiness_estimate(
            release_gate_status="warn",
            evidence_checks=[
                {"id": "live_beta_archive", "status": "warn"},
                {"id": "warning_alerts", "status": "warn"},
            ],
            external_checks=[
                {"id": "git_origin_remote", "status": "warn"},
                {"id": "docker_cli", "status": "warn"},
                {"id": "github_cli", "status": "warn"},
            ],
            actions={"status": "planned"},
            remaining_items=[{"id": str(index)} for index in range(6)],
        )

        self.assertEqual(estimate["percent"], 94)
        self.assertEqual(estimate["remaining_items"], 6)
        self.assertEqual(
            [(deduction["id"], deduction["points"]) for deduction in estimate["deductions"]],
            [
                ("external_readiness_warnings", 3),
                ("live_beta_archive", 2),
                ("warning_alerts", 1),
            ],
        )
        self.assertEqual(
            estimate["deductions"][0]["check_ids"],
            ["git_origin_remote", "docker_cli", "github_cli"],
        )
        self.assertIn("git_origin_remote, docker_cli, github_cli", estimate["deductions"][0]["detail"])
        impacted = self.module.with_completion_impacts(
            [{"id": "git_origin_remote"}, {"id": "live_beta_archive"}],
            estimate["deductions"],
        )
        self.assertEqual(impacted[0]["completion_impact_points"], 1)
        self.assertEqual(impacted[1]["completion_impact_points"], 2)
        self.assertIn(
            "Clearing live_beta_archive is expected to recover 2 completion point(s)",
            impacted[1]["completion_impact"],
        )

    def test_release_status_markdown_includes_completion_deductions(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-release-status-") as tmp:
            output = Path(tmp) / "release-status.md"
            self.module.write_markdown(
                output,
                {
                    "generated_at": "2026-05-25T00:00:00+00:00",
                    "status": "warn",
                    "package_dir": "/tmp/package",
                    "release_gate_path": "gate.json",
                    "tarball": None,
                    "summary": {
                        "release_gate_status": "warn",
                        "release_evidence_status": "warn",
                        "external_readiness_status": "warn",
                        "evidence_check_counts": {"pass": 1, "warn": 2, "fail": 0, "skipped": 0, "other": 0},
                        "external_check_counts": {"pass": 0, "warn": 3, "fail": 0, "skipped": 0, "other": 0},
                        "warning_action_status": "planned",
                    },
                    "readiness_estimate": {
                        "percent": 94,
                        "remaining_items": 6,
                        "basis": "test basis",
                        "deductions": [
                            {
                                "id": "external_readiness_warnings",
                                "points": 3,
                                "detail": "3 external readiness warning check(s) remain.",
                                "check_ids": ["git_origin_remote", "docker_cli", "github_cli"],
                            }
                        ],
                    },
                    "next_actions": [],
                    "remaining_items": [
                        {
                            "id": "git_origin_remote",
                            "status": "warn",
                            "owner": "connected runner",
                            "action": "Add origin.",
                            "command": "git remote add origin REPLACE_WITH_REPO_URL",
                            "completion_impact": "Clearing git_origin_remote is expected to recover 1 completion point from external_readiness_warnings.",
                        }
                    ],
                    "handoff_commands": [],
                    "warnings": [],
                    "failures": [],
                },
            )

            markdown = output.read_text(encoding="utf-8")
            self.assertIn("- Approximate completion: 94%", markdown)
            self.assertIn("- Deduction external_readiness_warnings: -3 point(s).", markdown)
            self.assertIn("Source checks: git_origin_remote, docker_cli, github_cli.", markdown)
            self.assertIn("Completion impact: Clearing git_origin_remote is expected to recover 1 completion point", markdown)

    def test_release_status_markdown_notes_score_neutral_warning_actions(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-release-status-") as tmp:
            output = Path(tmp) / "release-status.md"
            self.module.write_markdown(
                output,
                {
                    "generated_at": "2026-05-25T00:00:00+00:00",
                    "status": "warn",
                    "package_dir": "/tmp/package",
                    "release_gate_path": "gate.json",
                    "tarball": None,
                    "summary": {
                        "release_gate_status": "warn",
                        "release_evidence_status": "warn",
                        "external_readiness_status": "pass",
                        "evidence_check_counts": {"pass": 1, "warn": 1, "fail": 0, "skipped": 0, "other": 0},
                        "external_check_counts": {"pass": 3, "warn": 0, "fail": 0, "skipped": 0, "other": 0},
                        "warning_action_status": "planned",
                    },
                    "readiness_estimate": {
                        "percent": 99,
                        "remaining_items": 1,
                        "basis": "test basis",
                        "deductions": [],
                    },
                    "next_actions": [],
                    "remaining_items": [
                        {
                            "id": "warning_actions",
                            "status": "planned",
                            "owner": "operator",
                            "action": "Review warning actions.",
                            "command": "python3 scripts/review_release_warnings.py --apply --operator-approved",
                        }
                    ],
                    "handoff_commands": [],
                    "warnings": [],
                    "failures": [],
                },
            )

            markdown = output.read_text(encoding="utf-8")
            self.assertIn(
                "- Completion note: Required for final completion; it does not recover a percentage point by itself",
                markdown,
            )

    def test_matching_release_gate_ignores_other_packages(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-release-status-") as tmp:
            base = Path(tmp)
            package_dir = (base / "package").absolute()
            other_package_dir = (base / "other-package").absolute()
            gates_dir = base / "release-gate"
            gates_dir.mkdir()
            (gates_dir / "release-gate-20260525-000000.json").write_text(
                json.dumps({"status": "fail", "package_dir": str(other_package_dir)}) + "\n",
                encoding="utf-8",
            )
            (gates_dir / "release-gate-20260525-000001.json").write_text(
                json.dumps({"status": "warn", "package_dir": str(package_dir)}) + "\n",
                encoding="utf-8",
            )

            matched = self.module.matching_release_gate(gates_dir, package_dir)

        self.assertIsNotNone(matched)
        self.assertEqual(matched.name, "release-gate-20260525-000001.json")

    def test_remaining_items_quote_package_paths(self) -> None:
        package_dir = Path("/tmp/quant evidence package")
        items = self.module.build_remaining_items(
            package_dir=package_dir,
            evidence={"checks": [{"id": "warning_alerts", "status": "warn", "message": "warnings"}]},
            external={"checks": []},
            actions={"status": "planned"},
        )

        commands = {item["id"]: item["command"] for item in items}
        automation_commands = {item["id"]: item.get("automation_command") for item in items}
        self.assertEqual(
            commands["warning_alerts"],
            "python3 scripts/review_release_warnings.py --package-dir '/tmp/quant evidence package' --no-write",
        )
        self.assertEqual(
            automation_commands["warning_alerts"],
            "python3 scripts/review_release_warnings.py --package-dir '/tmp/quant evidence package' --json-only --fail-if-action-needed",
        )
        self.assertEqual(
            commands["warning_actions"],
            self.module.warning_review_apply_command(package_dir),
        )

    def test_connected_runner_commands_quote_bundle_paths(self) -> None:
        bundle_dir = "/tmp/quant handoff bundle"

        self.assertEqual(
            self.module.connected_runner_preflight_command(bundle_dir),
            "cd '/tmp/quant handoff bundle' && "
            "PREFLIGHT_ONLY=true GIT_ORIGIN_URL=REPLACE_WITH_REPO_URL ./run-connected-runner-handoff.sh",
        )
        self.assertEqual(
            self.module.connected_runner_full_command(bundle_dir),
            "cd '/tmp/quant handoff bundle' && GIT_ORIGIN_URL=REPLACE_WITH_REPO_URL ./run-connected-runner-handoff.sh",
        )

    def test_connected_runner_remaining_items_scope_fallbacks_to_source(self) -> None:
        items = [
            {
                "id": "git_origin_remote",
                "status": "warn",
                "owner": "connected runner",
                "action": "Add origin.",
                "command": "git remote add origin REPLACE_WITH_REPO_URL",
                "verify_command": "git remote get-url origin",
                "final_verify_command": self.module.CONNECTED_STRICT_GATE_COMMAND,
            }
        ]
        updated = self.module.with_connected_runner_preferred_commands(
            items,
            preflight_command="cd '/tmp/quant handoff bundle' && PREFLIGHT_ONLY=true GIT_ORIGIN_URL=REPLACE_WITH_REPO_URL ./run-connected-runner-handoff.sh",
            full_command="cd '/tmp/quant handoff bundle' && GIT_ORIGIN_URL=REPLACE_WITH_REPO_URL ./run-connected-runner-handoff.sh",
            automation_command=(
                "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
                '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --json-only '
                "--fail-if-repo-url-required"
            ),
            package_dir=Path("/tmp/quant evidence package"),
            source_dir=Path("/tmp/quant handoff bundle/source"),
        )

        self.assertEqual(
            updated[0]["command"],
            "cd '/tmp/quant handoff bundle/source' && git remote add origin REPLACE_WITH_REPO_URL",
        )
        self.assertEqual(
            updated[0]["verify_command"],
            "cd '/tmp/quant handoff bundle/source' && git remote get-url origin",
        )
        self.assertEqual(
            updated[0]["final_verify_command"],
            f"cd '/tmp/quant handoff bundle/source' && {self.module.CONNECTED_STRICT_GATE_COMMAND}",
        )
        self.assertEqual(
            updated[0]["automation_command"],
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --json-only '
            "--fail-if-repo-url-required",
        )
        self.assertEqual(
            updated[0]["supporting_commands"]["Export repo URL example"],
            "export GIT_ORIGIN_URL=https://github.com/OWNER/REPO.git",
        )
        self.assertEqual(
            updated[0]["supporting_commands"]["Show external readiness summary JSON"],
            self.module.external_readiness_summary_json_command(),
        )
        self.assertEqual(
            updated[0]["supporting_commands"]["Gate external readiness summary JSON"],
            self.module.external_readiness_strict_summary_json_command(),
        )
        self.assertEqual(
            updated[0]["supporting_commands"]["Show connected-runner command only from env"],
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL '
            "--command-only --fail-if-repo-url-required",
        )
        self.assertEqual(
            updated[0]["supporting_commands"]["Show local readiness setup sequence"],
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL '
            "--local-readiness-setup-sequence-only --fail-if-local-readiness-not-pass",
        )
        self.assertEqual(
            updated[0]["supporting_commands"]["Show local readiness command sequence"],
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL '
            "--local-readiness-command-sequence-only --fail-if-local-readiness-not-pass",
        )
        self.assertEqual(
            updated[0]["supporting_commands"]["Preview local readiness setup sequence"],
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            '--owner "connected runner" --local-readiness-setup-sequence-only',
        )
        self.assertEqual(
            updated[0]["supporting_commands"]["Preview local readiness command sequence"],
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            '--owner "connected runner" --local-readiness-command-sequence-only',
        )

    def test_connected_runner_remaining_items_do_not_double_scope_source_fallbacks(self) -> None:
        items = [
            {
                "id": "git_origin_remote",
                "status": "warn",
                "owner": "connected runner",
                "action": "Add origin.",
                "command": (
                    "cd '/tmp/packaged quant handoff/source' && "
                    "cd '/tmp/earlier quant handoff/source' && "
                    "git remote add origin REPLACE_WITH_REPO_URL"
                ),
                "verify_command": (
                    "cd '/tmp/packaged quant handoff/source' && "
                    "cd '/tmp/earlier quant handoff/source' && "
                    "git remote get-url origin"
                ),
                "final_verify_command": (
                    "cd '/tmp/packaged quant handoff/source' && "
                    "cd '/tmp/earlier quant handoff/source' && "
                    + self.module.CONNECTED_STRICT_GATE_COMMAND
                ),
            }
        ]
        updated = self.module.with_connected_runner_preferred_commands(
            items,
            preflight_command="cd '/tmp/current quant handoff' && PREFLIGHT_ONLY=true GIT_ORIGIN_URL=REPLACE_WITH_REPO_URL ./run-connected-runner-handoff.sh",
            full_command="cd '/tmp/current quant handoff' && GIT_ORIGIN_URL=REPLACE_WITH_REPO_URL ./run-connected-runner-handoff.sh",
            source_dir=Path("/tmp/current quant handoff/source"),
        )

        self.assertEqual(updated[0]["command"].count("cd '/tmp/current quant handoff/source' && "), 1)
        self.assertEqual(updated[0]["verify_command"].count("cd '/tmp/current quant handoff/source' && "), 1)
        self.assertEqual(updated[0]["final_verify_command"].count("cd '/tmp/current quant handoff/source' && "), 1)
        self.assertNotIn("/tmp/packaged quant handoff", updated[0]["command"])
        self.assertNotIn("/tmp/packaged quant handoff", updated[0]["verify_command"])
        self.assertNotIn("/tmp/packaged quant handoff", updated[0]["final_verify_command"])
        self.assertNotIn("/tmp/earlier quant handoff", updated[0]["command"])
        self.assertNotIn("/tmp/earlier quant handoff", updated[0]["verify_command"])
        self.assertNotIn("/tmp/earlier quant handoff", updated[0]["final_verify_command"])

    def test_handoff_commands_quote_package_and_release_gate_paths(self) -> None:
        package_dir = Path("/tmp/quant evidence package")
        release_gate = Path("/tmp/quant gate/release gate.json")
        handoff_bundle = Path("/tmp/quant handoff bundle")
        commands = {
            item["label"]: item["command"]
            for item in self.module.build_handoff_commands(package_dir, release_gate, str(handoff_bundle))
        }

        self.assertEqual(
            commands["Refresh this status report"],
            self.module.refresh_release_status_command(package_dir, release_gate),
        )
        self.assertEqual(
            commands["Show this status report read-only"],
            self.module.read_only_release_status_command(package_dir, release_gate),
        )
        self.assertEqual(
            commands["Show this status report JSON"],
            self.module.release_status_json_command(package_dir, release_gate),
        )
        self.assertEqual(
            commands["Show release progress only"],
            self.module.release_status_progress_command(package_dir, release_gate),
        )
        self.assertEqual(
            commands["Show release progress JSON"],
            self.module.release_status_progress_json_command(package_dir, release_gate),
        )
        self.assertEqual(
            commands["Show completion plan"],
            self.module.release_status_completion_plan_command(package_dir, release_gate),
        )
        self.assertEqual(
            commands["Show completion plan JSON"],
            self.module.release_status_completion_plan_json_command(package_dir, release_gate),
        )
        self.assertEqual(
            commands["Show completion requirements"],
            self.module.release_status_completion_requirements_command(package_dir, release_gate),
        )
        self.assertEqual(
            commands["Show completion requirements JSON"],
            self.module.release_status_completion_requirements_json_command(package_dir, release_gate),
        )
        self.assertEqual(commands["Run local warning-mode gate"], self.module.LOCAL_WARNING_GATE_COMMAND)
        self.assertEqual(commands["Run connected-runner strict gate"], self.module.CONNECTED_STRICT_GATE_COMMAND)
        self.assertEqual(
            commands["Show external readiness summary JSON"],
            self.module.external_readiness_summary_json_command(),
        )
        self.assertEqual(
            commands["Gate external readiness summary JSON"],
            self.module.external_readiness_strict_summary_json_command(),
        )
        self.assertEqual(
            commands["Verify evidence checksums"],
            self.module.verify_evidence_checksums_command(package_dir),
        )
        self.assertEqual(
            commands["Verify evidence checksums JSON"],
            self.module.verify_evidence_checksums_json_command(package_dir),
        )
        self.assertEqual(
            commands["Run read-only evidence check"],
            "python3 scripts/check_release_evidence.py --package-dir '/tmp/quant evidence package' --no-write",
        )
        self.assertEqual(
            commands["Show evidence check JSON"],
            "python3 scripts/check_release_evidence.py --package-dir '/tmp/quant evidence package' --json-only",
        )
        self.assertEqual(
            commands["Show next release step from git origin"],
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            "--repo-url-from-origin --no-write",
        )
        self.assertEqual(
            commands["Show next release step from env"],
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            "--repo-url-from-env GIT_ORIGIN_URL --no-write",
        )
        self.assertEqual(
            commands["Export repo URL example"],
            "export GIT_ORIGIN_URL=https://github.com/OWNER/REPO.git",
        )
        self.assertEqual(
            commands["Show next command only from env"],
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            "--repo-url-from-env GIT_ORIGIN_URL --command-only --fail-if-repo-url-required",
        )
        self.assertEqual(
            commands["Show remaining command sequence from env"],
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            "--repo-url-from-env GIT_ORIGIN_URL --command-sequence-only --fail-if-repo-url-required",
        )
        self.assertEqual(
            commands["Show next report JSON from env"],
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            "--repo-url-from-env GIT_ORIGIN_URL --json-only --fail-if-repo-url-required",
        )
        self.assertEqual(
            commands["Show connected-runner report JSON from env"],
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --json-only --fail-if-repo-url-required',
        )
        self.assertEqual(
            commands["Show connected-runner command only from env"],
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --command-only '
            "--fail-if-repo-url-required",
        )
        self.assertEqual(
            commands["Show connected-runner command sequence from env"],
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --command-sequence-only '
            "--fail-if-repo-url-required",
        )
        self.assertEqual(
            commands["Show operator sequence"],
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            "--owner operator --show-sequence --no-write",
        )
        self.assertEqual(
            commands["Show operator command only"],
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            "--owner operator --command-only --fail-if-repo-url-required",
        )
        self.assertEqual(
            commands["Show operator command sequence"],
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            "--owner operator --command-sequence-only --fail-if-repo-url-required",
        )
        self.assertEqual(
            commands["Show operator review sequence"],
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            "--owner operator --command-sequence-only --skip-operator-approved --fail-if-repo-url-required",
        )
        self.assertEqual(
            commands["Show warning pre-approval sequence"],
            "python3 scripts/review_release_warnings.py --package-dir "
            "'/tmp/quant evidence package' --pre-approval-sequence-only",
        )
        self.assertEqual(
            commands["Show operator report JSON"],
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            "--owner operator --json-only --fail-if-repo-url-required",
        )
        self.assertEqual(
            commands["Show connected-runner sequence from git origin"],
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            '--owner "connected runner" --repo-url-from-origin --show-sequence --no-write',
        )
        self.assertEqual(
            commands["Show connected-runner sequence from env"],
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --show-sequence --no-write',
        )
        self.assertEqual(
            commands["Show local connected-runner readiness"],
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            '--owner "connected runner" --summary-by-owner --show-sequence '
            "--local-readiness --no-write",
        )
        self.assertEqual(
            commands["Show local connected-runner readiness JSON"],
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --json-only '
            "--fail-if-repo-url-required --local-readiness",
        )
        self.assertEqual(
            commands["Gate local connected-runner readiness command only"],
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --command-only '
            "--fail-if-repo-url-required --local-readiness --fail-if-local-readiness-not-pass",
        )
        self.assertEqual(
            commands["Show local connected-runner readiness setup sequence"],
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL '
            "--local-readiness-setup-sequence-only --fail-if-local-readiness-not-pass",
        )
        self.assertEqual(
            commands["Show local connected-runner readiness command sequence"],
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL '
            "--local-readiness-command-sequence-only --fail-if-local-readiness-not-pass",
        )
        self.assertEqual(
            commands["Preview local connected-runner readiness setup sequence"],
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            '--owner "connected runner" --local-readiness-setup-sequence-only',
        )
        self.assertEqual(
            commands["Preview local connected-runner readiness command sequence"],
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            '--owner "connected runner" --local-readiness-command-sequence-only',
        )
        self.assertEqual(
            commands["Gate local connected-runner readiness JSON"],
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --json-only '
            "--fail-if-repo-url-required --local-readiness --fail-if-local-readiness-not-pass",
        )
        self.assertEqual(
            commands["Package connected-runner handoff"],
            self.module.package_connected_runner_handoff_command(package_dir),
        )
        self.assertEqual(
            commands["Verify connected-runner handoff JSON"],
            self.module.connected_runner_verify_json_command(handoff_bundle),
        )
        self.assertEqual(
            commands["Verify connected-runner handoff summary JSON"],
            self.module.connected_runner_verify_summary_json_command(handoff_bundle),
        )
        self.assertEqual(
            commands["Show connected-runner handoff context JSON"],
            self.module.connected_runner_handoff_context_json_command(handoff_bundle),
        )
        self.assertEqual(
            commands["Show connected-runner handoff command sequence"],
            self.module.connected_runner_handoff_command_sequence_command(handoff_bundle),
        )
        self.assertEqual(
            commands["Run connected-runner acceptance"],
            "python3 scripts/connected_runner_acceptance.py --handoff-root .. --require-external --check-gh-auth",
        )
        self.assertEqual(
            commands["Run connected-runner acceptance JSON"],
            "python3 scripts/connected_runner_acceptance.py --handoff-root .. --require-external --check-gh-auth --json-only",
        )
        self.assertEqual(
            commands["Run connected-runner acceptance summary JSON"],
            "python3 scripts/connected_runner_acceptance.py --handoff-root .. "
            "--require-external --check-gh-auth --summary-json-only",
        )
        self.assertEqual(
            commands["Review warning operator checklist"],
            "python3 scripts/review_release_warnings.py --package-dir '/tmp/quant evidence package' --no-write",
        )
        self.assertEqual(
            commands["Show warning action plan JSON"],
            "python3 scripts/review_release_warnings.py --package-dir '/tmp/quant evidence package' --json-only",
        )
        self.assertEqual(
            commands["Gate warning action plan JSON"],
            "python3 scripts/review_release_warnings.py --package-dir '/tmp/quant evidence package' --json-only --fail-if-action-needed",
        )
        self.assertEqual(
            commands["Show warning action summary JSON"],
            "python3 scripts/review_release_warnings.py --package-dir '/tmp/quant evidence package' --summary-json-only",
        )
        self.assertEqual(
            commands["Gate warning action summary JSON"],
            "python3 scripts/review_release_warnings.py --package-dir '/tmp/quant evidence package' --summary-json-only --fail-if-action-needed",
        )
        self.assertEqual(
            commands["Show warning pre-approval sequence"],
            "python3 scripts/review_release_warnings.py --package-dir "
            "'/tmp/quant evidence package' --pre-approval-sequence-only",
        )
        self.assertEqual(
            commands["Show warning review artifact paths"],
            "python3 scripts/review_release_warnings.py --package-dir '/tmp/quant evidence package' --review-artifacts-only",
        )
        self.assertEqual(
            commands["Show warning recommended next command"],
            "python3 scripts/review_release_warnings.py --package-dir '/tmp/quant evidence package' --next-command-only",
        )
        self.assertEqual(
            commands["Gate warning recommended next command"],
            (
                "python3 scripts/review_release_warnings.py --package-dir "
                "'/tmp/quant evidence package' --next-command-only --fail-if-action-needed"
            ),
        )
        self.assertEqual(
            commands["Apply reviewed warning actions"],
            self.module.warning_review_apply_command(package_dir),
        )
        self.assertEqual(commands["Preflight live-beta closeout"], self.module.LIVE_BETA_PREFLIGHT_COMMAND)
        self.assertEqual(
            commands["Preflight live-beta closeout JSON"],
            self.module.LIVE_BETA_PREFLIGHT_JSON_COMMAND,
        )
        self.assertEqual(
            commands["Show live-beta recommended next command"],
            self.module.LIVE_BETA_NEXT_COMMAND_ONLY_COMMAND,
        )
        self.assertEqual(
            commands["Start local backend for live-beta preflight"],
            self.module.LOCAL_BACKEND_START_COMMAND,
        )
        self.assertEqual(
            commands["Start local backend without reload for live-beta preflight"],
            self.module.LOCAL_BACKEND_START_NO_RELOAD_COMMAND,
        )
        self.assertEqual(
            commands["Start Docker backend for live-beta preflight"],
            self.module.DOCKER_BACKEND_START_COMMAND,
        )
        self.assertEqual(
            commands["Check backend health for live-beta preflight"],
            self.module.backend_health_check_command(),
        )
        self.assertEqual(commands["Archive live-beta closeout"], self.module.LIVE_BETA_CLOSEOUT_COMMAND)
        self.assertEqual(commands["Run final live-beta archive gate"], self.module.LIVE_BETA_FINAL_GATE_COMMAND)

    def test_cli_no_write_does_not_create_status_files(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-release-status-") as tmp:
            package_dir = Path(tmp) / "package"
            package_dir.mkdir()
            (package_dir / "manifest.json").write_text(
                json.dumps({"package_name": package_dir.name, "tarball": None}) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(REPORT_RELEASE_STATUS),
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
            self.assertIn("Release status: pass", completed.stdout)
            self.assertIn("Release status report: not written (--no-write)", completed.stdout)
            self.assertFalse((package_dir / "release-status.json").exists())
            self.assertFalse((package_dir / "release-status.md").exists())

    def test_cli_json_only_prints_report_without_writing_files(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-release-status-") as tmp:
            package_dir = Path(tmp) / "package"
            package_dir.mkdir()
            (package_dir / "manifest.json").write_text(
                json.dumps({"package_name": package_dir.name, "tarball": None}) + "\n",
                encoding="utf-8",
            )
            (package_dir / "evidence-checksums.json").write_text("{}\n", encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(REPORT_RELEASE_STATUS),
                    "--package-dir",
                    str(package_dir),
                    "--json-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "pass")
            self.assertEqual(payload["package_dir"], str(package_dir.absolute()))
            self.assertEqual(payload["summary"]["release_evidence_status"], "not available")
            self.assertEqual(payload["progress_summary"]["status"], "pass")
            self.assertEqual(payload["progress_summary"]["remaining_items"], 0)
            self.assertIn("show_progress_json", payload["progress_summary"]["commands"])
            self.assertEqual(payload["handoff_commands"][1]["label"], "Show this status report read-only")
            self.assertEqual(payload["handoff_commands"][2]["label"], "Show this status report JSON")
            self.assertFalse((package_dir / "release-status.json").exists())
            self.assertFalse((package_dir / "release-status.md").exists())

    def test_cli_progress_only_prints_compact_progress_without_writing_files(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-release-status-") as tmp:
            package_dir = Path(tmp) / "package"
            package_dir.mkdir()
            (package_dir / "manifest.json").write_text(
                json.dumps({"package_name": package_dir.name, "tarball": None}) + "\n",
                encoding="utf-8",
            )
            evidence_dir = package_dir / "00-external-readiness" / "20260525-000000"
            evidence_dir.mkdir(parents=True)
            (evidence_dir / "external-readiness.json").write_text(
                json.dumps(
                    {
                        "status": "warn",
                        "checks": [
                            {
                                "id": "docker_cli",
                                "status": "warn",
                                "message": "Docker is missing.",
                                "setup_command": "brew install --cask docker",
                            }
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(REPORT_RELEASE_STATUS),
                    "--package-dir",
                    str(package_dir),
                    "--progress-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("Release progress: 99%", completed.stdout)
            self.assertIn("Status: warn", completed.stdout)
            self.assertIn("Remaining IDs: docker_cli", completed.stdout)
            self.assertIn("Remaining by owner: connected runner: 1", completed.stdout)
            self.assertIn("Deductions:", completed.stdout)
            self.assertFalse((package_dir / "release-status.json").exists())
            self.assertFalse((package_dir / "release-status.md").exists())

    def test_cli_progress_json_only_prints_compact_payload_without_writing_files(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-release-status-") as tmp:
            package_dir = Path(tmp) / "package"
            package_dir.mkdir()
            (package_dir / "manifest.json").write_text(
                json.dumps({"package_name": package_dir.name, "tarball": None}) + "\n",
                encoding="utf-8",
            )
            evidence_dir = package_dir / "00-external-readiness" / "20260525-000000"
            evidence_dir.mkdir(parents=True)
            (evidence_dir / "external-readiness.json").write_text(
                json.dumps(
                    {
                        "status": "warn",
                        "checks": [
                            {
                                "id": "github_cli",
                                "status": "warn",
                                "message": "GitHub CLI is missing.",
                                "setup_command": "brew install gh",
                            }
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(REPORT_RELEASE_STATUS),
                    "--package-dir",
                    str(package_dir),
                    "--progress-json-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "warn")
            self.assertEqual(payload["percent"], 99)
            self.assertEqual(payload["remaining_items"], 1)
            self.assertEqual(payload["remaining_ids"], ["github_cli"])
            self.assertEqual(payload["remaining_by_owner"], {"connected runner": 1})
            self.assertEqual(payload["next_item_id"], "github_cli")
            self.assertEqual(payload["next_item_owner"], "connected runner")
            self.assertEqual(payload["next_command"], "brew install gh")
            self.assertEqual(
                payload["next_commands_by_owner"],
                {
                    "connected runner": {
                        "id": "github_cli",
                        "status": "warn",
                        "command": "brew install gh",
                        **self.module.completion_impacts_by_check_id(payload["deductions"])[
                            "github_cli"
                        ],
                    }
                },
            )
            self.assertEqual(
                payload["completion_plan"],
                [
                    {
                        "id": "github_cli",
                        "owner": "connected runner",
                        "status": "warn",
                        "command": "brew install gh",
                        "mode": "connected_runner_setup",
                        "requirements": ["connected_runner", "github_cli_auth"],
                        "final_verify_command": self.module.CONNECTED_STRICT_GATE_COMMAND,
                        **self.module.completion_impacts_by_check_id(payload["deductions"])[
                            "github_cli"
                        ],
                    }
                ],
            )
            self.assertEqual(
                payload["completion_requirements"],
                [
                    {
                        "requirement": "connected_runner",
                        "item_ids": ["github_cli"],
                        "owners": ["connected runner"],
                        "count": 1,
                    },
                    {
                        "requirement": "github_cli_auth",
                        "item_ids": ["github_cli"],
                        "owners": ["connected runner"],
                        "count": 1,
                    },
                ],
            )
            lane = payload["owner_lanes"]["connected runner"]
            self.assertEqual(lane["remaining_ids"], ["github_cli"])
            self.assertEqual(lane["commands"], {"next": "brew install gh"})
            self.assertEqual(lane["readiness"]["status"], "warn")
            self.assertEqual(lane["readiness"]["issue_ids"], ["github_cli"])
            self.assertEqual(lane["readiness"]["next_setup_command"], "brew install gh")
            self.assertEqual(payload["deductions"][0]["id"], "external_readiness_warnings")
            self.assertEqual(
                payload["commands"]["show_progress"],
                f"python3 scripts/report_release_status.py --package-dir {package_dir.absolute()} --progress-only",
            )
            self.assertEqual(
                payload["commands"]["show_progress_json"],
                f"python3 scripts/report_release_status.py --package-dir {package_dir.absolute()} --progress-json-only",
            )
            self.assertEqual(
                payload["commands"]["show_completion_plan"],
                f"python3 scripts/report_release_status.py --package-dir {package_dir.absolute()} --completion-plan-only",
            )
            self.assertEqual(
                payload["commands"]["show_completion_plan_json"],
                f"python3 scripts/report_release_status.py --package-dir {package_dir.absolute()} --completion-plan-json-only",
            )
            self.assertEqual(
                payload["commands"]["show_completion_requirements"],
                f"python3 scripts/report_release_status.py --package-dir {package_dir.absolute()} --completion-requirements-only",
            )
            self.assertEqual(
                payload["commands"]["show_completion_requirements_json"],
                f"python3 scripts/report_release_status.py --package-dir {package_dir.absolute()} --completion-requirements-json-only",
            )
            self.assertEqual(
                payload["commands"]["show_owner_lanes"],
                f"python3 scripts/report_release_status.py --package-dir {package_dir.absolute()} --owner-lanes-only",
            )
            self.assertEqual(
                payload["commands"]["show_owner_lanes_json"],
                f"python3 scripts/report_release_status.py --package-dir {package_dir.absolute()} --owner-lanes-json-only",
            )
            self.assertIn("--command-sequence-only", payload["commands"]["remaining_sequence"])
            self.assertIn(
                '--owner "connected runner"',
                payload["commands"]["connected_runner_command_only"],
            )
            self.assertIn("--command-only", payload["commands"]["connected_runner_command_only"])
            self.assertIn(
                '--owner "connected runner"',
                payload["commands"]["connected_runner_command_sequence"],
            )
            self.assertIn(
                "--command-sequence-only",
                payload["commands"]["connected_runner_command_sequence"],
            )
            self.assertIn("--command-only", payload["commands"]["next_command_only"])
            self.assertIn("--json-only", payload["commands"]["next_json_only"])
            self.assertIn("--owner operator --command-only", payload["commands"]["operator_command_only"])
            self.assertIn("--owner operator --command-sequence-only", payload["commands"]["operator_command_sequence"])
            self.assertIn("--skip-operator-approved", payload["commands"]["operator_review_sequence"])
            self.assertIn("--owner operator --json-only", payload["commands"]["operator_json_only"])
            self.assertIn("--json-only", payload["commands"]["local_readiness_json"])
            self.assertIn("--local-readiness", payload["commands"]["local_readiness_json"])
            self.assertIn("--command-only", payload["commands"]["local_readiness_command_only"])
            self.assertIn("--local-readiness", payload["commands"]["local_readiness_command_only"])
            self.assertIn("--local-readiness-setup-sequence-only", payload["commands"]["local_readiness_setup_sequence"])
            self.assertIn(
                "--local-readiness-command-sequence-only",
                payload["commands"]["local_readiness_command_sequence"],
            )
            self.assertIn(
                "--local-readiness-setup-sequence-only",
                payload["commands"]["local_readiness_setup_sequence_preview"],
            )
            self.assertNotIn(
                "--fail-if-local-readiness-not-pass",
                payload["commands"]["local_readiness_setup_sequence_preview"],
            )
            self.assertIn(
                "--local-readiness-command-sequence-only",
                payload["commands"]["local_readiness_command_sequence_preview"],
            )
            self.assertNotIn(
                "--fail-if-local-readiness-not-pass",
                payload["commands"]["local_readiness_command_sequence_preview"],
            )
            self.assertIn(
                "--local-readiness --fail-if-local-readiness-not-pass",
                payload["commands"]["local_readiness_gate_json"],
            )
            self.assertIn("--json-only --fail-if-action-needed", payload["commands"]["warning_gate_json"])
            self.assertIn("--summary-json-only", payload["commands"]["warning_summary_json"])
            self.assertIn(
                "--summary-json-only --fail-if-action-needed",
                payload["commands"]["warning_gate_summary_json"],
            )
            self.assertIn("--next-command-only --fail-if-action-needed", payload["commands"]["warning_next_command_gate"])
            self.assertIn("--review-artifacts-only", payload["commands"]["warning_review_artifacts"])
            self.assertIn("--apply --operator-approved", payload["commands"]["warning_apply"])
            self.assertEqual(payload["warning_review"]["status"], "pass")
            self.assertFalse(payload["warning_review"]["action_needed"])
            self.assertEqual(payload["warning_review"]["issue_ids"], [])
            self.assertEqual(
                payload["warning_review"]["review_sequence_command"],
                payload["commands"]["operator_review_sequence"],
            )
            self.assertEqual(payload["warning_review"]["pre_approval_review_sequence"], [])
            self.assertEqual(payload["warning_review"]["review_sequence"], [])
            self.assertFalse(payload["repo_url"]["required"])
            self.assertEqual(payload["local_readiness"]["status"], "warn")
            self.assertEqual(payload["local_readiness"]["issue_ids"], ["github_cli"])
            self.assertEqual(payload["local_readiness"]["next_setup_command"], "brew install gh")
            self.assertEqual(payload["local_readiness"]["setup_sequence"], ["brew install gh"])
            self.assertEqual(payload["local_readiness"]["verify_sequence"], [])
            self.assertEqual(payload["local_readiness"]["command_sequence"], ["brew install gh"])
            self.assertEqual(payload["package_dir"], str(package_dir.absolute()))
            self.assertFalse((package_dir / "release-status.json").exists())
            self.assertFalse((package_dir / "release-status.md").exists())

    def test_cli_completion_plan_modes_print_ordered_plan_without_writing_files(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-release-status-") as tmp:
            package_dir = Path(tmp) / "package"
            package_dir.mkdir()
            (package_dir / "manifest.json").write_text(
                json.dumps({"package_name": package_dir.name, "tarball": None}) + "\n",
                encoding="utf-8",
            )
            evidence_dir = package_dir / "00-external-readiness" / "20260525-000000"
            evidence_dir.mkdir(parents=True)
            (evidence_dir / "external-readiness.json").write_text(
                json.dumps(
                    {
                        "status": "warn",
                        "checks": [
                            {
                                "id": "docker_cli",
                                "status": "warn",
                                "message": "Docker is missing.",
                                "setup_command": "brew install --cask docker",
                            }
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            text_completed = subprocess.run(
                [
                    sys.executable,
                    str(REPORT_RELEASE_STATUS),
                    "--package-dir",
                    str(package_dir),
                    "--completion-plan-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(text_completed.returncode, 0, text_completed.stderr)
            self.assertIn("Completion plan: 99%", text_completed.stdout)
            self.assertIn("1. docker_cli [connected runner/warn] (+1 point)", text_completed.stdout)
            self.assertIn("command: brew install --cask docker", text_completed.stdout)

            json_completed = subprocess.run(
                [
                    sys.executable,
                    str(REPORT_RELEASE_STATUS),
                    "--package-dir",
                    str(package_dir),
                    "--completion-plan-json-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(json_completed.returncode, 0, json_completed.stderr)
            payload = json.loads(json_completed.stdout)
            self.assertEqual(payload[0]["id"], "docker_cli")
            self.assertEqual(payload[0]["owner"], "connected runner")
            self.assertEqual(payload[0]["command"], "brew install --cask docker")
            self.assertFalse((package_dir / "release-status.json").exists())
            self.assertFalse((package_dir / "release-status.md").exists())

    def test_cli_completion_requirements_modes_print_grouped_requirements_without_writing_files(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-release-status-") as tmp:
            package_dir = Path(tmp) / "package"
            package_dir.mkdir()
            (package_dir / "manifest.json").write_text(
                json.dumps({"package_name": package_dir.name, "tarball": None}) + "\n",
                encoding="utf-8",
            )
            evidence_dir = package_dir / "00-external-readiness" / "20260525-000000"
            evidence_dir.mkdir(parents=True)
            (evidence_dir / "external-readiness.json").write_text(
                json.dumps(
                    {
                        "status": "warn",
                        "checks": [
                            {
                                "id": "github_cli",
                                "status": "warn",
                                "message": "GitHub CLI is missing.",
                                "setup_command": "brew install gh",
                            }
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            text_completed = subprocess.run(
                [
                    sys.executable,
                    str(REPORT_RELEASE_STATUS),
                    "--package-dir",
                    str(package_dir),
                    "--completion-requirements-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(text_completed.returncode, 0, text_completed.stderr)
            self.assertIn("Completion requirements: 99%", text_completed.stdout)
            self.assertIn(
                "Note: repeated item sets mean one remaining action is gated by multiple prerequisites.",
                text_completed.stdout,
            )
            self.assertIn("1. connected_runner (1 item) [connected runner]", text_completed.stdout)
            self.assertIn("items: github_cli", text_completed.stdout)
            self.assertIn("next_item: github_cli", text_completed.stdout)
            self.assertIn("command: brew install gh", text_completed.stdout)
            self.assertIn("setup_command: brew install gh", text_completed.stdout)

            json_completed = subprocess.run(
                [
                    sys.executable,
                    str(REPORT_RELEASE_STATUS),
                    "--package-dir",
                    str(package_dir),
                    "--completion-requirements-json-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(json_completed.returncode, 0, json_completed.stderr)
            payload = json.loads(json_completed.stdout)
            self.assertEqual(payload[0]["requirement"], "connected_runner")
            self.assertEqual(payload[0]["item_ids"], ["github_cli"])
            self.assertEqual(payload[0]["owners"], ["connected runner"])
            self.assertEqual(payload[0]["guidance"]["next_item_id"], "github_cli")
            self.assertEqual(payload[0]["guidance"]["next_command"], "brew install gh")
            github_requirement = next(
                item for item in payload if item["requirement"] == "github_cli_auth"
            )
            self.assertEqual(
                github_requirement["guidance"]["setup_command"],
                "brew install gh",
            )
            self.assertFalse((package_dir / "release-status.json").exists())
            self.assertFalse((package_dir / "release-status.md").exists())

    def test_cli_owner_lanes_modes_print_commands_without_writing_files(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-release-status-") as tmp:
            package_dir = Path(tmp) / "package"
            package_dir.mkdir()
            (package_dir / "manifest.json").write_text(
                json.dumps({"package_name": package_dir.name, "tarball": None}) + "\n",
                encoding="utf-8",
            )
            evidence_dir = package_dir / "00-external-readiness" / "20260525-000000"
            evidence_dir.mkdir(parents=True)
            (evidence_dir / "external-readiness.json").write_text(
                json.dumps(
                    {
                        "status": "warn",
                        "checks": [
                            {
                                "id": "github_cli",
                                "status": "warn",
                                "message": "GitHub CLI is missing.",
                                "setup_command": "brew install gh",
                            }
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            text_completed = subprocess.run(
                [
                    sys.executable,
                    str(REPORT_RELEASE_STATUS),
                    "--package-dir",
                    str(package_dir),
                    "--owner-lanes-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(text_completed.returncode, 0, text_completed.stderr)
            self.assertIn("Owner lanes: 99%", text_completed.stdout)
            self.assertIn("1. connected runner (1 item)", text_completed.stdout)
            self.assertIn("command: brew install gh", text_completed.stdout)
            self.assertIn("requires: connected_runner, github_cli_auth", text_completed.stdout)

            json_completed = subprocess.run(
                [
                    sys.executable,
                    str(REPORT_RELEASE_STATUS),
                    "--package-dir",
                    str(package_dir),
                    "--owner-lanes-json-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(json_completed.returncode, 0, json_completed.stderr)
            payload = json.loads(json_completed.stdout)
            self.assertEqual(payload["connected runner"]["remaining_ids"], ["github_cli"])
            self.assertEqual(payload["connected runner"]["commands"]["next"], "brew install gh")
            self.assertFalse((package_dir / "release-status.json").exists())
            self.assertFalse((package_dir / "release-status.md").exists())

    def test_cli_progress_json_only_uses_latest_package_when_package_dir_is_omitted(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-release-status-latest-") as tmp:
            packages_dir = Path(tmp) / "packages"
            older_package = packages_dir / "20260526-KRW-BTC-beta-001"
            latest_package = packages_dir / "20260526-KRW-BTC-beta-002"
            release_gate_path = Path(tmp) / "release-gate-pass.json"
            older_package.mkdir(parents=True)
            latest_package.mkdir(parents=True)
            release_gate_path.write_text(
                json.dumps({"status": "pass", "steps": []}) + "\n",
                encoding="utf-8",
            )
            (older_package / "manifest.json").write_text(
                json.dumps(
                    {
                        "package_name": older_package.name,
                        "generated_at": "2026-05-25T00:00:00+00:00",
                        "tarball": None,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (latest_package / "manifest.json").write_text(
                json.dumps(
                    {
                        "package_name": latest_package.name,
                        "generated_at": "2026-05-25T00:01:00+00:00",
                        "tarball": None,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(REPORT_RELEASE_STATUS),
                    "--packages-dir",
                    str(packages_dir),
                    "--release-gate",
                    str(release_gate_path),
                    "--progress-json-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["package_dir"], str(latest_package.absolute()))
        self.assertEqual(payload["status"], "pass")
        self.assertFalse((latest_package / "release-status.json").exists())

    def test_cli_refuses_to_rewrite_after_checksums_without_explicit_allow(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-release-status-") as tmp:
            package_dir = Path(tmp) / "package"
            package_dir.mkdir()
            (package_dir / "manifest.json").write_text(
                json.dumps({"package_name": package_dir.name, "tarball": None}) + "\n",
                encoding="utf-8",
            )
            (package_dir / "evidence-checksums.json").write_text("{}\n", encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(REPORT_RELEASE_STATUS),
                    "--package-dir",
                    str(package_dir),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("Refusing to rewrite release-status files", completed.stderr)
            self.assertFalse((package_dir / "release-status.json").exists())
            self.assertFalse((package_dir / "release-status.md").exists())

    def test_cli_can_explicitly_rewrite_after_checksums(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-release-status-") as tmp:
            package_dir = Path(tmp) / "package"
            package_dir.mkdir()
            (package_dir / "manifest.json").write_text(
                json.dumps({"package_name": package_dir.name, "tarball": None}) + "\n",
                encoding="utf-8",
            )
            (package_dir / "evidence-checksums.json").write_text("{}\n", encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(REPORT_RELEASE_STATUS),
                    "--package-dir",
                    str(package_dir),
                    "--allow-post-checksum-write",
                    "--no-refresh-tarball",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue((package_dir / "release-status.json").is_file())
            self.assertTrue((package_dir / "release-status.md").is_file())
            payload = json.loads((package_dir / "release-status.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["progress_summary"]["status"], "pass")
            self.assertIn("next_commands_by_owner", payload["progress_summary"])
            self.assertIn("Release status report:", completed.stdout)


if __name__ == "__main__":
    unittest.main()
