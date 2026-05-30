#!/usr/bin/env python3
"""Smoke tests for release evidence command-safety checks."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHECK_RELEASE_EVIDENCE = PROJECT_ROOT / "scripts" / "check_release_evidence.py"


def load_check_release_evidence():
    spec = importlib.util.spec_from_file_location("check_release_evidence", CHECK_RELEASE_EVIDENCE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {CHECK_RELEASE_EVIDENCE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def checks_by_id(checks: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {str(check["id"]): check for check in checks}


class CheckReleaseEvidenceSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_check_release_evidence()

    def test_command_safety_accepts_current_handoff_commands(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-evidence-check-") as tmp:
            package_dir = Path(tmp)
            release_gate_path = Path("artifacts/release-gate/release-gate-test.json")
            snapshot_deductions = [
                {
                    "id": "external_readiness_warnings",
                    "points": 1,
                    "check_ids": ["git_origin_remote"],
                    "detail": "Git origin remote still needs connected-runner setup.",
                },
                {
                    "id": "warning_alerts",
                    "points": 1,
                    "check_ids": ["warning_actions"],
                    "detail": "Warning actions still need operator review.",
                },
            ]
            (package_dir / "release-status.json").write_text(
                json.dumps(
                    {
                        "package_dir": str(package_dir),
                        "readiness_estimate": {
                            "deductions": snapshot_deductions,
                            "percent": 96,
                            "remaining_items": 3,
                        },
                        "status": "warn",
                        "handoff_commands": [
                            {
                                "label": "Show this status report JSON",
                                "command": (
                                    "python3 scripts/report_release_status.py "
                                    "--package-dir /tmp/package --json-only"
                                ),
                            },
                            {
                                "label": "Show release progress only",
                                "command": self.module.release_status_progress_command(package_dir),
                            },
                            {
                                "label": "Show release progress JSON",
                                "command": self.module.release_status_progress_json_command(package_dir),
                            },
                            {
                                "label": "Show completion plan",
                                "command": self.module.release_status_completion_plan_command(package_dir),
                            },
                            {
                                "label": "Show completion plan JSON",
                                "command": self.module.release_status_completion_plan_json_command(package_dir),
                            },
                            {
                                "label": "Show completion requirements",
                                "command": self.module.release_status_completion_requirements_command(package_dir),
                            },
                            {
                                "label": "Show completion requirements JSON",
                                "command": self.module.release_status_completion_requirements_json_command(package_dir),
                            },
                            {
                                "label": "Show owner lanes",
                                "command": self.module.release_status_owner_lanes_command(package_dir),
                            },
                            {
                                "label": "Show owner lanes JSON",
                                "command": self.module.release_status_owner_lanes_json_command(package_dir),
                            },
                            {
                                "label": "Show external readiness summary JSON",
                                "command": self.module.external_readiness_summary_json_command(),
                            },
                            {
                                "label": "Gate external readiness summary JSON",
                                "command": self.module.external_readiness_strict_summary_json_command(),
                            },
                            {
                                "label": "Show evidence check JSON",
                                "command": (
                                    "python3 scripts/check_release_evidence.py "
                                    "--package-dir /tmp/package --json-only"
                                ),
                            },
                            {
                                "label": "Verify evidence checksums JSON",
                                "command": (
                                    "python3 scripts/write_evidence_checksums.py "
                                    "--package-dir /tmp/package --verify --json-only"
                                ),
                            },
                            {
                                "label": "Verify connected-runner handoff JSON",
                                "command": (
                                    "python3 scripts/package_connected_runner_handoff.py "
                                    "--verify /tmp/handoff --json-only"
                                ),
                            },
                            {
                                "label": "Verify connected-runner handoff summary JSON",
                                "command": (
                                    "python3 scripts/package_connected_runner_handoff.py "
                                    "--verify /tmp/handoff --summary-json-only"
                                ),
                            },
                            {
                                "label": "Show connected-runner handoff context JSON",
                                "command": self.module.connected_runner_handoff_context_json_command(
                                    "/tmp/handoff"
                                ),
                            },
                            {
                                "label": "Show connected-runner handoff command sequence",
                                "command": self.module.connected_runner_handoff_command_sequence_command(
                                    "/tmp/handoff"
                                ),
                            },
                            {
                                "label": "Run connected-runner acceptance JSON",
                                "command": (
                                    "python3 scripts/connected_runner_acceptance.py "
                                    "--handoff-root .. --require-external --check-gh-auth --json-only"
                                ),
                            },
                            {
                                "label": "Run connected-runner acceptance summary JSON",
                                "command": (
                                    "python3 scripts/connected_runner_acceptance.py "
                                    "--handoff-root .. --require-external --check-gh-auth --summary-json-only"
                                ),
                            },
                            {
                                "label": "Show local connected-runner readiness setup sequence",
                                "command": (
                                    self.module.next_release_local_readiness_setup_sequence_env_command(
                                        package_dir
                                    )
                                ),
                            },
                            {
                                "label": "Show local connected-runner readiness command sequence",
                                "command": (
                                    self.module.next_release_local_readiness_command_sequence_env_command(
                                        package_dir
                                    )
                                ),
                            },
                            {
                                "label": "Preview local connected-runner readiness setup sequence",
                                "command": (
                                    self.module.next_release_local_readiness_setup_sequence_preview_command(
                                        package_dir
                                    )
                                ),
                            },
                            {
                                "label": "Preview local connected-runner readiness command sequence",
                                "command": (
                                    self.module.next_release_local_readiness_command_sequence_preview_command(
                                        package_dir
                                    )
                                ),
                            },
                            {
                                "label": "Show remaining command sequence from env",
                                "command": self.module.next_release_command_sequence_env_command(package_dir),
                            },
                            {
                                "label": "Show warning review artifact paths",
                                "command": self.module.warning_review_artifacts_only_command(package_dir),
                            },
                            {
                                "label": "Show warning action summary JSON",
                                "command": self.module.warning_review_summary_json_command(package_dir),
                            },
                            {
                                "label": "Gate warning action summary JSON",
                                "command": self.module.warning_review_gate_summary_json_command(package_dir),
                            },
                            {
                                "label": "Show warning pre-approval sequence",
                                "command": self.module.warning_review_pre_approval_sequence_command(package_dir),
                            }
                        ],
                        "remaining_items": [
                            {
                                "id": "git_origin_remote",
                                "owner": "connected runner",
                                "preferred_command": (
                                    "cd /tmp/handoff && PREFLIGHT_ONLY=true "
                                    "GIT_ORIGIN_URL=REPLACE_WITH_REPO_URL ./run-connected-runner-handoff.sh"
                                ),
                                "status": "warn",
                                "automation_command": (
                                    "python3 scripts/next_release_step.py --package-dir /tmp/package "
                                    '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL '
                                    "--json-only --fail-if-repo-url-required --local-readiness "
                                    "--fail-if-local-readiness-not-pass"
                                ),
                                "command_gate": self.module.next_release_local_readiness_command_only_env_command(
                                    package_dir
                                ),
                            },
                            {
                                "id": "live_beta_archive",
                                "preferred_command": (
                                    "python3 scripts/archive_live_beta_closeout.py "
                                    "--api-base http://localhost:8000 --symbol KRW-BTC "
                                    "--backup-reference /backups/quant-lab.sqlite3 --preflight"
                                ),
                                "command": (
                                    "python3 scripts/archive_live_beta_closeout.py "
                                    "--api-base http://localhost:8000 --symbol KRW-BTC "
                                    "--backup-reference /backups/quant-lab.sqlite3"
                                ),
                                "automation_command": (
                                    "python3 scripts/archive_live_beta_closeout.py "
                                    "--api-base http://localhost:8000 --symbol KRW-BTC "
                                    "--backup-reference /backups/quant-lab.sqlite3 --preflight --json"
                                ),
                                "next_command_only_command": self.module.LIVE_BETA_NEXT_COMMAND_ONLY_COMMAND,
                                "final_verify_command": (
                                    "python3 scripts/release_gate.py --run-smoke "
                                    "--strict-external --check-gh-auth --require-live-beta"
                                ),
                                "supporting_commands": {
                                    "Start local backend": self.module.LOCAL_BACKEND_START_COMMAND,
                                    "Start local backend without reload": (
                                        self.module.LOCAL_BACKEND_START_NO_RELOAD_COMMAND
                                    ),
                                    "Start Docker backend": self.module.DOCKER_BACKEND_START_COMMAND,
                                    "Check backend health": self.module.backend_health_check_command(),
                                },
                            },
                            {
                                "id": "warning_actions",
                                "owner": "operator",
                                "status": "planned",
                                "command": self.module.warning_review_apply_command(package_dir),
                                "automation_command": (
                                    "python3 scripts/review_release_warnings.py "
                                    "--package-dir /tmp/package --json-only --fail-if-action-needed"
                                ),
                                "next_command_only_command": (
                                    self.module.warning_review_next_command_only_command(package_dir)
                                ),
                                "next_command_gate_command": (
                                    self.module.warning_review_next_command_gate_command(package_dir)
                                ),
                                "supporting_commands": {
                                    "Show warning pre-approval sequence": (
                                        self.module.warning_review_pre_approval_sequence_command(package_dir)
                                    ),
                                    "Show warning summary JSON": (
                                        self.module.warning_review_summary_json_command(package_dir)
                                    ),
                                    "Show warning review artifact paths": (
                                        self.module.warning_review_artifacts_only_command(package_dir)
                                    ),
                                },
                            },
                        ],
                        "progress_summary": {
                            "next_command": "cd /tmp/handoff && PREFLIGHT_ONLY=true GIT_ORIGIN_URL=REPLACE_WITH_REPO_URL ./run-connected-runner-handoff.sh",
                            "next_item_id": "git_origin_remote",
                            "next_item_owner": "connected runner",
                            "connected_runner_handoff_bundle": "/tmp/handoff",
                            "completion_impacts": self.module.completion_impacts_by_check_id(
                                snapshot_deductions
                            ),
                            "completion_plan": [
                                {
                                    "id": "git_origin_remote",
                                    "owner": "connected runner",
                                    "status": "warn",
                                    "command": (
                                        "cd /tmp/handoff && PREFLIGHT_ONLY=true "
                                        "GIT_ORIGIN_URL=REPLACE_WITH_REPO_URL "
                                        "./run-connected-runner-handoff.sh"
                                    ),
                                    "mode": "connected_runner_preflight",
                                    "requirements": [
                                        "connected_runner",
                                        "real_git_remote_url",
                                        "docker_cli",
                                        "github_cli_auth",
                                    ],
                                    "automation_command": (
                                        "python3 scripts/next_release_step.py --package-dir /tmp/package "
                                        '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL '
                                        "--json-only --fail-if-repo-url-required --local-readiness "
                                        "--fail-if-local-readiness-not-pass"
                                    ),
                                    **self.module.completion_impacts_by_check_id(snapshot_deductions)[
                                        "git_origin_remote"
                                    ],
                                },
                                {
                                    "id": "live_beta_archive",
                                    "owner": "unassigned",
                                    "status": "unknown",
                                    "command": (
                                        "python3 scripts/archive_live_beta_closeout.py "
                                        "--api-base http://localhost:8000 --symbol KRW-BTC "
                                        "--backup-reference /backups/quant-lab.sqlite3 --preflight"
                                    ),
                                    "mode": "live_beta_closeout",
                                    "requirements": [
                                        "github_cli_auth",
                                        "live_beta_window_complete",
                                        "running_backend",
                                        "backup_reference",
                                    ],
                                    "automation_command": (
                                        "python3 scripts/archive_live_beta_closeout.py "
                                        "--api-base http://localhost:8000 --symbol KRW-BTC "
                                        "--backup-reference /backups/quant-lab.sqlite3 --preflight --json"
                                    ),
                                    "final_verify_command": (
                                        "python3 scripts/release_gate.py --run-smoke "
                                        "--strict-external --check-gh-auth --require-live-beta"
                                    ),
                                },
                                {
                                    "id": "warning_actions",
                                    "owner": "operator",
                                    "status": "planned",
                                    "command": self.module.warning_review_apply_command(package_dir),
                                    "mode": "operator_approval",
                                    "requirements": [
                                        "operator_checklist_review",
                                        "operator_approval",
                                        "running_backend",
                                    ],
                                    "backend": self.module.expected_warning_backend_guidance(),
                                    "automation_command": (
                                        "python3 scripts/review_release_warnings.py "
                                        "--package-dir /tmp/package --json-only --fail-if-action-needed"
                                    ),
                                    **self.module.completion_impacts_by_check_id(snapshot_deductions)[
                                        "warning_actions"
                                    ],
                                    "requires_operator_approval": True,
                                    "pre_approval_review_sequence": [
                                        self.module.warning_review_summary_json_command(package_dir),
                                        self.module.warning_review_artifacts_only_command(package_dir),
                                    ],
                                    "review_sequence": [
                                        self.module.warning_review_summary_json_command(package_dir),
                                        self.module.warning_review_artifacts_only_command(package_dir),
                                        self.module.warning_review_apply_command(package_dir),
                                    ],
                                },
                            ],
                            "completion_requirements": [
                                {
                                    "requirement": "connected_runner",
                                    "item_ids": ["git_origin_remote"],
                                    "owners": ["connected runner"],
                                    "count": 1,
                                },
                                {
                                    "requirement": "real_git_remote_url",
                                    "item_ids": ["git_origin_remote"],
                                    "owners": ["connected runner"],
                                    "count": 1,
                                },
                                {
                                    "requirement": "docker_cli",
                                    "item_ids": ["git_origin_remote"],
                                    "owners": ["connected runner"],
                                    "count": 1,
                                },
                                {
                                    "requirement": "github_cli_auth",
                                    "item_ids": ["git_origin_remote", "live_beta_archive"],
                                    "owners": ["connected runner", "unassigned"],
                                    "count": 2,
                                },
                                {
                                    "requirement": "live_beta_window_complete",
                                    "item_ids": ["live_beta_archive"],
                                    "owners": ["unassigned"],
                                    "count": 1,
                                },
                                {
                                    "requirement": "running_backend",
                                    "item_ids": ["live_beta_archive", "warning_actions"],
                                    "owners": ["unassigned", "operator"],
                                    "count": 2,
                                },
                                {
                                    "requirement": "backup_reference",
                                    "item_ids": ["live_beta_archive"],
                                    "owners": ["unassigned"],
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
                            "deductions": snapshot_deductions,
                            "package_dir": str(package_dir),
                            "percent": 96,
                            "release_gate_path": str(release_gate_path),
                            "remaining_by_owner": {
                                "connected runner": 1,
                                "operator": 1,
                            },
                            "remaining_ids": [
                                "git_origin_remote",
                                "live_beta_archive",
                                "warning_actions",
                            ],
                            "remaining_items": 3,
                            "status": "warn",
                            "next_commands_by_owner": {
                                "connected runner": {
                                    "id": "git_origin_remote",
                                    "status": "warn",
                                    "command": "cd /tmp/handoff && PREFLIGHT_ONLY=true GIT_ORIGIN_URL=REPLACE_WITH_REPO_URL ./run-connected-runner-handoff.sh",
                                    **self.module.completion_impacts_by_check_id(snapshot_deductions)[
                                        "git_origin_remote"
                                    ],
                                    "full_flow_command": (
                                        "cd /tmp/handoff && GIT_ORIGIN_URL=REPLACE_WITH_REPO_URL "
                                        "./run-connected-runner-handoff.sh"
                                    ),
                                    "supporting_commands": {
                                        "Show connected-runner command only from env": (
                                            self.module.next_release_connected_command_only_env_command(package_dir)
                                        ),
                                        "Show external readiness summary JSON": (
                                            self.module.external_readiness_summary_json_command()
                                        ),
                                        "Gate external readiness summary JSON": (
                                            self.module.external_readiness_strict_summary_json_command()
                                        ),
                                        "Show local readiness setup sequence": (
                                            self.module.next_release_local_readiness_setup_sequence_env_command(
                                                package_dir
                                            )
                                        ),
                                        "Show local readiness command sequence": (
                                            self.module.next_release_local_readiness_command_sequence_env_command(
                                                package_dir
                                            )
                                        ),
                                        "Preview local readiness setup sequence": (
                                            self.module.next_release_local_readiness_setup_sequence_preview_command(
                                                package_dir
                                            )
                                        ),
                                        "Preview local readiness command sequence": (
                                            self.module.next_release_local_readiness_command_sequence_preview_command(
                                                package_dir
                                            )
                                        ),
                                    },
                                },
                                "operator": {
                                    "id": "warning_actions",
                                    "status": "planned",
                                    "command": self.module.warning_review_apply_command(package_dir),
                                    **self.module.completion_impacts_by_check_id(snapshot_deductions)[
                                        "warning_actions"
                                    ],
                                    "automation_command": (
                                        "python3 scripts/review_release_warnings.py "
                                        "--package-dir /tmp/package --json-only --fail-if-action-needed"
                                    ),
                                    "supporting_commands": {
                                        "Show warning pre-approval sequence": (
                                            self.module.warning_review_pre_approval_sequence_command(package_dir)
                                        ),
                                        "Show warning summary JSON": (
                                            self.module.warning_review_summary_json_command(package_dir)
                                        ),
                                        "Gate warning summary JSON": (
                                            self.module.warning_review_gate_summary_json_command(package_dir)
                                        ),
                                        "Show warning review artifact paths": (
                                            self.module.warning_review_artifacts_only_command(package_dir)
                                        ),
                                        "Gate warning recommended next command": (
                                            self.module.warning_review_next_command_gate_command(package_dir)
                                        ),
                                    },
                                    "review_artifacts": {
                                        "action_plan": str(package_dir / "release-warning-actions.md"),
                                        "operator_checklist": str(
                                            package_dir / "release-warning-operator-checklist.md"
                                        ),
                                    },
                                }
                            },
                            "owner_lanes": {
                                "connected runner": {
                                    "remaining_items": 1,
                                    "remaining_ids": ["git_origin_remote"],
                                    "next_item_id": "git_origin_remote",
                                    "status": "warn",
                                    "mode": "connected_runner_preflight",
                                    "requirements": [
                                        "connected_runner",
                                        "real_git_remote_url",
                                        "docker_cli",
                                        "github_cli_auth",
                                    ],
                                    "next_requires_operator_approval": False,
                                    "requires_operator_approval": False,
                                    "review_artifacts": {},
                                    "supporting_command_labels": [
                                        "Show external readiness summary JSON",
                                        "Gate external readiness summary JSON",
                                        "Show local readiness setup sequence",
                                        "Show local readiness command sequence",
                                        "Preview local readiness setup sequence",
                                        "Preview local readiness command sequence",
                                        "Show connected-runner command only from env",
                                    ],
                                    "commands": {
                                        "next": (
                                            "cd /tmp/handoff && PREFLIGHT_ONLY=true "
                                            "GIT_ORIGIN_URL=REPLACE_WITH_REPO_URL "
                                            "./run-connected-runner-handoff.sh"
                                        ),
                                        "automation": (
                                            "python3 scripts/next_release_step.py --package-dir /tmp/package "
                                            '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL '
                                            "--json-only --fail-if-repo-url-required --local-readiness "
                                            "--fail-if-local-readiness-not-pass"
                                        ),
                                        "full_flow": (
                                            "cd /tmp/handoff && GIT_ORIGIN_URL=REPLACE_WITH_REPO_URL "
                                            "./run-connected-runner-handoff.sh"
                                        ),
                                        "supporting": {
                                            "Show connected-runner command only from env": (
                                                self.module.next_release_connected_command_only_env_command(package_dir)
                                            ),
                                            "Show external readiness summary JSON": (
                                                self.module.external_readiness_summary_json_command()
                                            ),
                                            "Gate external readiness summary JSON": (
                                                self.module.external_readiness_strict_summary_json_command()
                                            ),
                                            "Show local readiness setup sequence": (
                                                self.module.next_release_local_readiness_setup_sequence_env_command(
                                                    package_dir
                                                )
                                            ),
                                            "Show local readiness command sequence": (
                                                self.module.next_release_local_readiness_command_sequence_env_command(
                                                    package_dir
                                                )
                                            ),
                                            "Preview local readiness setup sequence": (
                                                self.module.next_release_local_readiness_setup_sequence_preview_command(
                                                    package_dir
                                                )
                                            ),
                                            "Preview local readiness command sequence": (
                                                self.module.next_release_local_readiness_command_sequence_preview_command(
                                                    package_dir
                                                )
                                            ),
                                        },
                                    },
                                    "has_automation_command": True,
                                    "has_full_flow_command": True,
                                    "repo_url": {
                                        "required": True,
                                        "placeholder": self.module.REPO_URL_PLACEHOLDER,
                                        "export_command": self.module.repo_url_export_example_command(),
                                        "command_gate": (
                                            self.module.next_release_connected_command_only_env_command(package_dir)
                                        ),
                                        "json_gate": (
                                            "python3 scripts/next_release_step.py --package-dir /tmp/package "
                                            '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL '
                                            "--json-only --fail-if-repo-url-required --local-readiness "
                                            "--fail-if-local-readiness-not-pass"
                                        ),
                                        "note": (
                                            f"Replace {self.module.REPO_URL_PLACEHOLDER} with a real HTTPS, SSH, or "
                                            "scp-style git remote URL before running connected-runner commands."
                                        ),
                                    },
                                    "readiness": {
                                        "status": "warn",
                                        "issue_ids": ["git_origin_remote"],
                                        "next_setup": {
                                            "id": "git_origin_remote",
                                            "status": "warn",
                                            "setup_command": (
                                                "cd /tmp/handoff/source && git remote add origin "
                                                "REPLACE_WITH_REPO_URL"
                                            ),
                                            "verify_command": (
                                                "cd /tmp/handoff/source && git remote get-url origin"
                                            ),
                                        },
                                        "next_setup_command": (
                                            "cd /tmp/handoff/source && git remote add origin REPLACE_WITH_REPO_URL"
                                        ),
                                        "setup_sequence": [
                                            "cd /tmp/handoff/source && git remote add origin REPLACE_WITH_REPO_URL"
                                        ],
                                        "verify_sequence": [
                                            "cd /tmp/handoff/source && git remote get-url origin"
                                        ],
                                        "command_sequence": [
                                            "cd /tmp/handoff/source && git remote add origin REPLACE_WITH_REPO_URL",
                                            "cd /tmp/handoff/source && git remote get-url origin",
                                        ],
                                        "json_command": (
                                            self.module.next_release_local_readiness_json_env_command(package_dir)
                                        ),
                                        "command_only_gate": (
                                            self.module.next_release_local_readiness_command_only_env_command(
                                                package_dir
                                            )
                                        ),
                                        "setup_sequence_command": (
                                            self.module.next_release_local_readiness_setup_sequence_env_command(
                                                package_dir
                                            )
                                        ),
                                        "command_sequence_command": (
                                            self.module.next_release_local_readiness_command_sequence_env_command(
                                                package_dir
                                            )
                                        ),
                                        "setup_sequence_preview_command": (
                                            self.module.next_release_local_readiness_setup_sequence_preview_command(
                                                package_dir
                                            )
                                        ),
                                        "command_sequence_preview_command": (
                                            self.module.next_release_local_readiness_command_sequence_preview_command(
                                                package_dir
                                            )
                                        ),
                                        "json_gate": (
                                            self.module.next_release_local_readiness_gate_json_env_command(package_dir)
                                        ),
                                        "external_summary_json": self.module.external_readiness_summary_json_command(),
                                        "external_strict_summary_json": (
                                            self.module.external_readiness_strict_summary_json_command()
                                        ),
                                    },
                                },
                                "operator": {
                                    "remaining_items": 1,
                                    "remaining_ids": ["warning_actions"],
                                    "next_item_id": "warning_actions",
                                    "status": "planned",
                                    "mode": "operator_approval",
                                    "requirements": [
                                        "operator_checklist_review",
                                        "operator_approval",
                                        "running_backend",
                                    ],
                                    "next_requires_operator_approval": True,
                                    "requires_operator_approval": True,
                                    "review_artifacts": {
                                        "action_plan": str(package_dir / "release-warning-actions.md"),
                                        "operator_checklist": str(
                                            package_dir / "release-warning-operator-checklist.md"
                                        ),
                                    },
                                    "supporting_command_labels": [
                                        "Show warning pre-approval sequence",
                                        "Show warning summary JSON",
                                        "Show warning review artifact paths",
                                        "Gate warning summary JSON",
                                        "Gate warning recommended next command",
                                    ],
                                    "commands": {
                                        "next": self.module.warning_review_apply_command(package_dir),
                                        "automation": (
                                            "python3 scripts/review_release_warnings.py "
                                            "--package-dir /tmp/package --json-only --fail-if-action-needed"
                                        ),
                                        "supporting": {
                                            "Show warning pre-approval sequence": (
                                                self.module.warning_review_pre_approval_sequence_command(package_dir)
                                            ),
                                            "Show warning summary JSON": (
                                                self.module.warning_review_summary_json_command(package_dir)
                                            ),
                                            "Gate warning summary JSON": (
                                                self.module.warning_review_gate_summary_json_command(package_dir)
                                            ),
                                            "Show warning review artifact paths": (
                                                self.module.warning_review_artifacts_only_command(package_dir)
                                            ),
                                            "Gate warning recommended next command": (
                                                self.module.warning_review_next_command_gate_command(package_dir)
                                            ),
                                        },
                                    },
                                    "has_automation_command": True,
                                    "has_full_flow_command": False,
                                    "review": {
                                        "status": "planned",
                                        "action_needed": True,
                                        "issue_ids": ["warning_actions"],
                                        "next_command": self.module.warning_review_apply_command(package_dir),
                                        "requires_operator_approval": True,
                                        "summary_json": (
                                            self.module.warning_review_summary_json_command(package_dir)
                                        ),
                                        "gate_summary_json": (
                                            self.module.warning_review_gate_summary_json_command(package_dir)
                                        ),
                                        "pre_approval_sequence_command": (
                                            self.module.warning_review_pre_approval_sequence_command(package_dir)
                                        ),
                                        "gate_json": (
                                            "python3 scripts/review_release_warnings.py --package-dir /tmp/package "
                                            "--json-only --fail-if-action-needed"
                                        ),
                                        "next_command_gate": (
                                            self.module.warning_review_next_command_gate_command(package_dir)
                                        ),
                                        "review_artifacts_command": (
                                            self.module.warning_review_artifacts_only_command(package_dir)
                                        ),
                                        "review_artifacts": {
                                            "action_plan": str(package_dir / "release-warning-actions.md"),
                                            "operator_checklist": str(
                                                package_dir / "release-warning-operator-checklist.md"
                                            ),
                                        },
                                        "review_sequence_command": (
                                            "python3 scripts/next_release_step.py --package-dir /tmp/package "
                                            "--owner operator --command-sequence-only --skip-operator-approved "
                                            "--fail-if-repo-url-required"
                                        ),
                                        "pre_approval_review_sequence": [
                                            self.module.warning_review_summary_json_command(package_dir),
                                            self.module.warning_review_artifacts_only_command(package_dir),
                                        ],
                                        "review_sequence": [
                                            self.module.warning_review_summary_json_command(package_dir),
                                            self.module.warning_review_artifacts_only_command(package_dir),
                                            self.module.warning_review_apply_command(package_dir),
                                        ],
                                        "backend": {
                                            "backend": (
                                                "start the backend before applying reviewed warning actions"
                                            ),
                                            "local_start_command": self.module.LOCAL_BACKEND_START_COMMAND,
                                            "local_start_no_reload_command": (
                                                self.module.LOCAL_BACKEND_START_NO_RELOAD_COMMAND
                                            ),
                                            "docker_start_command": self.module.DOCKER_BACKEND_START_COMMAND,
                                            "health_check_command": self.module.backend_health_check_command(),
                                        },
                                    },
                                },
                                "unassigned": {
                                    "remaining_items": 1,
                                    "remaining_ids": ["live_beta_archive"],
                                    "next_item_id": "live_beta_archive",
                                    "status": "unknown",
                                    "mode": "live_beta_closeout",
                                    "requirements": [
                                        "github_cli_auth",
                                        "live_beta_window_complete",
                                        "running_backend",
                                        "backup_reference",
                                    ],
                                    "next_requires_operator_approval": False,
                                    "requires_operator_approval": False,
                                    "review_artifacts": {},
                                    "supporting_command_labels": [],
                                    "commands": {
                                        "next": (
                                            "python3 scripts/archive_live_beta_closeout.py "
                                            "--api-base http://localhost:8000 --symbol KRW-BTC "
                                            "--backup-reference /backups/quant-lab.sqlite3 --preflight"
                                        ),
                                        "automation": (
                                            "python3 scripts/archive_live_beta_closeout.py "
                                            "--api-base http://localhost:8000 --symbol KRW-BTC "
                                            "--backup-reference /backups/quant-lab.sqlite3 --preflight --json"
                                        ),
                                    },
                                    "has_automation_command": True,
                                    "has_full_flow_command": False,
                                },
                            },
                            "commands": {
                                "export_repo_url_example": self.module.repo_url_export_example_command(),
                                "next_command_only": (
                                    "python3 scripts/next_release_step.py --package-dir /tmp/package "
                                    "--repo-url-from-env GIT_ORIGIN_URL --command-only "
                                    "--fail-if-repo-url-required"
                                ),
                                "next_json_only": (
                                    "python3 scripts/next_release_step.py --package-dir /tmp/package "
                                    "--repo-url-from-env GIT_ORIGIN_URL --json-only "
                                    "--fail-if-repo-url-required"
                                ),
                                "connected_runner_command_only": (
                                    "python3 scripts/next_release_step.py --package-dir /tmp/package "
                                    '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL '
                                    "--command-only --fail-if-repo-url-required"
                                ),
                                "connected_runner_command_sequence": (
                                    "python3 scripts/next_release_step.py --package-dir /tmp/package "
                                    '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL '
                                    "--command-sequence-only --fail-if-repo-url-required"
                                ),
                                "operator_command_only": (
                                    "python3 scripts/next_release_step.py --package-dir /tmp/package "
                                    "--owner operator --command-only --fail-if-repo-url-required"
                                ),
                                "operator_command_sequence": (
                                    "python3 scripts/next_release_step.py --package-dir /tmp/package "
                                    "--owner operator --command-sequence-only --fail-if-repo-url-required"
                                ),
                                "operator_review_sequence": (
                                    "python3 scripts/next_release_step.py --package-dir /tmp/package "
                                    "--owner operator --command-sequence-only --skip-operator-approved "
                                    "--fail-if-repo-url-required"
                                ),
                                "operator_json_only": (
                                    "python3 scripts/next_release_step.py --package-dir /tmp/package "
                                    "--owner operator --json-only --fail-if-repo-url-required"
                                ),
                                "remaining_sequence": self.module.next_release_command_sequence_env_command(package_dir),
                                "show_progress": self.module.release_status_progress_command(
                                    package_dir,
                                    release_gate_path,
                                ),
                                "show_progress_json": self.module.release_status_progress_json_command(
                                    package_dir,
                                    release_gate_path,
                                ),
                                "show_completion_plan": (
                                    self.module.release_status_completion_plan_command(
                                        package_dir,
                                        release_gate_path,
                                    )
                                ),
                                "show_completion_plan_json": (
                                    self.module.release_status_completion_plan_json_command(
                                        package_dir,
                                        release_gate_path,
                                    )
                                ),
                                "show_completion_requirements": (
                                    self.module.release_status_completion_requirements_command(
                                        package_dir,
                                        release_gate_path,
                                    )
                                ),
                                "show_completion_requirements_json": (
                                    self.module.release_status_completion_requirements_json_command(
                                        package_dir,
                                        release_gate_path,
                                    )
                                ),
                                "show_owner_lanes": (
                                    self.module.release_status_owner_lanes_command(
                                        package_dir,
                                        release_gate_path,
                                    )
                                ),
                                "show_owner_lanes_json": (
                                    self.module.release_status_owner_lanes_json_command(
                                        package_dir,
                                        release_gate_path,
                                    )
                                ),
                                "local_readiness_json": (
                                    self.module.next_release_local_readiness_json_env_command(package_dir)
                                ),
                                "local_readiness_command_only": (
                                    self.module.next_release_local_readiness_command_only_env_command(package_dir)
                                ),
                                "local_readiness_setup_sequence": (
                                    self.module.next_release_local_readiness_setup_sequence_env_command(package_dir)
                                ),
                                "local_readiness_command_sequence": (
                                    self.module.next_release_local_readiness_command_sequence_env_command(package_dir)
                                ),
                                "local_readiness_setup_sequence_preview": (
                                    self.module.next_release_local_readiness_setup_sequence_preview_command(
                                        package_dir
                                    )
                                ),
                                "local_readiness_command_sequence_preview": (
                                    self.module.next_release_local_readiness_command_sequence_preview_command(
                                        package_dir
                                    )
                                ),
                                "local_readiness_gate_json": (
                                    self.module.next_release_local_readiness_gate_json_env_command(package_dir)
                                ),
                                "external_readiness_summary_json": (
                                    self.module.external_readiness_summary_json_command()
                                ),
                                "external_readiness_strict_summary_json": (
                                    self.module.external_readiness_strict_summary_json_command()
                                ),
                                "connected_runner_acceptance_summary_json": (
                                    self.module.connected_runner_acceptance_summary_json_command()
                                ),
                                "handoff_bundle_verify_summary_json": (
                                    self.module.connected_runner_verify_summary_json_command("/tmp/handoff")
                                ),
                                "handoff_context_json": (
                                    self.module.connected_runner_handoff_context_json_command("/tmp/handoff")
                                ),
                                "handoff_command_sequence": (
                                    self.module.connected_runner_handoff_command_sequence_command("/tmp/handoff")
                                ),
                                "warning_gate_json": (
                                    "python3 scripts/review_release_warnings.py --package-dir /tmp/package "
                                    "--json-only --fail-if-action-needed"
                                ),
                                "warning_summary_json": (
                                    self.module.warning_review_summary_json_command(package_dir)
                                ),
                                "warning_gate_summary_json": (
                                    self.module.warning_review_gate_summary_json_command(package_dir)
                                ),
                                "warning_pre_approval_sequence": (
                                    self.module.warning_review_pre_approval_sequence_command(package_dir)
                                ),
                                "warning_next_command_gate": (
                                    self.module.warning_review_next_command_gate_command(package_dir)
                                ),
                                "warning_review_artifacts": (
                                    self.module.warning_review_artifacts_only_command(package_dir)
                                ),
                                "warning_apply": self.module.warning_review_apply_command(package_dir),
                            },
                            "repo_url": {
                                "required": True,
                                "placeholder": self.module.REPO_URL_PLACEHOLDER,
                                "export_command": self.module.repo_url_export_example_command(),
                                "command_gate": self.module.next_release_command_only_env_command(package_dir),
                                "json_gate": self.module.next_release_json_only_env_command(package_dir),
                                "message": (
                                    "Replace REPLACE_WITH_REPO_URL with a real git remote URL before "
                                    "running connected-runner commands."
                                ),
                            },
                            "local_readiness": {
                                "status": "warn",
                                "issue_ids": ["git_origin_remote"],
                                "next_setup": {
                                    "id": "git_origin_remote",
                                    "status": "warn",
                                    "setup_command": (
                                        "cd /tmp/handoff/source && git remote add origin "
                                        "REPLACE_WITH_REPO_URL"
                                    ),
                                    "verify_command": "cd /tmp/handoff/source && git remote get-url origin",
                                },
                                "next_setup_command": (
                                    "cd /tmp/handoff/source && git remote add origin REPLACE_WITH_REPO_URL"
                                ),
                                "setup_sequence": [
                                    "cd /tmp/handoff/source && git remote add origin REPLACE_WITH_REPO_URL"
                                ],
                                "verify_sequence": ["cd /tmp/handoff/source && git remote get-url origin"],
                                "command_sequence": [
                                    "cd /tmp/handoff/source && git remote add origin REPLACE_WITH_REPO_URL",
                                    "cd /tmp/handoff/source && git remote get-url origin",
                                ],
                                "json_command": (
                                    self.module.next_release_local_readiness_json_env_command(package_dir)
                                ),
                                "command_only_gate": (
                                    self.module.next_release_local_readiness_command_only_env_command(package_dir)
                                ),
                                "setup_sequence_command": (
                                    self.module.next_release_local_readiness_setup_sequence_env_command(package_dir)
                                ),
                                "command_sequence_command": (
                                    self.module.next_release_local_readiness_command_sequence_env_command(package_dir)
                                ),
                                "setup_sequence_preview_command": (
                                    self.module.next_release_local_readiness_setup_sequence_preview_command(
                                        package_dir
                                    )
                                ),
                                "command_sequence_preview_command": (
                                    self.module.next_release_local_readiness_command_sequence_preview_command(
                                        package_dir
                                    )
                                ),
                                "json_gate": (
                                    self.module.next_release_local_readiness_gate_json_env_command(package_dir)
                                ),
                                "external_summary_json": self.module.external_readiness_summary_json_command(),
                                "external_strict_summary_json": (
                                    self.module.external_readiness_strict_summary_json_command()
                                ),
                            },
                            "warning_review": {
                                "status": "planned",
                                "action_needed": True,
                                "issue_ids": ["warning_actions"],
                                "next_command": self.module.warning_review_apply_command(package_dir),
                                "requires_operator_approval": True,
                                "summary_json": self.module.warning_review_summary_json_command(package_dir),
                                "gate_summary_json": (
                                    self.module.warning_review_gate_summary_json_command(package_dir)
                                ),
                                "pre_approval_sequence_command": (
                                    self.module.warning_review_pre_approval_sequence_command(package_dir)
                                ),
                                "gate_json": (
                                    "python3 scripts/review_release_warnings.py --package-dir /tmp/package "
                                    "--json-only --fail-if-action-needed"
                                ),
                                "next_command_gate": self.module.warning_review_next_command_gate_command(package_dir),
                                "review_artifacts_command": (
                                    self.module.warning_review_artifacts_only_command(package_dir)
                                ),
                                "apply_command": self.module.warning_review_apply_command(package_dir),
                                "review_artifacts": {
                                    "action_plan": str(package_dir / "release-warning-actions.md"),
                                    "operator_checklist": str(
                                        package_dir / "release-warning-operator-checklist.md"
                                    ),
                                },
                                "review_sequence_command": (
                                    "python3 scripts/next_release_step.py --package-dir /tmp/package "
                                    "--owner operator --command-sequence-only --skip-operator-approved "
                                    "--fail-if-repo-url-required"
                                ),
                                "pre_approval_review_sequence": [
                                    self.module.warning_review_summary_json_command(package_dir),
                                    self.module.warning_review_artifacts_only_command(package_dir),
                                ],
                                "review_sequence": [
                                    self.module.warning_review_summary_json_command(package_dir),
                                    self.module.warning_review_artifacts_only_command(package_dir),
                                    self.module.warning_review_apply_command(package_dir),
                                ],
                                "backend": {
                                    "backend": "start the backend before applying reviewed warning actions",
                                    "local_start_command": self.module.LOCAL_BACKEND_START_COMMAND,
                                    "local_start_no_reload_command": (
                                        self.module.LOCAL_BACKEND_START_NO_RELOAD_COMMAND
                                    ),
                                    "docker_start_command": self.module.DOCKER_BACKEND_START_COMMAND,
                                    "health_check_command": self.module.backend_health_check_command(),
                                },
                            },
                        },
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            (package_dir / "next-release-step.json").write_text(
                json.dumps(
                    {
                        "next_command": (
                            "cd /tmp/handoff && PREFLIGHT_ONLY=true "
                            "GIT_ORIGIN_URL=REPLACE_WITH_REPO_URL ./run-connected-runner-handoff.sh"
                        ),
                        "repo_url_required": True,
                        "repo_url_export_command": self.module.repo_url_export_example_command(),
                        "repo_url_command_gate": self.module.next_release_command_only_env_command(package_dir),
                        "repo_url_json_gate": self.module.next_release_connected_json_only_env_command(package_dir),
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            checks = checks_by_id(self.module.check_handoff_command_safety(package_dir))

        self.assertEqual(checks["handoff_backup_reference_placeholders_absent"]["status"], "pass")
        self.assertEqual(checks["handoff_repo_url_placeholder_shell_safe"]["status"], "pass")
        self.assertEqual(checks["handoff_repo_url_required_gate"]["status"], "pass")
        self.assertEqual(checks["handoff_repo_url_top_level_gates"]["status"], "pass")
        self.assertEqual(checks["handoff_repo_url_export_example"]["status"], "pass")
        self.assertEqual(checks["handoff_command_sequence_only"]["status"], "pass")
        self.assertEqual(checks["handoff_release_status_json_command"]["status"], "pass")
        self.assertEqual(checks["handoff_release_status_progress_command"]["status"], "pass")
        self.assertEqual(checks["handoff_release_status_progress_json_command"]["status"], "pass")
        self.assertEqual(checks["handoff_release_status_completion_plan_command"]["status"], "pass")
        self.assertEqual(checks["handoff_release_status_completion_plan_json_command"]["status"], "pass")
        self.assertEqual(checks["handoff_release_status_completion_requirements_command"]["status"], "pass")
        self.assertEqual(checks["handoff_release_status_completion_requirements_json_command"]["status"], "pass")
        self.assertEqual(checks["handoff_release_status_owner_lanes_command"]["status"], "pass")
        self.assertEqual(checks["handoff_release_status_owner_lanes_json_command"]["status"], "pass")
        self.assertEqual(checks["handoff_release_status_progress_summary"]["status"], "pass")
        self.assertEqual(checks["handoff_release_status_progress_snapshot"]["status"], "pass")
        self.assertEqual(checks["handoff_release_status_progress_owner_next"]["status"], "pass")
        self.assertEqual(checks["handoff_release_status_progress_next_step_command"]["status"], "pass")
        self.assertEqual(checks["handoff_release_status_progress_release_gate"]["status"], "pass")
        self.assertEqual(checks["handoff_release_status_progress_repo_url"]["status"], "pass")
        self.assertEqual(checks["handoff_release_status_progress_local_readiness"]["status"], "pass")
        self.assertEqual(checks["handoff_release_status_progress_warning_review"]["status"], "pass")
        self.assertEqual(checks["handoff_release_status_owner_supporting_commands"]["status"], "pass")
        self.assertEqual(checks["handoff_release_status_progress_handoff_bundle"]["status"], "pass")
        self.assertEqual(checks["handoff_external_readiness_summary_json_command"]["status"], "pass")
        self.assertEqual(checks["handoff_external_readiness_strict_summary_json_command"]["status"], "pass")
        self.assertEqual(checks["handoff_release_evidence_json_command"]["status"], "pass")
        self.assertEqual(checks["handoff_evidence_checksum_json_verify_command"]["status"], "pass")
        self.assertEqual(checks["handoff_bundle_verify_json_command"]["status"], "pass")
        self.assertEqual(checks["handoff_bundle_verify_summary_json_command"]["status"], "pass")
        self.assertEqual(checks["handoff_connected_runner_acceptance_json_command"]["status"], "pass")
        self.assertEqual(checks["handoff_connected_runner_acceptance_summary_json_command"]["status"], "pass")
        self.assertEqual(checks["handoff_live_beta_backup_reference_example"]["status"], "pass")
        self.assertEqual(checks["handoff_live_beta_preflight_json_command"]["status"], "pass")
        self.assertEqual(checks["handoff_live_beta_backend_support_commands"]["status"], "pass")
        self.assertEqual(checks["handoff_live_beta_command_builder_set"]["status"], "pass")
        self.assertEqual(checks["handoff_warning_apply_operator_approval"]["status"], "pass")
        self.assertEqual(checks["handoff_warning_json_action_gate"]["status"], "pass")
        self.assertEqual(checks["handoff_warning_summary_json"]["status"], "pass")
        self.assertEqual(checks["handoff_warning_summary_json_gate"]["status"], "pass")
        self.assertEqual(checks["handoff_warning_next_command_only"]["status"], "pass")
        self.assertEqual(checks["handoff_warning_next_command_gate"]["status"], "pass")
        self.assertEqual(checks["handoff_warning_review_artifacts_only"]["status"], "pass")
        self.assertEqual(checks["handoff_local_readiness_json_gate"]["status"], "pass")
        self.assertEqual(checks["handoff_local_readiness_command_gate"]["status"], "pass")
        self.assertEqual(checks["handoff_local_readiness_setup_sequence"]["status"], "pass")
        self.assertEqual(checks["handoff_local_readiness_command_sequence"]["status"], "pass")
        self.assertEqual(checks["handoff_local_readiness_setup_sequence_preview"]["status"], "pass")
        self.assertEqual(checks["handoff_local_readiness_command_sequence_preview"]["status"], "pass")

    def test_command_safety_is_skipped_before_handoff_commands_exist(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-evidence-check-") as tmp:
            checks = checks_by_id(self.module.check_handoff_command_safety(Path(tmp)))

        self.assertEqual(checks["handoff_command_artifacts"]["status"], "skipped")
        self.assertEqual(checks["handoff_backup_reference_placeholders_absent"]["status"], "skipped")
        self.assertEqual(checks["handoff_repo_url_placeholder_shell_safe"]["status"], "skipped")
        self.assertEqual(checks["handoff_repo_url_required_gate"]["status"], "skipped")
        self.assertEqual(checks["handoff_repo_url_top_level_gates"]["status"], "skipped")
        self.assertEqual(checks["handoff_release_status_json_command"]["status"], "skipped")
        self.assertEqual(checks["handoff_release_status_progress_command"]["status"], "skipped")
        self.assertEqual(checks["handoff_release_status_progress_json_command"]["status"], "skipped")
        self.assertEqual(checks["handoff_release_status_completion_plan_command"]["status"], "skipped")
        self.assertEqual(checks["handoff_release_status_completion_plan_json_command"]["status"], "skipped")
        self.assertEqual(checks["handoff_release_status_completion_requirements_command"]["status"], "skipped")
        self.assertEqual(checks["handoff_release_status_completion_requirements_json_command"]["status"], "skipped")
        self.assertEqual(checks["handoff_release_status_owner_lanes_command"]["status"], "skipped")
        self.assertEqual(checks["handoff_release_status_owner_lanes_json_command"]["status"], "skipped")
        self.assertEqual(checks["handoff_release_status_progress_summary"]["status"], "skipped")
        self.assertEqual(checks["handoff_release_status_progress_snapshot"]["status"], "skipped")
        self.assertEqual(checks["handoff_release_status_progress_owner_next"]["status"], "skipped")
        self.assertEqual(checks["handoff_release_status_progress_next_step_command"]["status"], "skipped")
        self.assertEqual(checks["handoff_release_status_progress_release_gate"]["status"], "skipped")
        self.assertEqual(checks["handoff_release_status_progress_repo_url"]["status"], "skipped")
        self.assertEqual(checks["handoff_release_status_progress_local_readiness"]["status"], "skipped")
        self.assertEqual(checks["handoff_release_status_progress_warning_review"]["status"], "skipped")
        self.assertEqual(checks["handoff_release_status_owner_supporting_commands"]["status"], "skipped")
        self.assertEqual(checks["handoff_release_status_progress_handoff_bundle"]["status"], "skipped")
        self.assertEqual(checks["handoff_external_readiness_summary_json_command"]["status"], "skipped")
        self.assertEqual(checks["handoff_external_readiness_strict_summary_json_command"]["status"], "skipped")
        self.assertEqual(checks["handoff_command_sequence_only"]["status"], "skipped")
        self.assertEqual(checks["handoff_release_evidence_json_command"]["status"], "skipped")
        self.assertEqual(checks["handoff_evidence_checksum_json_verify_command"]["status"], "skipped")
        self.assertEqual(checks["handoff_bundle_verify_json_command"]["status"], "skipped")
        self.assertEqual(checks["handoff_bundle_verify_summary_json_command"]["status"], "skipped")
        self.assertEqual(checks["handoff_connected_runner_acceptance_json_command"]["status"], "skipped")
        self.assertEqual(
            checks["handoff_connected_runner_acceptance_summary_json_command"]["status"], "skipped"
        )
        self.assertEqual(checks["handoff_live_beta_backup_reference_example"]["status"], "skipped")
        self.assertEqual(checks["handoff_live_beta_preflight_json_command"]["status"], "skipped")
        self.assertEqual(checks["handoff_live_beta_backend_support_commands"]["status"], "skipped")
        self.assertEqual(checks["handoff_live_beta_command_builder_set"]["status"], "skipped")
        self.assertEqual(checks["handoff_warning_apply_operator_approval"]["status"], "skipped")
        self.assertEqual(checks["handoff_warning_json_action_gate"]["status"], "skipped")
        self.assertEqual(checks["handoff_warning_summary_json"]["status"], "skipped")
        self.assertEqual(checks["handoff_warning_summary_json_gate"]["status"], "skipped")
        self.assertEqual(checks["handoff_warning_next_command_only"]["status"], "skipped")
        self.assertEqual(checks["handoff_warning_next_command_gate"]["status"], "skipped")
        self.assertEqual(checks["handoff_warning_review_artifacts_only"]["status"], "skipped")
        self.assertEqual(checks["handoff_local_readiness_json_gate"]["status"], "skipped")
        self.assertEqual(checks["handoff_local_readiness_command_gate"]["status"], "skipped")
        self.assertEqual(checks["handoff_local_readiness_setup_sequence"]["status"], "skipped")
        self.assertEqual(checks["handoff_local_readiness_command_sequence"]["status"], "skipped")
        self.assertEqual(checks["handoff_local_readiness_setup_sequence_preview"]["status"], "skipped")
        self.assertEqual(checks["handoff_local_readiness_command_sequence_preview"]["status"], "skipped")

    def test_command_safety_rejects_old_placeholders_and_unapproved_apply(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-evidence-check-") as tmp:
            package_dir = Path(tmp)
            (package_dir / "release-status.md").write_text(
                "\n".join(
                    [
                        "```bash",
                        "python3 scripts/archive_live_beta_closeout.py --backup-reference PATH_TO_BACKUP",
                        "```",
                        "```bash",
                        "PREFLIGHT_ONLY=true GIT_ORIGIN_URL=<repo-url> ./run-connected-runner-handoff.sh",
                        "```",
                        "```bash",
                        "python3 scripts/review_release_warnings.py --package-dir /tmp/package --apply",
                        "```",
                        "```bash",
                        "python3 scripts/review_release_warnings.py --package-dir /tmp/package --json-only",
                        "```",
                        "```bash",
                        'python3 scripts/next_release_step.py --owner "connected runner" --json-only --local-readiness',
                        "```",
                        "```bash",
                        "python3 scripts/next_release_step.py --repo-url-from-env GIT_ORIGIN_URL --json-only",
                        "```",
                        "```bash",
                        "python3 scripts/package_connected_runner_handoff.py --verify /tmp/handoff",
                        "```",
                        "```bash",
                        "python3 scripts/connected_runner_acceptance.py --handoff-root .. --require-external --check-gh-auth",
                        "```",
                    ]
                ),
                encoding="utf-8",
            )
            (package_dir / "next-release-step.md").write_text(
                "\n".join(
                    [
                        "```bash",
                        "cd /tmp/handoff && PREFLIGHT_ONLY=true "
                        "GIT_ORIGIN_URL=REPLACE_WITH_REPO_URL ./run-connected-runner-handoff.sh",
                        "```",
                    ]
                ),
                encoding="utf-8",
            )
            checks = checks_by_id(self.module.check_handoff_command_safety(package_dir))

        self.assertEqual(checks["handoff_backup_reference_placeholders_absent"]["status"], "fail")
        self.assertEqual(checks["handoff_repo_url_placeholder_shell_safe"]["status"], "fail")
        self.assertEqual(checks["handoff_repo_url_required_gate"]["status"], "fail")
        self.assertEqual(checks["handoff_repo_url_top_level_gates"]["status"], "fail")
        self.assertEqual(checks["handoff_release_status_json_command"]["status"], "fail")
        self.assertEqual(checks["handoff_release_status_progress_command"]["status"], "fail")
        self.assertEqual(checks["handoff_release_status_progress_json_command"]["status"], "fail")
        self.assertEqual(checks["handoff_release_status_completion_plan_command"]["status"], "fail")
        self.assertEqual(checks["handoff_release_status_completion_plan_json_command"]["status"], "fail")
        self.assertEqual(checks["handoff_release_status_completion_requirements_command"]["status"], "fail")
        self.assertEqual(checks["handoff_release_status_completion_requirements_json_command"]["status"], "fail")
        self.assertEqual(checks["handoff_release_status_progress_summary"]["status"], "fail")
        self.assertEqual(checks["handoff_release_status_progress_snapshot"]["status"], "fail")
        self.assertEqual(checks["handoff_release_status_progress_owner_next"]["status"], "fail")
        self.assertEqual(checks["handoff_release_status_progress_next_step_command"]["status"], "fail")
        self.assertEqual(checks["handoff_release_status_progress_release_gate"]["status"], "fail")
        self.assertEqual(checks["handoff_release_status_progress_repo_url"]["status"], "fail")
        self.assertEqual(checks["handoff_release_status_progress_local_readiness"]["status"], "fail")
        self.assertEqual(checks["handoff_release_status_progress_warning_review"]["status"], "fail")
        self.assertEqual(checks["handoff_release_status_owner_supporting_commands"]["status"], "fail")
        self.assertEqual(checks["handoff_release_status_progress_handoff_bundle"]["status"], "fail")
        self.assertEqual(checks["handoff_external_readiness_summary_json_command"]["status"], "fail")
        self.assertEqual(checks["handoff_external_readiness_strict_summary_json_command"]["status"], "fail")
        self.assertEqual(checks["handoff_command_sequence_only"]["status"], "fail")
        self.assertEqual(checks["handoff_release_evidence_json_command"]["status"], "fail")
        self.assertEqual(checks["handoff_evidence_checksum_json_verify_command"]["status"], "fail")
        self.assertEqual(checks["handoff_bundle_verify_json_command"]["status"], "fail")
        self.assertEqual(checks["handoff_bundle_verify_summary_json_command"]["status"], "fail")
        self.assertEqual(checks["handoff_connected_runner_acceptance_json_command"]["status"], "fail")
        self.assertEqual(checks["handoff_connected_runner_acceptance_summary_json_command"]["status"], "fail")
        self.assertEqual(checks["handoff_live_beta_backup_reference_example"]["status"], "fail")
        self.assertEqual(checks["handoff_live_beta_preflight_json_command"]["status"], "fail")
        self.assertEqual(checks["handoff_live_beta_backend_support_commands"]["status"], "fail")
        self.assertEqual(checks["handoff_live_beta_command_builder_set"]["status"], "fail")
        self.assertEqual(checks["handoff_warning_apply_operator_approval"]["status"], "fail")
        self.assertEqual(checks["handoff_warning_json_action_gate"]["status"], "fail")
        self.assertEqual(checks["handoff_warning_summary_json"]["status"], "fail")
        self.assertEqual(checks["handoff_warning_summary_json_gate"]["status"], "fail")
        self.assertEqual(checks["handoff_warning_next_command_only"]["status"], "fail")
        self.assertEqual(checks["handoff_warning_next_command_gate"]["status"], "fail")
        self.assertEqual(checks["handoff_warning_review_artifacts_only"]["status"], "fail")
        self.assertEqual(checks["handoff_local_readiness_json_gate"]["status"], "fail")
        self.assertEqual(checks["handoff_local_readiness_command_gate"]["status"], "fail")
        self.assertEqual(checks["handoff_local_readiness_setup_sequence"]["status"], "fail")
        self.assertEqual(checks["handoff_local_readiness_command_sequence"]["status"], "fail")
        self.assertEqual(checks["handoff_local_readiness_setup_sequence_preview"]["status"], "fail")
        self.assertEqual(checks["handoff_local_readiness_command_sequence_preview"]["status"], "fail")

    def test_command_safety_fails_when_progress_next_command_differs_from_next_step_json(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-evidence-check-") as tmp:
            package_dir = Path(tmp)
            (package_dir / "release-status.json").write_text(
                json.dumps(
                    {
                        "progress_summary": {
                            "next_command": "cd /tmp/handoff-a && ./run-connected-runner-handoff.sh"
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (package_dir / "next-release-step.json").write_text(
                json.dumps({"next_command": "cd /tmp/handoff-b && ./run-connected-runner-handoff.sh"})
                + "\n",
                encoding="utf-8",
            )

            checks = checks_by_id(self.module.check_handoff_command_safety(package_dir))

        self.assertEqual(checks["handoff_release_status_progress_next_step_command"]["status"], "fail")

    def test_command_safety_accepts_final_gate_when_no_remaining_items(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-evidence-check-") as tmp:
            package_dir = Path(tmp)
            (package_dir / "release-status.json").write_text(
                json.dumps(
                    {
                        "remaining_items": [],
                        "progress_summary": {
                            "remaining_items": 0,
                            "next_command": None,
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (package_dir / "next-release-step.json").write_text(
                json.dumps({"next_command": self.module.LIVE_BETA_FINAL_GATE_COMMAND}) + "\n",
                encoding="utf-8",
            )

            checks = checks_by_id(self.module.check_handoff_command_safety(package_dir))

        self.assertEqual(checks["handoff_release_status_progress_next_step_command"]["status"], "pass")

    def test_command_safety_fails_when_progress_snapshot_differs_from_top_level(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-evidence-check-") as tmp:
            package_dir = Path(tmp)
            deductions = [
                {
                    "id": "external_readiness_warnings",
                    "points": 1,
                    "check_ids": ["git_origin_remote"],
                    "detail": "Git origin remote still needs connected-runner setup.",
                }
            ]
            (package_dir / "release-status.json").write_text(
                json.dumps(
                    {
                        "package_dir": str(package_dir),
                        "readiness_estimate": {
                            "deductions": deductions,
                            "percent": 96,
                            "remaining_items": 1,
                        },
                        "remaining_items": [
                            {
                                "id": "git_origin_remote",
                                "owner": "connected runner",
                            }
                        ],
                        "status": "warn",
                        "progress_summary": {
                            "deductions": deductions,
                            "package_dir": str(package_dir),
                            "percent": 96,
                            "remaining_by_owner": {"connected runner": 1},
                            "remaining_ids": ["docker_cli"],
                            "remaining_items": 1,
                            "status": "warn",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            checks = checks_by_id(self.module.check_handoff_command_safety(package_dir))

        self.assertEqual(checks["handoff_release_status_progress_snapshot"]["status"], "fail")

    def test_command_safety_fails_when_progress_completion_impacts_are_stale(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-evidence-check-") as tmp:
            package_dir = Path(tmp)
            deductions = [
                {
                    "id": "external_readiness_warnings",
                    "points": 1,
                    "check_ids": ["git_origin_remote"],
                    "detail": "Git origin remote still needs connected-runner setup.",
                }
            ]
            (package_dir / "release-status.json").write_text(
                json.dumps(
                    {
                        "package_dir": str(package_dir),
                        "readiness_estimate": {
                            "deductions": deductions,
                            "percent": 96,
                            "remaining_items": 1,
                        },
                        "remaining_items": [
                            {
                                "id": "git_origin_remote",
                                "owner": "connected runner",
                            }
                        ],
                        "status": "warn",
                        "progress_summary": {
                            "completion_impacts": {
                                "docker_cli": {
                                    "completion_deduction_id": "external_readiness_warnings"
                                }
                            },
                            "deductions": deductions,
                            "package_dir": str(package_dir),
                            "percent": 96,
                            "remaining_by_owner": {"connected runner": 1},
                            "remaining_ids": ["git_origin_remote"],
                            "remaining_items": 1,
                            "status": "warn",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            checks = checks_by_id(self.module.check_handoff_command_safety(package_dir))

        self.assertEqual(checks["handoff_release_status_progress_snapshot"]["status"], "fail")
        self.assertIn(
            "progress_summary.completion_impacts",
            str(checks["handoff_release_status_progress_snapshot"]["message"]),
        )

    def test_command_safety_fails_when_progress_completion_plan_is_stale(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-evidence-check-") as tmp:
            package_dir = Path(tmp)
            deductions = [
                {
                    "id": "external_readiness_warnings",
                    "points": 1,
                    "check_ids": ["git_origin_remote"],
                    "detail": "Git origin remote still needs connected-runner setup.",
                }
            ]
            expected_command = "git remote add origin REPLACE_WITH_REPO_URL"
            (package_dir / "release-status.json").write_text(
                json.dumps(
                    {
                        "package_dir": str(package_dir),
                        "readiness_estimate": {
                            "deductions": deductions,
                            "percent": 96,
                            "remaining_items": 1,
                        },
                        "remaining_items": [
                            {
                                "id": "git_origin_remote",
                                "owner": "connected runner",
                                "status": "warn",
                                "command": expected_command,
                            }
                        ],
                        "status": "warn",
                        "progress_summary": {
                            "completion_impacts": self.module.completion_impacts_by_check_id(
                                deductions
                            ),
                            "completion_plan": [
                                {
                                    "id": "docker_cli",
                                    "owner": "connected runner",
                                    "status": "warn",
                                    "command": "brew install --cask docker",
                                }
                            ],
                            "deductions": deductions,
                            "package_dir": str(package_dir),
                            "percent": 96,
                            "remaining_by_owner": {"connected runner": 1},
                            "remaining_ids": ["git_origin_remote"],
                            "remaining_items": 1,
                            "status": "warn",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            checks = checks_by_id(self.module.check_handoff_command_safety(package_dir))

        self.assertEqual(checks["handoff_release_status_progress_snapshot"]["status"], "fail")
        self.assertIn(
            "progress_summary.completion_plan",
            str(checks["handoff_release_status_progress_snapshot"]["message"]),
        )

    def test_command_safety_fails_when_completion_plan_warning_backend_is_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-evidence-check-") as tmp:
            package_dir = Path(tmp)
            warning_apply = self.module.warning_review_apply_command(package_dir)
            (package_dir / "release-status.json").write_text(
                json.dumps(
                    {
                        "package_dir": str(package_dir),
                        "readiness_estimate": {
                            "deductions": [],
                            "percent": 96,
                            "remaining_items": 1,
                        },
                        "remaining_items": [
                            {
                                "id": "warning_actions",
                                "owner": "operator",
                                "status": "planned",
                                "command": warning_apply,
                            }
                        ],
                        "status": "warn",
                        "progress_summary": {
                            "completion_impacts": {},
                            "completion_plan": [
                                {
                                    "id": "warning_actions",
                                    "owner": "operator",
                                    "status": "planned",
                                    "command": warning_apply,
                                    "mode": "operator_approval",
                                    "requirements": [
                                        "operator_checklist_review",
                                        "operator_approval",
                                        "running_backend",
                                    ],
                                    "requires_operator_approval": True,
                                }
                            ],
                            "deductions": [],
                            "package_dir": str(package_dir),
                            "percent": 96,
                            "remaining_by_owner": {"operator": 1},
                            "remaining_ids": ["warning_actions"],
                            "remaining_items": 1,
                            "status": "warn",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            checks = checks_by_id(self.module.check_handoff_command_safety(package_dir))

        self.assertEqual(
            checks["handoff_completion_plan_warning_backend_guidance"]["status"],
            "fail",
        )
        self.assertIn(
            "warning_actions.backend",
            str(checks["handoff_completion_plan_warning_backend_guidance"]["message"]),
        )

    def test_command_safety_fails_when_progress_owner_next_differs_from_remaining_items(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-evidence-check-") as tmp:
            package_dir = Path(tmp)
            deductions = [
                {
                    "id": "external_readiness_warnings",
                    "points": 1,
                    "check_ids": ["git_origin_remote"],
                    "detail": "Git origin remote still needs connected-runner setup.",
                }
            ]
            expected_command = "cd /tmp/handoff && PREFLIGHT_ONLY=true GIT_ORIGIN_URL=REPLACE_WITH_REPO_URL ./run-connected-runner-handoff.sh"
            (package_dir / "release-status.json").write_text(
                json.dumps(
                    {
                        "package_dir": str(package_dir),
                        "readiness_estimate": {
                            "deductions": deductions,
                            "percent": 96,
                            "remaining_items": 1,
                        },
                        "remaining_items": [
                            {
                                "id": "git_origin_remote",
                                "owner": "connected runner",
                                "preferred_command": expected_command,
                                "status": "warn",
                            }
                        ],
                        "status": "warn",
                        "progress_summary": {
                            "deductions": deductions,
                            "completion_impacts": self.module.completion_impacts_by_check_id(
                                deductions
                            ),
                            "completion_plan": [
                                {
                                    "id": "git_origin_remote",
                                    "owner": "connected runner",
                                    "status": "warn",
                                    "command": expected_command,
                                    "mode": "connected_runner_preflight",
                                    "requirements": [
                                        "connected_runner",
                                        "real_git_remote_url",
                                        "docker_cli",
                                        "github_cli_auth",
                                    ],
                                    **self.module.completion_impacts_by_check_id(deductions)[
                                        "git_origin_remote"
                                    ],
                                }
                            ],
                            "completion_requirements": [
                                {
                                    "requirement": "connected_runner",
                                    "item_ids": ["git_origin_remote"],
                                    "owners": ["connected runner"],
                                    "count": 1,
                                },
                                {
                                    "requirement": "real_git_remote_url",
                                    "item_ids": ["git_origin_remote"],
                                    "owners": ["connected runner"],
                                    "count": 1,
                                },
                                {
                                    "requirement": "docker_cli",
                                    "item_ids": ["git_origin_remote"],
                                    "owners": ["connected runner"],
                                    "count": 1,
                                },
                                {
                                    "requirement": "github_cli_auth",
                                    "item_ids": ["git_origin_remote"],
                                    "owners": ["connected runner"],
                                    "count": 1,
                                },
                            ],
                            "owner_lanes": {
                                "connected runner": {
                                    "remaining_items": 1,
                                    "remaining_ids": ["git_origin_remote"],
                                    "next_item_id": "docker_cli",
                                    "status": "warn",
                                    "mode": "connected_runner_preflight",
                                    "requirements": [
                                        "connected_runner",
                                        "real_git_remote_url",
                                        "docker_cli",
                                        "github_cli_auth",
                                    ],
                                    "next_requires_operator_approval": False,
                                    "requires_operator_approval": False,
                                    "review_artifacts": {},
                                    "supporting_command_labels": [],
                                    "commands": {"next": "stale command"},
                                    "has_automation_command": False,
                                    "has_full_flow_command": False,
                                }
                            },
                            "next_command": "stale command",
                            "next_commands_by_owner": {
                                "connected runner": {
                                    "id": "docker_cli",
                                    "status": "warn",
                                    "command": "stale command",
                                }
                            },
                            "next_item_id": "docker_cli",
                            "next_item_owner": "connected runner",
                            "package_dir": str(package_dir),
                            "percent": 96,
                            "remaining_by_owner": {"connected runner": 1},
                            "remaining_ids": ["git_origin_remote"],
                            "remaining_items": 1,
                            "status": "warn",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            checks = checks_by_id(self.module.check_handoff_command_safety(package_dir))

        self.assertEqual(checks["handoff_release_status_progress_snapshot"]["status"], "pass")
        self.assertEqual(checks["handoff_release_status_progress_owner_next"]["status"], "fail")

    def test_command_safety_fails_when_progress_owner_completion_impact_is_stale(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-evidence-check-") as tmp:
            package_dir = Path(tmp)
            deductions = [
                {
                    "id": "external_readiness_warnings",
                    "points": 1,
                    "check_ids": ["git_origin_remote"],
                    "detail": "Git origin remote still needs connected-runner setup.",
                }
            ]
            expected_command = (
                "cd /tmp/handoff && PREFLIGHT_ONLY=true "
                "GIT_ORIGIN_URL=REPLACE_WITH_REPO_URL ./run-connected-runner-handoff.sh"
            )
            (package_dir / "release-status.json").write_text(
                json.dumps(
                    {
                        "package_dir": str(package_dir),
                        "readiness_estimate": {
                            "deductions": deductions,
                            "percent": 96,
                            "remaining_items": 1,
                        },
                        "remaining_items": [
                            {
                                "id": "git_origin_remote",
                                "owner": "connected runner",
                                "preferred_command": expected_command,
                                "status": "warn",
                            }
                        ],
                        "status": "warn",
                        "progress_summary": {
                            "completion_impacts": self.module.completion_impacts_by_check_id(
                                deductions
                            ),
                            "completion_plan": [
                                {
                                    "id": "git_origin_remote",
                                    "owner": "connected runner",
                                    "status": "warn",
                                    "command": expected_command,
                                    "mode": "connected_runner_preflight",
                                    "requirements": [
                                        "connected_runner",
                                        "real_git_remote_url",
                                        "docker_cli",
                                        "github_cli_auth",
                                    ],
                                    **self.module.completion_impacts_by_check_id(deductions)[
                                        "git_origin_remote"
                                    ],
                                }
                            ],
                            "completion_requirements": [
                                {
                                    "requirement": "connected_runner",
                                    "item_ids": ["git_origin_remote"],
                                    "owners": ["connected runner"],
                                    "count": 1,
                                },
                                {
                                    "requirement": "real_git_remote_url",
                                    "item_ids": ["git_origin_remote"],
                                    "owners": ["connected runner"],
                                    "count": 1,
                                },
                                {
                                    "requirement": "docker_cli",
                                    "item_ids": ["git_origin_remote"],
                                    "owners": ["connected runner"],
                                    "count": 1,
                                },
                                {
                                    "requirement": "github_cli_auth",
                                    "item_ids": ["git_origin_remote"],
                                    "owners": ["connected runner"],
                                    "count": 1,
                                },
                            ],
                            "owner_lanes": {
                                "connected runner": {
                                    "remaining_items": 1,
                                    "remaining_ids": ["git_origin_remote"],
                                    "next_item_id": "git_origin_remote",
                                    "status": "warn",
                                    "mode": "connected_runner_preflight",
                                    "requirements": [
                                        "connected_runner",
                                        "real_git_remote_url",
                                        "docker_cli",
                                        "github_cli_auth",
                                    ],
                                    "next_requires_operator_approval": False,
                                    "requires_operator_approval": False,
                                    "review_artifacts": {},
                                    "supporting_command_labels": [],
                                    "commands": {"next": expected_command},
                                    "has_automation_command": False,
                                    "has_full_flow_command": False,
                                    "repo_url": {
                                        "required": True,
                                        "placeholder": self.module.REPO_URL_PLACEHOLDER,
                                        "export_command": self.module.repo_url_export_example_command(),
                                        "note": (
                                            f"Replace {self.module.REPO_URL_PLACEHOLDER} with a real HTTPS, SSH, or "
                                            "scp-style git remote URL before running connected-runner commands."
                                        ),
                                    },
                                }
                            },
                            "deductions": deductions,
                            "next_command": expected_command,
                            "next_commands_by_owner": {
                                "connected runner": {
                                    "id": "git_origin_remote",
                                    "status": "warn",
                                    "command": expected_command,
                                    "completion_impact_points": 99,
                                }
                            },
                            "next_item_id": "git_origin_remote",
                            "next_item_owner": "connected runner",
                            "package_dir": str(package_dir),
                            "percent": 96,
                            "remaining_by_owner": {"connected runner": 1},
                            "remaining_ids": ["git_origin_remote"],
                            "remaining_items": 1,
                            "status": "warn",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            checks = checks_by_id(self.module.check_handoff_command_safety(package_dir))

        self.assertEqual(checks["handoff_release_status_progress_snapshot"]["status"], "pass")
        self.assertEqual(checks["handoff_release_status_progress_owner_next"]["status"], "fail")
        self.assertIn(
            "completion_impact_points",
            str(checks["handoff_release_status_progress_owner_next"]["message"]),
        )

    def test_command_safety_fails_when_progress_local_readiness_differs_from_runner_items(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-evidence-check-") as tmp:
            package_dir = Path(tmp)
            git_setup = "cd /tmp/handoff/source && git remote add origin REPLACE_WITH_REPO_URL"
            git_verify = "cd /tmp/handoff/source && git remote get-url origin"
            docker_setup = "cd /tmp/handoff/source && brew install --cask docker && docker compose version"
            docker_verify = "cd /tmp/handoff/source && docker compose version"
            local_commands = {
                "local_readiness_json": self.module.next_release_local_readiness_json_env_command(package_dir),
                "local_readiness_command_only": (
                    self.module.next_release_local_readiness_command_only_env_command(package_dir)
                ),
                "local_readiness_setup_sequence": (
                    self.module.next_release_local_readiness_setup_sequence_env_command(package_dir)
                ),
                "local_readiness_command_sequence": (
                    self.module.next_release_local_readiness_command_sequence_env_command(package_dir)
                ),
                "local_readiness_setup_sequence_preview": (
                    self.module.next_release_local_readiness_setup_sequence_preview_command(package_dir)
                ),
                "local_readiness_command_sequence_preview": (
                    self.module.next_release_local_readiness_command_sequence_preview_command(package_dir)
                ),
                "local_readiness_gate_json": (
                    self.module.next_release_local_readiness_gate_json_env_command(package_dir)
                ),
                "external_readiness_summary_json": self.module.external_readiness_summary_json_command(),
                "external_readiness_strict_summary_json": (
                    self.module.external_readiness_strict_summary_json_command()
                ),
            }
            (package_dir / "release-status.json").write_text(
                json.dumps(
                    {
                        "remaining_items": [
                            {
                                "id": "git_origin_remote",
                                "owner": "connected runner",
                                "status": "warn",
                                "command": git_setup,
                                "verify_command": git_verify,
                            },
                            {
                                "id": "docker_cli",
                                "owner": "connected runner",
                                "status": "warn",
                                "command": docker_setup,
                                "verify_command": docker_verify,
                            },
                        ],
                        "progress_summary": {
                            "commands": local_commands,
                            "local_readiness": {
                                "status": "warn",
                                "issue_ids": ["git_origin_remote"],
                                "next_setup": {
                                    "id": "git_origin_remote",
                                    "status": "warn",
                                    "setup_command": git_setup,
                                    "verify_command": git_verify,
                                },
                                "next_setup_command": git_setup,
                                "setup_sequence": [git_setup],
                                "verify_sequence": [git_verify],
                                "command_sequence": [git_setup, git_verify],
                                "json_command": local_commands["local_readiness_json"],
                                "command_only_gate": local_commands["local_readiness_command_only"],
                                "setup_sequence_command": local_commands["local_readiness_setup_sequence"],
                                "command_sequence_command": local_commands[
                                    "local_readiness_command_sequence"
                                ],
                                "setup_sequence_preview_command": local_commands[
                                    "local_readiness_setup_sequence_preview"
                                ],
                                "command_sequence_preview_command": local_commands[
                                    "local_readiness_command_sequence_preview"
                                ],
                                "json_gate": local_commands["local_readiness_gate_json"],
                                "external_summary_json": local_commands["external_readiness_summary_json"],
                                "external_strict_summary_json": local_commands[
                                    "external_readiness_strict_summary_json"
                                ],
                            },
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            checks = checks_by_id(self.module.check_handoff_command_safety(package_dir))

        self.assertEqual(checks["handoff_release_status_progress_local_readiness"]["status"], "fail")
        self.assertIn(
            "local_readiness.issue_ids",
            str(checks["handoff_release_status_progress_local_readiness"]["message"]),
        )

    def test_command_safety_fails_when_progress_warning_review_differs_from_operator_items(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-evidence-check-") as tmp:
            package_dir = Path(tmp)
            warning_no_write = (
                f"python3 scripts/review_release_warnings.py --package-dir {package_dir} --no-write"
            )
            warning_apply = self.module.warning_review_apply_command(package_dir)
            warning_commands = {
                "warning_summary_json": self.module.warning_review_summary_json_command(package_dir),
                "warning_gate_summary_json": (
                    self.module.warning_review_gate_summary_json_command(package_dir)
                ),
                "warning_gate_json": (
                    f"python3 scripts/review_release_warnings.py --package-dir {package_dir} "
                    "--json-only --fail-if-action-needed"
                ),
                "warning_next_command_gate": self.module.warning_review_next_command_gate_command(
                    package_dir
                ),
                "warning_review_artifacts": self.module.warning_review_artifacts_only_command(
                    package_dir
                ),
                "warning_apply": warning_apply,
                "operator_review_sequence": (
                    f"python3 scripts/next_release_step.py --package-dir {package_dir} "
                    "--owner operator --command-sequence-only --skip-operator-approved "
                    "--fail-if-repo-url-required"
                ),
            }
            (package_dir / "release-status.json").write_text(
                json.dumps(
                    {
                        "remaining_items": [
                            {
                                "id": "warning_alerts",
                                "owner": "operator",
                                "status": "warn",
                                "command": warning_no_write,
                            },
                            {
                                "id": "warning_actions",
                                "owner": "operator",
                                "status": "planned",
                                "command": warning_apply,
                            },
                        ],
                        "progress_summary": {
                            "commands": warning_commands,
                            "warning_review": {
                                "status": "planned",
                                "action_needed": True,
                                "issue_ids": ["warning_alerts"],
                                "next_command": "stale command",
                                "requires_operator_approval": True,
                                "summary_json": warning_commands["warning_summary_json"],
                                "gate_summary_json": warning_commands["warning_gate_summary_json"],
                                "gate_json": warning_commands["warning_gate_json"],
                                "next_command_gate": warning_commands["warning_next_command_gate"],
                                "review_artifacts_command": warning_commands[
                                    "warning_review_artifacts"
                                ],
                                "apply_command": warning_commands["warning_apply"],
                                "review_artifacts": {
                                    "action_plan": str(package_dir / "release-warning-actions.md"),
                                    "operator_checklist": str(
                                        package_dir / "release-warning-operator-checklist.md"
                                    ),
                                },
                                "review_sequence_command": warning_commands["operator_review_sequence"],
                                "pre_approval_review_sequence": [
                                    warning_commands["warning_summary_json"],
                                    warning_commands["warning_review_artifacts"],
                                ],
                                "review_sequence": [
                                    warning_commands["warning_summary_json"],
                                    warning_commands["warning_review_artifacts"],
                                    warning_commands["warning_apply"],
                                ],
                            },
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            checks = checks_by_id(self.module.check_handoff_command_safety(package_dir))

        self.assertEqual(checks["handoff_release_status_progress_warning_review"]["status"], "fail")
        self.assertIn(
            "warning_review.issue_ids",
            str(checks["handoff_release_status_progress_warning_review"]["message"]),
        )
        self.assertIn(
            "warning_review.next_command",
            str(checks["handoff_release_status_progress_warning_review"]["message"]),
        )

    def test_command_safety_fails_when_progress_warning_review_sequence_is_stale(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-evidence-check-") as tmp:
            package_dir = Path(tmp)
            warning_no_write = (
                f"python3 scripts/review_release_warnings.py --package-dir {package_dir} --no-write"
            )
            warning_apply = self.module.warning_review_apply_command(package_dir)
            warning_commands = {
                "warning_summary_json": self.module.warning_review_summary_json_command(package_dir),
                "warning_gate_summary_json": (
                    self.module.warning_review_gate_summary_json_command(package_dir)
                ),
                "warning_gate_json": (
                    f"python3 scripts/review_release_warnings.py --package-dir {package_dir} "
                    "--json-only --fail-if-action-needed"
                ),
                "warning_next_command_gate": self.module.warning_review_next_command_gate_command(
                    package_dir
                ),
                "warning_review_artifacts": self.module.warning_review_artifacts_only_command(
                    package_dir
                ),
                "warning_apply": warning_apply,
                "operator_review_sequence": (
                    f"python3 scripts/next_release_step.py --package-dir {package_dir} "
                    "--owner operator --command-sequence-only --skip-operator-approved "
                    "--fail-if-repo-url-required"
                ),
            }
            (package_dir / "release-status.json").write_text(
                json.dumps(
                    {
                        "remaining_items": [
                            {
                                "id": "warning_alerts",
                                "owner": "operator",
                                "status": "warn",
                                "command": warning_no_write,
                            },
                            {
                                "id": "warning_actions",
                                "owner": "operator",
                                "status": "planned",
                                "command": warning_apply,
                            },
                        ],
                        "progress_summary": {
                            "commands": warning_commands,
                            "warning_review": {
                                "status": "planned",
                                "action_needed": True,
                                "issue_ids": ["warning_alerts", "warning_actions"],
                                "next_command": warning_no_write,
                                "requires_operator_approval": True,
                                "summary_json": warning_commands["warning_summary_json"],
                                "gate_summary_json": warning_commands["warning_gate_summary_json"],
                                "gate_json": warning_commands["warning_gate_json"],
                                "next_command_gate": warning_commands["warning_next_command_gate"],
                                "review_artifacts_command": warning_commands[
                                    "warning_review_artifacts"
                                ],
                                "apply_command": warning_commands["warning_apply"],
                                "review_artifacts": {
                                    "action_plan": str(package_dir / "release-warning-actions.md"),
                                    "operator_checklist": str(
                                        package_dir / "release-warning-operator-checklist.md"
                                    ),
                                },
                                "review_sequence_command": warning_commands["operator_review_sequence"],
                                "pre_approval_review_sequence": [
                                    warning_commands["warning_summary_json"],
                                    warning_commands["warning_review_artifacts"],
                                ],
                                "review_sequence": [
                                    warning_commands["warning_apply"],
                                    warning_commands["warning_summary_json"],
                                ],
                            },
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            checks = checks_by_id(self.module.check_handoff_command_safety(package_dir))

        self.assertEqual(checks["handoff_release_status_progress_warning_review"]["status"], "fail")
        self.assertIn(
            "warning_review.review_sequence",
            str(checks["handoff_release_status_progress_warning_review"]["message"]),
        )

    def test_command_safety_fails_when_progress_release_gate_command_is_stale(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-evidence-check-") as tmp:
            package_dir = Path(tmp)
            release_gate_path = Path("artifacts/release-gate/release-gate-test.json")
            (package_dir / "release-status.json").write_text(
                json.dumps(
                    {
                        "progress_summary": {
                            "release_gate_path": str(release_gate_path),
                            "commands": {
                                "show_progress": self.module.release_status_progress_command(
                                    package_dir,
                                    release_gate_path,
                                ),
                                "show_progress_json": self.module.release_status_progress_json_command(
                                    package_dir,
                                    "artifacts/release-gate/stale.json",
                                ),
                            },
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (package_dir / "next-release-step.json").write_text(
                json.dumps({"next_command": "python3 scripts/next_release_step.py --no-write"})
                + "\n",
                encoding="utf-8",
            )

            checks = checks_by_id(self.module.check_handoff_command_safety(package_dir))

        self.assertEqual(checks["handoff_release_status_progress_release_gate"]["status"], "fail")

    def test_warning_triage_no_write_does_not_create_files(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-evidence-check-") as tmp:
            package_dir = Path(tmp)
            triage = self.module.write_warning_triage(
                package_dir,
                [{"id": "external_readiness_status", "status": "warn", "message": "warning"}],
                write=False,
            )

            self.assertTrue(triage["write_skipped"])
            self.assertIsNone(triage["json_path"])
            self.assertIsNone(triage["markdown_path"])
            self.assertFalse((package_dir / "release-warning-triage.json").exists())
            self.assertFalse((package_dir / "release-warning-triage.md").exists())

    def test_cli_no_write_does_not_create_check_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-evidence-check-") as tmp:
            package_dir = Path(tmp) / "package"
            package_dir.mkdir()
            (package_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "included": [],
                        "missing": [],
                        "safety": {
                            "env_file_excluded": True,
                            "live_trading_enabled_by_script": False,
                            "stock_etf_live_routing_enabled": False,
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(CHECK_RELEASE_EVIDENCE),
                    "--package-dir",
                    str(package_dir),
                    "--no-write",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 1)
            self.assertIn("Release evidence check: not written (--no-write)", completed.stdout)
            self.assertFalse((package_dir / "release-evidence-check.json").exists())
            self.assertFalse((package_dir / "release-warning-triage.json").exists())
            self.assertFalse((package_dir / "release-warning-triage.md").exists())

    def test_cli_json_only_prints_summary_without_writing_files(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-evidence-check-") as tmp:
            package_dir = Path(tmp) / "package"
            package_dir.mkdir()
            (package_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "included": [],
                        "missing": [],
                        "safety": {
                            "env_file_excluded": True,
                            "live_trading_enabled_by_script": False,
                            "stock_etf_live_routing_enabled": False,
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(CHECK_RELEASE_EVIDENCE),
                    "--package-dir",
                    str(package_dir),
                    "--json-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 1)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["package_dir"], str(package_dir.absolute()))
            self.assertEqual(payload["status"], "fail")
            self.assertTrue(payload["warning_triage"]["write_skipped"])
            self.assertFalse((package_dir / "release-evidence-check.json").exists())
            self.assertFalse((package_dir / "release-warning-triage.json").exists())
            self.assertFalse((package_dir / "release-warning-triage.md").exists())

    def test_cli_no_write_rejects_output_path(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(CHECK_RELEASE_EVIDENCE),
                "--no-write",
                "--output",
                "/tmp/release-evidence-check.json",
            ],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("--output cannot be used with --no-write", completed.stderr)


if __name__ == "__main__":
    unittest.main()
