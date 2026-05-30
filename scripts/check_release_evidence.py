#!/usr/bin/env python3
"""Validate a Quant Lab evidence package before release review."""

from __future__ import annotations

import argparse
import json
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.handoff_commands import (
        DOCKER_BACKEND_START_COMMAND,
        LIVE_BETA_BACKUP_REFERENCE_EXAMPLE,
        LIVE_BETA_CLOSEOUT_COMMAND,
        LIVE_BETA_FINAL_GATE_COMMAND,
        LIVE_BETA_NEXT_COMMAND_ONLY_COMMAND,
        LIVE_BETA_PREFLIGHT_COMMAND,
        LIVE_BETA_PREFLIGHT_JSON_COMMAND,
        LOCAL_BACKEND_START_COMMAND,
        LOCAL_BACKEND_START_NO_RELOAD_COMMAND,
        REPO_URL_PLACEHOLDER,
        backend_health_check_command,
        connected_runner_acceptance_summary_json_command,
        connected_runner_handoff_command_sequence_command,
        connected_runner_handoff_context_json_command,
        connected_runner_verify_summary_json_command,
        completion_impacts_by_check_id,
        external_readiness_strict_summary_json_command,
        external_readiness_summary_json_command,
        next_release_command_only_env_command,
        next_release_command_sequence_env_command,
        next_release_json_only_env_command,
        next_release_connected_command_only_env_command,
        next_release_connected_json_only_env_command,
        next_release_local_readiness_command_only_env_command,
        next_release_local_readiness_command_sequence_env_command,
        next_release_local_readiness_command_sequence_preview_command,
        next_release_local_readiness_gate_json_env_command,
        next_release_local_readiness_json_env_command,
        next_release_local_readiness_setup_sequence_env_command,
        next_release_local_readiness_setup_sequence_preview_command,
        release_status_completion_plan_command,
        release_status_completion_plan_json_command,
        release_status_completion_requirements_command,
        release_status_completion_requirements_json_command,
        release_status_owner_lanes_command,
        release_status_owner_lanes_json_command,
        release_status_progress_command,
        release_status_progress_json_command,
        repo_url_export_example_command,
        owner_lanes_summary as shared_owner_lanes_summary,
        warning_review_apply_command,
        warning_review_artifacts_only_command,
        warning_backend_guidance_payload,
        warning_review_gate_summary_json_command,
        warning_review_next_command_gate_command,
        warning_review_next_command_only_command,
        warning_review_pre_approval_sequence_command,
        warning_review_summary_json_command,
    )
    from scripts.release_artifacts import latest_manifest_package_dir
    from scripts.release_manifest import REQUIRED_EVIDENCE_DOC_SUFFIXES
except ModuleNotFoundError:  # pragma: no cover - supports running from scripts/
    from handoff_commands import (
        DOCKER_BACKEND_START_COMMAND,
        LIVE_BETA_BACKUP_REFERENCE_EXAMPLE,
        LIVE_BETA_CLOSEOUT_COMMAND,
        LIVE_BETA_FINAL_GATE_COMMAND,
        LIVE_BETA_NEXT_COMMAND_ONLY_COMMAND,
        LIVE_BETA_PREFLIGHT_COMMAND,
        LIVE_BETA_PREFLIGHT_JSON_COMMAND,
        LOCAL_BACKEND_START_COMMAND,
        LOCAL_BACKEND_START_NO_RELOAD_COMMAND,
        REPO_URL_PLACEHOLDER,
        backend_health_check_command,
        connected_runner_acceptance_summary_json_command,
        connected_runner_handoff_command_sequence_command,
        connected_runner_handoff_context_json_command,
        connected_runner_verify_summary_json_command,
        completion_impacts_by_check_id,
        external_readiness_strict_summary_json_command,
        external_readiness_summary_json_command,
        next_release_command_only_env_command,
        next_release_command_sequence_env_command,
        next_release_json_only_env_command,
        next_release_connected_command_only_env_command,
        next_release_connected_json_only_env_command,
        next_release_local_readiness_command_only_env_command,
        next_release_local_readiness_command_sequence_env_command,
        next_release_local_readiness_command_sequence_preview_command,
        next_release_local_readiness_gate_json_env_command,
        next_release_local_readiness_json_env_command,
        next_release_local_readiness_setup_sequence_env_command,
        next_release_local_readiness_setup_sequence_preview_command,
        release_status_completion_plan_command,
        release_status_completion_plan_json_command,
        release_status_completion_requirements_command,
        release_status_completion_requirements_json_command,
        release_status_owner_lanes_command,
        release_status_owner_lanes_json_command,
        release_status_progress_command,
        release_status_progress_json_command,
        repo_url_export_example_command,
        owner_lanes_summary as shared_owner_lanes_summary,
        warning_review_apply_command,
        warning_review_artifacts_only_command,
        warning_backend_guidance_payload,
        warning_review_gate_summary_json_command,
        warning_review_next_command_gate_command,
        warning_review_next_command_only_command,
        warning_review_pre_approval_sequence_command,
        warning_review_summary_json_command,
    )
    from release_artifacts import latest_manifest_package_dir
    from release_manifest import REQUIRED_EVIDENCE_DOC_SUFFIXES


REQUIRED_LABELS: tuple[str, ...] = (
    "external_readiness",
    "verification_summary",
    "ops_smoke_check",
    "crypto_live_beta_drill",
    "local_smoke_check",
)

REQUIRED_DOC_SUFFIXES = REQUIRED_EVIDENCE_DOC_SUFFIXES

COMMAND_SAFETY_FILES: tuple[str, ...] = (
    "release-status.md",
    "release-status.json",
    "next-release-step.md",
    "next-release-step.json",
    "release-warning-actions.md",
    "release-warning-actions.json",
    "release-warning-operator-checklist.md",
)

COMPLETION_IMPACT_FIELDS: tuple[str, ...] = (
    "completion_deduction_id",
    "completion_deduction_points",
    "completion_impact_points",
    "completion_impact",
    "completion_source_checks",
)


def selected_remaining_command(item: dict[str, Any]) -> str | None:
    for key in ("preferred_command", "command", "automation_command"):
        command = item.get(key)
        if isinstance(command, str) and command:
            return command
    return None


def expected_warning_backend_guidance() -> dict[str, str]:
    return warning_backend_guidance_payload()


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


