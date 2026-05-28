#!/usr/bin/env python3
"""Validate that the completion audit stays aligned with release handoff context."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_MARKERS: tuple[tuple[str, str], ...] = (
    ("completion_percent", "96% complete"),
    ("completion_deductions", "completion-deduction"),
    ("completion_impact", "completion impact"),
    ("handoff_completion_requirements", "Completion requirements:"),
    ("handoff_manifest_quickstart", "manifest.json handoff_context.quickstart"),
    ("handoff_manifest_completion_plan", "manifest.json handoff_context.completion_plan"),
    ("handoff_manifest_completion_requirements", "manifest.json handoff_context.completion_requirements"),
    ("handoff_manifest_remaining_ids", "manifest.json handoff_context.remaining_ids"),
    ("handoff_manifest_next_item", "manifest.json handoff_context.next_item_id"),
    ("handoff_manifest_owner_lanes", "manifest.json handoff_context.owner_lanes"),
    ("handoff_manifest_bundle_commands", "manifest.json handoff_context.bundle_commands"),
    ("handoff_manifest_bundle_sequence", "manifest.json handoff_context.bundle_command_sequence"),
    ("handoff_manifest_gate_summary", "manifest.json handoff_context.bundle_gate_summary"),
    ("handoff_manifest_first_gate_by_owner", "manifest.json handoff_context.bundle_gate_summary.first_gate_by_owner"),
    ("handoff_context_json_command", "package_connected_runner_handoff.py --verify PATH_TO_HANDOFF_BUNDLE --handoff-context-json-only"),
    ("handoff_command_sequence_command", "package_connected_runner_handoff.py --verify PATH_TO_HANDOFF_BUNDLE --handoff-command-sequence-only"),
    ("handoff_manifest_handoff_context_json", "manifest.json handoff_context.bundle_commands.show_handoff_context_json"),
    (
        "handoff_manifest_handoff_command_sequence",
        "manifest.json handoff_context.bundle_commands.show_handoff_command_sequence",
    ),
    (
        "handoff_manifest_completion_context_audit",
        "manifest.json handoff_context.bundle_commands.audit_completion_context_json",
    ),
    (
        "handoff_manifest_completion_plan_json",
        "manifest.json handoff_context.bundle_commands.show_completion_plan_json",
    ),
    (
        "handoff_manifest_completion_requirements_json",
        "manifest.json handoff_context.bundle_commands.show_completion_requirements_json",
    ),
    ("handoff_manifest_progress_json", "manifest.json handoff_context.bundle_commands.show_progress_json"),
    ("handoff_manifest_verify_bundle_summary", "manifest.json handoff_context.bundle_commands.verify_bundle_summary_json"),
    ("handoff_manifest_acceptance_summary", "manifest.json handoff_context.bundle_commands.acceptance_summary_json"),
    ("handoff_manifest_owner_lanes_summary", "manifest.json handoff_context.bundle_commands.show_owner_lanes_json"),
    (
        "handoff_manifest_operator_review_sequence",
        "manifest.json handoff_context.bundle_commands.show_operator_review_sequence",
    ),
    ("handoff_manifest_warning_summary", "manifest.json handoff_context.bundle_commands.show_warning_summary_json"),
    ("handoff_manifest_warning_artifacts", "manifest.json handoff_context.bundle_commands.show_warning_artifacts"),
    ("handoff_manifest_warning_gate", "manifest.json handoff_context.bundle_commands.gate_warning_summary_json"),
    (
        "completion_audit_bundle_command",
        "python3 scripts/check_completion_audit.py --handoff-bundle PATH_TO_HANDOFF_BUNDLE",
    ),
    ("connected_runner_sequence", "--summary-by-owner --show-sequence --no-write"),
    ("handoff_export_first_command", "export GIT_ORIGIN_URL=https://github.com/OWNER/REPO.git"),
    ("progress_json_command", "python3 scripts/report_release_status.py --package-dir PATH_TO_EVIDENCE_PACKAGE --progress-json-only"),
    ("completion_plan_command", "python3 scripts/report_release_status.py --package-dir PATH_TO_EVIDENCE_PACKAGE --completion-plan-only"),
    ("completion_plan_json_command", "python3 scripts/report_release_status.py --package-dir PATH_TO_EVIDENCE_PACKAGE --completion-plan-json-only"),
    ("completion_requirements_command", "python3 scripts/report_release_status.py --package-dir PATH_TO_EVIDENCE_PACKAGE --completion-requirements-only"),
    ("completion_requirements_json_command", "python3 scripts/report_release_status.py --package-dir PATH_TO_EVIDENCE_PACKAGE --completion-requirements-json-only"),
    ("owner_lanes_command", "python3 scripts/report_release_status.py --package-dir PATH_TO_EVIDENCE_PACKAGE --owner-lanes-only"),
    ("owner_lanes_json_command", "python3 scripts/report_release_status.py --package-dir PATH_TO_EVIDENCE_PACKAGE --owner-lanes-json-only"),
    ("latest_package_default", "Omit `--package-dir` to select the latest local evidence package"),
    ("progress_summary_completion_impacts", "progress_summary.completion_impacts"),
    ("progress_summary_completion_plan", "progress_summary.completion_plan"),
    ("progress_summary_completion_requirements", "progress_summary.completion_requirements"),
    ("progress_summary_completion_requirements_command", "progress_summary.commands.show_completion_requirements"),
    ("progress_summary_completion_requirements_json_command", "progress_summary.commands.show_completion_requirements_json"),
    ("progress_summary_owner_lanes", "progress_summary.owner_lanes"),
    ("progress_summary_owner_lanes_commands", "progress_summary.owner_lanes.*.commands"),
    ("progress_summary_owner_lanes_readiness", "progress_summary.owner_lanes.*.readiness"),
    ("progress_summary_owner_lanes_review", "progress_summary.owner_lanes.*.review"),
    ("progress_summary_owner_lanes_command", "progress_summary.commands.show_owner_lanes"),
    ("progress_summary_owner_lanes_json_command", "progress_summary.commands.show_owner_lanes_json"),
    ("progress_summary_completion_plan_mode", "completion_plan mode"),
    ("progress_summary_completion_plan_requirements", "completion_plan requirements"),
    ("progress_summary_completion_plan_pre_approval_sequence", "completion_plan pre_approval_review_sequence"),
    ("embedded_progress_summary", "progress_summary.next_commands_by_owner"),
    ("progress_summary_warning_review", "progress_summary.warning_review"),
    ("progress_summary_warning_review_sequence_command", "progress_summary.warning_review.review_sequence_command"),
    (
        "progress_summary_warning_review_pre_approval_sequence",
        "progress_summary.warning_review.pre_approval_review_sequence",
    ),
    (
        "progress_summary_warning_review_pre_approval_command",
        "progress_summary.warning_review.pre_approval_sequence_command",
    ),
    ("progress_summary_handoff_context_json", "progress_summary.commands.handoff_context_json"),
    ("progress_summary_handoff_command_sequence", "progress_summary.commands.handoff_command_sequence"),
    ("progress_summary_operator_review_sequence", "progress_summary.commands.operator_review_sequence"),
    ("operator_review_skip_apply", "next_release_step.py --skip-operator-approved"),
    (
        "warning_pre_approval_sequence_command",
        "review_release_warnings.py --package-dir PATH_TO_EVIDENCE_PACKAGE --pre-approval-sequence-only",
    ),
    ("progress_summary_handoff_summary", "summary-json-only"),
    ("external_readiness_summary_json", "check_external_readiness.py --summary-json-only"),
    ("warning_summary_json", "review_release_warnings.py --package-dir PATH_TO_EVIDENCE_PACKAGE --summary-json-only"),
    (
        "local_readiness_command_sequence",
        "python3 scripts/next_release_step.py --package-dir PATH_TO_EVIDENCE_PACKAGE --local-readiness-command-sequence-only --fail-if-local-readiness-not-pass",
    ),
    (
        "local_readiness_setup_sequence_preview",
        "progress_summary.commands.local_readiness_setup_sequence_preview",
    ),
    (
        "local_readiness_command_sequence_preview",
        "progress_summary.commands.local_readiness_command_sequence_preview",
    ),
    ("theme_smoke_command", "python3 scripts/check_frontend_theme.py"),
    ("theme_smoke_result", "Frontend theme smoke"),
    ("script_test_count", "Script smoke tests:"),
    ("git_origin_remote", "git_origin_remote"),
    ("docker_cli", "docker_cli"),
    ("github_cli", "github_cli"),
    ("live_beta_archive", "live_beta_archive"),
    ("warning_alerts", "warning_alerts"),
    ("warning_actions", "warning_actions"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check docs/completion-audit.md release context markers.")
    parser.add_argument(
        "--audit-path",
        default="docs/completion-audit.md",
        help="Completion audit markdown path.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print a JSON report instead of human-readable checks.",
    )
    parser.add_argument(
        "--handoff-bundle",
        help="Optional handoff bundle directory or manifest.json path to validate bundle command marker coverage.",
    )
    return parser.parse_args()


def marker_present(text: str, lower_text: str, marker: str) -> bool:
    haystack = lower_text if marker.islower() else text
    needle = marker if marker.islower() else marker
    return needle in haystack


def handoff_bundle_manifest_path(handoff_bundle: Path) -> Path:
    if handoff_bundle.is_dir():
        return handoff_bundle / "manifest.json"
    return handoff_bundle


def handoff_bundle_command_marker_checks(
    text: str,
    lower_text: str,
    handoff_bundle: Path,
) -> tuple[Path, list[dict[str, Any]]]:
    manifest_path = handoff_bundle_manifest_path(handoff_bundle)
    required_markers = {marker for _, marker in REQUIRED_MARKERS}
    checks: list[dict[str, Any]] = []
    if not manifest_path.exists():
        checks.append(
            {
                "id": "handoff_bundle_manifest_exists",
                "status": "fail",
                "message": f"Handoff bundle manifest is missing: {manifest_path}",
            }
        )
        return manifest_path, checks

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        checks.append(
            {
                "id": "handoff_bundle_manifest_json",
                "status": "fail",
                "message": f"Handoff bundle manifest is not valid JSON: {exc}",
            }
        )
        return manifest_path, checks

    handoff_context = manifest.get("handoff_context") if isinstance(manifest, dict) else None
    bundle_commands = handoff_context.get("bundle_commands") if isinstance(handoff_context, dict) else None
    if not isinstance(bundle_commands, dict):
        checks.append(
            {
                "id": "handoff_bundle_commands_present",
                "status": "fail",
                "message": "Handoff bundle manifest is missing handoff_context.bundle_commands.",
            }
        )
        return manifest_path, checks

    checks.append(
        {
            "id": "handoff_bundle_commands_present",
            "status": "pass",
            "message": "Handoff bundle manifest includes handoff_context.bundle_commands.",
        }
    )
    for command_key in sorted(bundle_commands):
        marker = f"manifest.json handoff_context.bundle_commands.{command_key}"
        required = marker in required_markers
        documented = marker_present(text, lower_text, marker)
        checks.append(
            {
                "id": f"handoff_bundle_command_marker_{command_key}",
                "status": "pass" if required and documented else "fail",
                "message": (
                    f"Handoff bundle command marker is required and documented: {marker}"
                    if required and documented
                    else (
                        f"Missing REQUIRED_MARKERS entry for handoff bundle command marker: {marker}"
                        if not required
                        else f"Missing completion audit documentation for handoff bundle command marker: {marker}"
                    )
                ),
            }
        )
    return manifest_path, checks


def check_completion_audit(audit_path: Path, handoff_bundle: Path | None = None) -> dict[str, Any]:
    text = audit_path.read_text(encoding="utf-8")
    lower_text = text.lower()
    checks = []
    for check_id, marker in REQUIRED_MARKERS:
        passed = marker_present(text, lower_text, marker)
        checks.append(
            {
                "id": check_id,
                "status": "pass" if passed else "fail",
                "message": (
                    f"Found completion audit marker: {marker}"
                    if passed
                    else f"Missing completion audit marker: {marker}"
                ),
            }
        )

    report: dict[str, Any] = {"audit_path": str(audit_path), "checks": checks}
    if handoff_bundle is not None:
        manifest_path, bundle_checks = handoff_bundle_command_marker_checks(text, lower_text, handoff_bundle)
        report["handoff_bundle"] = str(handoff_bundle)
        report["handoff_bundle_manifest"] = str(manifest_path)
        checks.extend(bundle_checks)

    status = "pass" if all(check["status"] == "pass" for check in checks) else "fail"
    report["status"] = status
    return report


def main() -> int:
    args = parse_args()
    handoff_bundle = Path(args.handoff_bundle) if args.handoff_bundle else None
    report = check_completion_audit(Path(args.audit_path), handoff_bundle=handoff_bundle)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        for check in report["checks"]:
            print(f"{check['status'].upper():5} {check['id']}: {check['message']}")
        print(f"Completion audit check: {report['status']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
