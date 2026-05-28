#!/usr/bin/env python3
"""Validate an extracted connected-runner handoff before final release gating."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.handoff_commands import (
        CONNECTED_STRICT_GATE_COMMAND,
        DOCKER_BACKEND_START_COMMAND,
        LEGACY_REPO_URL_PLACEHOLDER,
        LIVE_BETA_CLOSEOUT_COMMAND,
        LIVE_BETA_FINAL_GATE_COMMAND,
        LIVE_BETA_NEXT_COMMAND_ONLY_COMMAND,
        LIVE_BETA_PREFLIGHT_COMMAND,
        LIVE_BETA_PREFLIGHT_JSON_COMMAND,
        LOCAL_BACKEND_START_COMMAND,
        LOCAL_BACKEND_START_NO_RELOAD_COMMAND,
        REPO_URL_PLACEHOLDER,
        backend_health_check_command,
        connected_runner_acceptance_command,
        connected_runner_acceptance_json_command,
        connected_runner_acceptance_summary_json_command,
        connected_runner_handoff_command_sequence_command,
        connected_runner_handoff_context_json_command,
        connected_runner_full_command,
        connected_runner_preflight_command,
        connected_runner_verify_command,
        connected_runner_verify_json_command,
        connected_runner_verify_summary_json_command,
        external_readiness_strict_summary_json_command,
        external_readiness_summary_json_command,
        git_origin_setup_command,
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
        read_only_evidence_check_command,
        read_only_warning_review_command,
        release_status_completion_plan_command,
        release_status_completion_plan_json_command,
        release_status_completion_requirements_command,
        release_status_completion_requirements_json_command,
        release_status_owner_lanes_command,
        release_status_owner_lanes_json_command,
        release_status_progress_command,
        release_status_progress_json_command,
        shell_arg,
        verify_evidence_checksums_json_command,
        warning_review_apply_command,
        warning_review_artifacts_only_command,
        warning_review_gate_summary_json_command,
        warning_review_gate_json_command,
        warning_review_json_command,
        warning_review_next_command_gate_command,
        warning_review_next_command_only_command,
        warning_review_summary_json_command,
    )
    from scripts.connected_runner_contract import (
        REQUIRED_GITIGNORE_PATTERNS,
        RUNNER_REMOTE_VALIDATE_CALL_MARKER,
        RUNNER_SCRIPT_MARKERS,
        RUNNER_SCRIPT_ORDER_RULES,
        append_progress_summary_checks,
        compact_check_summary,
        is_forbidden_source_path,
        missing_required_gitignore_patterns,
        verify_handoff_completion_context,
        verify_runner_remote_guard,
        verify_runner_script_order,
    )
    from scripts.release_artifacts import latest_json_file, latest_package_candidate
    from scripts.release_manifest import HANDOFF_REQUIRED_SOURCE_FILES
except ModuleNotFoundError:  # pragma: no cover - supports running from scripts/
    from handoff_commands import (
        CONNECTED_STRICT_GATE_COMMAND,
        DOCKER_BACKEND_START_COMMAND,
        LEGACY_REPO_URL_PLACEHOLDER,
        LIVE_BETA_CLOSEOUT_COMMAND,
        LIVE_BETA_FINAL_GATE_COMMAND,
        LIVE_BETA_NEXT_COMMAND_ONLY_COMMAND,
        LIVE_BETA_PREFLIGHT_COMMAND,
        LIVE_BETA_PREFLIGHT_JSON_COMMAND,
        LOCAL_BACKEND_START_COMMAND,
        LOCAL_BACKEND_START_NO_RELOAD_COMMAND,
        REPO_URL_PLACEHOLDER,
        backend_health_check_command,
        connected_runner_acceptance_command,
        connected_runner_acceptance_json_command,
        connected_runner_acceptance_summary_json_command,
        connected_runner_handoff_command_sequence_command,
        connected_runner_handoff_context_json_command,
        connected_runner_full_command,
        connected_runner_preflight_command,
        connected_runner_verify_command,
        connected_runner_verify_json_command,
        connected_runner_verify_summary_json_command,
        external_readiness_strict_summary_json_command,
        external_readiness_summary_json_command,
        git_origin_setup_command,
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
        read_only_evidence_check_command,
        read_only_warning_review_command,
        release_status_completion_plan_command,
        release_status_completion_plan_json_command,
        release_status_completion_requirements_command,
        release_status_completion_requirements_json_command,
        release_status_owner_lanes_command,
        release_status_owner_lanes_json_command,
        release_status_progress_command,
        release_status_progress_json_command,
        shell_arg,
        verify_evidence_checksums_json_command,
        warning_review_apply_command,
        warning_review_artifacts_only_command,
        warning_review_gate_summary_json_command,
        warning_review_gate_json_command,
        warning_review_json_command,
        warning_review_next_command_gate_command,
        warning_review_next_command_only_command,
        warning_review_summary_json_command,
    )
    from connected_runner_contract import (
        REQUIRED_GITIGNORE_PATTERNS,
        RUNNER_REMOTE_VALIDATE_CALL_MARKER,
        RUNNER_SCRIPT_MARKERS,
        RUNNER_SCRIPT_ORDER_RULES,
        append_progress_summary_checks,
        compact_check_summary,
        is_forbidden_source_path,
        missing_required_gitignore_patterns,
        verify_handoff_completion_context,
        verify_runner_remote_guard,
        verify_runner_script_order,
    )
    from release_artifacts import latest_json_file, latest_package_candidate
    from release_manifest import HANDOFF_REQUIRED_SOURCE_FILES


LOCAL_GENERATED_PREFIXES: tuple[Path, ...] = (
    Path(".git"),
    Path("backend/.venv"),
    Path("frontend/node_modules"),
    Path("frontend/dist"),
    Path("frontend/.vite"),
    Path("artifacts/connected-runner-acceptance"),
    Path("artifacts/external-readiness"),
    Path("artifacts/verification"),
    Path("artifacts/local-smoke"),
    Path("artifacts/ops-smoke"),
    Path("artifacts/crypto-drills"),
    Path("artifacts/evidence-packages"),
    Path("artifacts/handoff-bundles"),
    Path("artifacts/release-gate"),
    Path("artifacts/live-beta"),
)

REQUIRED_SOURCE_FILES = HANDOFF_REQUIRED_SOURCE_FILES

COPIED_EVIDENCE_COMMAND_FILES: tuple[str, ...] = (
    "release-status.md",
    "release-status.json",
    "next-release-step.md",
    "next-release-step.json",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run connected-runner handoff acceptance checks.")
    parser.add_argument(
        "--handoff-root",
        help="Extracted handoff bundle root. Defaults to the parent of source/ when available.",
    )
    parser.add_argument(
        "--source-root",
        help="Quant Lab source root. Defaults to the current directory or HANDOFF_ROOT/source.",
    )
    parser.add_argument(
        "--package-dir",
        help=(
            "Copied evidence package directory, or a local evidence package with a sibling .tgz archive. "
            "Defaults to the latest HANDOFF_ROOT/evidence/* package."
        ),
    )
    parser.add_argument(
        "--output-dir",
        help=(
            "Directory for acceptance reports. Defaults to HANDOFF_ROOT/acceptance-artifacts "
            "when a handoff root is available, otherwise SOURCE_ROOT/artifacts/connected-runner-acceptance."
        ),
    )
    parser.add_argument(
        "--require-external",
        action="store_true",
        help="Fail when git origin, Docker, or GitHub CLI are unavailable.",
    )
    parser.add_argument(
        "--check-gh-auth",
        action="store_true",
        help="Check GitHub CLI authentication when GitHub CLI is available.",
    )
    parser.add_argument(
        "--run-strict-gate",
        action="store_true",
        help="Also run scripts/release_gate.py --run-smoke --strict-external after acceptance preflight; adds --check-gh-auth when requested.",
    )
    parser.add_argument("--symbol", default="KRW-BTC", help="Market symbol for the optional strict gate.")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000", help="Backend base URL for smoke checks.")
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Print the acceptance report as JSON instead of human-readable lines.",
    )
    parser.add_argument(
        "--summary-json-only",
        action="store_true",
        help="Print a compact machine-readable acceptance summary without verbose check details.",
    )
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def add_check(
    checks: list[dict[str, Any]],
    *,
    check_id: str,
    label: str,
    status: str,
    message: str,
    evidence: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    checks.append(
        {
            "id": check_id,
            "label": label,
            "status": status,
            "message": message,
            "evidence": evidence,
            "details": details or {},
        }
    )


def run_command(command: list[str], *, cwd: Path) -> dict[str, Any]:
    env = dict(os.environ, PYTHONPYCACHEPREFIX=os.environ.get("PYTHONPYCACHEPREFIX", "/tmp/quant-pycache"))
    started_at = datetime.now(timezone.utc).isoformat()
    completed = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True)
    return {
        "command": command,
        "cwd": str(cwd),
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def detect_source_root(args: argparse.Namespace) -> Path:
    if args.source_root:
        return Path(args.source_root).absolute()

    if args.handoff_root:
        handoff_source = Path(args.handoff_root).absolute() / "source"
        if (handoff_source / "scripts/release_gate.py").is_file():
            return handoff_source

    cwd = Path.cwd().absolute()
    if (cwd / "scripts/release_gate.py").is_file():
        return cwd
    if (cwd / "source/scripts/release_gate.py").is_file():
        return (cwd / "source").absolute()

    raise FileNotFoundError("Could not find Quant Lab source root. Pass --source-root.")


def detect_handoff_root(args: argparse.Namespace, source_root: Path) -> Path | None:
    if args.handoff_root:
        return Path(args.handoff_root).absolute()
    parent = source_root.parent
    if (parent / "HANDOFF.md").is_file() and (parent / "evidence").is_dir():
        return parent.absolute()
    return None


def latest_package_dir(*, handoff_root: Path | None, source_root: Path) -> Path | None:
    candidates: list[Path] = []
    if handoff_root is not None:
        evidence_root = handoff_root / "evidence"
        candidates.extend(path for path in evidence_root.glob("*") if (path / "manifest.json").is_file())
    local_packages = source_root / "artifacts/evidence-packages"
    candidates.extend(path for path in local_packages.glob("*") if (path / "manifest.json").is_file())
    latest = latest_package_candidate(candidates, metadata_files=("manifest.json", "release-status.json"))
    if latest is None:
        return None
    return latest.absolute()


def local_generated_paths(source_root: Path) -> list[str]:
    generated: list[str] = []
    for prefix in LOCAL_GENERATED_PREFIXES:
        path = source_root / prefix
        if path.exists():
            generated.append(prefix.as_posix())
    return sorted(generated)


def forbidden_source_paths(source_root: Path) -> list[str]:
    forbidden: list[str] = []
    for path in source_root.rglob("*"):
        relative_path = path.relative_to(source_root)
        if is_forbidden_source_path(relative_path, allowed_prefixes=LOCAL_GENERATED_PREFIXES):
            forbidden.append(relative_path.as_posix())
    return sorted(forbidden)


def missing_gitignore_patterns(source_root: Path) -> tuple[list[str], str | None]:
    gitignore_path = source_root / ".gitignore"
    try:
        text = gitignore_path.read_text(encoding="utf-8")
    except OSError as exc:
        return list(REQUIRED_GITIGNORE_PATTERNS), str(exc)
    return missing_required_gitignore_patterns(text), None


def newest_json(root: Path, pattern: str) -> Path | None:
    return latest_json_file(root, pattern)


def evidence_archive_candidates(package_dir: Path) -> list[Path]:
    archive_candidates = sorted(package_dir.glob("*.tgz"))
    sibling_archive = package_dir.with_name(f"{package_dir.name}.tgz")
    if sibling_archive.is_file():
        archive_candidates.append(sibling_archive)
    return sorted(set(archive_candidates))


def verify_evidence_archive(package_dir: Path) -> tuple[str, str]:
    archive_candidates = evidence_archive_candidates(package_dir)
    if not archive_candidates:
        sibling_archive = package_dir.with_name(f"{package_dir.name}.tgz")
        return "fail", f"No evidence archive .tgz found under {package_dir} or at {sibling_archive}."
    archive = archive_candidates[-1]
    sidecar = archive.with_suffix(archive.suffix + ".sha256")
    if not sidecar.is_file():
        return "fail", f"Evidence archive SHA256 sidecar is missing: {sidecar}."
    expected_line = sidecar.read_text(encoding="utf-8").strip()
    expected_hash = expected_line.split()[0] if expected_line else ""
    actual_hash = sha256_file(archive)
    if expected_hash != actual_hash:
        return "fail", f"Evidence archive SHA256 mismatch for {archive}."
    try:
        with tarfile.open(archive, "r:gz") as tar:
            names = set(tar.getnames())
    except (OSError, tarfile.TarError) as exc:
        return "fail", f"Evidence archive is unreadable: {exc}."
    required_suffixes = {"manifest.json", "release-status.md", "evidence-checksums.json"}
    missing_suffixes = [
        suffix
        for suffix in sorted(required_suffixes)
        if not any(name.endswith("/" + suffix) or name == suffix for name in names)
    ]
    if missing_suffixes:
        return "fail", "Evidence archive is missing required files: " + ", ".join(missing_suffixes)
    return "pass", f"Evidence archive sidecar matches and required files are present: {archive}."


def command_payload_check(
    checks: list[dict[str, Any]],
    *,
    check_id: str,
    expected: str,
    actual: Any = None,
    contains_text: str | None = None,
    require_when_contains: str | None = None,
) -> None:
    if contains_text is not None:
        if require_when_contains is not None and require_when_contains not in contains_text:
            checks.append(
                {
                    "id": check_id,
                    "status": "skipped",
                    "expected": f"{expected} when {require_when_contains} is present",
                    "actual": "not applicable",
                }
            )
            return
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

    if require_when_contains is not None:
        if not isinstance(actual, str) or require_when_contains not in actual:
            checks.append(
                {
                    "id": check_id,
                    "status": "skipped",
                    "expected": f"{expected} when {require_when_contains} is present",
                    "actual": actual if isinstance(actual, str) else type(actual).__name__,
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


def connected_runner_item_command_checks(
    checks: list[dict[str, Any]],
    *,
    items: Any,
    expected_preflight: str,
    expected_full: str,
) -> None:
    if not isinstance(items, list):
        checks.append(
            {
                "id": "release_status_remaining_items",
                "status": "fail",
                "expected": "list",
                "actual": type(items).__name__,
            }
        )
        return

    connected_runner_items = [
        item for item in items if isinstance(item, dict) and item.get("owner") == "connected runner"
    ]
    if not connected_runner_items:
        checks.append(
            {
                "id": "release_status_connected_runner_items",
                "status": "skipped",
                "expected": "connected runner item when connected-runner work remains",
                "actual": 0,
            }
        )
        return

    for index, item in enumerate(connected_runner_items):
        if "preferred_command" in item:
            command_payload_check(
                checks,
                check_id=f"release_status_item_{index}_preferred_command",
                expected=expected_preflight,
                actual=item.get("preferred_command"),
            )
        if "full_flow_command" in item:
            command_payload_check(
                checks,
                check_id=f"release_status_item_{index}_full_flow_command",
                expected=expected_full,
                actual=item.get("full_flow_command"),
            )


def handoff_command_list_check(
    checks: list[dict[str, Any]],
    *,
    check_id: str,
    payload: dict[str, Any],
    expected: str,
) -> None:
    commands = payload.get("handoff_commands")
    if not isinstance(commands, list):
        checks.append(
            {
                "id": f"{check_id}_commands",
                "status": "fail",
                "expected": "list",
                "actual": type(commands).__name__,
            }
        )
        return

    actual_commands = [
        item.get("command")
        for item in commands
        if isinstance(item, dict) and isinstance(item.get("command"), str)
    ]
    checks.append(
        {
            "id": check_id,
            "status": "pass" if expected in actual_commands else "fail",
            "expected": expected,
            "actual": "present" if expected in actual_commands else actual_commands,
        }
    )


def progress_summary_checks(
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
    append_progress_summary_checks(
        checks,
        payload=payload,
        expected_preflight=expected_preflight,
        expected_next_command_only=expected_next_command_only,
        expected_next_json_only=expected_next_json_only,
        expected_connected_command_only=expected_connected_command_only,
        expected_connected_command_sequence=expected_connected_command_sequence,
        expected_operator_command_only=expected_operator_command_only,
        expected_operator_command_sequence=expected_operator_command_sequence,
        expected_operator_review_sequence=expected_operator_review_sequence,
        expected_operator_json_only=expected_operator_json_only,
        expected_remaining_sequence=expected_remaining_sequence,
        expected_progress_json=expected_progress_json,
        expected_completion_plan=expected_completion_plan,
        expected_completion_plan_json=expected_completion_plan_json,
        expected_completion_requirements=expected_completion_requirements,
        expected_completion_requirements_json=expected_completion_requirements_json,
        expected_handoff_context_json=expected_handoff_context_json,
        expected_handoff_command_sequence=expected_handoff_command_sequence,
        expected_local_readiness_setup_sequence=expected_local_readiness_setup_sequence,
        expected_local_readiness_command_sequence=expected_local_readiness_command_sequence,
        expected_local_readiness_setup_sequence_preview=expected_local_readiness_setup_sequence_preview,
        expected_local_readiness_command_sequence_preview=expected_local_readiness_command_sequence_preview,
        expected_external_readiness_summary_json=expected_external_readiness_summary_json,
        expected_external_readiness_strict_summary_json=expected_external_readiness_strict_summary_json,
        expected_warning_gate_json=expected_warning_gate_json,
        expected_warning_summary_json=expected_warning_summary_json,
        expected_warning_gate_summary_json=expected_warning_gate_summary_json,
        expected_warning_review_artifacts_only=expected_warning_review_artifacts_only,
        expected_warning_review_next_command_gate=expected_warning_review_next_command_gate,
        expected_warning_action_plan_path=expected_warning_action_plan_path,
        expected_warning_operator_checklist_path=expected_warning_operator_checklist_path,
        expected_operator_command=expected_operator_command,
        expected_owner_lanes=expected_owner_lanes,
        expected_owner_lanes_json=expected_owner_lanes_json,
    )


def parse_command_json(
    checks: list[dict[str, Any]],
    *,
    filename: str,
    text: str | None,
) -> dict[str, Any] | None:
    if text is None:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        checks.append(
            {
                "id": f"{filename}_parse",
                "status": "fail",
                "expected": "valid JSON",
                "actual": str(exc),
            }
        )
        return None
    if not isinstance(payload, dict):
        checks.append(
            {
                "id": f"{filename}_object",
                "status": "fail",
                "expected": "object",
                "actual": type(payload).__name__,
            }
        )
        return None
    return payload


def verify_handoff_readme_completion_context(
    *,
    handoff_root: Path | None,
    package_dir: Path | None,
) -> tuple[str, str, dict[str, Any], str | None]:
    if handoff_root is None:
        return (
            "skipped",
            "No handoff root was provided, so HANDOFF.md completion context was not checked.",
            {},
            None,
        )
    if package_dir is None:
        return (
            "fail",
            "No copied evidence package was found, so HANDOFF.md completion context cannot be checked.",
            {},
            str(handoff_root / "HANDOFF.md"),
        )

    handoff_path = handoff_root / "HANDOFF.md"
    release_status_path = package_dir / "release-status.json"
    details: dict[str, Any] = {
        "handoff_path": str(handoff_path),
        "release_status_path": str(release_status_path),
    }
    try:
        readme_text = handoff_path.read_text(encoding="utf-8")
    except OSError as exc:
        details["read_error"] = str(exc)
        return "fail", f"HANDOFF.md could not be read: {exc}", details, str(handoff_path)
    try:
        release_status = json.loads(release_status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        details["read_error"] = str(exc)
        return "fail", f"Copied release-status.json could not be read: {exc}", details, str(release_status_path)

    context_ok, context_message, context_details = verify_handoff_completion_context(
        readme_text,
        release_status if isinstance(release_status, dict) else None,
    )
    details.update(context_details)
    return (
        "pass" if context_ok else "fail",
        context_message,
        details,
        str(handoff_path),
    )


def verify_copied_evidence_handoff_commands(
    *,
    handoff_root: Path | None,
    package_dir: Path | None,
) -> tuple[str, str, dict[str, Any], str | None]:
    if package_dir is None:
        return "fail", "No copied evidence package was found, so handoff commands cannot be checked.", {}, None

    command_files: dict[str, str] = {}
    checks: list[dict[str, Any]] = []
    details: dict[str, Any] = {
        "package_dir": str(package_dir),
        "handoff_root": str(handoff_root) if handoff_root else None,
        "files": [],
        "checks": checks,
    }

    for filename in COPIED_EVIDENCE_COMMAND_FILES:
        path = package_dir / filename
        if path.is_file():
            command_files[filename] = path.read_text(encoding="utf-8")
        checks.append(
            {
                "id": f"{filename}_present",
                "status": "pass" if filename in command_files else "fail",
                "expected": "present",
                "actual": "present" if filename in command_files else "missing",
            }
        )
    details["files"] = sorted(command_files)

    release_status = parse_command_json(
        checks,
        filename="release-status.json",
        text=command_files.get("release-status.json"),
    )
    next_step = parse_command_json(
        checks,
        filename="next-release-step.json",
        text=command_files.get("next-release-step.json"),
    )

    reference_bundle = None
    if release_status and isinstance(release_status.get("connected_runner_handoff_bundle"), str):
        reference_bundle = release_status["connected_runner_handoff_bundle"]
    elif handoff_root is not None:
        reference_bundle = str(handoff_root)

    if not reference_bundle:
        checks.append(
            {
                "id": "reference_bundle",
                "status": "fail",
                "expected": "connected_runner_handoff_bundle or handoff_root",
                "actual": None,
            }
        )
        failures = [check for check in checks if check["status"] == "fail"]
        details["failure_count"] = len(failures)
        return "fail", "Copied evidence does not identify a connected-runner bundle.", details, str(package_dir)

    expected_preflight = connected_runner_preflight_command(reference_bundle)
    expected_full = connected_runner_full_command(reference_bundle)
    expected_verify = connected_runner_verify_command(reference_bundle)
    expected_handoff_context_json = connected_runner_handoff_context_json_command(reference_bundle)
    expected_handoff_command_sequence = connected_runner_handoff_command_sequence_command(reference_bundle)
    details.update(
        {
            "reference_bundle": reference_bundle,
            "expected_preflight_command": expected_preflight,
            "expected_full_command": expected_full,
            "expected_verify_command": expected_verify,
            "expected_handoff_command_sequence_command": expected_handoff_command_sequence,
        }
    )

    release_status_md = command_files.get("release-status.md", "")
    next_step_md = command_files.get("next-release-step.md", "")
    if release_status_md:
        command_payload_check(
            checks,
            check_id="release_status_md_preflight_command",
            expected=expected_preflight,
            contains_text=release_status_md,
        )
        command_payload_check(
            checks,
            check_id="release_status_md_full_command",
            expected=expected_full,
            contains_text=release_status_md,
        )
        command_payload_check(
            checks,
            check_id="release_status_md_verify_command",
            expected=expected_verify,
            contains_text=release_status_md,
        )
    if next_step_md:
        command_payload_check(
            checks,
            check_id="next_release_step_md_preflight_command",
            expected=expected_preflight,
            contains_text=next_step_md,
            require_when_contains="run-connected-runner-handoff.sh",
        )
        command_payload_check(
            checks,
            check_id="next_release_step_md_full_command",
            expected=expected_full,
            contains_text=next_step_md,
            require_when_contains="run-connected-runner-handoff.sh",
        )

    if release_status is not None:
        command_payload_check(
            checks,
            check_id="release_status_json_preflight_command",
            expected=expected_preflight,
            actual=release_status.get("connected_runner_preflight_command"),
        )
        command_payload_check(
            checks,
            check_id="release_status_json_full_command",
            expected=expected_full,
            actual=release_status.get("connected_runner_full_command"),
        )
        connected_runner_item_command_checks(
            checks,
            items=release_status.get("remaining_items"),
            expected_preflight=expected_preflight,
            expected_full=expected_full,
        )
        release_package_dir = release_status.get("package_dir")
        if isinstance(release_package_dir, str) and release_package_dir:
            expected_next_step = next_release_step_command(release_package_dir)
            expected_repo_next_step = next_release_step_repo_command(release_package_dir)
            expected_origin_next_step = next_release_step_origin_command(release_package_dir)
            expected_env_next_step = next_release_step_env_command(release_package_dir)
            expected_command_only_env = next_release_command_only_env_command(release_package_dir)
            expected_command_sequence_env = next_release_command_sequence_env_command(release_package_dir)
            expected_json_only_env = next_release_json_only_env_command(release_package_dir)
            expected_connected_json_only_env = next_release_connected_json_only_env_command(release_package_dir)
            expected_connected_command_only_env = next_release_connected_command_only_env_command(release_package_dir)
            expected_connected_command_sequence_env = next_release_connected_command_sequence_env_command(
                release_package_dir
            )
            expected_sequence = next_release_sequence_command(release_package_dir)
            expected_operator_sequence = next_release_operator_sequence_command(release_package_dir)
            expected_operator_command_only = next_release_operator_command_only_command(release_package_dir)
            expected_operator_command_sequence = next_release_operator_command_sequence_command(release_package_dir)
            expected_operator_review_sequence = next_release_operator_review_sequence_command(release_package_dir)
            expected_operator_json_only = next_release_operator_json_only_command(release_package_dir)
            expected_connected_sequence = next_release_connected_sequence_command(release_package_dir)
            expected_connected_sequence_origin = next_release_connected_sequence_origin_command(release_package_dir)
            expected_connected_sequence_env = next_release_connected_sequence_env_command(release_package_dir)
            expected_local_readiness = next_release_local_readiness_command(release_package_dir)
            expected_local_readiness_command_only = next_release_local_readiness_command_only_env_command(release_package_dir)
            expected_local_readiness_json = next_release_local_readiness_json_env_command(release_package_dir)
            expected_local_readiness_gate_json = next_release_local_readiness_gate_json_env_command(release_package_dir)
            expected_local_readiness_setup_sequence = next_release_local_readiness_setup_sequence_env_command(
                release_package_dir
            )
            expected_local_readiness_command_sequence = next_release_local_readiness_command_sequence_env_command(
                release_package_dir
            )
            expected_local_readiness_setup_sequence_preview = (
                next_release_local_readiness_setup_sequence_preview_command(release_package_dir)
            )
            expected_local_readiness_command_sequence_preview = (
                next_release_local_readiness_command_sequence_preview_command(release_package_dir)
            )
            expected_external_readiness_summary_json = external_readiness_summary_json_command()
            expected_external_readiness_strict_summary_json = external_readiness_strict_summary_json_command()
            release_gate_path = release_status.get("release_gate_path")
            expected_release_status_progress = release_status_progress_command(
                release_package_dir,
                release_gate_path if isinstance(release_gate_path, str) else None,
            )
            expected_release_status_progress_json = release_status_progress_json_command(
                release_package_dir,
                release_gate_path if isinstance(release_gate_path, str) else None,
            )
            expected_release_status_completion_plan = release_status_completion_plan_command(
                release_package_dir,
                release_gate_path if isinstance(release_gate_path, str) else None,
            )
            expected_release_status_completion_plan_json = release_status_completion_plan_json_command(
                release_package_dir,
                release_gate_path if isinstance(release_gate_path, str) else None,
            )
            expected_release_status_completion_requirements = release_status_completion_requirements_command(
                release_package_dir,
                release_gate_path if isinstance(release_gate_path, str) else None,
            )
            expected_release_status_completion_requirements_json = (
                release_status_completion_requirements_json_command(
                    release_package_dir,
                    release_gate_path if isinstance(release_gate_path, str) else None,
                )
            )
            expected_release_status_owner_lanes = release_status_owner_lanes_command(
                release_package_dir,
                release_gate_path if isinstance(release_gate_path, str) else None,
            )
            expected_release_status_owner_lanes_json = release_status_owner_lanes_json_command(
                release_package_dir,
                release_gate_path if isinstance(release_gate_path, str) else None,
            )
            expected_read_only_evidence_check = read_only_evidence_check_command(release_package_dir)
            expected_read_only_warning_review = read_only_warning_review_command(release_package_dir)
            expected_warning_review_json = warning_review_json_command(release_package_dir)
            expected_warning_review_gate_json = warning_review_gate_json_command(release_package_dir)
            expected_warning_review_summary_json = warning_review_summary_json_command(release_package_dir)
            expected_warning_review_gate_summary_json = warning_review_gate_summary_json_command(release_package_dir)
            expected_warning_review_artifacts_only = warning_review_artifacts_only_command(release_package_dir)
            expected_warning_review_next_command_only = warning_review_next_command_only_command(release_package_dir)
            expected_warning_review_next_command_gate = warning_review_next_command_gate_command(release_package_dir)
            expected_warning_review_apply = warning_review_apply_command(release_package_dir)
            release_package_path = Path(release_package_dir)
            expected_warning_action_plan_path = str(release_package_path / "release-warning-actions.md")
            expected_warning_operator_checklist_path = str(
                release_package_path / "release-warning-operator-checklist.md"
            )
            expected_live_beta_preflight = LIVE_BETA_PREFLIGHT_COMMAND
            expected_live_beta_preflight_json = LIVE_BETA_PREFLIGHT_JSON_COMMAND
            expected_live_beta_next_command_only = LIVE_BETA_NEXT_COMMAND_ONLY_COMMAND
            expected_live_beta_closeout = LIVE_BETA_CLOSEOUT_COMMAND
            expected_live_beta_final_gate = LIVE_BETA_FINAL_GATE_COMMAND
            expected_live_beta_support_commands = {
                "backend_start_local": LOCAL_BACKEND_START_COMMAND,
                "backend_start_local_no_reload": LOCAL_BACKEND_START_NO_RELOAD_COMMAND,
                "backend_start_docker": DOCKER_BACKEND_START_COMMAND,
                "backend_health_check": backend_health_check_command(),
            }
            details["expected_next_release_step_command"] = expected_next_step
            details["expected_next_release_step_repo_command"] = expected_repo_next_step
            details["expected_next_release_step_origin_command"] = expected_origin_next_step
            details["expected_next_release_step_env_command"] = expected_env_next_step
            details["expected_next_release_command_only_env_command"] = expected_command_only_env
            details["expected_next_release_command_sequence_env_command"] = expected_command_sequence_env
            details["expected_next_release_json_only_env_command"] = expected_json_only_env
            details["expected_next_release_connected_json_only_env_command"] = expected_connected_json_only_env
            details["expected_next_release_connected_command_only_env_command"] = expected_connected_command_only_env
            details["expected_next_release_connected_command_sequence_env_command"] = expected_connected_command_sequence_env
            details["expected_next_release_sequence_command"] = expected_sequence
            details["expected_next_release_operator_sequence_command"] = expected_operator_sequence
            details["expected_next_release_operator_command_only_command"] = expected_operator_command_only
            details["expected_next_release_operator_command_sequence_command"] = expected_operator_command_sequence
            details["expected_next_release_operator_review_sequence_command"] = expected_operator_review_sequence
            details["expected_next_release_operator_json_only_command"] = expected_operator_json_only
            details["expected_next_release_connected_sequence_command"] = expected_connected_sequence
            details["expected_next_release_connected_sequence_origin_command"] = expected_connected_sequence_origin
            details["expected_next_release_connected_sequence_env_command"] = expected_connected_sequence_env
            details["expected_next_release_local_readiness_command"] = expected_local_readiness
            details["expected_next_release_local_readiness_command_only_command"] = expected_local_readiness_command_only
            details["expected_next_release_local_readiness_json_command"] = expected_local_readiness_json
            details["expected_next_release_local_readiness_gate_json_command"] = expected_local_readiness_gate_json
            details["expected_next_release_local_readiness_setup_sequence_command"] = (
                expected_local_readiness_setup_sequence
            )
            details["expected_next_release_local_readiness_command_sequence_command"] = (
                expected_local_readiness_command_sequence
            )
            details["expected_next_release_local_readiness_setup_sequence_preview_command"] = (
                expected_local_readiness_setup_sequence_preview
            )
            details["expected_next_release_local_readiness_command_sequence_preview_command"] = (
                expected_local_readiness_command_sequence_preview
            )
            details["expected_release_status_progress_command"] = expected_release_status_progress
            details["expected_release_status_progress_json_command"] = expected_release_status_progress_json
            details["expected_release_status_completion_plan_command"] = expected_release_status_completion_plan
            details["expected_release_status_completion_plan_json_command"] = (
                expected_release_status_completion_plan_json
            )
            details["expected_release_status_completion_requirements_command"] = (
                expected_release_status_completion_requirements
            )
            details["expected_release_status_completion_requirements_json_command"] = (
                expected_release_status_completion_requirements_json
            )
            details["expected_release_status_owner_lanes_command"] = expected_release_status_owner_lanes
            details["expected_release_status_owner_lanes_json_command"] = expected_release_status_owner_lanes_json
            details["expected_read_only_evidence_check_command"] = expected_read_only_evidence_check
            details["expected_read_only_warning_review_command"] = expected_read_only_warning_review
            details["expected_warning_review_json_command"] = expected_warning_review_json
            details["expected_warning_review_gate_json_command"] = expected_warning_review_gate_json
            details["expected_warning_review_artifacts_only_command"] = expected_warning_review_artifacts_only
            details["expected_warning_review_next_command_only_command"] = expected_warning_review_next_command_only
            details["expected_warning_review_next_command_gate_command"] = expected_warning_review_next_command_gate
            details["expected_warning_review_apply_command"] = expected_warning_review_apply
            details["expected_warning_action_plan_path"] = expected_warning_action_plan_path
            details["expected_warning_operator_checklist_path"] = expected_warning_operator_checklist_path
            details["expected_live_beta_preflight_command"] = expected_live_beta_preflight
            details["expected_live_beta_preflight_json_command"] = expected_live_beta_preflight_json
            details["expected_live_beta_next_command_only_command"] = expected_live_beta_next_command_only
            details["expected_live_beta_closeout_command"] = expected_live_beta_closeout
            details["expected_live_beta_final_gate_command"] = expected_live_beta_final_gate
            details["expected_live_beta_backend_support_commands"] = expected_live_beta_support_commands
            if release_status_md:
                command_payload_check(
                    checks,
                    check_id="release_status_md_read_only_evidence_check_command",
                    expected=expected_read_only_evidence_check,
                    contains_text=release_status_md,
                )
                command_payload_check(
                    checks,
                    check_id="release_status_md_progress_command",
                    expected=expected_release_status_progress,
                    contains_text=release_status_md,
                )
                command_payload_check(
                    checks,
                    check_id="release_status_md_progress_json_command",
                    expected=expected_release_status_progress_json,
                    contains_text=release_status_md,
                )
                command_payload_check(
                    checks,
                    check_id="release_status_md_completion_plan_command",
                    expected=expected_release_status_completion_plan,
                    contains_text=release_status_md,
                )
                command_payload_check(
                    checks,
                    check_id="release_status_md_completion_plan_json_command",
                    expected=expected_release_status_completion_plan_json,
                    contains_text=release_status_md,
                )
                command_payload_check(
                    checks,
                    check_id="release_status_md_read_only_warning_review_command",
                    expected=expected_read_only_warning_review,
                    contains_text=release_status_md,
                )
                command_payload_check(
                    checks,
                    check_id="release_status_md_warning_review_json_command",
                    expected=expected_warning_review_json,
                    contains_text=release_status_md,
                )
                command_payload_check(
                    checks,
                    check_id="release_status_md_warning_review_gate_json_command",
                    expected=expected_warning_review_gate_json,
                    contains_text=release_status_md,
                )
                command_payload_check(
                    checks,
                    check_id="release_status_md_warning_review_artifacts_only_command",
                    expected=expected_warning_review_artifacts_only,
                    contains_text=release_status_md,
                )
                command_payload_check(
                    checks,
                    check_id="release_status_md_warning_review_next_command_only_command",
                    expected=expected_warning_review_next_command_only,
                    contains_text=release_status_md,
                )
                command_payload_check(
                    checks,
                    check_id="release_status_md_warning_review_next_command_gate_command",
                    expected=expected_warning_review_next_command_gate,
                    contains_text=release_status_md,
                )
                command_payload_check(
                    checks,
                    check_id="release_status_md_warning_review_apply_command",
                    expected=expected_warning_review_apply,
                    contains_text=release_status_md,
                )
                command_payload_check(
                    checks,
                    check_id="release_status_md_live_beta_preflight_command",
                    expected=expected_live_beta_preflight,
                    contains_text=release_status_md,
                )
                command_payload_check(
                    checks,
                    check_id="release_status_md_live_beta_preflight_json_command",
                    expected=expected_live_beta_preflight_json,
                    contains_text=release_status_md,
                )
                command_payload_check(
                    checks,
                    check_id="release_status_md_live_beta_next_command_only_command",
                    expected=expected_live_beta_next_command_only,
                    contains_text=release_status_md,
                )
                command_payload_check(
                    checks,
                    check_id="release_status_md_live_beta_closeout_command",
                    expected=expected_live_beta_closeout,
                    contains_text=release_status_md,
                )
                command_payload_check(
                    checks,
                    check_id="release_status_md_live_beta_final_gate_command",
                    expected=expected_live_beta_final_gate,
                    contains_text=release_status_md,
                )
                for support_name, support_command in expected_live_beta_support_commands.items():
                    command_payload_check(
                        checks,
                        check_id=f"release_status_md_live_beta_{support_name}_support_command",
                        expected=support_command,
                        contains_text=release_status_md,
                    )
                command_payload_check(
                    checks,
                    check_id="release_status_md_next_step_command",
                    expected=expected_next_step,
                    contains_text=release_status_md,
                )
                command_payload_check(
                    checks,
                    check_id="release_status_md_next_step_repo_command",
                    expected=expected_repo_next_step,
                    contains_text=release_status_md,
                )
                command_payload_check(
                    checks,
                    check_id="release_status_md_next_step_origin_command",
                    expected=expected_origin_next_step,
                    contains_text=release_status_md,
                )
                command_payload_check(
                    checks,
                    check_id="release_status_md_next_step_env_command",
                    expected=expected_env_next_step,
                    contains_text=release_status_md,
                )
                command_payload_check(
                    checks,
                    check_id="release_status_md_next_step_connected_json_env_command",
                    expected=expected_connected_json_only_env,
                    contains_text=release_status_md,
                )
                command_payload_check(
                    checks,
                    check_id="release_status_md_next_step_local_readiness_json_command",
                    expected=expected_local_readiness_json,
                    contains_text=release_status_md,
                )
                command_payload_check(
                    checks,
                    check_id="release_status_md_next_step_local_readiness_command_only_command",
                    expected=expected_local_readiness_command_only,
                    contains_text=release_status_md,
                )
                command_payload_check(
                    checks,
                    check_id="release_status_md_next_step_local_readiness_setup_sequence_command",
                    expected=expected_local_readiness_setup_sequence,
                    contains_text=release_status_md,
                )
                command_payload_check(
                    checks,
                    check_id="release_status_md_next_step_local_readiness_command_sequence_command",
                    expected=expected_local_readiness_command_sequence,
                    contains_text=release_status_md,
                )
                command_payload_check(
                    checks,
                    check_id="release_status_md_next_step_local_readiness_setup_sequence_preview_command",
                    expected=expected_local_readiness_setup_sequence_preview,
                    contains_text=release_status_md,
                )
                command_payload_check(
                    checks,
                    check_id="release_status_md_next_step_local_readiness_command_sequence_preview_command",
                    expected=expected_local_readiness_command_sequence_preview,
                    contains_text=release_status_md,
                )
                command_payload_check(
                    checks,
                    check_id="release_status_md_next_step_local_readiness_gate_json_command",
                    expected=expected_local_readiness_gate_json,
                    contains_text=release_status_md,
                )
                command_payload_check(
                    checks,
                    check_id="release_status_md_command_only_env_command",
                    expected=expected_command_only_env,
                    contains_text=release_status_md,
                )
                command_payload_check(
                    checks,
                    check_id="release_status_md_json_only_env_command",
                    expected=expected_json_only_env,
                    contains_text=release_status_md,
                )
                command_payload_check(
                    checks,
                    check_id="release_status_md_sequence_command",
                    expected=expected_sequence,
                    contains_text=release_status_md,
                )
                command_payload_check(
                    checks,
                    check_id="release_status_md_operator_sequence_command",
                    expected=expected_operator_sequence,
                    contains_text=release_status_md,
                )
                command_payload_check(
                    checks,
                    check_id="release_status_md_operator_command_only_command",
                    expected=expected_operator_command_only,
                    contains_text=release_status_md,
                )
                command_payload_check(
                    checks,
                    check_id="release_status_md_operator_json_only_command",
                    expected=expected_operator_json_only,
                    contains_text=release_status_md,
                )
                command_payload_check(
                    checks,
                    check_id="release_status_md_connected_sequence_command",
                    expected=expected_connected_sequence,
                    contains_text=release_status_md,
                )
                command_payload_check(
                    checks,
                    check_id="release_status_md_connected_sequence_origin_command",
                    expected=expected_connected_sequence_origin,
                    contains_text=release_status_md,
                )
                command_payload_check(
                    checks,
                    check_id="release_status_md_connected_sequence_env_command",
                    expected=expected_connected_sequence_env,
                    contains_text=release_status_md,
                )
                command_payload_check(
                    checks,
                    check_id="release_status_md_local_readiness_command",
                    expected=expected_local_readiness,
                    contains_text=release_status_md,
                )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_next_step_handoff_command",
                payload=release_status,
                expected=expected_next_step,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_read_only_evidence_check_handoff_command",
                payload=release_status,
                expected=expected_read_only_evidence_check,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_progress_handoff_command",
                payload=release_status,
                expected=expected_release_status_progress,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_progress_json_handoff_command",
                payload=release_status,
                expected=expected_release_status_progress_json,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_completion_plan_handoff_command",
                payload=release_status,
                expected=expected_release_status_completion_plan,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_completion_plan_json_handoff_command",
                payload=release_status,
                expected=expected_release_status_completion_plan_json,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_completion_requirements_handoff_command",
                payload=release_status,
                expected=expected_release_status_completion_requirements,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_completion_requirements_json_handoff_command",
                payload=release_status,
                expected=expected_release_status_completion_requirements_json,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_owner_lanes_handoff_command",
                payload=release_status,
                expected=expected_release_status_owner_lanes,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_owner_lanes_json_handoff_command",
                payload=release_status,
                expected=expected_release_status_owner_lanes_json,
            )
            progress_summary_checks(
                checks,
                payload=release_status,
                expected_preflight=expected_preflight,
                expected_next_command_only=expected_command_only_env,
                expected_next_json_only=expected_json_only_env,
                expected_connected_command_only=expected_connected_command_only_env,
                expected_connected_command_sequence=expected_connected_command_sequence_env,
                expected_operator_command_only=expected_operator_command_only,
                expected_operator_command_sequence=expected_operator_command_sequence,
                expected_operator_review_sequence=expected_operator_review_sequence,
                expected_operator_json_only=expected_operator_json_only,
                expected_remaining_sequence=expected_command_sequence_env,
                expected_progress_json=expected_release_status_progress_json,
                expected_completion_plan=expected_release_status_completion_plan,
                expected_completion_plan_json=expected_release_status_completion_plan_json,
                expected_completion_requirements=expected_release_status_completion_requirements,
                expected_completion_requirements_json=expected_release_status_completion_requirements_json,
                expected_handoff_context_json=expected_handoff_context_json,
                expected_handoff_command_sequence=expected_handoff_command_sequence,
                expected_local_readiness_setup_sequence=expected_local_readiness_setup_sequence,
                expected_local_readiness_command_sequence=expected_local_readiness_command_sequence,
                expected_local_readiness_setup_sequence_preview=expected_local_readiness_setup_sequence_preview,
                expected_local_readiness_command_sequence_preview=expected_local_readiness_command_sequence_preview,
                expected_external_readiness_summary_json=expected_external_readiness_summary_json,
                expected_external_readiness_strict_summary_json=expected_external_readiness_strict_summary_json,
                expected_warning_gate_json=expected_warning_review_gate_json,
                expected_warning_summary_json=expected_warning_review_summary_json,
                expected_warning_gate_summary_json=expected_warning_review_gate_summary_json,
                expected_warning_review_artifacts_only=expected_warning_review_artifacts_only,
                expected_warning_review_next_command_gate=expected_warning_review_next_command_gate,
                expected_warning_action_plan_path=expected_warning_action_plan_path,
                expected_warning_operator_checklist_path=expected_warning_operator_checklist_path,
                expected_operator_command=expected_read_only_warning_review,
                expected_owner_lanes=expected_release_status_owner_lanes,
                expected_owner_lanes_json=expected_release_status_owner_lanes_json,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_read_only_warning_review_handoff_command",
                payload=release_status,
                expected=expected_read_only_warning_review,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_warning_review_apply_handoff_command",
                payload=release_status,
                expected=expected_warning_review_apply,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_warning_review_artifacts_only_handoff_command",
                payload=release_status,
                expected=expected_warning_review_artifacts_only,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_warning_review_next_command_only_handoff_command",
                payload=release_status,
                expected=expected_warning_review_next_command_only,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_warning_review_next_command_gate_handoff_command",
                payload=release_status,
                expected=expected_warning_review_next_command_gate,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_live_beta_preflight_handoff_command",
                payload=release_status,
                expected=expected_live_beta_preflight,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_live_beta_preflight_json_handoff_command",
                payload=release_status,
                expected=expected_live_beta_preflight_json,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_live_beta_next_command_only_handoff_command",
                payload=release_status,
                expected=expected_live_beta_next_command_only,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_live_beta_closeout_handoff_command",
                payload=release_status,
                expected=expected_live_beta_closeout,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_live_beta_final_gate_handoff_command",
                payload=release_status,
                expected=expected_live_beta_final_gate,
            )
            for support_name, support_command in expected_live_beta_support_commands.items():
                handoff_command_list_check(
                    checks,
                    check_id=f"release_status_json_live_beta_{support_name}_support_handoff_command",
                    payload=release_status,
                    expected=support_command,
                )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_next_step_repo_handoff_command",
                payload=release_status,
                expected=expected_repo_next_step,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_next_step_origin_handoff_command",
                payload=release_status,
                expected=expected_origin_next_step,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_next_step_env_handoff_command",
                payload=release_status,
                expected=expected_env_next_step,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_command_only_env_handoff_command",
                payload=release_status,
                expected=expected_command_only_env,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_json_only_env_handoff_command",
                payload=release_status,
                expected=expected_json_only_env,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_sequence_handoff_command",
                payload=release_status,
                expected=expected_sequence,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_operator_sequence_handoff_command",
                payload=release_status,
                expected=expected_operator_sequence,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_operator_command_only_handoff_command",
                payload=release_status,
                expected=expected_operator_command_only,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_operator_command_sequence_handoff_command",
                payload=release_status,
                expected=expected_operator_command_sequence,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_operator_review_sequence_handoff_command",
                payload=release_status,
                expected=expected_operator_review_sequence,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_operator_json_only_handoff_command",
                payload=release_status,
                expected=expected_operator_json_only,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_connected_sequence_handoff_command",
                payload=release_status,
                expected=expected_connected_sequence,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_connected_sequence_origin_handoff_command",
                payload=release_status,
                expected=expected_connected_sequence_origin,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_connected_sequence_env_handoff_command",
                payload=release_status,
                expected=expected_connected_sequence_env,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_local_readiness_handoff_command",
                payload=release_status,
                expected=expected_local_readiness,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_local_readiness_json_handoff_command",
                payload=release_status,
                expected=expected_local_readiness_json,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_local_readiness_command_only_handoff_command",
                payload=release_status,
                expected=expected_local_readiness_command_only,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_local_readiness_setup_sequence_handoff_command",
                payload=release_status,
                expected=expected_local_readiness_setup_sequence,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_local_readiness_command_sequence_handoff_command",
                payload=release_status,
                expected=expected_local_readiness_command_sequence,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_local_readiness_setup_sequence_preview_handoff_command",
                payload=release_status,
                expected=expected_local_readiness_setup_sequence_preview,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_local_readiness_command_sequence_preview_handoff_command",
                payload=release_status,
                expected=expected_local_readiness_command_sequence_preview,
            )
            handoff_command_list_check(
                checks,
                check_id="release_status_json_local_readiness_gate_json_handoff_command",
                payload=release_status,
                expected=expected_local_readiness_gate_json,
            )

    if next_step is not None:
        command_payload_check(
            checks,
            check_id="next_release_step_json_preflight_command",
            expected=expected_preflight,
            actual=next_step.get("bundle_preflight_command"),
            require_when_contains="run-connected-runner-handoff.sh",
        )
        command_payload_check(
            checks,
            check_id="next_release_step_json_full_command",
            expected=expected_full,
            actual=next_step.get("bundle_script_command"),
            require_when_contains="run-connected-runner-handoff.sh",
        )
        next_command = next_step.get("next_command")
        if isinstance(next_command, str) and "run-connected-runner-handoff.sh" in next_command:
            command_payload_check(
                checks,
                check_id="next_release_step_json_next_command",
                expected=expected_preflight,
                actual=next_command,
            )

    failures = [check for check in checks if check["status"] == "fail"]
    details["failure_count"] = len(failures)
    if failures:
        return (
            "fail",
            "Copied release-status/next-release-step handoff commands are missing or inconsistent.",
            details,
            str(package_dir),
        )

    if handoff_root is not None and reference_bundle != str(handoff_root):
        details["current_handoff_root_mismatch"] = {
            "current_handoff_root": str(handoff_root),
            "reference_bundle": reference_bundle,
        }
        return (
            "warn",
            (
                "Copied handoff commands are internally consistent, but they point to the packaging-time "
                "bundle path rather than this extracted handoff root. Run the bundled script from the "
                "current bundle root on this runner."
            ),
            details,
            str(package_dir),
        )

    return (
        "pass",
        "Copied release-status/next-release-step commands are internally consistent and point to this handoff root.",
        details,
        str(package_dir),
    )


def verify_runner_script(handoff_root: Path | None) -> tuple[str, str, dict[str, Any], str | None]:
    if handoff_root is None:
        return "warn", "No handoff root was detected, so the bundle runner script was not checked.", {}, None
    script_path = handoff_root / "run-connected-runner-handoff.sh"
    details: dict[str, Any] = {
        "script_path": str(script_path),
        "missing_markers": [],
        "order": None,
        "remote_guard": None,
        "syntax": None,
    }
    if not script_path.is_file():
        return "fail", "Connected-runner bundle script is missing.", details, str(script_path)
    executable = bool(script_path.stat().st_mode & 0o111)
    if not executable:
        return "fail", "Connected-runner bundle script is not executable.", details, str(script_path)
    text = script_path.read_text(encoding="utf-8")
    missing_markers = [marker for marker in RUNNER_SCRIPT_MARKERS if marker not in text]
    details["missing_markers"] = missing_markers
    if missing_markers:
        return (
            "fail",
            "Connected-runner bundle script is missing fail-fast preflight markers: "
            + ", ".join(missing_markers),
            details,
            str(script_path),
        )
    bash = shutil.which("bash")
    if bash is None:
        return "fail", "bash is unavailable; runner script syntax cannot be checked.", details, str(script_path)
    completed = subprocess.run([bash, "-n", str(script_path)], text=True, capture_output=True)
    details["syntax"] = {
        "command": [bash, "-n", str(script_path)],
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    if completed.returncode != 0:
        return "fail", "Connected-runner bundle script syntax check failed.", details, str(script_path)
    remote_guard_ok, remote_guard_message, remote_guard_details = verify_runner_remote_guard(text)
    details["remote_guard"] = remote_guard_details
    if not remote_guard_ok:
        return "fail", remote_guard_message, details, str(script_path)
    order_ok, order_message, order_details = verify_runner_script_order(text)
    details["order"] = order_details
    if not order_ok:
        return "fail", order_message, details, str(script_path)
    return (
        "pass",
        "Connected-runner bundle script is executable, syntactically valid, ordered safely, and has fail-fast remote/auth preflight.",
        details,
        str(script_path),
    )


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Connected Runner Acceptance",
        "",
        f"Generated at: {report['generated_at']}",
        f"Status: {report['status']}",
        f"Source root: `{report['source_root']}`",
        f"Handoff root: `{report.get('handoff_root') or 'not detected'}`",
        f"Evidence package: `{report.get('package_dir') or 'not detected'}`",
        "",
        "## Checks",
        "",
    ]
    for check in report["checks"]:
        lines.extend(
            [
                f"### {check['label']}",
                "",
                f"- Status: {check['status']}",
                f"- Message: {check['message']}",
            ]
        )
        if check.get("evidence"):
            lines.append(f"- Evidence: `{check['evidence']}`")
        lines.append("")

    lines.extend(
        [
            "## Next Commands",
            "",
            "```bash",
            "cd ..",
            "# Preflight rejects missing/placeholder/invalid GIT_ORIGIN_URL values, then self-verifies the bundle before external checks and remote setup.",
            f"PREFLIGHT_ONLY=true GIT_ORIGIN_URL={REPO_URL_PLACEHOLDER} ./run-connected-runner-handoff.sh",
            f"GIT_ORIGIN_URL={REPO_URL_PLACEHOLDER} ./run-connected-runner-handoff.sh",
            "# Or, from source/:",
            "git init",
            "git checkout -b codex/quant-lab-release",
            git_origin_setup_command(),
            "git remote get-url origin",
            "docker compose version",
            "gh auth status",
            "python3 scripts/connected_runner_acceptance.py --handoff-root .. --require-external --check-gh-auth",
            "python3 -m venv backend/.venv",
            "backend/.venv/bin/python -m pip install --upgrade pip",
            "backend/.venv/bin/python -m pip install -e \"backend[dev]\"",
            "npm ci --prefix frontend",
            CONNECTED_STRICT_GATE_COMMAND,
            "```",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    source_root = detect_source_root(args)
    handoff_root = detect_handoff_root(args, source_root)
    package_dir = (
        Path(args.package_dir).absolute()
        if args.package_dir
        else latest_package_dir(handoff_root=handoff_root, source_root=source_root)
    )
    if args.output_dir:
        output_dir = Path(args.output_dir)
    elif handoff_root is not None:
        output_dir = handoff_root / "acceptance-artifacts"
    else:
        output_dir = source_root / "artifacts/connected-runner-acceptance"
    if not output_dir.is_absolute():
        output_dir = source_root / output_dir
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_dir = output_dir / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    checks: list[dict[str, Any]] = []
    missing_required = [path for path in REQUIRED_SOURCE_FILES if not (source_root / path).is_file()]
    add_check(
        checks,
        check_id="required_source_files",
        label="Required Source Files",
        status="pass" if not missing_required else "fail",
        message=(
            "Required source files are present."
            if not missing_required
            else "Missing required source files: " + ", ".join(missing_required)
        ),
        evidence=str(source_root),
    )

    missing_gitignore, gitignore_error = missing_gitignore_patterns(source_root)
    add_check(
        checks,
        check_id="source_gitignore_guards",
        label="Source Gitignore Guards",
        status="pass" if not missing_gitignore else "fail",
        message=(
            "Source .gitignore keeps generated, dependency, data, backup, and secret paths out of git add."
            if not missing_gitignore
            else "Source .gitignore is missing guard pattern(s): " + ", ".join(missing_gitignore)
        ),
        evidence=str(source_root / ".gitignore"),
        details={
            "missing_patterns": missing_gitignore,
            "read_error": gitignore_error,
        },
    )

    forbidden = forbidden_source_paths(source_root)
    generated_paths = local_generated_paths(source_root)
    add_check(
        checks,
        check_id="source_safety_exclusions",
        label="Source Safety Exclusions",
        status="pass" if not forbidden else "fail",
        message=(
            "Source root excludes local secrets, local databases, backups, and unsafe generated files."
            if not forbidden
            else "Forbidden source paths are present: " + ", ".join(forbidden[:20])
        ),
        evidence=str(source_root),
        details={
            "forbidden_count": len(forbidden),
            "allowed_local_generated_paths": generated_paths,
        },
    )

    runner_status, runner_message, runner_details, runner_evidence = verify_runner_script(handoff_root)
    add_check(
        checks,
        check_id="handoff_runner_script",
        label="Handoff Runner Script",
        status=runner_status,
        message=runner_message,
        evidence=runner_evidence,
        details=runner_details,
    )
    handoff_context_status, handoff_context_message, handoff_context_details, handoff_context_evidence = (
        verify_handoff_readme_completion_context(
            handoff_root=handoff_root,
            package_dir=package_dir,
        )
    )
    add_check(
        checks,
        check_id="handoff_readme_completion_context",
        label="Handoff README Completion Context",
        status=handoff_context_status,
        message=handoff_context_message,
        evidence=handoff_context_evidence,
        details=handoff_context_details,
    )

    if package_dir is None:
        add_check(
            checks,
            check_id="evidence_package",
            label="Evidence Package",
            status="fail",
            message="No copied evidence package was found.",
        )
    else:
        add_check(
            checks,
            check_id="evidence_package",
            label="Evidence Package",
            status="pass" if (package_dir / "manifest.json").is_file() else "fail",
            message=(
                "Copied evidence package manifest is present."
                if (package_dir / "manifest.json").is_file()
                else "Copied evidence package manifest is missing."
            ),
            evidence=str(package_dir),
        )
        archive_status, archive_message = verify_evidence_archive(package_dir)
        add_check(
            checks,
            check_id="evidence_archive",
            label="Evidence Archive",
            status=archive_status,
            message=archive_message,
            evidence=str(package_dir),
        )
        command_status, command_message, command_details, command_evidence = verify_copied_evidence_handoff_commands(
            handoff_root=handoff_root,
            package_dir=package_dir,
        )
        add_check(
            checks,
            check_id="copied_evidence_handoff_commands",
            label="Copied Evidence Handoff Commands",
            status=command_status,
            message=command_message,
            evidence=command_evidence,
            details=command_details,
        )

    external_command = [sys.executable, "scripts/check_external_readiness.py"]
    external_output_dir = run_dir / "external-readiness"
    external_command.extend(["--output-dir", str(external_output_dir)])
    if args.require_external:
        external_command.extend(["--require-git-remote", "--require-docker", "--require-gh"])
    if args.check_gh_auth:
        external_command.append("--check-gh-auth")
    external_result = run_command(external_command, cwd=source_root)
    external_summary_path = newest_json(external_output_dir, "*/external-readiness.json")
    external_status = "fail" if external_result["returncode"] != 0 else "pass"
    external_message = "External readiness command completed."
    external_payload: dict[str, Any] | None = None
    if external_summary_path:
        external_payload = read_json(external_summary_path)
        external_status = str(external_payload.get("status") or external_status)
        if external_result["returncode"] != 0:
            external_status = "fail"
        external_message = f"External readiness status is {external_payload.get('status')}."
    add_check(
        checks,
        check_id="external_readiness",
        label="External Readiness",
        status=external_status,
        message=external_message,
        evidence=str(external_summary_path) if external_summary_path else None,
        details={"command": external_result, "summary": external_payload},
    )

    if args.run_strict_gate:
        strict_command = [
            sys.executable,
            "scripts/release_gate.py",
            "--run-smoke",
            "--strict-external",
            "--api-base",
            args.api_base,
            "--symbol",
            args.symbol.upper(),
        ]
        if args.check_gh_auth:
            strict_command.append("--check-gh-auth")
        strict_result = run_command(strict_command, cwd=source_root)
        add_check(
            checks,
            check_id="strict_release_gate",
            label="Strict Release Gate",
            status="pass" if strict_result["returncode"] == 0 else "fail",
            message=(
                "Strict release gate passed."
                if strict_result["returncode"] == 0
                else "Strict release gate failed; inspect stdout/stderr in the JSON report."
            ),
            details={"command": strict_result},
        )

    has_failures = any(check["status"] == "fail" for check in checks)
    has_warnings = any(check["status"] == "warn" for check in checks)
    status = "fail" if has_failures else ("warn" if has_warnings else "pass")
    json_path = run_dir / "connected-runner-acceptance.json"
    markdown_path = run_dir / "connected-runner-acceptance.md"
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "source_root": str(source_root),
        "handoff_root": str(handoff_root) if handoff_root else None,
        "package_dir": str(package_dir) if package_dir else None,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "require_external": bool(args.require_external),
        "check_gh_auth": bool(args.check_gh_auth),
        "run_strict_gate": bool(args.run_strict_gate),
        "checks": checks,
    }

    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(markdown_path, report)

    if args.summary_json_only:
        summary = {
            "generated_at": report["generated_at"],
            "status": status,
            "source_root": str(source_root),
            "handoff_root": str(handoff_root) if handoff_root else None,
            "package_dir": str(package_dir) if package_dir else None,
            "json_path": str(json_path),
            "markdown_path": str(markdown_path),
            "require_external": bool(args.require_external),
            "check_gh_auth": bool(args.check_gh_auth),
            "run_strict_gate": bool(args.run_strict_gate),
            "check_summary": compact_check_summary(report),
        }
        print(json.dumps(summary, indent=2, sort_keys=True))
    elif args.json_only:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        for check in checks:
            print(f"{check['status'].upper():5} {check['id']}: {check['message']}")
        print(f"Connected-runner acceptance: {json_path}")
    return 1 if status == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