def expected_completion_plan(
    remaining_items: list[Any],
    completion_impacts: dict[str, Any],
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
            entry["backend"] = expected_warning_backend_guidance()
        for key in ("automation_command", "verify_command", "final_verify_command", "full_flow_command"):
            value = item.get(key)
            if isinstance(value, str) and value:
                entry[key] = value
        impact = completion_impacts.get(item_id)
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
    next_commands_by_owner: dict[str, Any],
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


BACKUP_REFERENCE_PLACEHOLDERS: tuple[str, ...] = (
    "PATH_TO_BACKUP",
    "BACKUP_REFERENCE",
    "<backup-path>",
    "<backup-reference>",
)

SHELL_UNSAFE_REPO_PLACEHOLDERS: tuple[str, ...] = (
    "GIT_ORIGIN_URL=<repo-url>",
    "git remote add origin <repo-url>",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check a Quant Lab evidence package.")
    parser.add_argument(
        "--package-dir",
        help="Evidence package directory. Defaults to the latest artifacts/evidence-packages/* directory.",
    )
    parser.add_argument(
        "--packages-dir",
        default="artifacts/evidence-packages",
        help="Directory containing evidence package directories",
    )
    parser.add_argument(
        "--require-live-beta",
        action="store_true",
        help="Fail when a live beta archive is missing",
    )
    parser.add_argument(
        "--output",
        help="Path for the JSON check summary. Defaults to release-evidence-check.json in the package.",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help=(
            "Run checks without writing release-evidence-check.json, warning triage files, "
            "or refreshing the package tarball. Use after checksums have been published."
        ),
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Print the evidence check summary as JSON without writing files. Implies --no-write.",
    )
    parser.add_argument(
        "--no-refresh-tarball",
        action="store_true",
        help="Do not refresh the manifest tarball after writing the check summary",
    )
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def add_check(
    checks: list[dict[str, Any]],
    *,
    check_id: str,
    label: str,
    status: str,
    message: str,
    evidence: str | None = None,
) -> None:
    checks.append(
        {
            "id": check_id,
            "label": label,
            "status": status,
            "message": message,
            "evidence": evidence,
        }
    )


def included_by_label(manifest: dict[str, Any], label: str) -> list[dict[str, Any]]:
    return [item for item in manifest.get("included", []) if item.get("label") == label]


def target_paths(manifest: dict[str, Any]) -> list[Path]:
    paths: list[Path] = []
    for item in manifest.get("included", []):
        target = item.get("target")
        if isinstance(target, str):
            paths.append(Path(target))
    return paths


def first_existing_glob(package_dir: Path, pattern: str) -> Path | None:
    matches = sorted(package_dir.glob(pattern))
    return matches[-1] if matches else None


def collect_json_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        strings: list[str] = []
        for item in value:
            strings.extend(collect_json_strings(item))
        return strings
    if isinstance(value, dict):
        strings = []
        for item in value.values():
            strings.extend(collect_json_strings(item))
        return strings
    return []


def command_artifact_fragments(package_dir: Path) -> list[tuple[Path, str]]:
    fragments: list[tuple[Path, str]] = []
    for relative_path in COMMAND_SAFETY_FILES:
        path = package_dir / relative_path
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".json":
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                fragments.extend((path, line.strip()) for line in text.splitlines() if line.strip())
            else:
                fragments.extend((path, value) for value in collect_json_strings(payload))
        else:
            fragments.extend((path, line.strip()) for line in text.splitlines() if line.strip())
    return fragments


def describe_paths(paths: list[Path]) -> str:
    return ", ".join(str(path) for path in sorted(set(paths), key=str))


def check_handoff_command_safety(package_dir: Path) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    fragments = command_artifact_fragments(package_dir)
    existing_files = [package_dir / relative_path for relative_path in COMMAND_SAFETY_FILES if (package_dir / relative_path).is_file()]
    has_command_artifacts = bool(existing_files)

    add_check(
        checks,
        check_id="handoff_command_artifacts",
        label="Handoff command artifacts",
        status="pass" if has_command_artifacts else "skipped",
        message=(
            f"{len(existing_files)} handoff command artifact(s) are available for safety checks."
            if has_command_artifacts
            else "Handoff command artifacts are not generated yet; the release gate reruns this check after status and next-step files are written."
        ),
        evidence=describe_paths(existing_files) if existing_files else None,
    )

    placeholder_hits = [
        path
        for path, fragment in fragments
        if any(placeholder in fragment for placeholder in BACKUP_REFERENCE_PLACEHOLDERS)
    ]
    add_check(
        checks,
        check_id="handoff_backup_reference_placeholders_absent",
        label="Backup reference placeholders absent",
        status="skipped" if not has_command_artifacts else ("pass" if not placeholder_hits else "fail"),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "No backup-reference placeholders were found in handoff command artifacts."
                if not placeholder_hits
                else "Backup-reference placeholder text was found in: " + describe_paths(placeholder_hits)
            )
        ),
        evidence=describe_paths(placeholder_hits) if placeholder_hits else None,
    )

    shell_unsafe_repo_placeholder_hits = [
        path
        for path, fragment in fragments
        if any(placeholder in fragment for placeholder in SHELL_UNSAFE_REPO_PLACEHOLDERS)
    ]
    add_check(
        checks,
        check_id="handoff_repo_url_placeholder_shell_safe",
        label="Repo URL placeholders are shell-safe",
        status=(
            "skipped"
            if not has_command_artifacts
            else ("pass" if not shell_unsafe_repo_placeholder_hits else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "Generated repo URL placeholders are shell-safe."
                if not shell_unsafe_repo_placeholder_hits
                else "Shell-unsafe <repo-url> placeholder command(s) were found in: "
                + describe_paths(shell_unsafe_repo_placeholder_hits)
            )
        ),
        evidence=describe_paths(shell_unsafe_repo_placeholder_hits) if shell_unsafe_repo_placeholder_hits else None,
    )

    repo_url_env_automation_commands = [
        (path, fragment)
        for path, fragment in fragments
        if "next_release_step.py" in fragment
        and "--repo-url-from-env" in fragment
        and ("--json-only" in fragment or "--command-only" in fragment)
    ]
    unsafe_repo_url_env_automation_paths = [
        path
        for path, fragment in repo_url_env_automation_commands
        if "--fail-if-repo-url-required" not in fragment
    ]
    add_check(
        checks,
        check_id="handoff_repo_url_required_gate",
        label="Repo URL automation fails on placeholders",
        status=(
            "skipped"
            if not has_command_artifacts or not repo_url_env_automation_commands
            else ("pass" if not unsafe_repo_url_env_automation_paths else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "No repo-url-from-env automation command artifact was available yet."
                if not repo_url_env_automation_commands
                else (
                    "Every generated repo-url-from-env automation command includes --fail-if-repo-url-required."
                    if not unsafe_repo_url_env_automation_paths
                    else "Repo-url-from-env automation command(s) are missing --fail-if-repo-url-required: "
                    + describe_paths(unsafe_repo_url_env_automation_paths)
                )
            )
        ),
        evidence=(
            describe_paths(unsafe_repo_url_env_automation_paths)
            if unsafe_repo_url_env_automation_paths
            else None
        ),
    )

    next_step_files = [
        package_dir / relative_path
        for relative_path in ("next-release-step.md", "next-release-step.json")
        if (package_dir / relative_path).is_file()
    ]
    next_step_fragments = [
        (path, fragment)
        for path, fragment in fragments
        if path.name in {"next-release-step.md", "next-release-step.json"}
    ]
    next_step_requires_repo_url = any(REPO_URL_PLACEHOLDER in fragment for _path, fragment in next_step_fragments)
    expected_repo_url_gate_commands = {
        "command_gate": next_release_command_only_env_command(package_dir),
        "json_gate": next_release_connected_json_only_env_command(package_dir),
    }
    missing_repo_url_gate_names = [
        name
        for name, expected_command in expected_repo_url_gate_commands.items()
        if not any(expected_command in fragment for _path, fragment in next_step_fragments)
    ]
    add_check(
        checks,
        check_id="handoff_repo_url_top_level_gates",
        label="Repo URL top-level gate commands",
        status=(
            "skipped"
            if not has_command_artifacts or not next_step_files or not next_step_requires_repo_url
            else ("pass" if not missing_repo_url_gate_names else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "Next-step artifacts are not generated yet."
                if not next_step_files
                else (
                    "Next-step artifacts do not contain a repo URL placeholder, so top-level repo URL gates are not required."
                    if not next_step_requires_repo_url
                    else (
                        "Next-step artifacts include top-level repo URL command and JSON gates."
                        if not missing_repo_url_gate_names
                        else "Next-step artifacts are missing top-level repo URL gate command(s): "
                        + ", ".join(missing_repo_url_gate_names)
                    )
                )
            )
        ),
        evidence=", ".join(missing_repo_url_gate_names) if missing_repo_url_gate_names else None,
    )

    expected_repo_url_export_command = repo_url_export_example_command()
    repo_url_export_example_paths = [
        path
        for path, fragment in next_step_fragments
        if expected_repo_url_export_command in fragment
    ]
    add_check(
        checks,
        check_id="handoff_repo_url_export_example",
        label="Repo URL export example",
        status=(
            "skipped"
            if not has_command_artifacts or not next_step_files or not next_step_requires_repo_url
            else ("pass" if repo_url_export_example_paths else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "Next-step artifacts are not generated yet."
                if not next_step_files
                else (
                    "Next-step artifacts do not contain a repo URL placeholder, so an export example is not required."
                    if not next_step_requires_repo_url
                    else (
                        "Next-step artifacts include a concrete GIT_ORIGIN_URL export example."
                        if repo_url_export_example_paths
                        else "Next-step artifacts are missing a concrete GIT_ORIGIN_URL export example."
                    )
                )
            )
        ),
        evidence=describe_paths(repo_url_export_example_paths) if repo_url_export_example_paths else None,
    )

    expected_command_sequence_paths = [
        path
        for path, fragment in fragments
        if next_release_command_sequence_env_command(package_dir) in fragment
    ]
    add_check(
        checks,
        check_id="handoff_command_sequence_only",
        label="Remaining command sequence automation",
        status=(
            "skipped"
            if not has_command_artifacts
            else ("pass" if expected_command_sequence_paths else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "Generated handoff commands include command-sequence-only automation."
                if expected_command_sequence_paths
                else "Handoff command sequence automation is missing --command-sequence-only."
            )
        ),
        evidence=describe_paths(expected_command_sequence_paths) if expected_command_sequence_paths else None,
    )

    release_status_json_commands = [
        path
        for path, fragment in fragments
        if "report_release_status.py" in fragment and "--json-only" in fragment
    ]
    add_check(
        checks,
        check_id="handoff_release_status_json_command",
        label="Release status JSON automation command",
        status=(
            "skipped"
            if not has_command_artifacts
            else ("pass" if release_status_json_commands else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "At least one generated release-status command prints JSON without writing files."
                if release_status_json_commands
                else "No report_release_status.py --json-only handoff command was available."
            )
        ),
        evidence=describe_paths(release_status_json_commands) if release_status_json_commands else None,
    )

    release_status_progress_commands = [
        path
        for path, fragment in fragments
        if "report_release_status.py" in fragment and "--progress-only" in fragment
    ]
    add_check(
        checks,
        check_id="handoff_release_status_progress_command",
        label="Release status progress command",
        status=(
            "skipped"
            if not has_command_artifacts
            else ("pass" if release_status_progress_commands else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "At least one generated release-status command prints compact progress without writing files."
                if release_status_progress_commands
                else "No report_release_status.py --progress-only handoff command was available."
            )
        ),
        evidence=describe_paths(release_status_progress_commands) if release_status_progress_commands else None,
    )

    release_status_progress_json_commands = [
        path
        for path, fragment in fragments
        if "report_release_status.py" in fragment and "--progress-json-only" in fragment
    ]
    add_check(
        checks,
        check_id="handoff_release_status_progress_json_command",
        label="Release status progress JSON command",
        status=(
            "skipped"
            if not has_command_artifacts
            else ("pass" if release_status_progress_json_commands else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "At least one generated release-status command prints compact progress JSON without writing files."
                if release_status_progress_json_commands
                else "No report_release_status.py --progress-json-only handoff command was available."
            )
        ),
        evidence=describe_paths(release_status_progress_json_commands) if release_status_progress_json_commands else None,
    )

    release_status_completion_plan_commands = [
        path
        for path, fragment in fragments
        if "report_release_status.py" in fragment and "--completion-plan-only" in fragment
    ]
    add_check(
        checks,
        check_id="handoff_release_status_completion_plan_command",
        label="Release status completion plan command",
        status=(
            "skipped"
            if not has_command_artifacts
            else ("pass" if release_status_completion_plan_commands else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "At least one generated release-status command prints the ordered completion plan without writing files."
                if release_status_completion_plan_commands
                else "No report_release_status.py --completion-plan-only handoff command was available."
            )
        ),
        evidence=describe_paths(release_status_completion_plan_commands)
        if release_status_completion_plan_commands
        else None,
    )

    release_status_completion_plan_json_commands = [
        path
        for path, fragment in fragments
        if "report_release_status.py" in fragment and "--completion-plan-json-only" in fragment
    ]
    add_check(
        checks,
        check_id="handoff_release_status_completion_plan_json_command",
        label="Release status completion plan JSON command",
        status=(
            "skipped"
            if not has_command_artifacts
            else ("pass" if release_status_completion_plan_json_commands else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "At least one generated release-status command prints the ordered completion plan as JSON without writing files."
                if release_status_completion_plan_json_commands
                else "No report_release_status.py --completion-plan-json-only handoff command was available."
            )
        ),
        evidence=describe_paths(release_status_completion_plan_json_commands)
        if release_status_completion_plan_json_commands
        else None,
    )

    release_status_completion_requirements_commands = [
        path
        for path, fragment in fragments
        if "report_release_status.py" in fragment and "--completion-requirements-only" in fragment
    ]
    add_check(
        checks,
        check_id="handoff_release_status_completion_requirements_command",
        label="Release status completion requirements command",
        status=(
            "skipped"
            if not has_command_artifacts
            else ("pass" if release_status_completion_requirements_commands else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "At least one generated release-status command prints grouped completion requirements without writing files."
                if release_status_completion_requirements_commands
                else "No report_release_status.py --completion-requirements-only handoff command was available."
            )
        ),
        evidence=describe_paths(release_status_completion_requirements_commands)
        if release_status_completion_requirements_commands
        else None,
    )

    release_status_completion_requirements_json_commands = [
        path
        for path, fragment in fragments
        if "report_release_status.py" in fragment and "--completion-requirements-json-only" in fragment
    ]
    add_check(
        checks,
        check_id="handoff_release_status_completion_requirements_json_command",
        label="Release status completion requirements JSON command",
        status=(
            "skipped"
            if not has_command_artifacts
            else ("pass" if release_status_completion_requirements_json_commands else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "At least one generated release-status command prints grouped completion requirements as JSON without writing files."
                if release_status_completion_requirements_json_commands
                else "No report_release_status.py --completion-requirements-json-only handoff command was available."
            )
        ),
        evidence=describe_paths(release_status_completion_requirements_json_commands)
        if release_status_completion_requirements_json_commands
        else None,
    )

    release_status_owner_lanes_commands = [
        path
        for path, fragment in fragments
        if "report_release_status.py" in fragment and "--owner-lanes-only" in fragment
    ]
    add_check(
        checks,
        check_id="handoff_release_status_owner_lanes_command",
        label="Release status owner lanes command",
        status=(
            "skipped"
            if not has_command_artifacts
            else ("pass" if release_status_owner_lanes_commands else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "At least one generated release-status command prints owner-lane progress without writing files."
                if release_status_owner_lanes_commands
                else "No report_release_status.py --owner-lanes-only handoff command was available."
            )
        ),
        evidence=describe_paths(release_status_owner_lanes_commands)
        if release_status_owner_lanes_commands
        else None,
    )

    release_status_owner_lanes_json_commands = [
        path
        for path, fragment in fragments
        if "report_release_status.py" in fragment and "--owner-lanes-json-only" in fragment
    ]
    add_check(
        checks,
        check_id="handoff_release_status_owner_lanes_json_command",
        label="Release status owner lanes JSON command",
        status=(
            "skipped"
            if not has_command_artifacts
            else ("pass" if release_status_owner_lanes_json_commands else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "At least one generated release-status command prints owner-lane progress as JSON without writing files."
                if release_status_owner_lanes_json_commands
                else "No report_release_status.py --owner-lanes-json-only handoff command was available."
            )
        ),
        evidence=describe_paths(release_status_owner_lanes_json_commands)
        if release_status_owner_lanes_json_commands
        else None,
    )

    release_status_json_path = package_dir / "release-status.json"
    release_status_payload: dict[str, Any] | None = None
    progress_summary: dict[str, Any] | None = None
    progress_summary_error: str | None = None
    if release_status_json_path.is_file():
        try:
            candidate_payload = read_json(release_status_json_path)
            if isinstance(candidate_payload, dict):
                release_status_payload = candidate_payload
                candidate = release_status_payload.get("progress_summary")
                if isinstance(candidate, dict):
                    progress_summary = candidate
                else:
                    progress_summary_error = "release-status.json progress_summary is missing or not an object."
            else:
                progress_summary_error = "release-status.json is not an object."
        except (OSError, json.JSONDecodeError) as exc:
            progress_summary_error = f"release-status.json could not be read as JSON: {exc}"
    elif has_command_artifacts:
        progress_summary_error = "release-status.json is missing."

    required_progress_fields = {
        "next_command",
        "next_item_id",
        "next_item_owner",
        "next_commands_by_owner",
        "commands",
        "warning_review",
        "release_gate_path",
        "status",
        "percent",
        "remaining_items",
        "remaining_ids",
        "remaining_by_owner",
        "completion_impacts",
        "completion_plan",
        "completion_requirements",
        "owner_lanes",
        "deductions",
        "package_dir",
    }
    required_progress_command_keys = {
        "connected_runner_command_only",
        "connected_runner_command_sequence",
        "export_repo_url_example",
        "next_command_only",
        "next_json_only",
        "operator_command_only",
        "operator_command_sequence",
        "operator_review_sequence",
        "operator_json_only",
        "remaining_sequence",
        "show_completion_plan",
        "show_completion_plan_json",
        "show_completion_requirements",
        "show_completion_requirements_json",
        "show_owner_lanes",
        "show_owner_lanes_json",
        "show_progress",
        "show_progress_json",
        "local_readiness_json",
        "local_readiness_command_only",
        "local_readiness_setup_sequence",
        "local_readiness_command_sequence",
        "local_readiness_setup_sequence_preview",
        "local_readiness_command_sequence_preview",
        "local_readiness_gate_json",
        "external_readiness_summary_json",
        "external_readiness_strict_summary_json",
        "connected_runner_acceptance_summary_json",
        "warning_gate_json",
        "warning_summary_json",
        "warning_gate_summary_json",
        "warning_pre_approval_sequence",
        "warning_next_command_gate",
        "warning_review_artifacts",
        "warning_apply",
    }
    if progress_summary and progress_summary.get("connected_runner_handoff_bundle"):
        required_progress_command_keys.add("handoff_bundle_verify_summary_json")
        required_progress_command_keys.add("handoff_context_json")
        required_progress_command_keys.add("handoff_command_sequence")
    missing_progress_fields = sorted(
        field for field in required_progress_fields if not progress_summary or field not in progress_summary
    )
    progress_commands = progress_summary.get("commands") if progress_summary else None
    missing_progress_command_keys = sorted(
        key
        for key in required_progress_command_keys
        if not isinstance(progress_commands, dict) or key not in progress_commands
    )
    add_check(
        checks,
        check_id="handoff_release_status_progress_summary",
        label="Release status embedded progress summary",
        status=(
            "skipped"
            if not has_command_artifacts
            else (
                "pass"
                if not progress_summary_error and not missing_progress_fields and not missing_progress_command_keys
                else "fail"
            )
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "release-status.json embeds compact progress summary fields and resume command keys."
                if not progress_summary_error and not missing_progress_fields and not missing_progress_command_keys
                else (
                    progress_summary_error
                    or "release-status.json progress_summary is missing field(s): "
                    + ", ".join(missing_progress_fields + missing_progress_command_keys)
                )
            )
        ),
        evidence=str(release_status_json_path) if release_status_json_path.is_file() else None,
    )

    progress_snapshot_errors: list[str] = []
    if progress_summary_error:
        progress_snapshot_errors.append(progress_summary_error)
    elif not isinstance(release_status_payload, dict):
        progress_snapshot_errors.append("release-status.json is missing or not an object")
    else:
        readiness_estimate = release_status_payload.get("readiness_estimate")
        remaining_items = release_status_payload.get("remaining_items")
        if not isinstance(readiness_estimate, dict):
            progress_snapshot_errors.append("release-status.json readiness_estimate is missing or not an object")
        else:
            expected_progress_fields = {
                "percent": readiness_estimate.get("percent"),
                "remaining_items": readiness_estimate.get("remaining_items"),
                "deductions": readiness_estimate.get("deductions"),
            }
            for field, expected in expected_progress_fields.items():
                if progress_summary.get(field) != expected:
                    progress_snapshot_errors.append(f"progress_summary.{field} != readiness_estimate.{field}")
            deductions = readiness_estimate.get("deductions")
            expected_completion_impacts = (
                completion_impacts_by_check_id(deductions) if isinstance(deductions, list) else {}
            )
            if progress_summary.get("completion_impacts") != expected_completion_impacts:
                progress_snapshot_errors.append(
                    "progress_summary.completion_impacts != readiness_estimate deductions"
                )
        if progress_summary.get("status") != release_status_payload.get("status"):
            progress_snapshot_errors.append("progress_summary.status != status")
        if progress_summary.get("package_dir") != release_status_payload.get("package_dir"):
            progress_snapshot_errors.append("progress_summary.package_dir != package_dir")
        if not isinstance(remaining_items, list):
            progress_snapshot_errors.append("release-status.json remaining_items is missing or not a list")
        else:
            remaining_ids: list[str] = []
            remaining_by_owner: dict[str, int] = {}
            for item in remaining_items:
                if not isinstance(item, dict):
                    continue
                item_id = item.get("id")
                if isinstance(item_id, str):
                    remaining_ids.append(item_id)
                owner = item.get("owner")
                if isinstance(owner, str):
                    remaining_by_owner[owner] = remaining_by_owner.get(owner, 0) + 1
            if progress_summary.get("remaining_ids") != remaining_ids:
                progress_snapshot_errors.append("progress_summary.remaining_ids != remaining_items ids")
            if progress_summary.get("remaining_by_owner") != remaining_by_owner:
                progress_snapshot_errors.append("progress_summary.remaining_by_owner != remaining_items owner counts")
            completion_impacts = progress_summary.get("completion_impacts")
            expected_plan = expected_completion_plan(
                remaining_items,
                completion_impacts if isinstance(completion_impacts, dict) else {},
            )
            if progress_summary.get("completion_plan") != expected_plan:
                progress_snapshot_errors.append("progress_summary.completion_plan != remaining_items")
            expected_requirements = completion_requirements_summary(expected_plan)
            if progress_summary.get("completion_requirements") != expected_requirements:
                progress_snapshot_errors.append(
                    "progress_summary.completion_requirements != completion_plan requirements"
                )
            next_by_owner = progress_summary.get("next_commands_by_owner")
            expected_owner_lanes = owner_lanes_summary(
                remaining_by_owner=remaining_by_owner,
                next_commands_by_owner=next_by_owner if isinstance(next_by_owner, dict) else {},
                completion_plan=expected_plan,
                local_readiness=progress_summary.get("local_readiness"),
                warning_review=progress_summary.get("warning_review"),
            )
            if progress_summary.get("owner_lanes") != expected_owner_lanes:
                progress_snapshot_errors.append("progress_summary.owner_lanes != owner progress summary")
    add_check(
        checks,
        check_id="handoff_release_status_progress_snapshot",
        label="Release status progress top-level snapshot",
        status=(
            "skipped"
            if not has_command_artifacts
            else ("pass" if not progress_snapshot_errors else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "release-status.json progress summary mirrors top-level status, readiness, package, and remaining-item snapshots."
                if not progress_snapshot_errors
                else "release-status.json progress_summary top-level snapshot is missing or stale: "
                + ", ".join(progress_snapshot_errors)
            )
        ),
        evidence=str(release_status_json_path) if release_status_json_path.is_file() else None,
    )

    completion_plan_backend_errors: list[str] = []
    if progress_summary_error:
        completion_plan_backend_errors.append(progress_summary_error)
    else:
        completion_plan = progress_summary.get("completion_plan") if progress_summary else None
        if not isinstance(completion_plan, list):
            completion_plan_backend_errors.append("progress_summary.completion_plan")
        else:
            expected_backend = expected_warning_backend_guidance()
            for item in completion_plan:
                if not isinstance(item, dict) or item.get("id") != "warning_actions":
                    continue
                requirements = item.get("requirements")
                has_running_backend = isinstance(requirements, list) and "running_backend" in requirements
                if has_running_backend and item.get("backend") != expected_backend:
                    completion_plan_backend_errors.append("warning_actions.backend")
    add_check(
        checks,
        check_id="handoff_completion_plan_warning_backend_guidance",
        label="Completion plan warning backend guidance",
        status=(
            "skipped"
            if not has_command_artifacts
            else ("pass" if not completion_plan_backend_errors else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "Completion plan includes backend start and health-check guidance before approval-only warning actions."
                if not completion_plan_backend_errors
                else "Completion plan warning backend guidance is missing or stale: "
                + ", ".join(completion_plan_backend_errors)
            )
        ),
        evidence=str(release_status_json_path) if release_status_json_path.is_file() else None,
    )

    progress_owner_next_errors: list[str] = []
    if progress_summary_error:
        progress_owner_next_errors.append(progress_summary_error)
    elif not isinstance(release_status_payload, dict):
        progress_owner_next_errors.append("release-status.json is missing or not an object")
    else:
        remaining_items = release_status_payload.get("remaining_items")
        next_commands_by_owner = progress_summary.get("next_commands_by_owner")
        if not isinstance(remaining_items, list):
            progress_owner_next_errors.append("release-status.json remaining_items is missing or not a list")
        elif not isinstance(next_commands_by_owner, dict):
            progress_owner_next_errors.append("progress_summary.next_commands_by_owner is missing or not an object")
        else:
            first_item: dict[str, Any] | None = next(
                (item for item in remaining_items if isinstance(item, dict)),
                None,
            )
            if first_item is None:
                if progress_summary.get("next_item_id") is not None:
                    progress_owner_next_errors.append("progress_summary.next_item_id should be null")
                if progress_summary.get("next_item_owner") is not None:
                    progress_owner_next_errors.append("progress_summary.next_item_owner should be null")
                if progress_summary.get("next_command") is not None:
                    progress_owner_next_errors.append("progress_summary.next_command should be null")
            else:
                expected_next_command = (
                    first_item.get("preferred_command")
                    if isinstance(first_item.get("preferred_command"), str)
                    else first_item.get("command")
                )
                expected_next_fields = {
                    "next_item_id": first_item.get("id"),
                    "next_item_owner": first_item.get("owner"),
                    "next_command": expected_next_command,
                }
                for field, expected in expected_next_fields.items():
                    if progress_summary.get(field) != expected:
                        progress_owner_next_errors.append(f"progress_summary.{field} != first remaining item")
            first_by_owner: dict[str, dict[str, Any]] = {}
            for item in remaining_items:
                if not isinstance(item, dict):
                    continue
                owner = item.get("owner")
                if isinstance(owner, str) and owner not in first_by_owner:
                    first_by_owner[owner] = item
            if set(next_commands_by_owner) != set(first_by_owner):
                progress_owner_next_errors.append(
                    "progress_summary.next_commands_by_owner keys != remaining item owners"
                )
            for owner, item in first_by_owner.items():
                owner_entry = next_commands_by_owner.get(owner)
                if not isinstance(owner_entry, dict):
                    progress_owner_next_errors.append(f"next_commands_by_owner.{owner}")
                    continue
                expected_owner_command = (
                    item.get("preferred_command")
                    if isinstance(item.get("preferred_command"), str)
                    else item.get("command")
                )
                expected_owner_fields = {
                    "id": item.get("id"),
                    "status": item.get("status"),
                    "command": expected_owner_command,
                }
                for field, expected in expected_owner_fields.items():
                    if owner_entry.get(field) != expected:
                        progress_owner_next_errors.append(
                            f"next_commands_by_owner.{owner}.{field} != first owner item"
                        )
                completion_impacts = progress_summary.get("completion_impacts")
                completion_impact = None
                if isinstance(completion_impacts, dict):
                    completion_impact = completion_impacts.get(str(item.get("id") or ""))
                for field in COMPLETION_IMPACT_FIELDS:
                    expected = item.get(field)
                    if expected is None and isinstance(completion_impact, dict):
                        expected = completion_impact.get(field)
                    if expected is not None and owner_entry.get(field) != expected:
                        progress_owner_next_errors.append(
                            f"next_commands_by_owner.{owner}.{field} != first owner completion impact"
                        )
    add_check(
        checks,
        check_id="handoff_release_status_progress_owner_next",
        label="Release status progress owner next entries",
        status=(
            "skipped"
            if not has_command_artifacts
            else ("pass" if not progress_owner_next_errors else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "release-status.json progress summary next item and owner entries match the ordered remaining items."
                if not progress_owner_next_errors
                else "release-status.json progress_summary next/owner entries are missing or stale: "
                + ", ".join(progress_owner_next_errors)
            )
        ),
        evidence=str(release_status_json_path) if release_status_json_path.is_file() else None,
    )

    next_step_json_path = package_dir / "next-release-step.json"
    next_step_payload: dict[str, Any] | None = None
    next_step_error: str | None = None
    if next_step_json_path.is_file():
        try:
            candidate = read_json(next_step_json_path)
            if isinstance(candidate, dict):
                next_step_payload = candidate
            else:
                next_step_error = "next-release-step.json is not an object."
        except (OSError, json.JSONDecodeError) as exc:
            next_step_error = f"next-release-step.json could not be read as JSON: {exc}"
    elif has_command_artifacts:
        next_step_error = "next-release-step.json is missing."
    progress_next_command_errors: list[str] = []
    if progress_summary_error:
        progress_next_command_errors.append(progress_summary_error)
    if next_step_error:
        progress_next_command_errors.append(next_step_error)
    if not progress_next_command_errors:
        progress_next_command = progress_summary.get("next_command") if progress_summary else None
        next_step_command = next_step_payload.get("next_command") if next_step_payload else None
        remaining_items = (
            release_status_payload.get("remaining_items")
            if isinstance(release_status_payload, dict)
            else None
        )
        no_remaining_items = isinstance(remaining_items, list) and not remaining_items
        if no_remaining_items:
            if progress_next_command is not None:
                progress_next_command_errors.append("progress_summary.next_command should be null")
            if next_step_command != LIVE_BETA_FINAL_GATE_COMMAND:
                progress_next_command_errors.append("next-release-step.json final gate command")
        else:
            if not isinstance(progress_next_command, str) or not progress_next_command:
                progress_next_command_errors.append("progress_summary.next_command")
            if not isinstance(next_step_command, str) or not next_step_command:
                progress_next_command_errors.append("next-release-step.json next_command")
            if (
                isinstance(progress_next_command, str)
                and isinstance(next_step_command, str)
                and progress_next_command != next_step_command
            ):
                progress_next_command_errors.append(
                    "progress_summary.next_command != next-release-step.json next_command"
                )
    add_check(
        checks,
        check_id="handoff_release_status_progress_next_step_command",
        label="Release status progress next-step command",
        status=(
            "skipped"
            if not has_command_artifacts
            else ("pass" if not progress_next_command_errors else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "release-status.json progress next command matches next-release-step.json."
                if not progress_next_command_errors
                else "Archived progress and next-step commands are missing or mismatched: "
                + ", ".join(progress_next_command_errors)
            )
        ),
        evidence=(
            f"{release_status_json_path}, {next_step_json_path}"
            if release_status_json_path.is_file() and next_step_json_path.is_file()
            else None
        ),
    )

    progress_release_gate_errors: list[str] = []
    progress_release_gate_path = progress_summary.get("release_gate_path") if progress_summary else None
    if not isinstance(progress_release_gate_path, str) or not progress_release_gate_path:
        progress_release_gate_errors.append("progress_summary.release_gate_path")
    if not isinstance(progress_commands, dict):
        progress_release_gate_errors.append("progress_summary.commands")
    if not progress_release_gate_errors:
        expected_progress_commands = {
            "show_progress": release_status_progress_command(package_dir, progress_release_gate_path),
            "show_progress_json": release_status_progress_json_command(package_dir, progress_release_gate_path),
            "show_completion_requirements": release_status_completion_requirements_command(
                package_dir,
                progress_release_gate_path,
            ),
            "show_completion_requirements_json": release_status_completion_requirements_json_command(
                package_dir,
                progress_release_gate_path,
            ),
            "show_owner_lanes": release_status_owner_lanes_command(
                package_dir,
                progress_release_gate_path,
            ),
            "show_owner_lanes_json": release_status_owner_lanes_json_command(
                package_dir,
                progress_release_gate_path,
            ),
        }
        for key, expected in expected_progress_commands.items():
            if progress_commands.get(key) != expected:
                progress_release_gate_errors.append(f"commands.{key}")
    add_check(
        checks,
        check_id="handoff_release_status_progress_release_gate",
        label="Release status progress release gate command",
        status=(
            "skipped"
            if not has_command_artifacts
            else ("pass" if not progress_summary_error and not progress_release_gate_errors else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "release-status.json progress commands preserve the matching release gate summary path."
                if not progress_summary_error and not progress_release_gate_errors
                else (
                    progress_summary_error
                    or "release-status.json progress release gate metadata is missing or stale: "
                    + ", ".join(progress_release_gate_errors)
                )
            )
        ),
        evidence=str(release_status_json_path) if release_status_json_path.is_file() else None,
    )

    progress_repo_url = progress_summary.get("repo_url") if progress_summary else None
    progress_repo_url_errors: list[str] = []
    if not isinstance(progress_repo_url, dict):
        progress_repo_url_errors.append("progress_summary.repo_url is missing or not an object")
    elif next_step_requires_repo_url:
        expected_progress_repo_url = {
            "required": True,
            "placeholder": REPO_URL_PLACEHOLDER,
            "export_command": expected_repo_url_export_command,
            "command_gate": next_release_command_only_env_command(package_dir),
            "json_gate": next_release_json_only_env_command(package_dir),
        }
        for key, expected in expected_progress_repo_url.items():
            if progress_repo_url.get(key) != expected:
                progress_repo_url_errors.append(f"repo_url.{key}")
    elif isinstance(progress_repo_url, dict) and progress_repo_url.get("required") is not False:
        progress_repo_url_errors.append("repo_url.required should be false when no repo URL placeholder remains")

    add_check(
        checks,
        check_id="handoff_release_status_progress_repo_url",
        label="Release status progress repo URL metadata",
        status=(
            "skipped"
            if not has_command_artifacts
            else ("pass" if not progress_summary_error and not progress_repo_url_errors else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "release-status.json progress summary exposes repo URL placeholder/export/gate metadata."
                if not progress_summary_error and not progress_repo_url_errors
                else (
                    progress_summary_error
                    or "release-status.json progress_summary repo URL metadata is missing or stale: "
                    + ", ".join(progress_repo_url_errors)
                )
            )
        ),
        evidence=str(release_status_json_path) if release_status_json_path.is_file() else None,
    )

    progress_local_readiness = progress_summary.get("local_readiness") if progress_summary else None
    progress_local_readiness_errors: list[str] = []
    required_local_readiness_fields = {
        "status",
        "issue_ids",
        "next_setup",
        "next_setup_command",
        "setup_sequence",
        "verify_sequence",
        "command_sequence",
        "json_command",
        "command_only_gate",
        "setup_sequence_command",
        "command_sequence_command",
        "json_gate",
        "external_summary_json",
        "external_strict_summary_json",
    }
    if not isinstance(progress_local_readiness, dict):
        progress_local_readiness_errors.append("progress_summary.local_readiness is missing or not an object")
    else:
        missing_local_readiness_fields = sorted(
            field for field in required_local_readiness_fields if field not in progress_local_readiness
        )
        progress_local_readiness_errors.extend(
            f"local_readiness.{field}" for field in missing_local_readiness_fields
        )
        expected_local_readiness_commands = {
            "json_command": "local_readiness_json",
            "command_only_gate": "local_readiness_command_only",
            "setup_sequence_command": "local_readiness_setup_sequence",
            "command_sequence_command": "local_readiness_command_sequence",
            "setup_sequence_preview_command": "local_readiness_setup_sequence_preview",
            "command_sequence_preview_command": "local_readiness_command_sequence_preview",
            "json_gate": "local_readiness_gate_json",
            "external_summary_json": "external_readiness_summary_json",
            "external_strict_summary_json": "external_readiness_strict_summary_json",
        }
        for field, command_key in expected_local_readiness_commands.items():
            expected = progress_commands.get(command_key) if isinstance(progress_commands, dict) else None
            if not isinstance(expected, str) or progress_local_readiness.get(field) != expected:
                progress_local_readiness_errors.append(f"local_readiness.{field}")
        if isinstance(release_status_payload, dict) and isinstance(
            release_status_payload.get("remaining_items"),
            list,
        ):
            remaining_items = release_status_payload.get("remaining_items")
            runner_items = [
                item
                for item in remaining_items
                if (
                    isinstance(item, dict)
                    and item.get("owner") == "connected runner"
                    and item.get("status") in {"warn", "fail"}
                )
            ]
            expected_issue_ids = [str(item.get("id") or "external_readiness") for item in runner_items]
            if progress_local_readiness.get("issue_ids") != expected_issue_ids:
                progress_local_readiness_errors.append("local_readiness.issue_ids")
            expected_local_status = "pass"
            if any(item.get("status") == "fail" for item in runner_items):
                expected_local_status = "fail"
            elif runner_items:
                expected_local_status = "warn"
            if progress_local_readiness.get("status") != expected_local_status:
                progress_local_readiness_errors.append("local_readiness.status")
            next_setup = progress_local_readiness.get("next_setup")
            if runner_items:
                expected_next_setup = runner_items[0]
                if not isinstance(next_setup, dict):
                    progress_local_readiness_errors.append("local_readiness.next_setup")
                else:
                    expected_next_setup_fields = {
                        "id": str(expected_next_setup.get("id") or "external_readiness"),
                        "status": expected_next_setup.get("status"),
                        "setup_command": expected_next_setup.get("command"),
                        "verify_command": expected_next_setup.get("verify_command"),
                    }
                    for field, expected in expected_next_setup_fields.items():
                        if expected is not None and next_setup.get(field) != expected:
                            progress_local_readiness_errors.append(f"local_readiness.next_setup.{field}")
                expected_next_setup_command = expected_next_setup.get("command")
                if (
                    isinstance(expected_next_setup_command, str)
                    and progress_local_readiness.get("next_setup_command") != expected_next_setup_command
                ):
                    progress_local_readiness_errors.append("local_readiness.next_setup_command")
            elif next_setup is not None or progress_local_readiness.get("next_setup_command") is not None:
                progress_local_readiness_errors.append("local_readiness.next_setup")
    add_check(
        checks,
        check_id="handoff_release_status_progress_local_readiness",
        label="Release status progress local readiness metadata",
        status=(
            "skipped"
            if not has_command_artifacts
            else ("pass" if not progress_summary_error and not progress_local_readiness_errors else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "release-status.json progress summary exposes connected-runner local readiness setup/verify metadata."
                if not progress_summary_error and not progress_local_readiness_errors
                else (
                    progress_summary_error
                    or "release-status.json progress_summary local readiness metadata is missing or stale: "
                    + ", ".join(progress_local_readiness_errors)
                )
            )
        ),
        evidence=str(release_status_json_path) if release_status_json_path.is_file() else None,
    )

    progress_warning_review = progress_summary.get("warning_review") if progress_summary else None
    progress_warning_review_errors: list[str] = []
    required_warning_review_fields = {
        "status",
        "action_needed",
        "issue_ids",
        "next_command",
        "requires_operator_approval",
        "summary_json",
        "gate_summary_json",
        "pre_approval_sequence_command",
        "gate_json",
        "next_command_gate",
        "review_artifacts_command",
        "apply_command",
        "review_artifacts",
        "review_sequence_command",
        "pre_approval_review_sequence",
        "review_sequence",
        "backend",
    }
    if not isinstance(progress_warning_review, dict):
        progress_warning_review_errors.append("progress_summary.warning_review is missing or not an object")
    else:
        missing_warning_review_fields = sorted(
            field for field in required_warning_review_fields if field not in progress_warning_review
        )
        progress_warning_review_errors.extend(
            f"warning_review.{field}" for field in missing_warning_review_fields
        )
        expected_warning_review_commands = {
            "summary_json": "warning_summary_json",
            "gate_summary_json": "warning_gate_summary_json",
            "pre_approval_sequence_command": "warning_pre_approval_sequence",
            "gate_json": "warning_gate_json",
            "next_command_gate": "warning_next_command_gate",
            "review_artifacts_command": "warning_review_artifacts",
            "apply_command": "warning_apply",
            "review_sequence_command": "operator_review_sequence",
        }
        for field, command_key in expected_warning_review_commands.items():
            expected = progress_commands.get(command_key) if isinstance(progress_commands, dict) else None
            if not isinstance(expected, str) or progress_warning_review.get(field) != expected:
                progress_warning_review_errors.append(f"warning_review.{field}")
        review_artifacts = progress_warning_review.get("review_artifacts")
        if progress_warning_review.get("action_needed"):
            if not isinstance(review_artifacts, dict):
                progress_warning_review_errors.append("warning_review.review_artifacts")
            else:
                expected_review_artifacts = {
                    "action_plan": str(package_dir / "release-warning-actions.md"),
                    "operator_checklist": str(package_dir / "release-warning-operator-checklist.md"),
                }
                for label, expected in expected_review_artifacts.items():
                    if review_artifacts.get(label) != expected:
                        progress_warning_review_errors.append(f"warning_review.review_artifacts.{label}")
        if isinstance(release_status_payload, dict) and isinstance(
            release_status_payload.get("remaining_items"),
            list,
        ):
            remaining_items = release_status_payload.get("remaining_items")
            operator_items = [
                item
                for item in remaining_items
                if (
                    isinstance(item, dict)
                    and item.get("owner") == "operator"
                    and item.get("id") in {"warning_alerts", "warning_actions"}
                )
            ]
            expected_warning_issue_ids = [
                str(item.get("id") or "warning_review") for item in operator_items
            ]
            if progress_warning_review.get("issue_ids") != expected_warning_issue_ids:
                progress_warning_review_errors.append("warning_review.issue_ids")
            expected_warning_status = "pass"
            if any(item.get("status") == "fail" for item in operator_items):
                expected_warning_status = "fail"
            elif any(item.get("id") == "warning_actions" for item in operator_items):
                expected_warning_status = "planned"
            elif operator_items:
                expected_warning_status = "warn"
            if progress_warning_review.get("status") != expected_warning_status:
                progress_warning_review_errors.append("warning_review.status")
            if progress_warning_review.get("action_needed") is not bool(operator_items):
                progress_warning_review_errors.append("warning_review.action_needed")
            expected_operator_approval = any(item.get("id") == "warning_actions" for item in operator_items)
            if progress_warning_review.get("requires_operator_approval") is not expected_operator_approval:
                progress_warning_review_errors.append("warning_review.requires_operator_approval")
            expected_backend = (
                expected_warning_backend_guidance()
                if expected_operator_approval
                else {}
            )
            if progress_warning_review.get("backend") != expected_backend:
                progress_warning_review_errors.append("warning_review.backend")
            expected_next_warning_command = None
            if operator_items:
                for key in ("preferred_command", "command", "automation_command"):
                    command = operator_items[0].get(key)
                    if isinstance(command, str) and command:
                        expected_next_warning_command = command
                        break
            if progress_warning_review.get("next_command") != expected_next_warning_command:
                progress_warning_review_errors.append("warning_review.next_command")
            expected_pre_approval_review_sequence = [
                command
                for command in (
                    progress_warning_review.get("summary_json"),
                    progress_warning_review.get("review_artifacts_command"),
                )
                if operator_items and isinstance(command, str) and command
            ]
            if (
                progress_warning_review.get("pre_approval_review_sequence")
                != expected_pre_approval_review_sequence
            ):
                progress_warning_review_errors.append("warning_review.pre_approval_review_sequence")
            expected_review_sequence = [
                command
                for command in (
                    progress_warning_review.get("summary_json"),
                    progress_warning_review.get("review_artifacts_command"),
                    (
                        progress_warning_review.get("apply_command")
                        if any(item.get("id") == "warning_actions" for item in operator_items)
                        else None
                    ),
                )
                if operator_items and isinstance(command, str) and command
            ]
            if progress_warning_review.get("review_sequence") != expected_review_sequence:
                progress_warning_review_errors.append("warning_review.review_sequence")
    add_check(
        checks,
        check_id="handoff_release_status_progress_warning_review",
        label="Release status progress warning review metadata",
        status=(
            "skipped"
            if not has_command_artifacts
            else ("pass" if not progress_summary_error and not progress_warning_review_errors else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "release-status.json progress summary exposes warning review artifact/gate metadata."
                if not progress_summary_error and not progress_warning_review_errors
                else (
                    progress_summary_error
                    or "release-status.json progress_summary warning review metadata is missing or stale: "
                    + ", ".join(progress_warning_review_errors)
                )
            )
        ),
        evidence=str(release_status_json_path) if release_status_json_path.is_file() else None,
    )

    next_commands_by_owner = progress_summary.get("next_commands_by_owner") if progress_summary else None
    operator_next = (
        next_commands_by_owner.get("operator")
        if isinstance(next_commands_by_owner, dict)
        else None
    )
    connected_runner_next = (
        next_commands_by_owner.get("connected runner")
        if isinstance(next_commands_by_owner, dict)
        else None
    )
    owner_support_errors: list[str] = []
    if isinstance(connected_runner_next, dict) and connected_runner_next.get("id") in {
        "git_origin_remote",
        "docker_cli",
        "github_cli",
    }:
        supporting_commands = connected_runner_next.get("supporting_commands")
        if not isinstance(supporting_commands, dict):
            owner_support_errors.append(
                "release-status.json progress_summary.next_commands_by_owner.connected runner is missing "
                "supporting_commands."
            )
        else:
            expected_connected_runner_supporting = {
                "Show external readiness summary JSON": (
                    progress_commands.get("external_readiness_summary_json")
                    if isinstance(progress_commands, dict)
                    else None
                ),
                "Gate external readiness summary JSON": (
                    progress_commands.get("external_readiness_strict_summary_json")
                    if isinstance(progress_commands, dict)
                    else None
                ),
                "Show local readiness setup sequence": (
                    progress_commands.get("local_readiness_setup_sequence")
                    if isinstance(progress_commands, dict)
                    else None
                ),
                "Show local readiness command sequence": (
                    progress_commands.get("local_readiness_command_sequence")
                    if isinstance(progress_commands, dict)
                    else None
                ),
                "Preview local readiness setup sequence": (
                    progress_commands.get("local_readiness_setup_sequence_preview")
                    if isinstance(progress_commands, dict)
                    else None
                ),
                "Preview local readiness command sequence": (
                    progress_commands.get("local_readiness_command_sequence_preview")
                    if isinstance(progress_commands, dict)
                    else None
                ),
            }
            missing_connected_runner_supporting = [
                label
                for label, expected in expected_connected_runner_supporting.items()
                if not isinstance(expected, str) or supporting_commands.get(label) != expected
            ]
            if missing_connected_runner_supporting:
                owner_support_errors.append(
                    "release-status.json progress_summary connected-runner supporting command(s) missing or stale: "
                    + ", ".join(missing_connected_runner_supporting)
                )
    if isinstance(operator_next, dict) and operator_next.get("id") in {"warning_alerts", "warning_actions"}:
        supporting_commands = operator_next.get("supporting_commands")
        if not isinstance(supporting_commands, dict):
            owner_support_errors.append(
                "release-status.json progress_summary.next_commands_by_owner.operator is missing "
                "supporting_commands."
            )
        else:
            expected_operator_supporting = {
                "Show warning pre-approval sequence": (
                    progress_commands.get("warning_pre_approval_sequence")
                    if isinstance(progress_commands, dict)
                    else None
                ),
                "Show warning summary JSON": (
                    progress_commands.get("warning_summary_json")
                    if isinstance(progress_commands, dict)
                    else None
                ),
                "Gate warning summary JSON": (
                    progress_commands.get("warning_gate_summary_json")
                    if isinstance(progress_commands, dict)
                    else None
                ),
                "Show warning review artifact paths": (
                    progress_commands.get("warning_review_artifacts")
                    if isinstance(progress_commands, dict)
                    else None
                ),
                "Gate warning recommended next command": (
                    progress_commands.get("warning_next_command_gate")
                    if isinstance(progress_commands, dict)
                    else None
                ),
            }
            missing_operator_supporting = [
                label
                for label, expected in expected_operator_supporting.items()
                if not isinstance(expected, str) or supporting_commands.get(label) != expected
            ]
            if missing_operator_supporting:
                owner_support_errors.append(
                    "release-status.json progress_summary operator supporting command(s) missing or stale: "
                    + ", ".join(missing_operator_supporting)
                )
        review_artifacts = operator_next.get("review_artifacts")
        if not isinstance(review_artifacts, dict):
            owner_support_errors.append(
                "release-status.json progress_summary.next_commands_by_owner.operator is missing "
                "review_artifacts."
            )
        else:
            expected_review_artifacts = {
                "action_plan": str(package_dir / "release-warning-actions.md"),
                "operator_checklist": str(package_dir / "release-warning-operator-checklist.md"),
            }
            missing_review_artifacts = [
                label
                for label, expected in expected_review_artifacts.items()
                if review_artifacts.get(label) != expected
            ]
            if missing_review_artifacts:
                owner_support_errors.append(
                    "release-status.json progress_summary operator review artifact path(s) missing or stale: "
                    + ", ".join(missing_review_artifacts)
                )
    add_check(
        checks,
        check_id="handoff_release_status_owner_supporting_commands",
        label="Release status owner supporting commands",
        status=(
            "skipped"
            if not has_command_artifacts
            else ("pass" if not progress_summary_error and not owner_support_errors else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "release-status.json owner progress entries preserve connected-runner command-only/readiness helpers, warning review supporting commands, and review artifact paths."
                if not progress_summary_error and not owner_support_errors
                else (
                    progress_summary_error
                    or "; ".join(owner_support_errors)
                    or "Owner supporting commands are invalid."
                )
            )
        ),
        evidence=str(release_status_json_path) if release_status_json_path.is_file() else None,
    )

    progress_handoff_bundle_errors: list[str] = []
    progress_handoff_bundle = progress_summary.get("connected_runner_handoff_bundle") if progress_summary else None
    if isinstance(progress_handoff_bundle, str) and progress_handoff_bundle:
        expected_bundle_cd = f"cd {progress_handoff_bundle} &&"
        expected_source_cd = f"cd {progress_handoff_bundle}/source &&"
        bundle_command_checks = {}
        next_command = progress_summary.get("next_command") if progress_summary else None
        if isinstance(next_command, str) and "run-connected-runner-handoff.sh" in next_command:
            bundle_command_checks["next_command"] = next_command
        if isinstance(connected_runner_next, dict):
            connected_runner_command = connected_runner_next.get("command")
            connected_runner_full_flow = connected_runner_next.get("full_flow_command")
            if isinstance(connected_runner_command, str) and connected_runner_command:
                bundle_command_checks["connected_runner.command"] = connected_runner_command
            if isinstance(connected_runner_full_flow, str) and connected_runner_full_flow:
                bundle_command_checks["connected_runner.full_flow_command"] = connected_runner_full_flow
        for field, command in bundle_command_checks.items():
            if not isinstance(command, str) or expected_bundle_cd not in command:
                progress_handoff_bundle_errors.append(field)
        if isinstance(progress_local_readiness, dict):
            local_bundle_commands = []
            for field in ("next_setup_command",):
                value = progress_local_readiness.get(field)
                if isinstance(value, str):
                    local_bundle_commands.append((f"local_readiness.{field}", value))
            for field in ("setup_sequence", "verify_sequence", "command_sequence"):
                values = progress_local_readiness.get(field)
                if isinstance(values, list):
                    local_bundle_commands.extend(
                        (f"local_readiness.{field}", value)
                        for value in values
                        if isinstance(value, str) and value.startswith("cd ")
                    )
            for field, command in local_bundle_commands:
                if expected_source_cd not in command:
                    progress_handoff_bundle_errors.append(field)
        expected_verify_summary = (
            connected_runner_verify_summary_json_command(progress_handoff_bundle)
            if isinstance(progress_commands, dict)
            else None
        )
        expected_context_json = (
            connected_runner_handoff_context_json_command(progress_handoff_bundle)
            if isinstance(progress_commands, dict)
            else None
        )
        expected_command_sequence = (
            connected_runner_handoff_command_sequence_command(progress_handoff_bundle)
            if isinstance(progress_commands, dict)
            else None
        )
        if (
            not isinstance(progress_commands, dict)
            or progress_commands.get("handoff_bundle_verify_summary_json") != expected_verify_summary
        ):
            progress_handoff_bundle_errors.append("commands.handoff_bundle_verify_summary_json")
        if (
            not isinstance(progress_commands, dict)
            or progress_commands.get("handoff_context_json") != expected_context_json
        ):
            progress_handoff_bundle_errors.append("commands.handoff_context_json")
        if (
            not isinstance(progress_commands, dict)
            or progress_commands.get("handoff_command_sequence") != expected_command_sequence
        ):
            progress_handoff_bundle_errors.append("commands.handoff_command_sequence")
    add_check(
        checks,
        check_id="handoff_release_status_progress_handoff_bundle",
        label="Release status progress handoff bundle metadata",
        status=(
            "skipped"
            if not has_command_artifacts
            else ("pass" if not progress_summary_error and not progress_handoff_bundle_errors else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "release-status.json progress summary keeps connected-runner commands aligned with the handoff bundle path."
                if not progress_summary_error and not progress_handoff_bundle_errors
                else (
                    progress_summary_error
                    or "release-status.json progress_summary handoff bundle metadata is missing or stale: "
                    + ", ".join(progress_handoff_bundle_errors)
                )
            )
        ),
        evidence=str(release_status_json_path) if release_status_json_path.is_file() else None,
    )

    external_readiness_summary_json_commands = [
        path
        for path, fragment in fragments
        if external_readiness_summary_json_command() in fragment
    ]
    external_readiness_strict_summary_json_commands = [
        path
        for path, fragment in fragments
        if external_readiness_strict_summary_json_command() in fragment
    ]
    add_check(
        checks,
        check_id="handoff_external_readiness_summary_json_command",
        label="External readiness summary JSON command",
        status=(
            "skipped"
            if not has_command_artifacts
            else ("pass" if external_readiness_summary_json_commands else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "At least one generated external-readiness command prints compact summary JSON."
                if external_readiness_summary_json_commands
                else "No check_external_readiness.py --summary-json-only handoff command was available."
            )
        ),
        evidence=(
            describe_paths(external_readiness_summary_json_commands)
            if external_readiness_summary_json_commands
            else None
        ),
    )
    add_check(
        checks,
        check_id="handoff_external_readiness_strict_summary_json_command",
        label="External readiness strict summary JSON command",
        status=(
            "skipped"
            if not has_command_artifacts
            else ("pass" if external_readiness_strict_summary_json_commands else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "At least one generated external-readiness command gates connected-runner readiness while printing compact summary JSON."
                if external_readiness_strict_summary_json_commands
                else (
                    "No strict check_external_readiness.py --require-git-remote --require-docker "
                    "--require-gh --check-gh-auth --summary-json-only handoff command was available."
                )
            )
        ),
        evidence=(
            describe_paths(external_readiness_strict_summary_json_commands)
            if external_readiness_strict_summary_json_commands
            else None
        ),
    )

    release_evidence_json_commands = [
        path
        for path, fragment in fragments
        if "check_release_evidence.py" in fragment and "--json-only" in fragment
    ]
    add_check(
        checks,
        check_id="handoff_release_evidence_json_command",
        label="Release evidence JSON automation command",
        status=(
            "skipped"
            if not has_command_artifacts
            else ("pass" if release_evidence_json_commands else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "At least one generated release-evidence command prints JSON without writing files."
                if release_evidence_json_commands
                else "No check_release_evidence.py --json-only handoff command was available."
            )
        ),
        evidence=describe_paths(release_evidence_json_commands) if release_evidence_json_commands else None,
    )

    checksum_json_verify_commands = [
        path
        for path, fragment in fragments
        if "write_evidence_checksums.py" in fragment
        and "--verify" in fragment
        and "--json-only" in fragment
    ]
    add_check(
        checks,
        check_id="handoff_evidence_checksum_json_verify_command",
        label="Evidence checksum JSON verify command",
        status=(
            "skipped"
            if not has_command_artifacts
            else ("pass" if checksum_json_verify_commands else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "At least one generated checksum verification command prints JSON for automation."
                if checksum_json_verify_commands
                else "No write_evidence_checksums.py --verify --json-only handoff command was available."
            )
        ),
        evidence=describe_paths(checksum_json_verify_commands) if checksum_json_verify_commands else None,
    )

    handoff_verify_commands = [
        (path, fragment)
        for path, fragment in fragments
        if "package_connected_runner_handoff.py" in fragment and "--verify" in fragment
    ]
    handoff_verify_json_commands = [
        path
        for path, fragment in handoff_verify_commands
        if "--json-only" in fragment
    ]
    handoff_verify_summary_json_commands = [
        path
        for path, fragment in handoff_verify_commands
        if "--summary-json-only" in fragment
    ]
    add_check(
        checks,
        check_id="handoff_bundle_verify_json_command",
        label="Handoff bundle verify JSON command",
        status=(
            "skipped"
            if not has_command_artifacts or not handoff_verify_commands
            else ("pass" if handoff_verify_json_commands else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "No handoff bundle verify command artifact was available yet."
                if not handoff_verify_commands
                else (
                    "At least one generated handoff bundle verify command prints JSON for automation."
                    if handoff_verify_json_commands
                    else "Handoff bundle verify command(s) are missing --json-only."
                )
            )
        ),
        evidence=describe_paths(handoff_verify_json_commands) if handoff_verify_json_commands else None,
    )
    add_check(
        checks,
        check_id="handoff_bundle_verify_summary_json_command",
        label="Handoff bundle verify summary JSON command",
        status=(
            "skipped"
            if not has_command_artifacts or not handoff_verify_commands
            else ("pass" if handoff_verify_summary_json_commands else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "No handoff bundle verify command artifact was available yet."
                if not handoff_verify_commands
                else (
                    "At least one generated handoff bundle verify command prints compact summary JSON for automation."
                    if handoff_verify_summary_json_commands
                    else "Handoff bundle verify command(s) are missing --summary-json-only."
                )
            )
        ),
        evidence=(
            describe_paths(handoff_verify_summary_json_commands)
            if handoff_verify_summary_json_commands
            else None
        ),
    )

    acceptance_commands = [
        (path, fragment)
        for path, fragment in fragments
        if "connected_runner_acceptance.py" in fragment
    ]
    acceptance_json_commands = [
        path
        for path, fragment in acceptance_commands
        if "--json-only" in fragment
    ]
    acceptance_summary_json_commands = [
        path
        for path, fragment in acceptance_commands
        if "--summary-json-only" in fragment
    ]
    add_check(
        checks,
        check_id="handoff_connected_runner_acceptance_json_command",
        label="Connected-runner acceptance JSON command",
        status=(
            "skipped"
            if not has_command_artifacts or not acceptance_commands
            else ("pass" if acceptance_json_commands else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "No connected-runner acceptance command artifact was available yet."
                if not acceptance_commands
                else (
                    "At least one generated connected-runner acceptance command prints JSON for automation."
                    if acceptance_json_commands
                    else "Connected-runner acceptance command(s) are missing --json-only."
                )
            )
        ),
        evidence=describe_paths(acceptance_json_commands) if acceptance_json_commands else None,
    )
    add_check(
        checks,
        check_id="handoff_connected_runner_acceptance_summary_json_command",
        label="Connected-runner acceptance summary JSON command",
        status=(
            "skipped"
            if not has_command_artifacts or not acceptance_commands
            else ("pass" if acceptance_summary_json_commands else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "No connected-runner acceptance command artifact was available yet."
                if not acceptance_commands
                else (
                    "At least one generated connected-runner acceptance command prints compact summary JSON for automation."
                    if acceptance_summary_json_commands
                    else "Connected-runner acceptance command(s) are missing --summary-json-only."
                )
            )
        ),
        evidence=(
            describe_paths(acceptance_summary_json_commands)
            if acceptance_summary_json_commands
            else None
        ),
    )

    live_beta_commands = [
        (path, fragment)
        for path, fragment in fragments
        if "python3" in fragment and "archive_live_beta_closeout.py" in fragment
    ]
    unsafe_live_beta_paths = [
        path
        for path, fragment in live_beta_commands
        if LIVE_BETA_BACKUP_REFERENCE_EXAMPLE not in fragment
    ]
    add_check(
        checks,
        check_id="handoff_live_beta_backup_reference_example",
        label="Live-beta closeout backup reference",
        status=(
            "skipped"
            if not has_command_artifacts or not live_beta_commands
            else ("pass" if not unsafe_live_beta_paths else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "Live-beta closeout commands use the documented backup-reference example."
                if live_beta_commands and not unsafe_live_beta_paths
                else (
                    "No live-beta closeout command artifact was available yet."
                    if not live_beta_commands
                    else "Live-beta closeout command(s) are missing the documented backup-reference example: "
                    + describe_paths(unsafe_live_beta_paths)
                )
            )
        ),
        evidence=describe_paths(unsafe_live_beta_paths) if unsafe_live_beta_paths else None,
    )

    live_beta_preflight_json_paths = [
        path
        for path, fragment in live_beta_commands
        if "--preflight" in fragment and "--json" in fragment
    ]
    add_check(
        checks,
        check_id="handoff_live_beta_preflight_json_command",
        label="Live-beta preflight JSON command",
        status=(
            "skipped"
            if not has_command_artifacts or not live_beta_commands
            else ("pass" if live_beta_preflight_json_paths else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "No live-beta closeout command artifact was available yet."
                if not live_beta_commands
                else (
                    "At least one generated live-beta preflight command prints JSON for automation."
                    if live_beta_preflight_json_paths
                    else "Live-beta closeout command(s) are missing --preflight --json automation."
                )
            )
        ),
        evidence=describe_paths(live_beta_preflight_json_paths) if live_beta_preflight_json_paths else None,
    )

    expected_live_beta_support_commands = {
        "backend_start_local": LOCAL_BACKEND_START_COMMAND,
        "backend_start_local_no_reload": LOCAL_BACKEND_START_NO_RELOAD_COMMAND,
        "backend_start_docker": DOCKER_BACKEND_START_COMMAND,
        "backend_health_check": backend_health_check_command(),
    }
    missing_live_beta_support_names = [
        name
        for name, expected_command in expected_live_beta_support_commands.items()
        if not any(expected_command in fragment for _path, fragment in fragments)
    ]
    add_check(
        checks,
        check_id="handoff_live_beta_backend_support_commands",
        label="Live-beta backend support commands",
        status=(
            "skipped"
            if not has_command_artifacts or not live_beta_commands
            else ("pass" if not missing_live_beta_support_names else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "No live-beta closeout command artifact was available yet."
                if not live_beta_commands
                else (
                    "Generated live-beta handoff commands include backend start, no-reload fallback, and health-check commands."
                    if not missing_live_beta_support_names
                    else "Generated live-beta handoff commands are missing backend support command(s): "
                    + ", ".join(missing_live_beta_support_names)
                )
            )
        ),
        evidence=", ".join(missing_live_beta_support_names) if missing_live_beta_support_names else None,
    )

    expected_live_beta_commands = {
        "preflight": LIVE_BETA_PREFLIGHT_COMMAND,
        "preflight_json": LIVE_BETA_PREFLIGHT_JSON_COMMAND,
        "next_command_only": LIVE_BETA_NEXT_COMMAND_ONLY_COMMAND,
        "archive": LIVE_BETA_CLOSEOUT_COMMAND,
        "final_gate": LIVE_BETA_FINAL_GATE_COMMAND,
    }
    missing_live_beta_command_names = [
        name
        for name, expected_command in expected_live_beta_commands.items()
        if not any(expected_command in fragment for _path, fragment in fragments)
    ]
    add_check(
        checks,
        check_id="handoff_live_beta_command_builder_set",
        label="Live-beta shared command set",
        status=(
            "skipped"
            if not has_command_artifacts
            else ("pass" if not missing_live_beta_command_names else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "Generated live-beta handoff commands match the shared command builders."
                if not missing_live_beta_command_names
                else "Generated live-beta handoff commands are missing shared-builder command(s): "
                + ", ".join(missing_live_beta_command_names)
            )
        ),
        evidence=", ".join(missing_live_beta_command_names) if missing_live_beta_command_names else None,
    )

    unsafe_apply_paths = [
        path
        for path, fragment in fragments
        if "review_release_warnings.py" in fragment
        and "--apply" in fragment
        and "--operator-approved" not in fragment
    ]
    add_check(
        checks,
        check_id="handoff_warning_apply_operator_approval",
        label="Warning apply requires operator approval",
        status="skipped" if not has_command_artifacts else ("pass" if not unsafe_apply_paths else "fail"),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "Every generated warning apply command includes --operator-approved."
                if not unsafe_apply_paths
                else "Warning apply command(s) are missing --operator-approved: "
                + describe_paths(unsafe_apply_paths)
            )
        ),
        evidence=describe_paths(unsafe_apply_paths) if unsafe_apply_paths else None,
    )

    warning_json_commands = [
        (path, fragment)
        for path, fragment in fragments
        if "review_release_warnings.py" in fragment
        and "--json-only" in fragment
    ]
    warning_json_gate_paths = [
        path
        for path, fragment in warning_json_commands
        if "--fail-if-action-needed" in fragment
    ]
    add_check(
        checks,
        check_id="handoff_warning_json_action_gate",
        label="Warning JSON automation gates unresolved actions",
        status=(
            "skipped"
            if not has_command_artifacts or not warning_json_commands
            else ("pass" if warning_json_gate_paths else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "No warning JSON automation command artifact was available yet."
                if not warning_json_commands
                else (
                    "At least one generated warning JSON automation command includes --fail-if-action-needed."
                    if warning_json_gate_paths
                    else "Warning JSON automation command(s) are missing --fail-if-action-needed."
                )
            )
        ),
        evidence=describe_paths(warning_json_gate_paths) if warning_json_gate_paths else None,
    )

    expected_warning_summary_json_paths = [
        path
        for path, fragment in fragments
        if warning_review_summary_json_command(package_dir) in fragment
    ]
    expected_warning_summary_gate_paths = [
        path
        for path, fragment in fragments
        if warning_review_gate_summary_json_command(package_dir) in fragment
    ]
    expected_warning_pre_approval_sequence_paths = [
        path
        for path, fragment in fragments
        if warning_review_pre_approval_sequence_command(package_dir) in fragment
    ]
    add_check(
        checks,
        check_id="handoff_warning_summary_json",
        label="Warning summary JSON automation",
        status=(
            "skipped"
            if not has_command_artifacts
            else ("pass" if expected_warning_summary_json_paths else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "Generated warning handoff commands include compact summary JSON automation."
                if expected_warning_summary_json_paths
                else "Warning handoff command(s) are missing --summary-json-only automation."
            )
        ),
        evidence=(
            describe_paths(expected_warning_summary_json_paths)
            if expected_warning_summary_json_paths
            else None
        ),
    )
    add_check(
        checks,
        check_id="handoff_warning_summary_json_gate",
        label="Warning summary JSON action gate",
        status=(
            "skipped"
            if not has_command_artifacts
            else ("pass" if expected_warning_summary_gate_paths else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "Generated warning handoff commands include compact summary JSON with --fail-if-action-needed."
                if expected_warning_summary_gate_paths
                else "Warning compact summary JSON automation is missing --fail-if-action-needed."
            )
        ),
        evidence=(
            describe_paths(expected_warning_summary_gate_paths)
            if expected_warning_summary_gate_paths
            else None
        ),
    )
    add_check(
        checks,
        check_id="handoff_warning_pre_approval_sequence",
        label="Warning pre-approval review sequence",
        status=(
            "skipped"
            if not has_command_artifacts
            else ("pass" if expected_warning_pre_approval_sequence_paths else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "Generated warning handoff commands include an apply-free pre-approval review sequence."
                if expected_warning_pre_approval_sequence_paths
                else "Warning handoff command(s) are missing --pre-approval-sequence-only automation."
            )
        ),
        evidence=(
            describe_paths(expected_warning_pre_approval_sequence_paths)
            if expected_warning_pre_approval_sequence_paths
            else None
        ),
    )

    expected_warning_next_command_paths = [
        path
        for path, fragment in fragments
        if warning_review_next_command_only_command(package_dir) in fragment
    ]
    add_check(
        checks,
        check_id="handoff_warning_next_command_only",
        label="Warning recommended next command automation",
        status=(
            "skipped"
            if not has_command_artifacts
            else ("pass" if expected_warning_next_command_paths else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "Generated warning handoff commands include recommended-next command-only automation."
                if expected_warning_next_command_paths
                else "Warning handoff command(s) are missing --next-command-only automation."
            )
        ),
        evidence=describe_paths(expected_warning_next_command_paths) if expected_warning_next_command_paths else None,
    )

    expected_warning_next_gate_paths = [
        path
        for path, fragment in fragments
        if warning_review_next_command_gate_command(package_dir) in fragment
    ]
    add_check(
        checks,
        check_id="handoff_warning_next_command_gate",
        label="Warning recommended next command gate",
        status=(
            "skipped"
            if not has_command_artifacts
            else ("pass" if expected_warning_next_gate_paths else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "Generated warning handoff commands include command-only automation with --fail-if-action-needed."
                if expected_warning_next_gate_paths
                else "Warning recommended-next command automation is missing --fail-if-action-needed."
            )
        ),
        evidence=describe_paths(expected_warning_next_gate_paths) if expected_warning_next_gate_paths else None,
    )

    expected_warning_artifact_paths = [
        path
        for path, fragment in fragments
        if warning_review_artifacts_only_command(package_dir) in fragment
    ]
    add_check(
        checks,
        check_id="handoff_warning_review_artifacts_only",
        label="Warning review artifact path automation",
        status=(
            "skipped"
            if not has_command_artifacts
            else ("pass" if expected_warning_artifact_paths else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "Generated warning handoff commands include review-artifacts-only automation."
                if expected_warning_artifact_paths
                else "Warning handoff command(s) are missing --review-artifacts-only automation."
            )
        ),
        evidence=describe_paths(expected_warning_artifact_paths) if expected_warning_artifact_paths else None,
    )

    warning_actions_json_path = package_dir / "release-warning-actions.json"
    warning_backend_errors: list[str] = []
    if warning_actions_json_path.is_file():
        try:
            warning_actions_payload = read_json(warning_actions_json_path)
        except (OSError, json.JSONDecodeError) as exc:
            warning_backend_errors.append(f"release-warning-actions.json: {exc}")
        else:
            if isinstance(warning_actions_payload, dict):
                recommended_next = warning_actions_payload.get("recommended_next")
                recommended_requires_approval = (
                    isinstance(recommended_next, dict)
                    and recommended_next.get("requires_operator_approval") is True
                )
                if recommended_requires_approval:
                    expected_backend = expected_warning_backend_guidance()
                    if warning_actions_payload.get("backend") != expected_backend:
                        warning_backend_errors.append("backend")
                    if recommended_next.get("backend") != expected_backend:
                        warning_backend_errors.append("recommended_next.backend")
            else:
                warning_backend_errors.append("release-warning-actions.json payload")
    add_check(
        checks,
        check_id="handoff_warning_backend_guidance",
        label="Warning apply backend guidance",
        status=(
            "skipped"
            if not warning_actions_json_path.is_file()
            else ("pass" if not warning_backend_errors else "fail")
        ),
        message=(
            "release-warning-actions.json is not generated yet."
            if not warning_actions_json_path.is_file()
            else (
                "Warning action plan includes backend start and health-check guidance before approval-only apply."
                if not warning_backend_errors
                else "Warning action plan backend guidance is missing or stale: "
                + ", ".join(warning_backend_errors)
            )
        ),
        evidence=str(warning_actions_json_path) if warning_actions_json_path.is_file() else None,
    )

    local_readiness_json_commands = [
        (path, fragment)
        for path, fragment in fragments
        if "next_release_step.py" in fragment
        and "--json-only" in fragment
        and "--local-readiness" in fragment
    ]
    local_readiness_gate_paths = [
        path
        for path, fragment in local_readiness_json_commands
        if "--fail-if-local-readiness-not-pass" in fragment
    ]
    add_check(
        checks,
        check_id="handoff_local_readiness_json_gate",
        label="Local readiness JSON automation gates unresolved runner checks",
        status=(
            "skipped"
            if not has_command_artifacts or not local_readiness_json_commands
            else ("pass" if local_readiness_gate_paths else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "No local-readiness JSON automation command artifact was available yet."
                if not local_readiness_json_commands
                else (
                    "At least one generated local-readiness JSON automation command includes --fail-if-local-readiness-not-pass."
                    if local_readiness_gate_paths
                    else "Local-readiness JSON automation command(s) are missing --fail-if-local-readiness-not-pass."
                )
            )
        ),
        evidence=describe_paths(local_readiness_gate_paths) if local_readiness_gate_paths else None,
    )

    expected_local_readiness_command_gate_paths = [
        path
        for path, fragment in fragments
        if next_release_local_readiness_command_only_env_command(package_dir) in fragment
    ]
    add_check(
        checks,
        check_id="handoff_local_readiness_command_gate",
        label="Local readiness command-only gate",
        status=(
            "skipped"
            if not has_command_artifacts
            else ("pass" if expected_local_readiness_command_gate_paths else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "Generated handoff commands include command-only local-readiness automation with fail-closed gating."
                if expected_local_readiness_command_gate_paths
                else "Local-readiness command-only automation is missing fail-closed gating."
            )
        ),
        evidence=(
            describe_paths(expected_local_readiness_command_gate_paths)
            if expected_local_readiness_command_gate_paths
            else None
        ),
    )

    expected_local_readiness_setup_sequence_paths = [
        path
        for path, fragment in fragments
        if next_release_local_readiness_setup_sequence_env_command(package_dir) in fragment
    ]
    add_check(
        checks,
        check_id="handoff_local_readiness_setup_sequence",
        label="Local readiness setup sequence automation",
        status=(
            "skipped"
            if not has_command_artifacts
            else ("pass" if expected_local_readiness_setup_sequence_paths else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "Generated handoff commands include setup-sequence-only local-readiness automation."
                if expected_local_readiness_setup_sequence_paths
                else "Local-readiness setup-sequence-only automation is missing."
            )
        ),
        evidence=(
            describe_paths(expected_local_readiness_setup_sequence_paths)
            if expected_local_readiness_setup_sequence_paths
            else None
        ),
    )

    expected_local_readiness_command_sequence_paths = [
        path
        for path, fragment in fragments
        if next_release_local_readiness_command_sequence_env_command(package_dir) in fragment
    ]
    add_check(
        checks,
        check_id="handoff_local_readiness_command_sequence",
        label="Local readiness setup and verify sequence automation",
        status=(
            "skipped"
            if not has_command_artifacts
            else ("pass" if expected_local_readiness_command_sequence_paths else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "Generated handoff commands include setup-and-verify local-readiness automation."
                if expected_local_readiness_command_sequence_paths
                else "Local-readiness setup-and-verify automation is missing."
            )
        ),
        evidence=(
            describe_paths(expected_local_readiness_command_sequence_paths)
            if expected_local_readiness_command_sequence_paths
            else None
        ),
    )

    expected_local_readiness_setup_preview_paths = [
        path
        for path, fragment in fragments
        if next_release_local_readiness_setup_sequence_preview_command(package_dir) in fragment
    ]
    add_check(
        checks,
        check_id="handoff_local_readiness_setup_sequence_preview",
        label="Local readiness setup sequence preview",
        status=(
            "skipped"
            if not has_command_artifacts
            else ("pass" if expected_local_readiness_setup_preview_paths else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "Generated handoff commands include a non-gating setup-sequence preview."
                if expected_local_readiness_setup_preview_paths
                else "Local-readiness setup-sequence preview automation is missing."
            )
        ),
        evidence=(
            describe_paths(expected_local_readiness_setup_preview_paths)
            if expected_local_readiness_setup_preview_paths
            else None
        ),
    )

    expected_local_readiness_command_preview_paths = [
        path
        for path, fragment in fragments
        if next_release_local_readiness_command_sequence_preview_command(package_dir) in fragment
    ]
    add_check(
        checks,
        check_id="handoff_local_readiness_command_sequence_preview",
        label="Local readiness setup and verify sequence preview",
        status=(
            "skipped"
            if not has_command_artifacts
            else ("pass" if expected_local_readiness_command_preview_paths else "fail")
        ),
        message=(
            "Handoff command artifacts are not generated yet."
            if not has_command_artifacts
            else (
                "Generated handoff commands include a non-gating setup-and-verify preview."
                if expected_local_readiness_command_preview_paths
                else "Local-readiness setup-and-verify preview automation is missing."
            )
        ),
        evidence=(
            describe_paths(expected_local_readiness_command_preview_paths)
            if expected_local_readiness_command_preview_paths
            else None
        ),
    )

    return checks


