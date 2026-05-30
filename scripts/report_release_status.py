#!/usr/bin/env python3
"""Summarize the latest Quant Lab release package into operator-readable status files."""

from __future__ import annotations

import argparse
import json
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.handoff_commands import (
        LIVE_BETA_BACKUP_REFERENCE_EXAMPLE,
        LIVE_BETA_CLOSEOUT_COMMAND,
        LIVE_BETA_FINAL_GATE_COMMAND,
        LIVE_BETA_NEXT_COMMAND_ONLY_COMMAND,
        LIVE_BETA_PREFLIGHT_COMMAND,
        LIVE_BETA_PREFLIGHT_JSON_COMMAND,
        CONNECTED_STRICT_GATE_COMMAND,
        DOCKER_BACKEND_START_COMMAND,
        LOCAL_BACKEND_START_COMMAND,
        LOCAL_BACKEND_START_NO_RELOAD_COMMAND,
        LOCAL_WARNING_GATE_COMMAND,
        REPO_URL_PLACEHOLDER,
        backend_health_check_command,
        connected_runner_acceptance_command,
        connected_runner_acceptance_json_command,
        connected_runner_acceptance_summary_json_command,
        connected_runner_bundle_script_command,
        connected_runner_handoff_command_sequence_command,
        connected_runner_handoff_context_json_command,
        connected_runner_full_command as shared_connected_runner_full_command,
        connected_runner_preflight_command as shared_connected_runner_preflight_command,
        connected_runner_preflight_only_command,
        evidence_check_json_command,
        external_readiness_strict_summary_json_command,
        external_readiness_summary_json_command,
        completion_impacts_by_check_id,
        format_completion_deduction,
        next_release_command_only_env_command,
        next_release_command_sequence_env_command,
        next_release_connected_command_only_env_command,
        next_release_connected_command_sequence_env_command,
        next_release_connected_json_only_env_command,
        next_release_connected_sequence_command,
        next_release_connected_sequence_env_command,
        next_release_connected_sequence_origin_command,
        next_release_json_only_env_command,
        next_release_local_readiness_command,
        next_release_local_readiness_command_only_env_command,
        next_release_local_readiness_command_sequence_env_command,
        next_release_local_readiness_command_sequence_preview_command,
        next_release_local_readiness_gate_json_env_command,
        next_release_local_readiness_json_env_command,
        next_release_local_readiness_setup_sequence_env_command,
        next_release_local_readiness_setup_sequence_preview_command,
        next_release_operator_command_only_command,
        next_release_operator_command_sequence_command,
        next_release_operator_json_only_command,
        next_release_operator_review_sequence_command,
        next_release_operator_sequence_command,
        next_release_sequence_command,
        next_release_step_command,
        next_release_step_env_command,
        next_release_step_origin_command,
        next_release_step_repo_command,
        package_connected_runner_handoff_command,
        read_only_release_status_command,
        read_only_evidence_check_command,
        read_only_warning_review_command,
        refresh_release_status_command,
        release_status_completion_plan_command,
        release_status_completion_plan_json_command,
        release_status_completion_requirements_command,
        release_status_completion_requirements_json_command,
        release_status_progress_command,
        release_status_progress_json_command,
        release_status_owner_lanes_command,
        release_status_owner_lanes_json_command,
        release_status_json_command,
        repo_url_export_example_command,
        shell_arg,
        source_scoped_command,
        owner_lanes_summary as shared_owner_lanes_summary,
        connected_runner_verify_command,
        connected_runner_verify_json_command,
        connected_runner_verify_summary_json_command,
        verify_evidence_checksums_command,
        verify_evidence_checksums_json_command,
        warning_review_apply_command,
        warning_review_artifacts_only_command,
        warning_backend_guidance_payload as shared_warning_backend_guidance_payload,
        warning_review_gate_summary_json_command,
        warning_review_gate_json_command,
        warning_review_json_command,
        warning_review_next_command_gate_command,
        warning_review_next_command_only_command,
        warning_review_pre_approval_sequence_command,
        warning_review_summary_json_command,
        with_completion_impacts,
    )
    from scripts.release_artifacts import (
        latest_json_file,
        latest_manifest_package_dir,
    )
except ModuleNotFoundError:  # pragma: no cover - supports running from scripts/
    from handoff_commands import (
        LIVE_BETA_BACKUP_REFERENCE_EXAMPLE,
        LIVE_BETA_CLOSEOUT_COMMAND,
        LIVE_BETA_FINAL_GATE_COMMAND,
        LIVE_BETA_NEXT_COMMAND_ONLY_COMMAND,
        LIVE_BETA_PREFLIGHT_COMMAND,
        LIVE_BETA_PREFLIGHT_JSON_COMMAND,
        CONNECTED_STRICT_GATE_COMMAND,
        DOCKER_BACKEND_START_COMMAND,
        LOCAL_BACKEND_START_COMMAND,
        LOCAL_BACKEND_START_NO_RELOAD_COMMAND,
        LOCAL_WARNING_GATE_COMMAND,
        REPO_URL_PLACEHOLDER,
        backend_health_check_command,
        connected_runner_acceptance_command,
        connected_runner_acceptance_json_command,
        connected_runner_acceptance_summary_json_command,
        connected_runner_bundle_script_command,
        connected_runner_handoff_command_sequence_command,
        connected_runner_handoff_context_json_command,
        connected_runner_full_command as shared_connected_runner_full_command,
        connected_runner_preflight_command as shared_connected_runner_preflight_command,
        connected_runner_preflight_only_command,
        evidence_check_json_command,
        external_readiness_strict_summary_json_command,
        external_readiness_summary_json_command,
        completion_impacts_by_check_id,
        format_completion_deduction,
        next_release_command_only_env_command,
        next_release_command_sequence_env_command,
        next_release_connected_command_only_env_command,
        next_release_connected_command_sequence_env_command,
        next_release_connected_json_only_env_command,
        next_release_connected_sequence_command,
        next_release_connected_sequence_env_command,
        next_release_connected_sequence_origin_command,
        next_release_json_only_env_command,
        next_release_local_readiness_command,
        next_release_local_readiness_command_only_env_command,
        next_release_local_readiness_command_sequence_env_command,
        next_release_local_readiness_command_sequence_preview_command,
        next_release_local_readiness_gate_json_env_command,
        next_release_local_readiness_json_env_command,
        next_release_local_readiness_setup_sequence_env_command,
        next_release_local_readiness_setup_sequence_preview_command,
        next_release_operator_command_only_command,
        next_release_operator_command_sequence_command,
        next_release_operator_json_only_command,
        next_release_operator_review_sequence_command,
        next_release_operator_sequence_command,
        next_release_sequence_command,
        next_release_step_command,
        next_release_step_env_command,
        next_release_step_origin_command,
        next_release_step_repo_command,
        package_connected_runner_handoff_command,
        read_only_release_status_command,
        read_only_evidence_check_command,
        read_only_warning_review_command,
        refresh_release_status_command,
        release_status_completion_plan_command,
        release_status_completion_plan_json_command,
        release_status_completion_requirements_command,
        release_status_completion_requirements_json_command,
        release_status_progress_command,
        release_status_progress_json_command,
        release_status_owner_lanes_command,
        release_status_owner_lanes_json_command,
        release_status_json_command,
        repo_url_export_example_command,
        shell_arg,
        source_scoped_command,
        owner_lanes_summary as shared_owner_lanes_summary,
        connected_runner_verify_command,
        connected_runner_verify_json_command,
        connected_runner_verify_summary_json_command,
        verify_evidence_checksums_command,
        verify_evidence_checksums_json_command,
        warning_review_apply_command,
        warning_review_artifacts_only_command,
        warning_backend_guidance_payload as shared_warning_backend_guidance_payload,
        warning_review_gate_summary_json_command,
        warning_review_gate_json_command,
        warning_review_json_command,
        warning_review_next_command_gate_command,
        warning_review_next_command_only_command,
        warning_review_pre_approval_sequence_command,
        warning_review_summary_json_command,
        with_completion_impacts,
    )
    from release_artifacts import latest_json_file, latest_manifest_package_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write a compact Quant Lab release status report.")
    parser.add_argument(
        "--package-dir",
        help="Evidence package directory. Defaults to the latest artifacts/evidence-packages/* package.",
    )
    parser.add_argument(
        "--packages-dir",
        default="artifacts/evidence-packages",
        help="Directory containing evidence package directories.",
    )
    parser.add_argument(
        "--release-gate",
        help="Release gate JSON summary. Defaults to the latest artifacts/release-gate/release-gate-*.json.",
    )
    parser.add_argument(
        "--release-gates-dir",
        default="artifacts/release-gate",
        help="Directory containing release gate summaries.",
    )
    parser.add_argument(
        "--output-prefix",
        help="Output prefix. Defaults to release-status inside the evidence package.",
    )
    parser.add_argument(
        "--no-refresh-tarball",
        action="store_true",
        help="Do not refresh the package tarball after writing the report.",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Print status without writing release-status files or refreshing the package tarball.",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Print the release status report as JSON without writing files. Implies --no-write.",
    )
    parser.add_argument(
        "--progress-only",
        action="store_true",
        help="Print only completion percent, remaining IDs, owner counts, and deductions. Implies --no-write.",
    )
    parser.add_argument(
        "--progress-json-only",
        action="store_true",
        help="Print only compact progress data as JSON without writing files. Implies --no-write.",
    )
    parser.add_argument(
        "--completion-plan-only",
        action="store_true",
        help="Print only the ordered remaining completion plan without writing files. Implies --no-write.",
    )
    parser.add_argument(
        "--completion-plan-json-only",
        action="store_true",
        help="Print only the ordered remaining completion plan as JSON without writing files. Implies --no-write.",
    )
    parser.add_argument(
        "--completion-requirements-only",
        action="store_true",
        help="Print only grouped completion-plan requirements without writing files. Implies --no-write.",
    )
    parser.add_argument(
        "--completion-requirements-json-only",
        action="store_true",
        help="Print only grouped completion-plan requirements as JSON without writing files. Implies --no-write.",
    )
    parser.add_argument(
        "--owner-lanes-only",
        action="store_true",
        help="Print only owner-lane progress, next item, and approval state without writing files. Implies --no-write.",
    )
    parser.add_argument(
        "--owner-lanes-json-only",
        action="store_true",
        help="Print only owner-lane progress as JSON without writing files. Implies --no-write.",
    )
    parser.add_argument(
        "--allow-post-checksum-write",
        action="store_true",
        help=(
            "Allow rewriting release-status files after evidence checksums have been published. "
            "Rerun scripts/write_evidence_checksums.py afterward."
        ),
    )
    return parser.parse_args()


def latest_release_gate(release_gates_dir: Path) -> Path | None:
    return latest_json_file(release_gates_dir, "release-gate-*.json")


def matching_release_gate(release_gates_dir: Path, package_dir: Path) -> Path | None:
    for path in sorted(release_gates_dir.glob("release-gate-*.json"), reverse=True):
        try:
            payload = read_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        gate_package_dir = payload.get("package_dir")
        if isinstance(gate_package_dir, str) and Path(gate_package_dir).absolute() == package_dir:
            return path
    return None


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def first_existing_glob(base: Path, pattern: str) -> Path | None:
    matches = sorted(base.glob(pattern))
    return matches[-1] if matches else None


def status_counts(checks: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"pass": 0, "warn": 0, "fail": 0, "skipped": 0, "other": 0}
    for check in checks:
        status = str(check.get("status") or "other")
        counts[status if status in counts else "other"] += 1
    return counts


def format_counts(counts: dict[str, int]) -> str:
    return ", ".join(f"{key}: {counts.get(key, 0)}" for key in ("pass", "warn", "fail", "skipped", "other"))


