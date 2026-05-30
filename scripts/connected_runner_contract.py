"""Shared connected-runner script contract checks."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping

try:
    from scripts.handoff_commands import (
        CONNECTED_STRICT_GATE_COMMAND,
        ENV_REPO_URL_PLACEHOLDER,
        GENERIC_REPO_URL_PLACEHOLDER,
        LEGACY_REPO_URL_PLACEHOLDER,
        REPO_URL_PLACEHOLDER,
        format_completion_deduction,
    )
except ModuleNotFoundError:  # pragma: no cover - supports running from scripts/
    from handoff_commands import (
        CONNECTED_STRICT_GATE_COMMAND,
        ENV_REPO_URL_PLACEHOLDER,
        GENERIC_REPO_URL_PLACEHOLDER,
        LEGACY_REPO_URL_PLACEHOLDER,
        REPO_URL_PLACEHOLDER,
        format_completion_deduction,
    )


RUNNER_REMOTE_VALIDATE_CALL_MARKER = "\nvalidate_git_origin_url\n\nBRANCH_NAME="
REQUIRED_GITIGNORE_PATTERNS: tuple[str, ...] = (
    ".env",
    ".venv/",
    "node_modules/",
    "dist/",
    ".vite/",
    "data/",
    "artifacts/",
    "backups/",
    "*.duckdb",
    "*.parquet",
)

PACKAGED_SOURCE_EXCLUDED_NAMES: tuple[str, ...] = (
    ".DS_Store",
    ".env",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "artifacts",
    "backups",
    "data",
    "dist",
    "node_modules",
)

FORBIDDEN_SOURCE_PARTS: tuple[str, ...] = (
    ".env",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "backups",
    "data",
)
FORBIDDEN_SOURCE_SUFFIXES: tuple[str, ...] = (".duckdb", ".parquet", ".pyc")


def compact_check_summary(report: Mapping[str, Any]) -> dict[str, Any]:
    checks = report.get("checks")
    if not isinstance(checks, list):
        checks = []

    counts = {"pass": 0, "warn": 0, "fail": 0, "other": 0}
    warnings: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []

    for check in checks:
        if not isinstance(check, Mapping):
            counts["other"] += 1
            continue
        status = str(check.get("status", "other"))
        if status in counts:
            counts[status] += 1
        else:
            counts["other"] += 1

        if status not in {"warn", "fail"}:
            continue
        item = {
            "id": str(check.get("id", "")),
            "message": str(check.get("message", "")),
        }
        label = check.get("label")
        if label:
            item["label"] = str(label)
        evidence = check.get("evidence")
        if evidence:
            item["evidence"] = str(evidence)
        if status == "warn":
            warnings.append(item)
        else:
            failures.append(item)

    return {
        "status": str(report.get("status", "unknown")),
        "check_count": len(checks),
        "counts": counts,
        "warnings": warnings,
        "failures": failures,
    }

RUNNER_SCRIPT_MARKERS: tuple[str, ...] = (
    "require_command git",
    "require_command python3",
    "require_command npm",
    "require_command docker",
    "require_command gh",
    "docker compose version >/dev/null",
    "gh auth status >/dev/null",
    "gh auth setup-git",
    "SETUP_GH_GIT_AUTH=false",
    "GitHub CLI git credential setup failed",
    "package_connected_runner_handoff.py\" --verify",
    "git ls-remote",
    "GIT_ORIGIN_URL must be an HTTPS, SSH, or scp-style git remote URL",
    "GIT_ORIGIN_URL must be a real remote URL",
    "GIT_ORIGIN_URL must be a real remote URL, not a placeholder value",
    REPO_URL_PLACEHOLDER,
    "validate_git_origin_url",
    RUNNER_REMOTE_VALIDATE_CALL_MARKER,
    "remote_path_without_slashes",
    "PREFLIGHT_ONLY",
    "preflight-only flow finished",
)

RUNNER_SCRIPT_ORDER_RULES: tuple[tuple[str, str, str], ...] = (
    (
        "missing_remote_guard_before_command_preflight",
        'if [ -z "${GIT_ORIGIN_URL:-}" ]; then',
        "require_command git",
    ),
    (
        "placeholder_remote_guard_before_command_preflight",
        f'if [ "${{GIT_ORIGIN_URL}}" = "{REPO_URL_PLACEHOLDER}" ] || [ "${{GIT_ORIGIN_URL}}" = "{LEGACY_REPO_URL_PLACEHOLDER}" ]; then',
        "require_command git",
    ),
    (
        "literal_placeholder_remote_guard_before_command_preflight",
        f'if [ "${{GIT_ORIGIN_URL}}" = "{GENERIC_REPO_URL_PLACEHOLDER}" ] || [ "${{GIT_ORIGIN_URL}}" = "{ENV_REPO_URL_PLACEHOLDER}" ]; then',
        "require_command git",
    ),
    (
        "remote_format_guard_before_command_preflight",
        'case "${GIT_ORIGIN_URL}" in',
        "require_command git",
    ),
    (
        "remote_validate_call_before_command_preflight",
        RUNNER_REMOTE_VALIDATE_CALL_MARKER,
        "require_command git",
    ),
    (
        "python_preflight_before_bundle_self_verify",
        "require_command python3",
        'python3 "${SOURCE_DIR}/scripts/package_connected_runner_handoff.py" --verify "${SCRIPT_DIR}"',
    ),
    (
        "bundle_self_verify_before_external_preflight",
        'python3 "${SOURCE_DIR}/scripts/package_connected_runner_handoff.py" --verify "${SCRIPT_DIR}"',
        "docker compose version >/dev/null",
    ),
    (
        "remote_reachability_before_remote_add",
        'git ls-remote "${GIT_ORIGIN_URL}" >/dev/null',
        'git remote add origin "${GIT_ORIGIN_URL}"',
    ),
    (
        "auth_preflight_before_dependency_install",
        "gh auth status >/dev/null",
        "python3 -m venv backend/.venv",
    ),
    (
        "gh_git_auth_setup_before_remote_reachability",
        "gh auth setup-git >/dev/null",
        'git ls-remote "${GIT_ORIGIN_URL}" >/dev/null',
    ),
    (
        "remote_reachability_before_dependency_install",
        'git ls-remote "${GIT_ORIGIN_URL}" >/dev/null',
        "python3 -m venv backend/.venv",
    ),
    (
        "acceptance_before_dependency_install",
        "python3 scripts/connected_runner_acceptance.py --handoff-root .. --require-external --check-gh-auth",
        "python3 -m venv backend/.venv",
    ),
    (
        "preflight_only_exit_before_dependency_install",
        'if [ "${PREFLIGHT_ONLY}" = "true" ]; then',
        "python3 -m venv backend/.venv",
    ),
    (
        "dependency_install_before_push",
        "npm ci --prefix frontend",
        'git push -u origin "${BRANCH_NAME}"',
    ),
    (
        "strict_gate_after_push",
        'git push -u origin "${BRANCH_NAME}"',
        CONNECTED_STRICT_GATE_COMMAND,
    ),
)

RUNNER_REMOTE_GUARD_CASES: tuple[tuple[str, str | None, str], ...] = (
    ("missing", None, "Set GIT_ORIGIN_URL to the target git remote URL before running this script."),
    ("placeholder", REPO_URL_PLACEHOLDER, "GIT_ORIGIN_URL must be a real remote URL"),
    ("legacy_placeholder", LEGACY_REPO_URL_PLACEHOLDER, "GIT_ORIGIN_URL must be a real remote URL"),
    ("placeholder_repo_url", GENERIC_REPO_URL_PLACEHOLDER, "GIT_ORIGIN_URL must be a real remote URL"),
    ("placeholder_env_name", ENV_REPO_URL_PLACEHOLDER, "GIT_ORIGIN_URL must be a real remote URL"),
    ("invalid_format", "not-a-url", "GIT_ORIGIN_URL must be an HTTPS, SSH, or scp-style git remote URL"),
    ("missing_https_host", "https:///example/quant-lab.git", "GIT_ORIGIN_URL must be an HTTPS, SSH, or scp-style git remote URL"),
    ("missing_ssh_host", "ssh:///example/quant-lab.git", "GIT_ORIGIN_URL must be an HTTPS, SSH, or scp-style git remote URL"),
    ("missing_scp_host", "git@:example/quant-lab.git", "GIT_ORIGIN_URL must be an HTTPS, SSH, or scp-style git remote URL"),
    ("missing_remote_path", "https://github.com/", "GIT_ORIGIN_URL must be an HTTPS, SSH, or scp-style git remote URL"),
)


def missing_runner_script_markers(script_text: str) -> list[str]:
    return [marker for marker in RUNNER_SCRIPT_MARKERS if marker not in script_text]


def expected_handoff_completion_context_markers(release_status: dict[str, Any]) -> list[str]:
    readiness = release_status.get("readiness_estimate") or {}
    markers = [
        f"- Overall status: `{release_status.get('status', 'unknown')}`",
        f"- Approximate completion: `{readiness.get('percent', 'unknown')}%`",
        f"- Remaining handoff items: `{readiness.get('remaining_items', 'unknown')}`",
    ]
    for deduction in readiness.get("deductions") or []:
        markers.append(format_completion_deduction(deduction, code_id=True))
    progress_summary = release_status.get("progress_summary")
    requirements = progress_summary.get("completion_requirements") if isinstance(progress_summary, dict) else None
    if isinstance(requirements, list):
        for requirement in requirements:
            if not isinstance(requirement, Mapping):
                continue
            name = str(requirement.get("requirement") or "unknown")
            item_ids = requirement.get("item_ids")
            owners = requirement.get("owners")
            item_list = [str(item_id) for item_id in item_ids] if isinstance(item_ids, list) else []
            owner_list = [str(owner) for owner in owners] if isinstance(owners, list) else []
            raw_count = requirement.get("count")
            count = raw_count if isinstance(raw_count, int) else len(item_list)
            item_word = "item" if count == 1 else "items"
            owner_text = ", ".join(owner_list) if owner_list else "unassigned"
            item_text = ", ".join(item_list) if item_list else "none"
            markers.append(f"`{name}`: {count} {item_word} [{owner_text}] items: {item_text}")
    return markers


def handoff_completion_context_summary_lines(release_status: dict[str, Any]) -> list[str]:
    markers = expected_handoff_completion_context_markers(release_status)
    lines = markers[:3]
    readiness = release_status.get("readiness_estimate") or {}
    deductions = readiness.get("deductions") or []
    deduction_count = len(deductions)
    deduction_markers = markers[3 : 3 + deduction_count]
    requirement_markers = markers[3 + deduction_count :]
    if deduction_markers:
        lines.append("- Completion deductions:")
        lines.extend(f"  - {marker}" for marker in deduction_markers)
    else:
        lines.append("- Completion deductions: none listed.")
    if requirement_markers:
        lines.append("- Completion requirements:")
        lines.extend(f"  - {marker}" for marker in requirement_markers)
    else:
        lines.append("- Completion requirements: none listed.")
    return lines


def verify_handoff_completion_context(
    readme_text: str,
    release_status: dict[str, Any] | None,
) -> tuple[bool, str, dict[str, Any]]:
    if not isinstance(release_status, dict):
        return (
            False,
            "HANDOFF.md completion context could not be checked because release-status.json is missing or invalid.",
            {"missing_markers": [], "expected_markers": []},
        )
    expected_markers = expected_handoff_completion_context_markers(release_status)
    missing_markers = [marker for marker in expected_markers if marker not in readme_text]
    return (
        not missing_markers,
        (
            "HANDOFF.md completion context matches copied release-status.json."
            if not missing_markers
            else "HANDOFF.md completion context is missing release-status marker(s): "
            + ", ".join(missing_markers)
        ),
        {
            "missing_markers": missing_markers,
            "expected_markers": expected_markers,
        },
    )


def append_command_payload_check(
    checks: list[dict[str, Any]],
    *,
    check_id: str,
    expected: str,
    actual: Any = None,
    contains_text: str | None = None,
) -> None:
    if contains_text is not None:
        passed = expected in contains_text
        checks.append(
            {
                "id": check_id,
                "status": "pass" if passed else "fail",
                "expected": expected,
                "actual": "present" if passed else "missing",
            }
        )
        return

    passed = actual == expected
    checks.append(
        {
            "id": check_id,
            "status": "pass" if passed else "fail",
            "expected": expected,
            "actual": actual,
        }
    )


def append_progress_summary_checks(
    checks: list[dict[str, Any]],
    *,
    payload: dict[str, Any],
    expected_preflight: str,
    expected_next_command_only: str,
    expected_next_json_only: str,
    expected_connected_command_only: str,
    expected_connected_command_sequence: str,
    expected_operator_command_only: str,
    expected_operator_command_sequence: str,
    expected_operator_review_sequence: str,
    expected_operator_json_only: str,
    expected_remaining_sequence: str,
    expected_progress_json: str,
    expected_completion_plan: str,
    expected_completion_plan_json: str,
    expected_completion_requirements: str,
    expected_completion_requirements_json: str,
    expected_handoff_context_json: str | None,
    expected_handoff_command_sequence: str | None,
    expected_local_readiness_setup_sequence: str,
    expected_local_readiness_command_sequence: str,
    expected_local_readiness_setup_sequence_preview: str,
    expected_local_readiness_command_sequence_preview: str,
    expected_external_readiness_summary_json: str,
    expected_external_readiness_strict_summary_json: str,
    expected_warning_gate_json: str,
    expected_warning_summary_json: str,
    expected_warning_gate_summary_json: str,
    expected_warning_review_artifacts_only: str,
    expected_warning_review_next_command_gate: str,
    expected_warning_action_plan_path: str,
    expected_warning_operator_checklist_path: str,
    expected_operator_command: str,
    expected_owner_lanes: str | None = None,
    expected_owner_lanes_json: str | None = None,
) -> None:
    progress_summary = payload.get("progress_summary")
    if not isinstance(progress_summary, dict):
        checks.append(
            {
                "id": "release_status_json_progress_summary",
                "status": "fail",
                "expected": "object",
                "actual": type(progress_summary).__name__,
            }
        )
        return

    required_fields = [
        "next_command",
        "next_item_id",
        "next_item_owner",
        "next_commands_by_owner",
        "owner_lanes",
        "commands",
    ]
    for field in required_fields:
        checks.append(
            {
                "id": f"release_status_json_progress_summary_{field}",
                "status": "pass" if field in progress_summary else "fail",
                "expected": "present",
                "actual": "present" if field in progress_summary else "missing",
            }
        )

    commands = progress_summary.get("commands")
    expected_commands = {
        "next_command_only": expected_next_command_only,
        "next_json_only": expected_next_json_only,
        "connected_runner_command_only": expected_connected_command_only,
        "connected_runner_command_sequence": expected_connected_command_sequence,
        "operator_command_only": expected_operator_command_only,
        "operator_command_sequence": expected_operator_command_sequence,
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
        "local_readiness_setup_sequence": expected_local_readiness_setup_sequence,
        "local_readiness_command_sequence": expected_local_readiness_command_sequence,
        "local_readiness_setup_sequence_preview": expected_local_readiness_setup_sequence_preview,
        "local_readiness_command_sequence_preview": expected_local_readiness_command_sequence_preview,
        "external_readiness_summary_json": expected_external_readiness_summary_json,
        "external_readiness_strict_summary_json": expected_external_readiness_strict_summary_json,
        "warning_gate_json": expected_warning_gate_json,
        "warning_summary_json": expected_warning_summary_json,
        "warning_gate_summary_json": expected_warning_gate_summary_json,
        "warning_next_command_gate": expected_warning_review_next_command_gate,
        "warning_review_artifacts": expected_warning_review_artifacts_only,
    }
    if not isinstance(commands, dict):
        checks.append(
            {
                "id": "release_status_json_progress_summary_commands_object",
                "status": "fail",
                "expected": "object",
                "actual": type(commands).__name__,
            }
        )
    else:
        for key, expected_command in expected_commands.items():
            if expected_command is None:
                continue
            append_command_payload_check(
                checks,
                check_id=f"release_status_json_progress_summary_command_{key}",
                expected=expected_command,
                actual=commands.get(key),
            )

    owner_lanes = progress_summary.get("owner_lanes")
    checks.append(
        {
            "id": "release_status_json_progress_summary_owner_lanes_object",
            "status": "pass" if isinstance(owner_lanes, dict) else "fail",
            "expected": "object",
            "actual": "object" if isinstance(owner_lanes, dict) else type(owner_lanes).__name__,
        }
    )

    warning_review = progress_summary.get("warning_review")
    if not isinstance(warning_review, dict):
        checks.append(
            {
                "id": "release_status_json_progress_summary_warning_review_object",
                "status": "fail",
                "expected": "object",
                "actual": type(warning_review).__name__,
            }
        )
    else:
        append_command_payload_check(
            checks,
            check_id="release_status_json_progress_summary_warning_review_sequence_command",
            expected=expected_operator_review_sequence,
            actual=warning_review.get("review_sequence_command"),
        )
        append_command_payload_check(
            checks,
            check_id="release_status_json_progress_summary_warning_review_summary_json",
            expected=expected_warning_summary_json,
            actual=warning_review.get("summary_json"),
        )
        append_command_payload_check(
            checks,
            check_id="release_status_json_progress_summary_warning_review_artifacts_command",
            expected=expected_warning_review_artifacts_only,
            actual=warning_review.get("review_artifacts_command"),
        )
        expected_pre_approval_sequence = (
            []
            if warning_review.get("action_needed") is False
            else [
                expected_warning_summary_json,
                expected_warning_review_artifacts_only,
            ]
        )
        actual_pre_approval_sequence = warning_review.get("pre_approval_review_sequence")
        checks.append(
            {
                "id": "release_status_json_progress_summary_warning_review_pre_approval_sequence",
                "status": (
                    "pass"
                    if actual_pre_approval_sequence == expected_pre_approval_sequence
                    else "fail"
                ),
                "expected": expected_pre_approval_sequence,
                "actual": actual_pre_approval_sequence,
            }
        )

    if progress_summary.get("next_item_owner") == "connected runner":
        append_command_payload_check(
            checks,
            check_id="release_status_json_progress_summary_next_command",
            expected=expected_preflight,
            actual=progress_summary.get("next_command"),
        )

    next_commands_by_owner = progress_summary.get("next_commands_by_owner")
    if not isinstance(next_commands_by_owner, dict):
        checks.append(
            {
                "id": "release_status_json_progress_summary_next_commands_by_owner_object",
                "status": "fail",
                "expected": "object",
                "actual": type(next_commands_by_owner).__name__,
            }
        )
        return

    connected_runner_next = next_commands_by_owner.get("connected runner")
    if isinstance(connected_runner_next, dict):
        append_command_payload_check(
            checks,
            check_id="release_status_json_progress_summary_connected_runner_next",
            expected=expected_preflight,
            actual=connected_runner_next.get("command"),
        )
        if connected_runner_next.get("id") in {"git_origin_remote", "docker_cli", "github_cli"}:
            supporting_commands = connected_runner_next.get("supporting_commands")
            if not isinstance(supporting_commands, dict):
                checks.append(
                    {
                        "id": "release_status_json_progress_summary_connected_runner_supporting_commands",
                        "status": "fail",
                        "expected": "object",
                        "actual": type(supporting_commands).__name__,
                    }
                )
            else:
                append_command_payload_check(
                    checks,
                    check_id="release_status_json_progress_summary_connected_runner_command_only",
                    expected=expected_connected_command_only,
                    actual=supporting_commands.get("Show connected-runner command only from env"),
                )
                append_command_payload_check(
                    checks,
                    check_id="release_status_json_progress_summary_connected_runner_external_readiness_summary_json",
                    expected=expected_external_readiness_summary_json,
                    actual=supporting_commands.get("Show external readiness summary JSON"),
                )
                append_command_payload_check(
                    checks,
                    check_id="release_status_json_progress_summary_connected_runner_external_readiness_strict_summary_json",
                    expected=expected_external_readiness_strict_summary_json,
                    actual=supporting_commands.get("Gate external readiness summary JSON"),
                )
                append_command_payload_check(
                    checks,
                    check_id="release_status_json_progress_summary_connected_runner_local_readiness_setup_sequence",
                    expected=expected_local_readiness_setup_sequence,
                    actual=supporting_commands.get("Show local readiness setup sequence"),
                )
                append_command_payload_check(
                    checks,
                    check_id="release_status_json_progress_summary_connected_runner_local_readiness_command_sequence",
                    expected=expected_local_readiness_command_sequence,
                    actual=supporting_commands.get("Show local readiness command sequence"),
                )
                append_command_payload_check(
                    checks,
                    check_id=(
                        "release_status_json_progress_summary_connected_runner_"
                        "local_readiness_setup_sequence_preview"
                    ),
                    expected=expected_local_readiness_setup_sequence_preview,
                    actual=supporting_commands.get("Preview local readiness setup sequence"),
                )
                append_command_payload_check(
                    checks,
                    check_id=(
                        "release_status_json_progress_summary_connected_runner_"
                        "local_readiness_command_sequence_preview"
                    ),
                    expected=expected_local_readiness_command_sequence_preview,
                    actual=supporting_commands.get("Preview local readiness command sequence"),
                )

    operator_next = next_commands_by_owner.get("operator")
    if isinstance(operator_next, dict):
        operator_next_id = operator_next.get("id")
        if operator_next_id in {"warning_alerts", "warning_actions"}:
            append_command_payload_check(
                checks,
                check_id="release_status_json_progress_summary_operator_next",
                expected=expected_operator_command,
                actual=operator_next.get("command"),
            )
            supporting_commands = operator_next.get("supporting_commands")
            if not isinstance(supporting_commands, dict):
                checks.append(
                    {
                        "id": "release_status_json_progress_summary_operator_supporting_commands",
                        "status": "fail",
                        "expected": "object",
                        "actual": type(supporting_commands).__name__,
                    }
                )
            else:
                append_command_payload_check(
                    checks,
                    check_id="release_status_json_progress_summary_operator_review_artifacts",
                    expected=expected_warning_review_artifacts_only,
                    actual=supporting_commands.get("Show warning review artifact paths"),
                )
                append_command_payload_check(
                    checks,
                    check_id="release_status_json_progress_summary_operator_summary_json",
                    expected=expected_warning_summary_json,
                    actual=supporting_commands.get("Show warning summary JSON"),
                )
                append_command_payload_check(
                    checks,
                    check_id="release_status_json_progress_summary_operator_summary_json_gate",
                    expected=expected_warning_gate_summary_json,
                    actual=supporting_commands.get("Gate warning summary JSON"),
                )
                append_command_payload_check(
                    checks,
                    check_id="release_status_json_progress_summary_operator_next_command_gate",
                    expected=expected_warning_review_next_command_gate,
                    actual=supporting_commands.get("Gate warning recommended next command"),
                )
            review_artifacts = operator_next.get("review_artifacts")
            if not isinstance(review_artifacts, dict):
                checks.append(
                    {
                        "id": "release_status_json_progress_summary_operator_review_artifacts_object",
                        "status": "fail",
                        "expected": "object",
                        "actual": type(review_artifacts).__name__,
                    }
                )
            else:
                append_command_payload_check(
                    checks,
                    check_id="release_status_json_progress_summary_operator_action_plan_path",
                    expected=expected_warning_action_plan_path,
                    actual=review_artifacts.get("action_plan"),
                )
                append_command_payload_check(
                    checks,
                    check_id="release_status_json_progress_summary_operator_checklist_path",
                    expected=expected_warning_operator_checklist_path,
                    actual=review_artifacts.get("operator_checklist"),
                )
        else:
            checks.append(
                {
                    "id": "release_status_json_progress_summary_operator_next",
                    "status": "skipped",
                    "expected": "warning review command when the operator next item is a warning item",
                    "actual": operator_next.get("command"),
                }
            )


def gitignore_patterns(text: str) -> set[str]:
    return {
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def missing_required_gitignore_patterns(text: str) -> list[str]:
    patterns = gitignore_patterns(text)
    return [pattern for pattern in REQUIRED_GITIGNORE_PATTERNS if pattern not in patterns]


def is_under_prefix(path: Path, prefix: Path) -> bool:
    return path == prefix or prefix in path.parents


def is_packaged_source_excluded(path: Path) -> bool:
    return (
        any(part in PACKAGED_SOURCE_EXCLUDED_NAMES for part in path.parts)
        or path.suffix in FORBIDDEN_SOURCE_SUFFIXES
    )


def is_forbidden_source_path(
    path: Path,
    *,
    allowed_prefixes: tuple[Path, ...] = (),
) -> bool:
    if any(is_under_prefix(path, prefix) for prefix in allowed_prefixes):
        return False
    return (
        any(part in FORBIDDEN_SOURCE_PARTS for part in path.parts)
        or path.suffix in FORBIDDEN_SOURCE_SUFFIXES
    )


def verify_runner_remote_guard(script_text: str) -> tuple[bool, str, dict[str, Any]]:
    bash = shutil.which("bash")
    details: dict[str, Any] = {"cases": []}
    if bash is None:
        return False, "bash is unavailable; runner script remote guard cannot be checked.", details

    for label, git_origin_url, expected_message in RUNNER_REMOTE_GUARD_CASES:
        env = os.environ.copy()
        env.pop("GIT_ORIGIN_URL", None)
        env["PREFLIGHT_ONLY"] = "true"
        if git_origin_url is not None:
            env["GIT_ORIGIN_URL"] = git_origin_url
        completed = subprocess.run([bash, "-s"], input=script_text, env=env, text=True, capture_output=True)
        output = "\n".join(part for part in (completed.stdout.strip(), completed.stderr.strip()) if part)
        details["cases"].append(
            {
                "case": label,
                "preflight_only": True,
                "returncode": completed.returncode,
                "expected_message": expected_message,
                "output": output,
            }
        )
        if completed.returncode != 2 or expected_message not in output:
            return False, f"Runner script remote guard failed for {label} GIT_ORIGIN_URL.", details
    return True, "Runner script rejects missing, placeholder, and invalid-format GIT_ORIGIN_URL before preflight.", details


def verify_runner_script_order(script_text: str) -> tuple[bool, str, dict[str, Any]]:
    details: dict[str, Any] = {"rules": []}
    failures: list[str] = []
    for rule_id, before, after in RUNNER_SCRIPT_ORDER_RULES:
        before_index = script_text.find(before)
        after_index = script_text.find(after)
        passed = before_index >= 0 and after_index >= 0 and before_index < after_index
        details["rules"].append(
            {
                "id": rule_id,
                "before": before,
                "after": after,
                "before_index": before_index,
                "after_index": after_index,
                "status": "pass" if passed else "fail",
            }
        )
        if not passed:
            failures.append(rule_id)
    if failures:
        return False, "Runner script command order is unsafe: " + ", ".join(failures), details
    return (
        True,
        "Runner script remote guard, self-verification, acceptance, install, push, and strict-gate order is safe.",
        details,
    )