def check_manifest(
    *,
    package_dir: Path,
    manifest: dict[str, Any],
    require_live_beta: bool,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    manifest_path = package_dir / "manifest.json"
    package_readme = package_dir / "README.md"

    add_check(
        checks,
        check_id="manifest_exists",
        label="Manifest exists",
        status="pass" if manifest_path.is_file() else "fail",
        message="manifest.json is present." if manifest_path.is_file() else "manifest.json is missing.",
        evidence=str(manifest_path),
    )
    add_check(
        checks,
        check_id="package_readme_exists",
        label="Package README exists",
        status="pass" if package_readme.is_file() else "fail",
        message="Package README is present." if package_readme.is_file() else "Package README is missing.",
        evidence=str(package_readme),
    )

    included_labels = {item.get("label") for item in manifest.get("included", [])}
    for label in REQUIRED_LABELS:
        add_check(
            checks,
            check_id=f"required_label_{label}",
            label=f"Required evidence: {label}",
            status="pass" if label in included_labels else "fail",
            message=f"{label} is included." if label in included_labels else f"{label} is missing.",
        )

    missing_labels = {item.get("label") for item in manifest.get("missing", [])}
    non_optional_missing = sorted(missing_labels - {"live_beta_archive"})
    if non_optional_missing:
        add_check(
            checks,
            check_id="non_optional_missing",
            label="No non-optional missing evidence",
            status="fail",
            message="Missing non-optional evidence: " + ", ".join(non_optional_missing),
        )
    else:
        add_check(
            checks,
            check_id="non_optional_missing",
            label="No non-optional missing evidence",
            status="pass",
            message="Only optional evidence is missing.",
        )

    live_beta_missing = "live_beta_archive" in missing_labels
    add_check(
        checks,
        check_id="live_beta_archive",
        label="Live beta archive",
        status="fail" if require_live_beta and live_beta_missing else ("warn" if live_beta_missing else "pass"),
        message=(
            "Live beta archive is missing."
            if live_beta_missing
            else "Live beta archive is included."
        ),
    )
    if not live_beta_missing:
        live_beta_items = included_by_label(manifest, "live_beta_archive")
        live_beta_path = Path(live_beta_items[0]["target"]) if live_beta_items else None
        expected_live_beta_files = (
            ("manifest.json", "Live beta archive manifest"),
            ("02-crypto-live-beta-drill.md", "Crypto live-beta drill Markdown"),
            ("03-strategy-health-handoff.md", "Strategy health handoff Markdown"),
            ("04-live-cutover-runbook.md", "Live cutover runbook Markdown"),
            ("05-live-window-closeout.md", "Live-window closeout Markdown"),
            ("raw-json/execution-settings.json", "Execution settings raw JSON"),
            ("raw-json/alert-review.json", "Alert review raw JSON"),
        )
        if live_beta_path is None:
            add_check(
                checks,
                check_id="live_beta_archive_target",
                label="Live beta archive target",
                status="fail",
                message="Live beta archive target is missing from the manifest.",
            )
        else:
            for relative_path, label in expected_live_beta_files:
                expected_path = live_beta_path / relative_path
                add_check(
                    checks,
                    check_id=f"live_beta_{relative_path.replace('/', '_').replace('.', '_')}",
                    label=label,
                    status="pass" if expected_path.is_file() else "fail",
                    message=(
                        f"{relative_path} is present in the live-beta archive."
                        if expected_path.is_file()
                        else f"{relative_path} is missing from the live-beta archive."
                    ),
                    evidence=str(expected_path),
                )
            archive_manifest_path = live_beta_path / "manifest.json"
            if archive_manifest_path.is_file():
                try:
                    archive_manifest = read_json(archive_manifest_path)
                except (OSError, json.JSONDecodeError) as exc:
                    add_check(
                        checks,
                        check_id="live_beta_archive_manifest_readable",
                        label="Live beta archive manifest readable",
                        status="fail",
                        message=f"Live beta archive manifest is unreadable: {exc}",
                        evidence=str(archive_manifest_path),
                    )
                else:
                    safety = archive_manifest.get("safety", {})
                    live_locked = (
                        archive_manifest.get("status") == "pass"
                        and safety.get("live_trading_enabled") is False
                        and safety.get("adapter_ready") is False
                        and safety.get("blocking_alert_count") == 0
                    )
                    add_check(
                        checks,
                        check_id="live_beta_archive_safety",
                        label="Live beta archive safety manifest",
                        status="pass" if live_locked else "fail",
                        message=(
                            "Live beta archive confirms live flags are locked and blocking alerts are clear."
                            if live_locked
                            else "Live beta archive safety manifest is not clean."
                        ),
                        evidence=str(archive_manifest_path),
                    )

    paths = target_paths(manifest)
    for suffix in REQUIRED_DOC_SUFFIXES:
        matched = any(str(path).endswith(suffix) and path.exists() for path in paths)
        add_check(
            checks,
            check_id=f"doc_{suffix.replace('/', '_')}",
            label=f"Document included: {suffix}",
            status="pass" if matched else "fail",
            message=f"{suffix} is included." if matched else f"{suffix} is missing.",
        )

    safety = manifest.get("safety", {})
    safety_expected = {
        "env_file_excluded": True,
        "live_trading_enabled_by_script": False,
        "stock_etf_live_routing_enabled": False,
    }
    for key, expected in safety_expected.items():
        actual = safety.get(key)
        add_check(
            checks,
            check_id=f"safety_{key}",
            label=f"Safety manifest: {key}",
            status="pass" if actual is expected else "fail",
            message=f"{key}={actual!r}; expected {expected!r}.",
        )

    env_file = package_dir / "06-runbooks-and-docs" / ".env"
    add_check(
        checks,
        check_id="env_file_absent",
        label="Secret env file excluded",
        status="pass" if not env_file.exists() else "fail",
        message=".env is absent from the evidence package." if not env_file.exists() else ".env is present in the evidence package.",
        evidence=str(env_file),
    )

    return checks


def check_verification(package_dir: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    verification_items = included_by_label(manifest, "verification_summary")
    verification_path = Path(verification_items[0]["target"]) if verification_items else None
    status = manifest.get("latest_verification_status")
    add_check(
        checks,
        check_id="manifest_verification_status",
        label="Manifest verification status",
        status="pass" if status == "pass" else "fail",
        message=f"Manifest verification status is {status!r}.",
    )
    if verification_path is None or not verification_path.is_file():
        add_check(
            checks,
            check_id="verification_file_readable",
            label="Verification file readable",
            status="fail",
            message="Verification summary file is missing.",
        )
        return checks

    payload = read_json(verification_path)
    payload_status = payload.get("status")
    add_check(
        checks,
        check_id="verification_file_status",
        label="Verification file status",
        status="pass" if payload_status == "pass" else "fail",
        message=f"Verification file status is {payload_status!r}.",
        evidence=str(verification_path),
    )
    failed_checks = [
        item.get("name")
        for item in payload.get("checks", [])
        if item.get("status") not in {"pass", "skipped"}
    ]
    add_check(
        checks,
        check_id="verification_subchecks",
        label="Verification subchecks",
        status="pass" if not failed_checks else "fail",
        message=(
            "All verification subchecks passed or were explicitly skipped."
            if not failed_checks
            else "Failed verification subchecks: " + ", ".join(str(item) for item in failed_checks)
        ),
        evidence=str(verification_path),
    )
    return checks


def check_external_readiness(package_dir: Path) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    readiness_path = first_existing_glob(package_dir, "00-external-readiness/**/external-readiness.json")
    add_check(
        checks,
        check_id="external_readiness_summary",
        label="External readiness summary",
        status="pass" if readiness_path else "fail",
        message=(
            "External readiness summary is present."
            if readiness_path
            else "External readiness summary is missing."
        ),
        evidence=str(readiness_path) if readiness_path else None,
    )
    if readiness_path is None:
        return checks
    payload = read_json(readiness_path)
    readiness_status = payload.get("status")
    add_check(
        checks,
        check_id="external_readiness_status",
        label="External readiness status",
        status="fail" if readiness_status == "fail" else ("warn" if readiness_status == "warn" else "pass"),
        message=f"External readiness status is {readiness_status!r}.",
        evidence=str(readiness_path),
    )
    return checks


def check_ops_smoke(package_dir: Path) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    summary_path = first_existing_glob(package_dir, "02-ops-smoke/**/ops-smoke-summary.json")
    execution_path = first_existing_glob(package_dir, "02-ops-smoke/**/execution_settings.json")
    alert_path = first_existing_glob(package_dir, "02-ops-smoke/**/alert_review.json")

    add_check(
        checks,
        check_id="ops_smoke_summary",
        label="Ops smoke summary",
        status="pass" if summary_path else "fail",
        message="Ops smoke summary is present." if summary_path else "Ops smoke summary is missing.",
        evidence=str(summary_path) if summary_path else None,
    )
    add_check(
        checks,
        check_id="execution_settings",
        label="Execution settings evidence",
        status="pass" if execution_path else "fail",
        message="Execution settings evidence is present." if execution_path else "Execution settings evidence is missing.",
        evidence=str(execution_path) if execution_path else None,
    )
    if execution_path:
        execution = read_json(execution_path)
        live_locked = (
            execution.get("live_trading_enabled") is False
            and execution.get("live_ack_configured") is False
            and execution.get("adapter_ready") is False
        )
        add_check(
            checks,
            check_id="live_lock",
            label="Live trading lock",
            status="pass" if live_locked else "fail",
            message=(
                "Live trading flag, ACK, and adapter readiness are locked."
                if live_locked
                else "Live trading lock evidence is not safe."
            ),
            evidence=str(execution_path),
        )

    add_check(
        checks,
        check_id="alert_review",
        label="Alert review evidence",
        status="pass" if alert_path else "fail",
        message="Alert review evidence is present." if alert_path else "Alert review evidence is missing.",
        evidence=str(alert_path) if alert_path else None,
    )
    if alert_path:
        alert_review = read_json(alert_path)
        items = alert_review.get("items", [])
        blocking_items = [
            item
            for item in items
            if item.get("level") in {"error", "halt"}
            or item.get("source") in {"paper_session_halt"}
        ]
        warning_count = sum(1 for item in items if item.get("level") == "warning")
        add_check(
            checks,
            check_id="blocking_alerts",
            label="No blocking alerts",
            status="pass" if not blocking_items else "fail",
            message=(
                "No halt/error alerts are present."
                if not blocking_items
                else f"{len(blocking_items)} halt/error alert(s) are present."
            ),
            evidence=str(alert_path),
        )
        add_check(
            checks,
            check_id="warning_alerts",
            label="Warning alerts",
            status="warn" if warning_count else "pass",
            message=(
                f"{warning_count} warning alert(s) need operator review."
                if warning_count
                else "No warning alerts are present."
            ),
            evidence=str(alert_path),
        )

    return checks


def check_crypto_drill(package_dir: Path) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    drill_json = first_existing_glob(package_dir, "03-crypto-drill/**/crypto-live-beta-drill.json")
    runbooks_json = first_existing_glob(package_dir, "03-crypto-drill/**/runbooks.json")
    dry_run_queue = first_existing_glob(package_dir, "03-crypto-drill/**/dry-run-queue.json")
    drill_markdown = first_existing_glob(package_dir, "03-crypto-drill/**/crypto-live-beta-drill*.md")

    for check_id, label, path in (
        ("crypto_drill_json", "Crypto drill JSON", drill_json),
        ("crypto_drill_markdown", "Crypto drill Markdown", drill_markdown),
        ("dry_run_queue", "Dry-run queue evidence", dry_run_queue),
        ("dry_run_runbooks", "Dry-run runbooks evidence", runbooks_json),
    ):
        add_check(
            checks,
            check_id=check_id,
            label=label,
            status="pass" if path else "fail",
            message=f"{label} is present." if path else f"{label} is missing.",
            evidence=str(path) if path else None,
        )

    if drill_json:
        payload = read_json(drill_json)
        markdown = payload.get("markdown", "")
        safe_boundary = (
            isinstance(markdown, str)
            and "no live order submission" in markdown.lower()
            and "stock/etf" in markdown.lower()
        )
        add_check(
            checks,
            check_id="crypto_drill_safety_boundary",
            label="Crypto drill safety boundary",
            status="pass" if safe_boundary else "fail",
            message=(
                "Crypto drill states no live submission and excludes stock/ETF routes."
                if safe_boundary
                else "Crypto drill safety boundary text was not found."
            ),
            evidence=str(drill_json),
        )

    return checks


def alert_recommendation(alert: dict[str, Any]) -> str:
    source = alert.get("source")
    rule = alert.get("rule")
    if source == "broker_paper_submission":
        return (
            "Confirm this was an intentional paper-only broker submission block. "
            "For Alpaca paper testing, rerun the evaluation with paper_submit_confirmation=true; "
            "otherwise acknowledge the warning as an expected guardrail."
        )
    if source == "paper_fill_drift" or rule == "paper_fill_quality_watch":
        return (
            "Keep the stock/ETF route in paper review, collect at least three linked paper fill notes, "
            "and approve handoff only after the paper fill quality gate becomes ready."
        )
    if source == "paper_session_risk":
        return "Review paper-session drawdown, exposure, and guardrails before promoting the strategy."
    if source == "portfolio_scan":
        return "Review the saved scenario scan result and confirm the threshold breach is understood."
    return "Review the alert in the dashboard or operations journal and record an operator decision."


def write_warning_triage(package_dir: Path, checks: list[dict[str, Any]], *, write: bool = True) -> dict[str, Any]:
    alert_path = first_existing_glob(package_dir, "02-ops-smoke/**/alert_review.json")
    warning_checks = [check for check in checks if check.get("status") == "warn"]
    alert_items: list[dict[str, Any]] = []
    if alert_path:
        alert_review = read_json(alert_path)
        raw_items = alert_review.get("items", [])
        if isinstance(raw_items, list):
            alert_items = [item for item in raw_items if item.get("level") == "warning"]

    live_beta_missing = any(check.get("id") == "live_beta_archive" and check.get("status") == "warn" for check in checks)
    triage = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "package_dir": str(package_dir),
        "status": "review_required" if warning_checks or alert_items or live_beta_missing else "clear",
        "summary": {
            "warning_checks": len(warning_checks),
            "warning_alerts": len(alert_items),
            "live_beta_archive_missing": live_beta_missing,
        },
        "live_beta_archive": {
            "status": "missing" if live_beta_missing else "present_or_not_required",
            "recommended_action": (
                "Expected before a real live-beta closeout. Keep this as a warning during preparation; "
                "after a live window, store the closeout archive under artifacts/live-beta/ and rerun with --require-live-beta."
                if live_beta_missing
                else "No live-beta archive warning was reported."
            ),
        },
        "warning_checks": warning_checks,
        "warning_alerts": [
            {
                "id": item.get("id"),
                "source": item.get("source"),
                "rule": item.get("rule"),
                "symbol": item.get("symbol"),
                "title": item.get("title"),
                "message": item.get("message"),
                "created_at": item.get("created_at"),
                "evaluation_id": item.get("evaluation_id"),
                "session_id": item.get("session_id"),
                "recommended_action": alert_recommendation(item),
            }
            for item in alert_items
        ],
    }

    json_path = package_dir / "release-warning-triage.json"
    markdown_path = package_dir / "release-warning-triage.md"

    lines = [
        "# Release Warning Triage",
        "",
        f"Generated at: {triage['generated_at']}",
        f"Package: {package_dir}",
        f"Status: {triage['status']}",
        "",
        "## Summary",
        "",
        f"- Warning checks: {triage['summary']['warning_checks']}",
        f"- Warning alerts: {triage['summary']['warning_alerts']}",
        f"- Live beta archive missing: {'yes' if live_beta_missing else 'no'}",
        "",
        "## Live Beta Archive",
        "",
        f"- Status: {triage['live_beta_archive']['status']}",
        f"- Recommended action: {triage['live_beta_archive']['recommended_action']}",
        "",
        "## Warning Alerts",
        "",
    ]
    if not triage["warning_alerts"]:
        lines.append("- No warning alerts were present.")
    else:
        for index, alert in enumerate(triage["warning_alerts"], start=1):
            lines.extend(
                [
                    f"### {index}. {alert.get('title') or alert.get('id')}",
                    "",
                    f"- Alert id: {alert.get('id')}",
                    f"- Source: {alert.get('source')}",
                    f"- Rule: {alert.get('rule')}",
                    f"- Symbol: {alert.get('symbol')}",
                    f"- Message: {alert.get('message')}",
                    f"- Recommended action: {alert.get('recommended_action')}",
                    "",
                ]
            )
    if write:
        json_path.write_text(json.dumps(triage, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        markdown_path.write_text("\n".join(lines), encoding="utf-8")
        triage["json_path"] = str(json_path)
        triage["markdown_path"] = str(markdown_path)
    else:
        triage["json_path"] = None
        triage["markdown_path"] = None
        triage["write_skipped"] = True
    return triage


def refresh_tarball(package_dir: Path, manifest: dict[str, Any]) -> None:
    tarball = manifest.get("tarball")
    if not isinstance(tarball, str) or not tarball:
        return
    tarball_path = Path(tarball)
    with tarfile.open(tarball_path, "w:gz") as tar:
        tar.add(package_dir, arcname=package_dir.name)


def main() -> int:
    args = parse_args()
    read_only = args.no_write or args.json_only
    if read_only and args.output:
        raise SystemExit("--output cannot be used with --no-write or --json-only.")
    package_dir = Path(args.package_dir) if args.package_dir else latest_manifest_package_dir(Path(args.packages_dir))
    package_dir = package_dir.absolute()
    manifest_path = package_dir / "manifest.json"
    manifest = read_json(manifest_path)

    checks: list[dict[str, Any]] = []
    checks.extend(
        check_manifest(
            package_dir=package_dir,
            manifest=manifest,
            require_live_beta=args.require_live_beta,
        )
    )
    checks.extend(check_verification(package_dir, manifest))
    checks.extend(check_external_readiness(package_dir))
    checks.extend(check_ops_smoke(package_dir))
    checks.extend(check_crypto_drill(package_dir))
    checks.extend(check_handoff_command_safety(package_dir))

    has_failures = any(check["status"] == "fail" for check in checks)
    has_warnings = any(check["status"] == "warn" for check in checks)
    status = "fail" if has_failures else ("warn" if has_warnings else "pass")
    warning_triage = write_warning_triage(package_dir, checks, write=not read_only)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "package_dir": str(package_dir),
        "status": status,
        "warning_triage": {
            "json_path": warning_triage.get("json_path"),
            "markdown_path": warning_triage.get("markdown_path"),
            "status": warning_triage.get("status"),
            "write_skipped": bool(warning_triage.get("write_skipped")),
        },
        "checks": checks,
    }
    output_path = Path(args.output) if args.output else package_dir / "release-evidence-check.json"
    if args.json_only:
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 1 if has_failures else 0

    if not args.no_write:
        output_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if not args.no_write and not args.no_refresh_tarball:
        refresh_tarball(package_dir, manifest)

    for check in checks:
        print(f"{check['status'].upper():5} {check['id']}: {check['message']}")
    if args.no_write:
        print("Warning triage: not written (--no-write)")
        print("Release evidence check: not written (--no-write)")
    else:
        print(f"Warning triage: {warning_triage.get('markdown_path')}")
        print(f"Release evidence check: {output_path}")
    return 1 if has_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