def warning_checks(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [check for check in checks if check.get("status") == "warn"]


def failing_checks(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [check for check in checks if check.get("status") == "fail"]


def check_by_id(checks: list[dict[str, Any]], check_id: str) -> dict[str, Any] | None:
    for check in checks:
        if check.get("id") == check_id:
            return check
    return None


def external_readiness(package_dir: Path) -> tuple[Path | None, dict[str, Any] | None]:
    path = first_existing_glob(package_dir, "00-external-readiness/*/external-readiness.json")
    return (path, read_json(path)) if path else (None, None)


def release_evidence(package_dir: Path) -> tuple[Path | None, dict[str, Any] | None]:
    path = package_dir / "release-evidence-check.json"
    return (path, read_json(path)) if path.exists() else (None, None)


def warning_actions(package_dir: Path) -> tuple[Path | None, dict[str, Any] | None]:
    path = package_dir / "release-warning-actions.json"
    return (path, read_json(path)) if path.exists() else (None, None)


def warning_actions_need_operator_action(actions: dict[str, Any] | None) -> bool:
    if not actions:
        return False
    summary = actions.get("summary")
    if isinstance(summary, dict) and summary.get("action_needed") is False:
        return False
    return actions.get("status") in {"planned", "fail"}


def warning_review_artifacts(package_dir: Path) -> dict[str, str]:
    return {
        "action_plan": str(package_dir / "release-warning-actions.md"),
        "operator_checklist": str(package_dir / "release-warning-operator-checklist.md"),
    }


def connected_runner_preflight_command(handoff_bundle: str | None) -> str | None:
    if not handoff_bundle:
        return None
    return shared_connected_runner_preflight_command(handoff_bundle)


def connected_runner_full_command(handoff_bundle: str | None) -> str | None:
    if not handoff_bundle:
        return None
    return shared_connected_runner_full_command(handoff_bundle)


def build_remaining_items(
    *,
    package_dir: Path,
    evidence: dict[str, Any] | None,
    external: dict[str, Any] | None,
    actions: dict[str, Any] | None,
) -> list[dict[str, str]]:
    evidence_checks = evidence.get("checks", []) if evidence else []
    external_checks = external.get("checks", []) if external else []
    items: list[dict[str, str]] = []

    for check in external_checks:
        if check.get("status") not in {"warn", "fail"}:
            continue
        items.append(
            {
                "id": str(check.get("id") or "external_readiness"),
                "status": str(check.get("status")),
                "owner": "connected runner",
                "action": str(
                    check.get("remediation")
                    or check.get("message")
                    or "Clear the external readiness gap."
                ),
                "command": str(
                    check.get("setup_command")
                    or check.get("verify_command")
                    or CONNECTED_STRICT_GATE_COMMAND
                ),
                "verify_command": str(check.get("verify_command") or ""),
                "final_verify_command": CONNECTED_STRICT_GATE_COMMAND,
            }
        )

    live_beta = check_by_id(evidence_checks, "live_beta_archive")
    if live_beta and live_beta.get("status") in {"warn", "fail"}:
        items.append(
            {
                "id": "live_beta_archive",
                "status": str(live_beta.get("status")),
                "owner": "operator",
                "action": str(
                    live_beta.get("message")
                    or "Archive closeout evidence after the live-beta window."
                ),
                "preferred_action": (
                    "Run the live-beta closeout preflight first; it checks backend reachability, "
                    "live-lock state, and blocking alerts without writing an archive."
                ),
                "preferred_command": LIVE_BETA_PREFLIGHT_COMMAND,
                "automation_command": LIVE_BETA_PREFLIGHT_JSON_COMMAND,
                "full_flow_command": LIVE_BETA_CLOSEOUT_COMMAND,
                "supporting_commands": {
                    "Start local backend": LOCAL_BACKEND_START_COMMAND,
                    "Start local backend without reload": LOCAL_BACKEND_START_NO_RELOAD_COMMAND,
                    "Start Docker backend": DOCKER_BACKEND_START_COMMAND,
                    "Check backend health": backend_health_check_command(),
                },
                "command": LIVE_BETA_CLOSEOUT_COMMAND,
                "final_verify_command": LIVE_BETA_FINAL_GATE_COMMAND,
            }
        )

    warning_alerts = check_by_id(evidence_checks, "warning_alerts")
    if warning_alerts and warning_alerts.get("status") in {"warn", "fail"}:
        items.append(
            {
                "id": "warning_alerts",
                "status": str(warning_alerts.get("status")),
                "owner": "operator",
                "action": str(
                    warning_alerts.get("message")
                    or "Review warning alerts and record an operator decision."
                ),
                "command": read_only_warning_review_command(package_dir),
                "automation_command": warning_review_gate_json_command(package_dir),
                "supporting_commands": {
                    "Show warning pre-approval sequence": warning_review_pre_approval_sequence_command(package_dir),
                    "Show warning summary JSON": warning_review_summary_json_command(package_dir),
                    "Gate warning summary JSON": warning_review_gate_summary_json_command(package_dir),
                    "Show warning review artifact paths": warning_review_artifacts_only_command(package_dir),
                    "Show warning recommended next command": warning_review_next_command_only_command(package_dir),
                    "Gate warning recommended next command": warning_review_next_command_gate_command(package_dir),
                },
                "review_artifacts": warning_review_artifacts(package_dir),
            }
        )

    action_status = actions.get("status") if actions else None
    if warning_actions_need_operator_action(actions):
        items.append(
            {
                "id": "warning_actions",
                "status": str(action_status),
                "owner": "operator",
                "action": "Review release-warning-operator-checklist.md, then apply or explicitly acknowledge the generated warning action plan.",
                "command": warning_review_apply_command(package_dir),
                "supporting_commands": {
                    "Show warning pre-approval sequence": warning_review_pre_approval_sequence_command(package_dir),
                    "Show warning summary JSON": warning_review_summary_json_command(package_dir),
                    "Gate warning summary JSON": warning_review_gate_summary_json_command(package_dir),
                    "Show warning review artifact paths": warning_review_artifacts_only_command(package_dir),
                    "Show warning recommended next command": warning_review_next_command_only_command(package_dir),
                    "Gate warning recommended next command": warning_review_next_command_gate_command(package_dir),
                },
                "review_artifacts": warning_review_artifacts(package_dir),
            }
        )

    return items


def with_connected_runner_preferred_commands(
    items: list[dict[str, Any]],
    *,
    preflight_command: str | None,
    full_command: str | None,
    automation_command: str | None = None,
    package_dir: Path | None = None,
    source_dir: Path | None = None,
) -> list[dict[str, Any]]:
    if not preflight_command:
        return items
    updated: list[dict[str, Any]] = []
    for item in items:
        copied = dict(item)
        if copied.get("owner") == "connected runner":
            copied["preferred_action"] = (
                "Run the connected-runner bundle preflight first; it rejects missing/placeholder/invalid "
                "remote URLs, self-verifies the bundle, then validates remote reachability, Docker, "
                "GitHub CLI auth, source safety, and copied evidence before dependency installation or push."
            )
            copied["preferred_command"] = preflight_command
            if automation_command:
                copied["automation_command"] = automation_command
            if full_command:
                copied["full_flow_command"] = full_command
            if source_dir:
                for key in ("command", "verify_command", "final_verify_command"):
                    if copied.get(key):
                        copied[key] = str(source_scoped_command(copied.get(key), source_dir))
            supporting_commands = dict(copied.get("supporting_commands") or {})
            supporting_commands.setdefault("Export repo URL example", repo_url_export_example_command())
            supporting_commands.setdefault("Show external readiness summary JSON", external_readiness_summary_json_command())
            supporting_commands.setdefault(
                "Gate external readiness summary JSON",
                external_readiness_strict_summary_json_command(),
            )
            if package_dir:
                supporting_commands.setdefault(
                    "Show connected-runner command only from env",
                    next_release_connected_command_only_env_command(package_dir),
                )
                supporting_commands.setdefault(
                    "Show local readiness setup sequence",
                    next_release_local_readiness_setup_sequence_env_command(package_dir),
                )
                supporting_commands.setdefault(
                    "Show local readiness command sequence",
                    next_release_local_readiness_command_sequence_env_command(package_dir),
                )
                supporting_commands.setdefault(
                    "Preview local readiness setup sequence",
                    next_release_local_readiness_setup_sequence_preview_command(package_dir),
                )
                supporting_commands.setdefault(
                    "Preview local readiness command sequence",
                    next_release_local_readiness_command_sequence_preview_command(package_dir),
                )
            copied["supporting_commands"] = supporting_commands
        updated.append(copied)
    return updated


def readiness_estimate(
    *,
    release_gate_status: str,
    evidence_checks: list[dict[str, Any]],
    external_checks: list[dict[str, Any]],
    actions: dict[str, Any] | None,
    remaining_items: list[dict[str, str]],
) -> dict[str, Any]:
    def check_ids(checks: list[dict[str, Any]], status: str) -> list[str]:
        return [
            str(check.get("id") or check.get("label") or "unknown")
            for check in checks
            if check.get("status") == status
        ]

    if release_gate_status == "fail" or any(check.get("status") == "fail" for check in evidence_checks + external_checks):
        failing_ids = check_ids(evidence_checks + external_checks, "fail")
        if release_gate_status == "fail":
            failing_ids.insert(0, "release_gate")
        return {
            "percent": 70,
            "basis": "A failing release gate or evidence check is still present.",
            "deductions": [
                {
                    "id": "failing_gate_or_check",
                    "points": 30,
                    "detail": "A failing release gate or evidence check caps the handoff estimate at 70%.",
                    "check_ids": failing_ids,
                }
            ],
            "remaining_items": len(remaining_items),
        }

    percent = 100
    deductions: list[dict[str, Any]] = []
    external_warning_ids = check_ids(external_checks, "warn")
    external_warning_count = len(external_warning_ids)
    if external_warning_count:
        percent -= external_warning_count
        deductions.append(
            {
                "id": "external_readiness_warnings",
                "points": external_warning_count,
                "detail": (
                    f"{external_warning_count} external readiness warning check(s) remain: "
                    + ", ".join(external_warning_ids)
                    + "."
                ),
                "check_ids": external_warning_ids,
            }
        )
    live_beta_check = check_by_id(evidence_checks, "live_beta_archive")
    if live_beta_check and live_beta_check.get("status") == "warn":
        percent -= 2
        deductions.append(
            {
                "id": "live_beta_archive",
                "points": 2,
                "detail": "Live-beta closeout archive is not present yet.",
                "check_ids": ["live_beta_archive"],
            }
        )
    warning_alerts_check = check_by_id(evidence_checks, "warning_alerts")
    if warning_alerts_check and warning_alerts_check.get("status") == "warn":
        percent -= 1
        deductions.append(
            {
                "id": "warning_alerts",
                "points": 1,
                "detail": "Warning-level alerts still need operator review.",
                "check_ids": ["warning_alerts"],
            }
        )
    if actions and actions.get("status") == "fail":
        percent -= 4
        deductions.append(
            {
                "id": "warning_actions_failed",
                "points": 4,
                "detail": "Generated warning actions failed and need correction.",
                "check_ids": ["warning_actions"],
            }
        )

    percent = max(0, min(100, percent))
    return {
        "percent": percent,
        "basis": (
            "Approximate handoff completion based on non-failing release evidence, "
            "external readiness gaps, warning alerts, and live-beta archive status."
        ),
        "deductions": deductions,
        "remaining_items": len(remaining_items),
    }


def build_next_actions(
    *,
    release_gate: dict[str, Any] | None,
    evidence: dict[str, Any] | None,
    external: dict[str, Any] | None,
    actions: dict[str, Any] | None,
    connected_runner_preflight: str | None = None,
) -> list[str]:
    next_actions: list[str] = []

    if release_gate and release_gate.get("status") == "fail":
        failed_steps = [
            str(step.get("name"))
            for step in release_gate.get("steps", [])
            if step.get("status") == "fail"
        ]
        next_actions.append("Fix failing release gate step(s): " + ", ".join(failed_steps))

    if external:
        external_gaps = [
            f"{check.get('label')}: {check.get('message')}"
            for check in external.get("checks", [])
            if check.get("status") in {"warn", "fail"}
        ]
        if external_gaps:
            if connected_runner_preflight:
                next_actions.append(
                    "Run the connected-runner bundle preflight first; it rejects missing/placeholder/invalid "
                    "remote URLs and self-verifies the bundle before external checks: "
                    + connected_runner_preflight
                )
            next_actions.append("Clear external readiness gaps on a connected runner: " + "; ".join(external_gaps))

    if evidence:
        checks = evidence.get("checks", [])
        if any(check.get("id") == "live_beta_archive" and check.get("status") == "warn" for check in checks):
            next_actions.append(
                "After the live-beta window, run scripts/archive_live_beta_closeout.py to archive closeout evidence under artifacts/live-beta/, then rerun with --require-live-beta."
            )
        if any(check.get("id") == "warning_alerts" and check.get("status") == "warn" for check in checks):
            next_actions.append(
                "Review release-warning-operator-checklist.md and release-warning-actions.md, then apply or acknowledge warning alerts through a running backend when an operator approves."
            )

    if warning_actions_need_operator_action(actions):
        next_actions.append("Resolve planned or failed warning actions before final handoff.")

    if not next_actions:
        next_actions.append("Attach the evidence package and release gate summary for final review.")
    return next_actions


def build_handoff_commands(
    package_dir: Path,
    release_gate_path: Path | None,
    connected_runner_handoff_bundle: str | None = None,
) -> list[dict[str, str]]:
    commands = [
        {
            "label": "Refresh this status report",
            "command": refresh_release_status_command(package_dir, release_gate_path),
            "when": "Only when you intend to rewrite release-status files after warning actions, live-beta archive updates, or external readiness changes; rerun checksums afterward.",
        },
        {
            "label": "Show this status report read-only",
            "command": read_only_release_status_command(package_dir, release_gate_path),
            "when": "Use after checksums are published when you need a fresh status calculation without changing package files.",
        },
        {
            "label": "Show this status report JSON",
            "command": release_status_json_command(package_dir, release_gate_path),
            "when": "Use in automation after checksums are published when the compact status report should be parsed without changing package files.",
        },
        {
            "label": "Show release progress only",
            "command": release_status_progress_command(package_dir, release_gate_path),
            "when": "Use when a handoff or status check needs only the current percent, remaining item IDs, owner counts, and deductions.",
        },
        {
            "label": "Show release progress JSON",
            "command": release_status_progress_json_command(package_dir, release_gate_path),
            "when": "Use in automation when only compact progress data should be parsed without dumping the full release status report.",
        },
        {
            "label": "Show completion plan",
            "command": release_status_completion_plan_command(package_dir, release_gate_path),
            "when": "Use when a handoff needs the ordered path from the current percent to 100% without dumping the full status report.",
        },
        {
            "label": "Show completion plan JSON",
            "command": release_status_completion_plan_json_command(package_dir, release_gate_path),
            "when": "Use in automation when only the ordered remaining completion plan should be parsed without dumping compact progress metadata.",
        },
        {
            "label": "Show completion requirements",
            "command": release_status_completion_requirements_command(package_dir, release_gate_path),
            "when": "Use when a handoff needs grouped blockers from the completion plan without dumping the full status report.",
        },
        {
            "label": "Show completion requirements JSON",
            "command": release_status_completion_requirements_json_command(package_dir, release_gate_path),
            "when": "Use in automation when grouped completion-plan blockers should be parsed without dumping compact progress metadata.",
        },
        {
            "label": "Show owner lanes",
            "command": release_status_owner_lanes_command(package_dir, release_gate_path),
            "when": "Use when a handoff needs the connected-runner/operator split, next item, requirements, and approval state without dumping the full status report.",
        },
        {
            "label": "Show owner lanes JSON",
            "command": release_status_owner_lanes_json_command(package_dir, release_gate_path),
            "when": "Use in automation when only owner-lane progress should be parsed without dumping compact progress metadata.",
        },
        {
            "label": "Run local warning-mode gate",
            "command": LOCAL_WARNING_GATE_COMMAND,
            "when": "Use on local machines without Docker or GitHub CLI.",
        },
        {
            "label": "Run connected-runner strict gate",
            "command": CONNECTED_STRICT_GATE_COMMAND,
            "when": "Use on CI or a Docker/GitHub-enabled handoff host with GitHub CLI auth.",
        },
        {
            "label": "Show external readiness summary JSON",
            "command": external_readiness_summary_json_command(),
            "when": "Use when automation only needs compact external-runner status counts plus warning/failure IDs.",
        },
        {
            "label": "Gate external readiness summary JSON",
            "command": external_readiness_strict_summary_json_command(),
            "when": "Use on the connected runner when missing origin, Docker, GitHub CLI, or GitHub auth should fail after printing compact JSON.",
        },
        {
            "label": "Verify evidence checksums",
            "command": verify_evidence_checksums_command(package_dir),
            "when": "Use after copying or extracting the evidence package.",
        },
        {
            "label": "Verify evidence checksums JSON",
            "command": verify_evidence_checksums_json_command(package_dir),
            "when": "Use in automation after copying or extracting the evidence package when checksum verification should be parsed.",
        },
        {
            "label": "Run read-only evidence check",
            "command": read_only_evidence_check_command(package_dir),
            "when": "Use after checksums are published when you need to inspect evidence status without changing package files.",
        },
        {
            "label": "Show evidence check JSON",
            "command": evidence_check_json_command(package_dir),
            "when": "Use in automation after checksums are published when the full evidence check summary should be parsed without changing package files.",
        },
        {
            "label": "Show next release step",
            "command": next_release_step_command(package_dir),
            "when": "Use when you need the single nearest handoff action and command.",
        },
        {
            "label": "Show next release step with repo URL",
            "command": next_release_step_repo_command(package_dir),
            "when": "Use on the connected runner to print a copy-paste-ready command while keeping archived evidence commands portable.",
        },
        {
            "label": "Show next release step from git origin",
            "command": next_release_step_origin_command(package_dir),
            "when": "Use on the connected runner after origin is configured to print copy-paste-ready commands from the local git remote without changing archived evidence.",
        },
        {
            "label": "Show next release step from env",
            "command": next_release_step_env_command(package_dir),
            "when": "Use on the connected runner after exporting GIT_ORIGIN_URL to print copy-paste-ready commands without changing archived evidence.",
        },
        {
            "label": "Export repo URL example",
            "command": repo_url_export_example_command(),
            "when": "Replace OWNER/REPO with the real repository before running repo-url-from-env or connected-runner commands.",
        },
        {
            "label": "Show next command only from env",
            "command": next_release_command_only_env_command(package_dir),
            "when": "Use in automation on the connected runner when you need exactly one next command and want placeholders to fail closed.",
        },
        {
            "label": "Show remaining command sequence from env",
            "command": next_release_command_sequence_env_command(package_dir),
            "when": "Use in terminal or shell automation when you need only the remaining handoff commands, one per line, with repository placeholders rejected.",
        },
        {
            "label": "Show next report JSON from env",
            "command": next_release_json_only_env_command(package_dir),
            "when": "Use in automation on the connected runner when you need the full next-step report as JSON without writing files.",
        },
        {
            "label": "Show connected-runner report JSON from env",
            "command": next_release_connected_json_only_env_command(package_dir),
            "when": "Use in connected-runner automation when you need only runner-owned next-step items as JSON.",
        },
        {
            "label": "Show connected-runner command only from env",
            "command": next_release_connected_command_only_env_command(package_dir),
            "when": "Use in connected-runner automation when you need only the next runner-owned command with repository placeholders rejected.",
        },
        {
            "label": "Show connected-runner command sequence from env",
            "command": next_release_connected_command_sequence_env_command(package_dir),
            "when": "Use in connected-runner shell automation when you need only runner-owned commands with repository placeholders rejected.",
        },
        {
            "label": "Show remaining handoff sequence",
            "command": next_release_sequence_command(package_dir),
            "when": "Use when handing work between connected-runner and operator owners and you need every remaining command in order.",
        },
        {
            "label": "Show operator sequence",
            "command": next_release_operator_sequence_command(package_dir),
            "when": "Use when an operator needs only live-beta archive and warning-review actions.",
        },
        {
            "label": "Show operator command only",
            "command": next_release_operator_command_only_command(package_dir),
            "when": "Use in operator automation when you need exactly one next command and no connected-runner repository URL placeholder.",
        },
        {
            "label": "Show operator command sequence",
            "command": next_release_operator_command_sequence_command(package_dir),
            "when": "Use in operator automation when you need only the remaining operator commands, one per line.",
        },
        {
            "label": "Show operator review sequence",
            "command": next_release_operator_review_sequence_command(package_dir),
            "when": "Use before approval to print operator review commands while omitting --apply --operator-approved.",
        },
        {
            "label": "Show warning pre-approval sequence",
            "command": warning_review_pre_approval_sequence_command(package_dir),
            "when": "Use before approval when automation needs only apply-free warning review commands, one per line.",
        },
        {
            "label": "Show operator report JSON",
            "command": next_release_operator_json_only_command(package_dir),
            "when": "Use in operator automation when you need the operator next-step report as JSON without writing files.",
        },
        {
            "label": "Show connected-runner sequence with repo URL",
            "command": next_release_connected_sequence_command(package_dir),
            "when": "Use on the connected runner to print all runner-owned commands with the concrete git remote URL.",
        },
        {
            "label": "Show connected-runner sequence from git origin",
            "command": next_release_connected_sequence_origin_command(package_dir),
            "when": "Use on the connected runner after origin is configured to print all runner-owned commands from the local git remote.",
        },
        {
            "label": "Show connected-runner sequence from env",
            "command": next_release_connected_sequence_env_command(package_dir),
            "when": "Use on the connected runner after exporting GIT_ORIGIN_URL to print all runner-owned commands.",
        },
        {
            "label": "Show local connected-runner readiness",
            "command": next_release_local_readiness_command(package_dir),
            "when": "Use on a candidate connected runner to inspect origin, Docker Compose, and GitHub CLI auth readiness without changing package files.",
        },
        {
            "label": "Show local connected-runner readiness JSON",
            "command": next_release_local_readiness_json_env_command(package_dir),
            "when": "Use in connected-runner automation to parse the next-step report and local readiness checks together.",
        },
        {
            "label": "Gate local connected-runner readiness command only",
            "command": next_release_local_readiness_command_only_env_command(package_dir),
            "when": "Use in connected-runner automation when you need exactly one next command but local readiness must pass first.",
        },
        {
            "label": "Show local connected-runner readiness setup sequence",
            "command": next_release_local_readiness_setup_sequence_env_command(package_dir),
            "when": "Use in shell automation when you need only unresolved setup commands for origin, Docker Compose, and GitHub CLI readiness.",
        },
        {
            "label": "Show local connected-runner readiness command sequence",
            "command": next_release_local_readiness_command_sequence_env_command(package_dir),
            "when": "Use in shell automation when you need unresolved setup commands followed by their matching verification commands.",
        },
        {
            "label": "Preview local connected-runner readiness setup sequence",
            "command": next_release_local_readiness_setup_sequence_preview_command(package_dir),
            "when": "Use during resume planning when you need unresolved setup commands without requiring GIT_ORIGIN_URL or failing on non-passing local readiness.",
        },
        {
            "label": "Preview local connected-runner readiness command sequence",
            "command": next_release_local_readiness_command_sequence_preview_command(package_dir),
            "when": "Use during resume planning when you need setup commands followed by verification commands without treating current local readiness as a failed gate.",
        },
        {
            "label": "Gate local connected-runner readiness JSON",
            "command": next_release_local_readiness_gate_json_env_command(package_dir),
            "when": "Use in connected-runner automation when non-passing local readiness should produce a non-zero exit after printing JSON.",
        },
        {
            "label": "Package connected-runner handoff",
            "command": package_connected_runner_handoff_command(package_dir),
            "when": "Use when no git remote is available and the source plus evidence must move to a connected runner.",
        },
        {
            "label": "Run connected-runner bundle script",
            "command": connected_runner_bundle_script_command(),
            "when": "Use from the extracted handoff bundle root to self-verify the bundle, initialize git, install dependencies, run acceptance, push, and rerun the strict gate.",
        },
        {
            "label": "Run connected-runner preflight only",
            "command": connected_runner_preflight_only_command(),
            "when": "Use from the extracted handoff bundle root as the first connected-runner command; it rejects missing/placeholder/invalid remote URLs, self-verifies the bundle, then validates remote reachability, command/auth readiness, source safety, runner script, and copied evidence before dependency installation or push.",
        },
        {
            "label": "Run connected-runner acceptance",
            "command": connected_runner_acceptance_command(),
            "when": "Use from the extracted handoff source directory after configuring git origin, Docker, and GitHub CLI, before dependency installation.",
        },
        {
            "label": "Run connected-runner acceptance JSON",
            "command": connected_runner_acceptance_json_command(),
            "when": "Use from the extracted handoff source directory when automation should parse the acceptance report from stdout.",
        },
        {
            "label": "Run connected-runner acceptance summary JSON",
            "command": connected_runner_acceptance_summary_json_command(),
            "when": "Use from the extracted handoff source directory when resume automation only needs compact status counts and warning/failure IDs.",
        },
        {
            "label": "Review warning operator checklist",
            "command": read_only_warning_review_command(package_dir),
            "when": "Use after checksums are published to inspect planned warning acknowledgements without rewriting package artifacts.",
        },
        {
            "label": "Show warning action plan JSON",
            "command": warning_review_json_command(package_dir),
            "when": "Use in operator automation when the warning action plan must be parsed without rewriting package artifacts.",
        },
        {
            "label": "Gate warning action plan JSON",
            "command": warning_review_gate_json_command(package_dir),
            "when": "Use in operator automation when unresolved warning actions should produce a non-zero exit after printing JSON.",
        },
        {
            "label": "Show warning action summary JSON",
            "command": warning_review_summary_json_command(package_dir),
            "when": "Use in operator automation when only compact warning counts, review artifacts, and recommended next command are needed.",
        },
        {
            "label": "Gate warning action summary JSON",
            "command": warning_review_gate_summary_json_command(package_dir),
            "when": "Use in operator automation when unresolved warning actions should produce a non-zero exit after printing compact JSON.",
        },
        {
            "label": "Show warning review artifact paths",
            "command": warning_review_artifacts_only_command(package_dir),
            "when": "Use in operator automation before approval to print the existing action-plan and checklist paths, failing if either artifact is missing.",
        },
        {
            "label": "Show warning recommended next command",
            "command": warning_review_next_command_only_command(package_dir),
            "when": "Use when automation or an operator needs only the next warning-review command selected from the action plan.",
        },
        {
            "label": "Gate warning recommended next command",
            "command": warning_review_next_command_gate_command(package_dir),
            "when": "Use when automation needs only the selected warning-review command but should still fail while warning actions remain unresolved.",
        },
        {
            "label": "Apply reviewed warning actions",
            "command": warning_review_apply_command(package_dir),
            "when": "Only after an operator approves the warning acknowledgement plan against a running backend.",
        },
        {
            "label": "Preflight live-beta closeout",
            "command": LIVE_BETA_PREFLIGHT_COMMAND,
            "when": "Use after a live-beta window before writing closeout files; it checks backend reachability, live-lock state, and blocking alerts.",
        },
        {
            "label": "Preflight live-beta closeout JSON",
            "command": LIVE_BETA_PREFLIGHT_JSON_COMMAND,
            "when": "Use in operator automation before writing closeout files when the live-beta preflight report should be parsed.",
        },
        {
            "label": "Show live-beta recommended next command",
            "command": LIVE_BETA_NEXT_COMMAND_ONLY_COMMAND,
            "when": "Use when automation or an operator needs only the next safe live-beta command selected from the preflight result.",
        },
        {
            "label": "Start local backend for live-beta preflight",
            "command": LOCAL_BACKEND_START_COMMAND,
            "when": "Use when live-beta preflight cannot reach the local backend and a local virtualenv backend should be started.",
        },
        {
            "label": "Start local backend without reload for live-beta preflight",
            "command": LOCAL_BACKEND_START_NO_RELOAD_COMMAND,
            "when": "Use when file watching or reload mode is blocked but the local virtualenv backend can bind localhost.",
        },
        {
            "label": "Start Docker backend for live-beta preflight",
            "command": DOCKER_BACKEND_START_COMMAND,
            "when": "Use when live-beta preflight cannot reach the backend and the Docker Compose backend service should be started.",
        },
        {
            "label": "Check backend health for live-beta preflight",
            "command": backend_health_check_command(),
            "when": "Use after starting the backend to confirm the live-beta preflight API target is reachable.",
        },
        {
            "label": "Archive live-beta closeout",
            "command": LIVE_BETA_CLOSEOUT_COMMAND,
            "when": "Use after a live-beta window, once live flags are locked again and a backup reference is available.",
        },
        {
            "label": "Run final live-beta archive gate",
            "command": LIVE_BETA_FINAL_GATE_COMMAND,
            "when": "Use after a live-beta closeout archive exists under artifacts/live-beta/.",
        },
    ]
    if connected_runner_handoff_bundle:
        commands.append(
            {
                "label": "Verify connected-runner handoff JSON",
                "command": connected_runner_verify_json_command(connected_runner_handoff_bundle),
                "when": "Use after copying or extracting a handoff bundle when bundle verification should be parsed from stdout.",
            }
        )
        commands.append(
            {
                "label": "Verify connected-runner handoff summary JSON",
                "command": connected_runner_verify_summary_json_command(connected_runner_handoff_bundle),
                "when": "Use after copying or extracting a handoff bundle when resume automation only needs compact status counts and warning/failure IDs.",
            }
        )
        commands.append(
            {
                "label": "Show connected-runner handoff context JSON",
                "command": connected_runner_handoff_context_json_command(connected_runner_handoff_bundle),
                "when": "Use when resume automation needs the bundle manifest handoff context without rewriting verification reports.",
            }
        )
        commands.append(
            {
                "label": "Show connected-runner handoff command sequence",
                "command": connected_runner_handoff_command_sequence_command(connected_runner_handoff_bundle),
                "when": "Use when resume automation needs only the ordered bundle-root commands without rewriting verification reports.",
            }
        )
    return commands


def refresh_package_tarball(package_dir: Path) -> Path | None:
    manifest_path = package_dir / "manifest.json"
    if not manifest_path.exists():
        return None
    manifest = read_json(manifest_path)
    tarball = manifest.get("tarball")
    if not isinstance(tarball, str) or not tarball:
        return None
    tarball_path = Path(tarball)
    with tarfile.open(tarball_path, "w:gz") as tar:
        tar.add(package_dir, arcname=package_dir.name)
    return tarball_path


def checksum_files_exist(package_dir: Path) -> bool:
    return any(
        (package_dir / filename).is_file()
        for filename in ("evidence-checksums.json", "evidence-checksums.sha256")
    )


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Quant Lab Release Status",
        "",
        f"Generated at: {report['generated_at']}",
        f"Overall status: {report['status']}",
        f"Evidence package: `{report['package_dir']}`",
        f"Release gate summary: `{report.get('release_gate_path') or 'not available'}`",
        f"Tarball: `{report.get('tarball') or 'not available'}`",
        "",
        "## Summary",
        "",
        f"- Release gate: {report['summary']['release_gate_status']}",
        f"- Release evidence: {report['summary']['release_evidence_status']}",
        f"- External readiness: {report['summary']['external_readiness_status']}",
        f"- Evidence checks: {format_counts(report['summary']['evidence_check_counts'])}",
        f"- External checks: {format_counts(report['summary']['external_check_counts'])}",
        f"- Warning actions: {report['summary']['warning_action_status']}",
        "",
    ]
    if report.get("connected_runner_handoff_bundle") or report.get("connected_runner_handoff_tarball"):
        lines.extend(
            [
                "## Connected Runner Handoff",
                "",
                f"- Bundle: `{report.get('connected_runner_handoff_bundle') or 'not available'}`",
                f"- Bundle verification: `{report.get('connected_runner_handoff_bundle_verification') or 'not available'}`",
                f"- Tarball: `{report.get('connected_runner_handoff_tarball') or 'not available'}`",
                f"- Tarball verification: `{report.get('connected_runner_handoff_tarball_verification') or 'not available'}`",
            ]
        )
        if report.get("connected_runner_handoff_bundle"):
            lines.extend(
                [
                    "- Verify:",
                    "",
                    "```bash",
                    connected_runner_verify_command(report["connected_runner_handoff_bundle"]),
                    "```",
                    "",
                ]
            )
            if report.get("connected_runner_preflight_command"):
                lines.extend(
                    [
                        "- First connected-runner command:",
                        "",
                        "```bash",
                        report["connected_runner_preflight_command"],
                        "```",
                        "",
                    ]
                )
            if report.get("connected_runner_full_command"):
                lines.extend(
                    [
                        "- Full connected-runner flow after preflight passes:",
                        "",
                        "```bash",
                        report["connected_runner_full_command"],
                        "```",
                        "",
                    ]
                )
        else:
            lines.append("")

    lines.extend(
        [
            "## Completion Estimate",
            "",
            f"- Approximate completion: {report['readiness_estimate']['percent']}%",
            f"- Remaining handoff items: {report['readiness_estimate']['remaining_items']}",
            f"- Basis: {report['readiness_estimate']['basis']}",
        ]
    )
    for deduction in report["readiness_estimate"].get("deductions", []):
        lines.append(f"- Deduction {format_completion_deduction(deduction)}")
    lines.extend(["", "## Next Actions", ""])
    lines.extend(f"- {action}" for action in report["next_actions"])

    if report["remaining_items"]:
        lines.extend(["", "## Remaining Handoff Items", ""])
        for item in report["remaining_items"]:
            lines.extend(
                [
                    f"### {item['id']}",
                    "",
                    f"- Status: {item['status']}",
                    f"- Owner: {item['owner']}",
                    "",
                ]
            )
            if item.get("completion_impact"):
                lines.extend([f"- Completion impact: {item['completion_impact']}", ""])
            else:
                completion_note = completion_note_for_item(item)
                if completion_note:
                    lines.extend([f"- Completion note: {completion_note}", ""])
            if item.get("preferred_action"):
                lines.extend(
                    [
                        f"- Preferred action: {item['preferred_action']}",
                        "",
                        "```bash",
                        item["preferred_command"],
                        "```",
                        "",
                    ]
                )
                if item.get("full_flow_command"):
                    lines.extend(
                        [
                            "- Full flow after preferred preflight passes:",
                            "",
                            "```bash",
                            item["full_flow_command"],
                            "```",
                            "",
                        ]
                    )
                lines.extend(
                    [
                        f"- Manual/remediation action: {item['action']}",
                        "",
                        "```bash",
                        item["command"],
                        "```",
                        "",
                    ]
                )
            else:
                lines.extend(
                    [
                        f"- Action: {item['action']}",
                        "",
                        "```bash",
                        item["command"],
                        "```",
                        "",
                    ]
                )
            if item.get("automation_command") and item["automation_command"] != item["command"]:
                lines.extend(
                    [
                        "- Automation JSON:",
                        "",
                        "```bash",
                        item["automation_command"],
                        "```",
                        "",
                    ]
                )
            if item.get("supporting_commands"):
                lines.append("- Supporting commands:")
                lines.append("")
                for label, command in item["supporting_commands"].items():
                    lines.extend(
                        [
                            f"  - {label}:",
                            "",
                            "```bash",
                            command,
                            "```",
                            "",
                        ]
                    )
            if item.get("final_verify_command") and item["final_verify_command"] != item["command"]:
                if item.get("verify_command") and item["verify_command"] != item["command"]:
                    lines.extend(
                        [
                            "- Verify:",
                            "",
                            "```bash",
                            item["verify_command"],
                            "```",
                            "",
                        ]
                    )
                lines.extend(
                    [
                        "- Final verify:",
                        "",
                        "```bash",
                        item["final_verify_command"],
                        "```",
                        "",
                    ]
                )

    lines.extend(["", "## Handoff Commands", ""])
    for command in report["handoff_commands"]:
        lines.extend(
            [
                f"### {command['label']}",
                "",
                f"- When: {command['when']}",
                "",
                "```bash",
                command["command"],
                "```",
                "",
            ]
        )

    if report["warnings"]:
        lines.extend(["", "## Warning Checks", ""])
        for warning in report["warnings"]:
            lines.append(f"- {warning.get('id')}: {warning.get('message')}")

    if report["failures"]:
        lines.extend(["", "## Failing Checks", ""])
        for failure in report["failures"]:
            lines.append(f"- {failure.get('id')}: {failure.get('message')}")

    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def progress_summary_lines(report: dict[str, Any]) -> list[str]:
    readiness = report.get("readiness_estimate") or {}
    remaining_items = report.get("remaining_items") or []
    remaining_ids = [str(item.get("id") or "unknown") for item in remaining_items]
    owner_counts: dict[str, int] = {}
    for item in remaining_items:
        owner = str(item.get("owner") or "unassigned")
        owner_counts[owner] = owner_counts.get(owner, 0) + 1

    lines = [
        f"Release progress: {readiness.get('percent', 'not available')}%",
        f"Status: {report.get('status', 'not available')}",
        f"Evidence package: {report.get('package_dir', 'not available')}",
        f"Remaining handoff items: {readiness.get('remaining_items', len(remaining_items))}",
    ]
    if remaining_ids:
        lines.append("Remaining IDs: " + ", ".join(remaining_ids))
    if owner_counts:
        owner_summary = ", ".join(f"{owner}: {count}" for owner, count in sorted(owner_counts.items()))
        lines.append("Remaining by owner: " + owner_summary)
    deductions = readiness.get("deductions") or []
    if deductions:
        lines.append("Deductions:")
        for deduction in deductions:
            lines.append(f"- {format_completion_deduction(deduction)}")
    else:
        lines.append("Deductions: none")
    return lines


def completion_note_for_item(item: dict[str, Any]) -> str | None:
    item_id = str(item.get("id") or "")
    if item_id == "warning_actions" and not item.get("completion_impact"):
        return (
            "Required for final completion; it does not recover a percentage point by itself "
            "because warning_alerts carries the operator-review deduction."
        )
    return None


def repo_url_guidance_lines(repo_url: Any) -> list[str]:
    if not isinstance(repo_url, dict) or repo_url.get("required") is not True:
        return []
    lines: list[str] = []
    fields = [
        ("note", "repo_url"),
        ("export_command", "repo_url_export"),
        ("command_gate", "repo_url_command_gate"),
        ("json_gate", "repo_url_json_gate"),
    ]
    for field, label in fields:
        value = repo_url.get(field)
        if isinstance(value, str) and value:
            lines.append(f"   {label}: {value}")
    return lines


def completion_plan_lines(report: dict[str, Any]) -> list[str]:
    progress = report.get("progress_summary") or progress_summary_payload(report)
    plan = progress.get("completion_plan") or []
    lines = [
        f"Completion plan: {progress.get('percent', 'unknown')}%",
        f"Status: {progress.get('status', 'unknown')}",
        f"Remaining items: {progress.get('remaining_items', len(plan))}",
    ]
    if not plan:
        lines.append("No remaining completion items.")
        return lines
    printed_command_values: set[str] = set()
    printed_repo_url_guidance = False
    for index, item in enumerate(plan, start=1):
        if not isinstance(item, dict):
            continue
        heading = (
            f"{index}. {item.get('id', 'unknown')} "
            f"[{item.get('owner', 'unassigned')}/{item.get('status', 'unknown')}]"
        )
        impact_points = item.get("completion_impact_points")
        if impact_points is not None:
            heading += f" (+{impact_points} point)"
        lines.append(heading)
        mode = item.get("mode")
        if isinstance(mode, str) and mode:
            lines.append(f"   mode: {mode}")
        requirements = item.get("requirements")
        if isinstance(requirements, list) and requirements:
            requirement_values = [
                str(value)
                for value in requirements
                if isinstance(value, str) and value
            ]
            if requirement_values:
                lines.append("   requires: " + ", ".join(requirement_values))
        if item.get("requires_operator_approval") is True:
            lines.append("   approval: operator approval required after checklist review")
        if isinstance(requirements, list) and "running_backend" in requirements:
            lines.extend(backend_requirement_guidance_lines(backend_requirement_guidance_payload()))
        completion_note = completion_note_for_item(item)
        if completion_note:
            lines.append(f"   note: {completion_note}")
        if item.get("owner") == "connected runner":
            command_values = [
                value
                for key in ("command", "automation_command", "full_flow_command")
                if isinstance((value := item.get(key)), str) and value
            ]
            if any(REPO_URL_PLACEHOLDER in value for value in command_values):
                owner_lanes = progress.get("owner_lanes")
                connected_lane = (
                    owner_lanes.get("connected runner")
                    if isinstance(owner_lanes, dict)
                    else None
                )
                repo_url = (
                    connected_lane.get("repo_url")
                    if isinstance(connected_lane, dict)
                    else None
                )
                if not repo_url:
                    repo_url = progress.get("repo_url")
                repo_url_lines = repo_url_guidance_lines(repo_url)
                if repo_url_lines:
                    if printed_repo_url_guidance:
                        lines.append("   repo_url: same as earlier in plan.")
                    else:
                        lines.extend(repo_url_lines)
                        printed_repo_url_guidance = True
        for key in ("command", "automation_command", "verify_command", "final_verify_command", "full_flow_command"):
            value = item.get(key)
            if isinstance(value, str) and value:
                if value in printed_command_values:
                    lines.append(f"   {key}: same as earlier in plan.")
                else:
                    lines.append(f"   {key}: {value}")
                    printed_command_values.add(value)
        impact = item.get("completion_impact")
        if isinstance(impact, str) and impact:
            lines.append(f"   impact: {impact}")
        pre_approval_review_sequence = item.get("pre_approval_review_sequence")
        if isinstance(pre_approval_review_sequence, list) and pre_approval_review_sequence:
            lines.append("   pre_approval_review_sequence:")
            for command_value in pre_approval_review_sequence:
                if isinstance(command_value, str) and command_value:
                    lines.append(f"   - {command_value}")
        review_sequence = item.get("review_sequence")
        if isinstance(review_sequence, list) and review_sequence:
            lines.append("   review_sequence:")
            for command_value in review_sequence:
                if isinstance(command_value, str) and command_value:
                    lines.append(f"   - {command_value}")
    return lines


def first_plan_item_for_requirement(requirement: str, plan: list[Any]) -> dict[str, Any] | None:
    requirement_item_ids = {
        "real_git_remote_url": "git_origin_remote",
        "docker_cli": "docker_cli",
        "github_cli_auth": "github_cli",
        "operator_review": "warning_alerts",
        "operator_checklist_review": "warning_actions",
        "operator_approval": "warning_actions",
        "running_backend": "warning_actions",
    }
    preferred_id = requirement_item_ids.get(requirement)
    for item in plan:
        if not isinstance(item, dict):
            continue
        if preferred_id and item.get("id") == preferred_id:
            return item
    for item in plan:
        if not isinstance(item, dict):
            continue
        requirements = item.get("requirements")
        if isinstance(requirements, list) and requirement in requirements:
            return item
    return None


def first_local_readiness_setup(progress: dict[str, Any], pattern: str) -> str | None:
    local_readiness = progress.get("local_readiness")
    if not isinstance(local_readiness, dict):
        return None
    setup_sequence = local_readiness.get("setup_sequence")
    if not isinstance(setup_sequence, list):
        return None
    for command in setup_sequence:
        if isinstance(command, str) and pattern in command:
            return command
    return None


def first_local_readiness_verify(progress: dict[str, Any], pattern: str) -> str | None:
    local_readiness = progress.get("local_readiness")
    if not isinstance(local_readiness, dict):
        return None
    verify_sequence = local_readiness.get("verify_sequence")
    if not isinstance(verify_sequence, list):
        return None
    for command in verify_sequence:
        if isinstance(command, str) and pattern in command:
            return command
    return None


def connected_runner_guidance_payload(progress: dict[str, Any]) -> dict[str, Any]:
    owner_lanes = progress.get("owner_lanes")
    lane = owner_lanes.get("connected runner") if isinstance(owner_lanes, dict) else None
    if not isinstance(lane, dict):
        return {}

    guidance: dict[str, Any] = {}
    handoff_bundle = progress.get("connected_runner_handoff_bundle")
    if isinstance(handoff_bundle, str) and handoff_bundle:
        guidance["handoff_bundle"] = handoff_bundle
    for field in ("status", "mode", "next_item_id", "remaining_ids"):
        value = lane.get(field)
        if value:
            guidance[field] = value
    repo_url = lane.get("repo_url") or progress.get("repo_url")
    if isinstance(repo_url, dict) and repo_url.get("required") is True:
        guidance["repo_url"] = repo_url
    commands = lane.get("commands")
    if isinstance(commands, dict):
        command_fields = {
            "next": "next_command",
            "automation": "automation_command",
            "full_flow": "full_flow_command",
        }
        for source, target in command_fields.items():
            command = commands.get(source)
            if isinstance(command, str) and command:
                guidance[target] = command
        supporting = commands.get("supporting")
        if isinstance(supporting, dict):
            selected_supporting = {
                label: command
                for label, command in supporting.items()
                if label
                in {
                    "Show connected-runner command only from env",
                    "Show local readiness setup sequence",
                    "Show local readiness command sequence",
                    "Gate external readiness summary JSON",
                }
                and isinstance(command, str)
                and command
            }
            if selected_supporting:
                guidance["supporting_commands"] = selected_supporting
    readiness = lane.get("readiness")
    if isinstance(readiness, dict):
        readiness_guidance = {
            key: readiness.get(key)
            for key in (
                "status",
                "next_setup",
                "command_only_gate",
                "setup_sequence_command",
                "command_sequence_command",
                "json_gate",
                "external_strict_summary_json",
            )
            if readiness.get(key)
        }
        if readiness_guidance:
            guidance["readiness"] = readiness_guidance
    return guidance


def review_artifacts_from_item_or_progress(
    item: dict[str, Any] | None,
    progress: dict[str, Any],
) -> dict[str, str]:
    review_artifacts = item.get("review_artifacts") if isinstance(item, dict) else None
    if not review_artifacts:
        warning_review = progress.get("warning_review")
        review_artifacts = (
            warning_review.get("review_artifacts")
            if isinstance(warning_review, dict)
            else None
        )
    if not isinstance(review_artifacts, dict):
        return {}
    return {
        str(label): path
        for label, path in sorted(review_artifacts.items())
        if isinstance(path, str) and path
    }


def review_artifact_lines(review_artifacts: dict[str, str]) -> list[str]:
    if not review_artifacts:
        return []
    lines = ["   review_artifacts:"]
    for label, path in review_artifacts.items():
        lines.append(f"   - {label}: {path}")
    return lines


def backend_requirement_guidance_payload() -> dict[str, str]:
    return shared_warning_backend_guidance_payload()


def backend_requirement_guidance_lines(guidance: dict[str, str]) -> list[str]:
    lines: list[str] = []
    for key, label in (
        ("backend", "backend"),
        ("local_start_command", "local_start_command"),
        ("local_start_no_reload_command", "local_start_no_reload_command"),
        ("docker_start_command", "docker_start_command"),
        ("health_check_command", "health_check_command"),
    ):
        value = guidance.get(key)
        if value:
            lines.append(f"   {label}: {value}")
    return lines


def completion_requirement_guidance_payload(
    requirement: str,
    progress: dict[str, Any],
) -> dict[str, Any]:
    plan = progress.get("completion_plan") or []
    item = first_plan_item_for_requirement(requirement, plan if isinstance(plan, list) else [])
    guidance: dict[str, Any] = {}

    if requirement == "connected_runner":
        return connected_runner_guidance_payload(progress)

    if requirement == "real_git_remote_url":
        owner_lanes = progress.get("owner_lanes")
        connected_lane = (
            owner_lanes.get("connected runner")
            if isinstance(owner_lanes, dict)
            else None
        )
        repo_url = (
            connected_lane.get("repo_url")
            if isinstance(connected_lane, dict)
            else None
        )
        if not repo_url:
            repo_url = progress.get("repo_url")
        if isinstance(repo_url, dict) and repo_url.get("required") is True:
            guidance["repo_url"] = repo_url
        return guidance

    if requirement == "docker_cli":
        setup_command = first_local_readiness_setup(progress, "docker")
        verify_command = first_local_readiness_verify(progress, "docker")
        if not setup_command and item:
            command = item.get("command")
            if isinstance(command, str) and command:
                setup_command = command
        if not verify_command and item:
            command = item.get("verify_command")
            if isinstance(command, str) and command:
                verify_command = command
        if setup_command:
            guidance["setup_command"] = setup_command
        if verify_command:
            guidance["verify_command"] = verify_command
    elif requirement == "github_cli_auth":
        setup_command = first_local_readiness_setup(progress, "gh auth")
        verify_command = first_local_readiness_verify(progress, "gh auth")
        if not setup_command and item:
            command = item.get("command")
            if isinstance(command, str) and command:
                setup_command = command
        if not verify_command and item:
            command = item.get("verify_command")
            if isinstance(command, str) and command:
                verify_command = command
        if setup_command:
            guidance["setup_command"] = setup_command
        if verify_command:
            guidance["verify_command"] = verify_command
    elif requirement == "operator_review" and item:
        command = item.get("command")
        if isinstance(command, str) and command:
            guidance["review_command"] = command
        review_sequence = item.get("review_sequence")
        if isinstance(review_sequence, list) and review_sequence:
            guidance["review_sequence"] = [
                command
                for command in review_sequence
                if isinstance(command, str) and command
            ]
        review_artifacts = review_artifacts_from_item_or_progress(item, progress)
        if review_artifacts:
            guidance["review_artifacts"] = review_artifacts
    elif requirement == "operator_checklist_review":
        warning_review = progress.get("warning_review")
        command = (
            warning_review.get("pre_approval_sequence_command")
            if isinstance(warning_review, dict)
            else None
        )
        if isinstance(command, str) and command:
            guidance["review_command"] = command
        sequence = (
            warning_review.get("pre_approval_review_sequence")
            if isinstance(warning_review, dict)
            else None
        )
        if isinstance(sequence, list) and sequence:
            guidance["pre_approval_review_sequence"] = [
                command
                for command in sequence
                if isinstance(command, str) and command
            ]
        review_artifacts = review_artifacts_from_item_or_progress(item, progress)
        if review_artifacts:
            guidance["review_artifacts"] = review_artifacts
    elif requirement == "operator_approval" and item:
        if item.get("requires_operator_approval") is True:
            guidance["requires_operator_approval"] = True
            guidance["approval"] = "operator approval required after checklist review"
        command = item.get("command")
        if isinstance(command, str) and command:
            guidance["apply_command"] = command
        review_artifacts = review_artifacts_from_item_or_progress(item, progress)
        if review_artifacts:
            guidance["review_artifacts"] = review_artifacts
    elif requirement == "running_backend":
        guidance.update(backend_requirement_guidance_payload())

    return guidance


def completion_requirements_json_payload(report: dict[str, Any]) -> list[dict[str, Any]]:
    progress = report.get("progress_summary") or progress_summary_payload(report)
    requirements = progress.get("completion_requirements") or []
    payload: list[dict[str, Any]] = []
    if not isinstance(requirements, list):
        return payload
    for item in requirements:
        if not isinstance(item, dict):
            continue
        entry = dict(item)
        requirement = entry.get("requirement")
        if isinstance(requirement, str):
            guidance = completion_requirement_guidance_payload(requirement, progress)
            if guidance:
                entry["guidance"] = guidance
        payload.append(entry)
    return payload


def completion_requirement_hint_lines(requirement: str, progress: dict[str, Any]) -> list[str]:
    plan = progress.get("completion_plan") or []
    item = first_plan_item_for_requirement(requirement, plan if isinstance(plan, list) else [])
    lines: list[str] = []

    if requirement == "connected_runner":
        guidance = connected_runner_guidance_payload(progress)
        handoff_bundle = guidance.get("handoff_bundle")
        if isinstance(handoff_bundle, str):
            lines.append(f"   handoff_bundle: {handoff_bundle}")
        next_item_id = guidance.get("next_item_id")
        if isinstance(next_item_id, str):
            lines.append(f"   next_item: {next_item_id}")
        repo_url = guidance.get("repo_url")
        lines.extend(repo_url_guidance_lines(repo_url))
        for field, label in (
            ("next_command", "command"),
            ("automation_command", "automation"),
            ("full_flow_command", "full_flow"),
        ):
            command = guidance.get(field)
            if isinstance(command, str) and command:
                lines.append(f"   {label}: {command}")
        readiness = guidance.get("readiness")
        if isinstance(readiness, dict):
            for field, label in (
                ("command_only_gate", "readiness_gate"),
                ("setup_sequence_command", "readiness_setup_sequence"),
                ("command_sequence_command", "readiness_command_sequence"),
            ):
                command = readiness.get(field)
                if isinstance(command, str) and command:
                    lines.append(f"   {label}: {command}")
        return lines

    if requirement == "real_git_remote_url":
        owner_lanes = progress.get("owner_lanes")
        connected_lane = (
            owner_lanes.get("connected runner")
            if isinstance(owner_lanes, dict)
            else None
        )
        repo_url = (
            connected_lane.get("repo_url")
            if isinstance(connected_lane, dict)
            else None
        )
        if not repo_url:
            repo_url = progress.get("repo_url")
        return repo_url_guidance_lines(repo_url)

    if requirement == "docker_cli":
        setup_command = first_local_readiness_setup(progress, "docker")
        if not setup_command and item:
            command = item.get("command")
            if isinstance(command, str) and command:
                setup_command = command
        if setup_command:
            lines.append(f"   setup_command: {setup_command}")
    elif requirement == "github_cli_auth":
        setup_command = first_local_readiness_setup(progress, "gh auth")
        if not setup_command and item:
            command = item.get("command")
            if isinstance(command, str) and command:
                setup_command = command
        if setup_command:
            lines.append(f"   setup_command: {setup_command}")
    elif requirement == "operator_review" and item:
        command = item.get("command")
        if isinstance(command, str) and command:
            lines.append(f"   review_command: {command}")
        lines.extend(review_artifact_lines(review_artifacts_from_item_or_progress(item, progress)))
    elif requirement == "operator_checklist_review":
        warning_review = progress.get("warning_review")
        command = (
            warning_review.get("pre_approval_sequence_command")
            if isinstance(warning_review, dict)
            else None
        )
        if isinstance(command, str) and command:
            lines.append(f"   review_command: {command}")
        lines.extend(review_artifact_lines(review_artifacts_from_item_or_progress(item, progress)))
    elif requirement == "operator_approval" and item and item.get("requires_operator_approval") is True:
        lines.append("   approval: operator approval required after checklist review")
        lines.extend(review_artifact_lines(review_artifacts_from_item_or_progress(item, progress)))
    elif requirement == "running_backend":
        lines.extend(backend_requirement_guidance_lines(backend_requirement_guidance_payload()))

    if item and requirement != "connected_runner":
        verify_command = item.get("verify_command")
        if isinstance(verify_command, str) and verify_command:
            lines.append(f"   verify_command: {verify_command}")
    return lines


def completion_requirements_lines(report: dict[str, Any]) -> list[str]:
    progress = report.get("progress_summary") or progress_summary_payload(report)
    requirements = progress.get("completion_requirements") or []
    lines = [
        f"Completion requirements: {progress.get('percent', 'unknown')}%",
        f"Status: {progress.get('status', 'unknown')}",
        f"Requirements: {len(requirements)}",
    ]
    if not requirements:
        lines.append("No remaining completion requirements.")
        return lines
    lines.append(
        "Note: repeated item sets mean one remaining action is gated by multiple prerequisites."
    )
    for index, item in enumerate(requirements, start=1):
        if not isinstance(item, dict):
            continue
        requirement = item.get("requirement", "unknown")
        count = item.get("count", 0)
        owners = item.get("owners") if isinstance(item.get("owners"), list) else []
        owner_text = ", ".join(str(owner) for owner in owners if isinstance(owner, str) and owner)
        heading = f"{index}. {requirement} ({count} item"
        if count != 1:
            heading += "s"
        heading += ")"
        if owner_text:
            heading += f" [{owner_text}]"
        lines.append(heading)
        item_ids = item.get("item_ids")
        if isinstance(item_ids, list) and item_ids:
            ids = [str(item_id) for item_id in item_ids if isinstance(item_id, str) and item_id]
            if ids:
                lines.append("   items: " + ", ".join(ids))
        if isinstance(requirement, str):
            lines.extend(completion_requirement_hint_lines(requirement, progress))
    return lines


def owner_lanes_lines(report: dict[str, Any]) -> list[str]:
    progress = report.get("progress_summary") or progress_summary_payload(report)
    lanes = progress.get("owner_lanes") or {}
    lines = [
        f"Owner lanes: {progress.get('percent', 'unknown')}%",
        f"Status: {progress.get('status', 'unknown')}",
        f"Lanes: {len(lanes) if isinstance(lanes, dict) else 0}",
    ]
    if not isinstance(lanes, dict) or not lanes:
        lines.append("No remaining owner lanes.")
        return lines
    for index, (owner, lane) in enumerate(lanes.items(), start=1):
        if not isinstance(lane, dict):
            continue
        remaining_items = lane.get("remaining_items", 0)
        item_word = "item" if remaining_items == 1 else "items"
        lines.append(f"{index}. {owner} ({remaining_items} {item_word})")
        remaining_ids = lane.get("remaining_ids")
        if isinstance(remaining_ids, list) and remaining_ids:
            ids = [str(item_id) for item_id in remaining_ids if isinstance(item_id, str) and item_id]
            if ids:
                lines.append("   items: " + ", ".join(ids))
        next_item_id = lane.get("next_item_id")
        if isinstance(next_item_id, str) and next_item_id:
            lines.append(f"   next: {next_item_id}")
        lane_next_command: str | None = None
        if lane.get("next_requires_operator_approval") is True:
            lines.append("   approval: next command requires operator approval after checklist review")
        elif lane.get("requires_operator_approval") is True:
            lines.append("   approval: later operator approval required after checklist review")
        repo_url = lane.get("repo_url")
        lines.extend(repo_url_guidance_lines(repo_url))
        commands = lane.get("commands")
        if isinstance(commands, dict):
            next_command = commands.get("next")
            if isinstance(next_command, str) and next_command:
                lane_next_command = next_command
                lines.append(f"   command: {next_command}")
            automation_command = commands.get("automation")
            if isinstance(automation_command, str) and automation_command:
                lines.append(f"   automation: {automation_command}")
            full_flow_command = commands.get("full_flow")
            if isinstance(full_flow_command, str) and full_flow_command:
                lines.append(f"   full_flow: {full_flow_command}")
        mode = lane.get("mode")
        if isinstance(mode, str) and mode:
            lines.append(f"   mode: {mode}")
        requirements = lane.get("requirements")
        if isinstance(requirements, list) and requirements:
            values = [str(value) for value in requirements if isinstance(value, str) and value]
            if values:
                lines.append("   requires: " + ", ".join(values))
        readiness = lane.get("readiness")
        if isinstance(readiness, dict) and readiness:
            status = readiness.get("status")
            if isinstance(status, str) and status:
                lines.append(f"   readiness: {status}")
            issue_ids = readiness.get("issue_ids")
            if isinstance(issue_ids, list) and issue_ids:
                values = [str(issue_id) for issue_id in issue_ids if isinstance(issue_id, str) and issue_id]
                if values:
                    lines.append("   readiness_issues: " + ", ".join(values))
            next_setup_command = readiness.get("next_setup_command")
            if isinstance(next_setup_command, str) and next_setup_command:
                lines.append(f"   readiness_next_setup: {next_setup_command}")
        review = lane.get("review")
        if isinstance(review, dict) and review:
            status = review.get("status")
            if isinstance(status, str) and status:
                lines.append(f"   review: {status}")
            issue_ids = review.get("issue_ids")
            if isinstance(issue_ids, list) and issue_ids:
                values = [str(issue_id) for issue_id in issue_ids if isinstance(issue_id, str) and issue_id]
                if values:
                    lines.append("   review_issues: " + ", ".join(values))
            next_review_command = review.get("next_command")
            if isinstance(next_review_command, str) and next_review_command:
                if lane_next_command and next_review_command == lane_next_command:
                    lines.append("   review_next: same as command above.")
                else:
                    lines.append(f"   review_next: {next_review_command}")
            backend_guidance = review.get("backend")
            if isinstance(backend_guidance, dict):
                backend_lines = backend_requirement_guidance_lines(
                    {
                        str(key): value
                        for key, value in backend_guidance.items()
                        if isinstance(value, str) and value
                    }
                )
                lines.extend(backend_lines)
        artifact_source = review.get("review_artifacts") if isinstance(review, dict) else None
        if not artifact_source:
            artifact_source = lane.get("review_artifacts")
        if isinstance(artifact_source, dict) and artifact_source:
            artifact_lines = [
                (str(label), path)
                for label, path in sorted(artifact_source.items())
                if isinstance(path, str) and path
            ]
            if artifact_lines:
                lines.append("   review_artifacts:")
                for label, path in artifact_lines:
                    lines.append(f"   - {label}: {path}")
        supporting_labels = lane.get("supporting_command_labels")
        if isinstance(supporting_labels, list) and supporting_labels:
            labels = [str(label) for label in supporting_labels if isinstance(label, str) and label]
            if labels:
                lines.append("   supporting: " + ", ".join(labels))
    return lines


def commands_by_label(report: dict[str, Any]) -> dict[str, str]:
    commands: dict[str, str] = {}
    for item in report.get("handoff_commands") or []:
        if not isinstance(item, dict):
            continue
        label = item.get("label")
        command = item.get("command")
        if isinstance(label, str) and isinstance(command, str):
            commands[label] = command
    return commands


def selected_remaining_command(item: dict[str, Any]) -> str | None:
    for key in ("preferred_command", "command", "automation_command"):
        command = item.get(key)
        if isinstance(command, str) and command:
            return command
    return None


def completion_plan_mode(item: dict[str, Any], command: str | None) -> str:
    item_id = str(item.get("id") or "unknown")
    owner = str(item.get("owner") or "unassigned")
    if item_id == "warning_actions":
        return "operator_approval"
    if item_id == "warning_alerts":
        return "operator_review"
    if item_id == "live_beta_archive":
        return "live_beta_closeout"
    if isinstance(command, str) and "PREFLIGHT_ONLY=true" in command:
        return "connected_runner_preflight"
    if owner == "connected runner":
        return "connected_runner_setup"
    return "manual"


def completion_plan_requirements(item: dict[str, Any], command: str | None) -> list[str]:
    item_id = str(item.get("id") or "unknown")
    owner = str(item.get("owner") or "unassigned")
    requirements: list[str] = []

    def add(value: str) -> None:
        if value not in requirements:
            requirements.append(value)

    if owner == "connected runner":
        add("connected_runner")
    command_values = [
        value
        for value in (
            command,
            item.get("automation_command"),
            item.get("full_flow_command"),
            item.get("verify_command"),
            item.get("final_verify_command"),
        )
        if isinstance(value, str)
    ]
    if any(REPO_URL_PLACEHOLDER in value or "GIT_ORIGIN_URL" in value for value in command_values):
        add("real_git_remote_url")
    if isinstance(command, str) and "PREFLIGHT_ONLY=true" in command:
        add("docker_cli")
        add("github_cli_auth")
    if item_id == "docker_cli" or any("docker" in value for value in command_values):
        add("docker_cli")
    if item_id == "github_cli" or any("gh auth" in value or "--check-gh-auth" in value for value in command_values):
        add("github_cli_auth")
    if item_id == "warning_alerts":
        add("operator_review")
    if item_id == "warning_actions":
        add("operator_checklist_review")
        add("operator_approval")
        add("running_backend")
    if item_id == "live_beta_archive":
        add("live_beta_window_complete")
        add("running_backend")
        add("backup_reference")
    return requirements


COMPLETION_IMPACT_FIELDS: tuple[str, ...] = (
    "completion_deduction_id",
    "completion_deduction_points",
    "completion_impact_points",
    "completion_impact",
    "completion_source_checks",
)


def repo_url_progress_guidance(
    *,
    next_command: str | None,
    next_commands_by_owner: dict[str, dict[str, Any]],
    commands: dict[str, str],
) -> dict[str, Any]:
    command_values: list[str] = []
    if next_command:
        command_values.append(next_command)
    command_values.extend(commands.values())
    for owner_entry in next_commands_by_owner.values():
        for key in ("command", "automation_command", "full_flow_command"):
            value = owner_entry.get(key)
            if isinstance(value, str):
                command_values.append(value)
        supporting_commands = owner_entry.get("supporting_commands")
        if isinstance(supporting_commands, dict):
            command_values.extend(str(value) for value in supporting_commands.values() if isinstance(value, str))

    required = any(REPO_URL_PLACEHOLDER in command for command in command_values)
    if not required:
        return {"required": False}

    return {
        "required": True,
        "placeholder": REPO_URL_PLACEHOLDER,
        "export_command": commands.get("export_repo_url_example") or repo_url_export_example_command(),
        "command_gate": commands.get("next_command_only"),
        "json_gate": commands.get("next_json_only"),
        "message": (
            f"Replace {REPO_URL_PLACEHOLDER} with a real git remote URL before running "
            "connected-runner commands."
        ),
    }


def local_readiness_progress_guidance(
    remaining_items: list[dict[str, Any]],
    commands: dict[str, str],
) -> dict[str, Any]:
    runner_items = [
        item
        for item in remaining_items
        if item.get("owner") == "connected runner" and item.get("status") in {"warn", "fail"}
    ]
    status = "pass"
    if any(item.get("status") == "fail" for item in runner_items):
        status = "fail"
    elif runner_items:
        status = "warn"

    setup_entries: list[dict[str, str]] = []
    setup_sequence: list[str] = []
    verify_sequence: list[str] = []
    command_sequence: list[str] = []
    for item in runner_items:
        setup_command = item.get("command")
        verify_command = item.get("verify_command")
        entry: dict[str, str] = {
            "id": str(item.get("id") or "external_readiness"),
            "status": str(item.get("status") or "unknown"),
        }
        if isinstance(setup_command, str) and setup_command:
            entry["setup_command"] = setup_command
            setup_sequence.append(setup_command)
            command_sequence.append(setup_command)
        if isinstance(verify_command, str) and verify_command:
            entry["verify_command"] = verify_command
            verify_sequence.append(verify_command)
            command_sequence.append(verify_command)
        if "setup_command" in entry or "verify_command" in entry:
            setup_entries.append(entry)

    next_setup = setup_entries[0] if setup_entries else None
    return {
        "status": status,
        "issue_ids": [str(item.get("id") or "external_readiness") for item in runner_items],
        "next_setup": next_setup,
        "next_setup_command": next_setup.get("setup_command") if next_setup else None,
        "setup_sequence": setup_sequence,
        "verify_sequence": verify_sequence,
        "command_sequence": command_sequence,
        "json_command": commands.get("local_readiness_json"),
        "command_only_gate": commands.get("local_readiness_command_only"),
        "setup_sequence_command": commands.get("local_readiness_setup_sequence"),
        "command_sequence_command": commands.get("local_readiness_command_sequence"),
        "setup_sequence_preview_command": commands.get("local_readiness_setup_sequence_preview"),
        "command_sequence_preview_command": commands.get("local_readiness_command_sequence_preview"),
        "json_gate": commands.get("local_readiness_gate_json"),
        "external_summary_json": commands.get("external_readiness_summary_json"),
        "external_strict_summary_json": commands.get("external_readiness_strict_summary_json"),
    }


def warning_review_progress_guidance(
    remaining_items: list[dict[str, Any]],
    commands: dict[str, str],
) -> dict[str, Any]:
    operator_items = [
        item
        for item in remaining_items
        if item.get("owner") == "operator" and item.get("id") in {"warning_alerts", "warning_actions"}
    ]
    status = "pass"
    if any(item.get("status") == "fail" for item in operator_items):
        status = "fail"
    elif any(item.get("id") == "warning_actions" for item in operator_items):
        status = "planned"
    elif operator_items:
        status = "warn"

    review_artifacts: dict[str, str] = {}
    for item in operator_items:
        artifacts = item.get("review_artifacts")
        if isinstance(artifacts, dict):
            review_artifacts.update(
                {
                    str(label): path
                    for label, path in artifacts.items()
                    if isinstance(path, str) and path
                }
            )

    supporting_commands: dict[str, str] = {}
    for item in operator_items:
        item_supporting_commands = item.get("supporting_commands")
        if isinstance(item_supporting_commands, dict):
            supporting_commands.update(
                {
                    str(label): command
                    for label, command in item_supporting_commands.items()
                    if isinstance(command, str) and command
                }
            )

    def command_value(command_key: str, supporting_label: str) -> str | None:
        return commands.get(command_key) or supporting_commands.get(supporting_label)

    summary_json = command_value("warning_summary_json", "Show warning summary JSON")
    gate_summary_json = command_value("warning_gate_summary_json", "Gate warning summary JSON")
    pre_approval_sequence_command = command_value(
        "warning_pre_approval_sequence",
        "Show warning pre-approval sequence",
    )
    gate_json = commands.get("warning_gate_json") or next(
        (
            item.get("automation_command")
            for item in operator_items
            if isinstance(item.get("automation_command"), str)
        ),
        None,
    )
    next_command_gate = command_value("warning_next_command_gate", "Gate warning recommended next command")
    review_artifacts_command = command_value("warning_review_artifacts", "Show warning review artifact paths")
    apply_command = commands.get("warning_apply") or next(
        (
            item.get("command")
            for item in operator_items
            if item.get("id") == "warning_actions" and isinstance(item.get("command"), str)
        ),
        None,
    )
    pre_approval_review_sequence = [
        command
        for command in (
            summary_json,
            review_artifacts_command,
        )
        if operator_items and isinstance(command, str) and command
    ]
    review_sequence = list(pre_approval_review_sequence)
    has_warning_actions = any(item.get("id") == "warning_actions" for item in operator_items)
    if has_warning_actions:
        if isinstance(apply_command, str) and apply_command:
            review_sequence.append(apply_command)
    return {
        "status": status,
        "action_needed": bool(operator_items),
        "issue_ids": [str(item.get("id") or "warning_review") for item in operator_items],
        "next_command": selected_remaining_command(operator_items[0]) if operator_items else None,
        "requires_operator_approval": any(item.get("id") == "warning_actions" for item in operator_items),
        "summary_json": summary_json,
        "gate_summary_json": gate_summary_json,
        "pre_approval_sequence_command": pre_approval_sequence_command,
        "gate_json": gate_json,
        "next_command_gate": next_command_gate,
        "review_artifacts_command": review_artifacts_command,
        "apply_command": apply_command,
        "review_artifacts": dict(sorted(review_artifacts.items())),
        "review_sequence_command": commands.get("operator_review_sequence"),
        "pre_approval_review_sequence": pre_approval_review_sequence,
        "review_sequence": review_sequence,
        "backend": backend_requirement_guidance_payload() if has_warning_actions else {},
    }


def first_remaining_by_owner(
    remaining_items: list[dict[str, Any]],
    completion_impacts: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for item in remaining_items:
        owner = str(item.get("owner") or "unassigned")
        if owner in selected:
            continue
        command = selected_remaining_command(item)
        if not command:
            continue
        entry: dict[str, Any] = {
            "id": str(item.get("id") or "unknown"),
            "status": str(item.get("status") or "unknown"),
            "command": command,
        }
        impact = None
        if completion_impacts:
            impact = completion_impacts.get(str(item.get("id") or ""))
        for key in COMPLETION_IMPACT_FIELDS:
            value = item.get(key)
            if value is None and isinstance(impact, dict):
                value = impact.get(key)
            if value is not None:
                entry[key] = value
        for key in ("automation_command", "full_flow_command"):
            value = item.get(key)
            if isinstance(value, str) and value:
                entry[key] = value
        supporting_commands = item.get("supporting_commands")
        if isinstance(supporting_commands, dict):
            command_map = {
                str(label): command
                for label, command in sorted(supporting_commands.items())
                if isinstance(command, str) and command
            }
            if command_map:
                entry["supporting_commands"] = command_map
        review_artifacts = item.get("review_artifacts")
        if isinstance(review_artifacts, dict):
            artifact_map = {
                str(label): path
                for label, path in sorted(review_artifacts.items())
                if isinstance(path, str) and path
            }
            if artifact_map:
                entry["review_artifacts"] = artifact_map
        selected[owner] = entry
    return dict(sorted(selected.items()))


def completion_plan_entries(
    remaining_items: list[dict[str, Any]],
    completion_impacts: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for item in remaining_items:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id") or "unknown")
        entry: dict[str, Any] = {
            "id": item_id,
            "owner": str(item.get("owner") or "unassigned"),
            "status": str(item.get("status") or "unknown"),
        }
        command = selected_remaining_command(item)
        if command:
            entry["command"] = command
        mode = completion_plan_mode(item, command)
        requirements = completion_plan_requirements(item, command)
        entry["mode"] = mode
        if requirements:
            entry["requirements"] = requirements
        if item_id == "warning_actions" and "running_backend" in requirements:
            entry["backend"] = backend_requirement_guidance_payload()
        for key in ("automation_command", "verify_command", "final_verify_command", "full_flow_command"):
            value = item.get(key)
            if isinstance(value, str) and value:
                entry[key] = value
        impact = completion_impacts.get(item_id) if completion_impacts else None
        for key in COMPLETION_IMPACT_FIELDS:
            value = item.get(key)
            if value is None and isinstance(impact, dict):
                value = impact.get(key)
            if value is not None:
                entry[key] = value
        review_artifacts = item.get("review_artifacts")
        if isinstance(review_artifacts, dict):
            artifact_map = {
                str(label): path
                for label, path in sorted(review_artifacts.items())
                if isinstance(path, str) and path
            }
            if artifact_map:
                entry["review_artifacts"] = artifact_map
        if entry["owner"] == "operator" and item_id in {"warning_alerts", "warning_actions"}:
            entry["requires_operator_approval"] = item_id == "warning_actions"
            supporting_commands = item.get("supporting_commands")
            pre_approval_review_sequence: list[str] = []
            if isinstance(supporting_commands, dict):
                for label in ("Show warning summary JSON", "Show warning review artifact paths"):
                    command_value = supporting_commands.get(label)
                    if isinstance(command_value, str) and command_value:
                        pre_approval_review_sequence.append(command_value)
            review_sequence = list(pre_approval_review_sequence)
            if item_id == "warning_actions" and command:
                review_sequence.append(command)
            if pre_approval_review_sequence:
                entry["pre_approval_review_sequence"] = pre_approval_review_sequence
            if review_sequence:
                entry["review_sequence"] = review_sequence
        entries.append(entry)
    return entries


def completion_requirements_summary(completion_plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    requirement_entries: dict[str, dict[str, Any]] = {}
    requirement_order: list[str] = []
    for item in completion_plan:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id") or "unknown")
        owner = str(item.get("owner") or "unassigned")
        requirements = item.get("requirements")
        if not isinstance(requirements, list):
            continue
        for requirement in requirements:
            if not isinstance(requirement, str) or not requirement:
                continue
            if requirement not in requirement_entries:
                requirement_entries[requirement] = {
                    "requirement": requirement,
                    "item_ids": [],
                    "owners": [],
                }
                requirement_order.append(requirement)
            entry = requirement_entries[requirement]
            if item_id not in entry["item_ids"]:
                entry["item_ids"].append(item_id)
            if owner not in entry["owners"]:
                entry["owners"].append(owner)
    return [
        {
            **requirement_entries[requirement],
            "count": len(requirement_entries[requirement]["item_ids"]),
        }
        for requirement in requirement_order
    ]


def owner_lanes_summary(
    *,
    remaining_by_owner: dict[str, int],
    next_commands_by_owner: dict[str, dict[str, Any]],
    completion_plan: list[dict[str, Any]],
    local_readiness: dict[str, Any] | None = None,
    warning_review: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    return shared_owner_lanes_summary(
        remaining_by_owner=remaining_by_owner,
        next_commands_by_owner=next_commands_by_owner,
        completion_plan=completion_plan,
        local_readiness=local_readiness,
        warning_review=warning_review,
    )


def progress_summary_payload(report: dict[str, Any]) -> dict[str, Any]:
    readiness = report.get("readiness_estimate") or {}
    remaining_items = report.get("remaining_items") or []
    owner_counts: dict[str, int] = {}
    remaining_ids: list[str] = []
    for item in remaining_items:
        remaining_ids.append(str(item.get("id") or "unknown"))
        owner = str(item.get("owner") or "unassigned")
        owner_counts[owner] = owner_counts.get(owner, 0) + 1

    handoff_commands = commands_by_label(report)
    next_item = remaining_items[0] if remaining_items else {}
    next_command = selected_remaining_command(next_item) if isinstance(next_item, dict) else None
    completion_impacts = completion_impacts_by_check_id(readiness.get("deductions") or [])
    selected_command_labels = {
        "show_progress": "Show release progress only",
        "show_progress_json": "Show release progress JSON",
        "show_completion_plan": "Show completion plan",
        "show_completion_plan_json": "Show completion plan JSON",
        "show_completion_requirements": "Show completion requirements",
        "show_completion_requirements_json": "Show completion requirements JSON",
        "show_owner_lanes": "Show owner lanes",
        "show_owner_lanes_json": "Show owner lanes JSON",
        "export_repo_url_example": "Export repo URL example",
        "next_command_only": "Show next command only from env",
        "next_json_only": "Show next report JSON from env",
        "remaining_sequence": "Show remaining command sequence from env",
        "connected_runner_command_only": "Show connected-runner command only from env",
        "connected_runner_command_sequence": "Show connected-runner command sequence from env",
        "operator_command_only": "Show operator command only",
        "operator_command_sequence": "Show operator command sequence",
        "operator_review_sequence": "Show operator review sequence",
        "operator_json_only": "Show operator report JSON",
        "local_readiness_json": "Show local connected-runner readiness JSON",
        "local_readiness_command_only": "Gate local connected-runner readiness command only",
        "local_readiness_setup_sequence": "Show local connected-runner readiness setup sequence",
        "local_readiness_command_sequence": "Show local connected-runner readiness command sequence",
        "local_readiness_setup_sequence_preview": "Preview local connected-runner readiness setup sequence",
        "local_readiness_command_sequence_preview": "Preview local connected-runner readiness command sequence",
        "local_readiness_gate_json": "Gate local connected-runner readiness JSON",
        "external_readiness_summary_json": "Show external readiness summary JSON",
        "external_readiness_strict_summary_json": "Gate external readiness summary JSON",
        "connected_runner_acceptance_summary_json": "Run connected-runner acceptance summary JSON",
        "handoff_bundle_verify_summary_json": "Verify connected-runner handoff summary JSON",
        "handoff_context_json": "Show connected-runner handoff context JSON",
        "handoff_command_sequence": "Show connected-runner handoff command sequence",
        "warning_gate_json": "Gate warning action plan JSON",
        "warning_summary_json": "Show warning action summary JSON",
        "warning_gate_summary_json": "Gate warning action summary JSON",
        "warning_pre_approval_sequence": "Show warning pre-approval sequence",
        "warning_next_command_gate": "Gate warning recommended next command",
        "warning_review_artifacts": "Show warning review artifact paths",
        "warning_apply": "Apply reviewed warning actions",
    }
    selected_commands = {
        key: handoff_commands[label]
        for key, label in selected_command_labels.items()
        if label in handoff_commands
    }
    next_commands_by_owner = first_remaining_by_owner(remaining_items, completion_impacts)
    completion_plan = completion_plan_entries(remaining_items, completion_impacts)
    remaining_by_owner = dict(sorted(owner_counts.items()))
    local_readiness = local_readiness_progress_guidance(remaining_items, selected_commands)
    warning_review = warning_review_progress_guidance(remaining_items, selected_commands)

    return {
        "status": report.get("status"),
        "percent": readiness.get("percent"),
        "remaining_items": readiness.get("remaining_items", len(remaining_items)),
        "remaining_ids": remaining_ids,
        "remaining_by_owner": remaining_by_owner,
        "completion_impacts": completion_impacts,
        "completion_plan": completion_plan,
        "completion_requirements": completion_requirements_summary(completion_plan),
        "owner_lanes": owner_lanes_summary(
            remaining_by_owner=remaining_by_owner,
            next_commands_by_owner=next_commands_by_owner,
            completion_plan=completion_plan,
            local_readiness=local_readiness,
            warning_review=warning_review,
        ),
        "next_item_id": next_item.get("id") if isinstance(next_item, dict) else None,
        "next_item_owner": next_item.get("owner") if isinstance(next_item, dict) else None,
        "next_command": next_command,
        "next_commands_by_owner": next_commands_by_owner,
        "deductions": readiness.get("deductions") or [],
        "commands": selected_commands,
        "repo_url": repo_url_progress_guidance(
            next_command=next_command,
            next_commands_by_owner=next_commands_by_owner,
            commands=selected_commands,
        ),
        "local_readiness": local_readiness,
        "warning_review": warning_review,
        "package_dir": report.get("package_dir"),
        "release_gate_path": report.get("release_gate_path"),
        "connected_runner_handoff_bundle": report.get("connected_runner_handoff_bundle"),
    }


def main() -> int:
    args = parse_args()
    read_only_output_modes = [
        args.progress_only,
        args.progress_json_only,
        args.completion_plan_only,
        args.completion_plan_json_only,
        args.completion_requirements_only,
        args.completion_requirements_json_only,
        args.owner_lanes_only,
        args.owner_lanes_json_only,
    ]
    if args.json_only and any(read_only_output_modes):
        raise SystemExit("--json-only cannot be combined with read-only output-only modes")
    if sum(1 for mode in read_only_output_modes if mode) > 1:
        raise SystemExit("Only one read-only output-only mode can be selected")
    if (
        args.no_write
        or args.json_only
        or args.progress_only
        or args.progress_json_only
        or args.completion_plan_only
        or args.completion_plan_json_only
        or args.completion_requirements_only
        or args.completion_requirements_json_only
        or args.owner_lanes_only
        or args.owner_lanes_json_only
    ) and args.output_prefix:
        raise SystemExit("--output-prefix cannot be combined with read-only output modes")
    package_dir = Path(args.package_dir) if args.package_dir else latest_manifest_package_dir(Path(args.packages_dir))
    package_dir = package_dir.absolute()
    release_gate_path = Path(args.release_gate) if args.release_gate else (
        matching_release_gate(Path(args.release_gates_dir), package_dir)
        if args.package_dir
        else latest_release_gate(Path(args.release_gates_dir))
    )
    release_gate_payload = read_json(release_gate_path) if release_gate_path and release_gate_path.exists() else None
    evidence_path, evidence_payload = release_evidence(package_dir)
    external_path, external_payload = external_readiness(package_dir)
    actions_path, actions_payload = warning_actions(package_dir)
    manifest = read_json(package_dir / "manifest.json")
    evidence_checks = evidence_payload.get("checks", []) if evidence_payload else []
    external_checks = external_payload.get("checks", []) if external_payload else []
    warnings = warning_checks(evidence_checks) + warning_checks(external_checks)
    failures = failing_checks(evidence_checks) + failing_checks(external_checks)
    release_gate_status = release_gate_payload.get("status") if release_gate_payload else "not available"
    release_evidence_status = evidence_payload.get("status") if evidence_payload else "not available"
    external_status = external_payload.get("status") if external_payload else "not available"
    action_status = actions_payload.get("status") if actions_payload else "not available"
    connected_runner_handoff_bundle = (
        release_gate_payload.get("connected_runner_handoff_bundle")
        if release_gate_payload
        else None
    )
    connected_runner_handoff_tarball = (
        release_gate_payload.get("connected_runner_handoff_tarball")
        if release_gate_payload
        else None
    )
    connected_runner_handoff_bundle_verification = (
        release_gate_payload.get("connected_runner_handoff_bundle_verification")
        if release_gate_payload
        else None
    )
    connected_runner_handoff_tarball_verification = (
        release_gate_payload.get("connected_runner_handoff_tarball_verification")
        if release_gate_payload
        else None
    )
    connected_runner_preflight = connected_runner_preflight_command(connected_runner_handoff_bundle)
    connected_runner_full = connected_runner_full_command(connected_runner_handoff_bundle)
    remaining_items = build_remaining_items(
        package_dir=package_dir,
        evidence=evidence_payload,
        external=external_payload,
        actions=actions_payload,
    )
    remaining_items = with_connected_runner_preferred_commands(
        remaining_items,
        preflight_command=connected_runner_preflight,
        full_command=connected_runner_full,
        automation_command=next_release_connected_json_only_env_command(package_dir),
        package_dir=package_dir,
        source_dir=(Path(connected_runner_handoff_bundle) / "source") if connected_runner_handoff_bundle else None,
    )
    readiness = readiness_estimate(
        release_gate_status=str(release_gate_status),
        evidence_checks=evidence_checks,
        external_checks=external_checks,
        actions=actions_payload,
        remaining_items=remaining_items,
    )
    remaining_items = with_completion_impacts(remaining_items, readiness.get("deductions", []))
    overall_status = "fail" if failures or release_gate_status == "fail" else (
        "warn" if warnings or release_evidence_status == "warn" or external_status == "warn" else "pass"
    )
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": overall_status,
        "package_dir": str(package_dir),
        "package_name": manifest.get("package_name"),
        "tarball": manifest.get("tarball"),
        "release_gate_path": str(release_gate_path) if release_gate_path else None,
        "release_evidence_path": str(evidence_path) if evidence_path else None,
        "external_readiness_path": str(external_path) if external_path else None,
        "warning_actions_path": str(actions_path) if actions_path else None,
        "connected_runner_handoff_bundle": connected_runner_handoff_bundle,
        "connected_runner_handoff_bundle_verification": connected_runner_handoff_bundle_verification,
        "connected_runner_handoff_tarball": connected_runner_handoff_tarball,
        "connected_runner_handoff_tarball_verification": connected_runner_handoff_tarball_verification,
        "connected_runner_preflight_command": connected_runner_preflight,
        "connected_runner_full_command": connected_runner_full,
        "summary": {
            "release_gate_status": release_gate_status,
            "release_evidence_status": release_evidence_status,
            "external_readiness_status": external_status,
            "evidence_check_counts": status_counts(evidence_checks),
            "external_check_counts": status_counts(external_checks),
            "warning_action_status": action_status,
        },
        "warnings": warnings,
        "failures": failures,
        "readiness_estimate": readiness,
        "remaining_items": remaining_items,
        "next_actions": build_next_actions(
            release_gate=release_gate_payload,
            evidence=evidence_payload,
            external=external_payload,
            actions=actions_payload,
            connected_runner_preflight=connected_runner_preflight,
        ),
        "handoff_commands": build_handoff_commands(
            package_dir,
            release_gate_path,
            connected_runner_handoff_bundle,
        ),
    }
    report["progress_summary"] = progress_summary_payload(report)

    if args.json_only:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1 if report["status"] == "fail" else 0

    if args.progress_only:
        print("\n".join(progress_summary_lines(report)))
        return 1 if report["status"] == "fail" else 0

    if args.progress_json_only:
        print(json.dumps(report["progress_summary"], indent=2, sort_keys=True))
        return 1 if report["status"] == "fail" else 0

    if args.completion_plan_only:
        print("\n".join(completion_plan_lines(report)))
        return 1 if report["status"] == "fail" else 0

    if args.completion_plan_json_only:
        print(json.dumps(report["progress_summary"]["completion_plan"], indent=2, sort_keys=True))
        return 1 if report["status"] == "fail" else 0

    if args.completion_requirements_only:
        print("\n".join(completion_requirements_lines(report)))
        return 1 if report["status"] == "fail" else 0

    if args.completion_requirements_json_only:
        print(json.dumps(completion_requirements_json_payload(report), indent=2, sort_keys=True))
        return 1 if report["status"] == "fail" else 0

    if args.owner_lanes_only:
        print("\n".join(owner_lanes_lines(report)))
        return 1 if report["status"] == "fail" else 0

    if args.owner_lanes_json_only:
        print(json.dumps(report["progress_summary"]["owner_lanes"], indent=2, sort_keys=True))
        return 1 if report["status"] == "fail" else 0

    if args.no_write:
        print(f"Release status: {report['status']}")
        print("Release status report: not written (--no-write)")
        print(f"Evidence package: {package_dir}")
        if release_gate_path:
            print(f"Release gate summary: {release_gate_path}")
        return 1 if report["status"] == "fail" else 0

    if checksum_files_exist(package_dir) and not args.allow_post_checksum_write:
        raise SystemExit(
            "Refusing to rewrite release-status files because evidence checksums already exist. "
            "Use --no-write for read-only inspection, or pass --allow-post-checksum-write and rerun "
            "scripts/write_evidence_checksums.py afterward."
        )

    output_prefix = Path(args.output_prefix) if args.output_prefix else package_dir / "release-status"
    json_path = output_prefix.with_suffix(".json")
    markdown_path = output_prefix.with_suffix(".md")
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(markdown_path, report)
    tarball_path = None if args.no_refresh_tarball else refresh_package_tarball(package_dir)

    print(f"Release status: {report['status']}")
    print(f"Release status report: {markdown_path}")
    if tarball_path:
        print(f"Refreshed tarball: {tarball_path}")
    return 1 if report["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
