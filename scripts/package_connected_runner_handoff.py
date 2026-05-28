#!/usr/bin/env python3
"""Create a source and evidence bundle for a connected release runner."""

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
from pathlib import Path, PurePosixPath
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
        owner_lanes_summary as shared_owner_lanes_summary,
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
        handoff_completion_context_summary_lines,
        verify_handoff_completion_context,
        is_packaged_source_excluded,
        missing_required_gitignore_patterns as missing_gitignore_patterns_from_text,
        missing_runner_script_markers,
        verify_runner_remote_guard as verify_runner_script_remote_guard,
        verify_runner_script_order,
    )
    from scripts.release_artifacts import latest_manifest_package_dir
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
        owner_lanes_summary as shared_owner_lanes_summary,
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
        handoff_completion_context_summary_lines,
        verify_handoff_completion_context,
        is_packaged_source_excluded,
        missing_required_gitignore_patterns as missing_gitignore_patterns_from_text,
        missing_runner_script_markers,
        verify_runner_remote_guard as verify_runner_script_remote_guard,
        verify_runner_script_order,
    )
    from release_artifacts import latest_manifest_package_dir
    from release_manifest import HANDOFF_REQUIRED_SOURCE_FILES


SOURCE_PATHS: tuple[str, ...] = (
    "README.md",
    ".env.example",
    ".gitignore",
    ".dockerignore",
    "docker-compose.yml",
    ".github",
    "backend/Dockerfile",
    "backend/pyproject.toml",
    "backend/app",
    "backend/tests",
    "frontend/Dockerfile",
    "frontend/index.html",
    "frontend/nginx.conf",
    "frontend/package-lock.json",
    "frontend/package.json",
    "frontend/src",
    "frontend/tsconfig.json",
    "frontend/tsconfig.node.json",
    "frontend/vite.config.ts",
    "docs",
    "scripts",
)

COPIED_EVIDENCE_COMMAND_FILES: tuple[str, ...] = (
    "release-status.md",
    "release-status.json",
    "next-release-step.md",
    "next-release-step.json",
)

HANDOFF_NEXT_STEP_MARKERS: tuple[str, ...] = (
    "## Current Completion Context",
    "## Current Bundle Next Steps",
    "export GIT_ORIGIN_URL=https://github.com/OWNER/REPO.git",
    "PREFLIGHT_ONLY=true ./run-connected-runner-handoff.sh",
    "source/scripts/next_release_step.py",
    '--handoff-bundle "$(pwd)"',
    "--handoff-context-json-only",
    "--handoff-command-sequence-only",
    "placeholder values are rejected",
    "--summary-by-owner",
    "--show-sequence",
    "--local-readiness",
    "--local-readiness --no-write",
    "--local-readiness-setup-sequence-only",
    "--local-readiness-command-sequence-only",
    "--fail-if-local-readiness-not-pass",
)

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Package Quant Lab source and evidence for a connected runner.")
    parser.add_argument(
        "--verify",
        help="Verify an existing connected-runner handoff bundle directory instead of creating a new one.",
    )
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
        "--project-root",
        default=".",
        help="Quant Lab project root.",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/handoff-bundles",
        help="Directory where connected-runner handoff bundles are created.",
    )
    parser.add_argument(
        "--bundle-dir",
        help="Exact handoff bundle directory to create. Fails if it already exists.",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Print the create or verify summary as JSON instead of human-readable lines.",
    )
    parser.add_argument(
        "--summary-json-only",
        action="store_true",
        help="Print a compact machine-readable summary without embedding verbose check details.",
    )
    parser.add_argument(
        "--handoff-context-json-only",
        action="store_true",
        help=(
            "Print only handoff_context JSON. With --verify, reads it from the existing bundle manifest; "
            "without --verify, computes it from the selected evidence package without creating a bundle."
        ),
    )
    parser.add_argument(
        "--handoff-command-sequence-only",
        action="store_true",
        help=(
            "Print only handoff_context bundle command sequence commands, one per line. With --verify, "
            "reads it from the existing bundle manifest; without --verify, computes it from the selected "
            "evidence package without creating a bundle."
        ),
    )
    return parser.parse_args()


def next_bundle_dir(output_dir: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    base = output_dir / f"quant-lab-connected-runner-handoff-{timestamp}"
    if not base.exists():
        return base
    for sequence in range(1, 100):
        candidate = output_dir / f"{base.name}-{sequence:02d}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"No available handoff bundle sequence under {output_dir}")


def should_skip(path: Path) -> bool:
    return is_packaged_source_excluded(path)


def iter_source_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for relative in SOURCE_PATHS:
        source = root / relative
        if not source.exists():
            continue
        if source.is_file():
            if not should_skip(Path(relative)):
                files.append(source)
            continue
        for path in sorted(source.rglob("*")):
            relative_path = path.relative_to(root)
            if path.is_file() and not should_skip(relative_path):
                files.append(path)
    return sorted(set(files), key=lambda path: str(path.relative_to(root)))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def copy_source(root: Path, bundle_dir: Path) -> list[dict[str, str]]:
    copied: list[dict[str, str]] = []
    source_root = bundle_dir / "source"
    for path in iter_source_files(root):
        relative_path = path.relative_to(root)
        target = source_root / relative_path
        copy_file(path, target)
        copied.append(
            {
                "path": str(relative_path),
                "sha256": sha256_file(path),
            }
        )
    return copied


def evidence_sources(package_dir: Path) -> list[Path]:
    candidates = [
        package_dir.with_suffix(".tgz"),
        package_dir.with_suffix(".tgz.sha256"),
        package_dir / "release-status.md",
        package_dir / "release-status.json",
        package_dir / "next-release-step.md",
        package_dir / "next-release-step.json",
        package_dir / "release-evidence-check.json",
        package_dir / "release-warning-triage.md",
        package_dir / "release-warning-triage.json",
        package_dir / "release-warning-actions.md",
        package_dir / "release-warning-actions.json",
        package_dir / "release-warning-operator-checklist.md",
        package_dir / "evidence-checksums.json",
        package_dir / "evidence-checksums.sha256",
        package_dir / "README.md",
        package_dir / "manifest.json",
    ]
    return [path for path in candidates if path.exists()]


def handoff_completion_context_lines(package_dir: Path) -> list[str]:
    release_status_path = package_dir / "release-status.json"
    if not release_status_path.exists():
        return [
            "## Current Completion Context",
            "",
            f"- Release status JSON is not available in `{package_dir.name}` yet.",
            f"- After packaging, inspect `evidence/{package_dir.name}/release-status.md` and `next-release-step.md`.",
            "",
        ]

    try:
        release_status = json.loads(release_status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [
            "## Current Completion Context",
            "",
            f"- Release status JSON could not be read: {exc}",
            f"- Inspect `evidence/{package_dir.name}/release-status.md` and `next-release-step.md` after transfer.",
            "",
        ]

    lines = [
        "## Current Completion Context",
        "",
    ]
    lines.extend(handoff_completion_context_summary_lines(release_status))
    lines.extend(
        [
            f"- Full status: `evidence/{package_dir.name}/release-status.md`",
            f"- Next step: `evidence/{package_dir.name}/next-release-step.md`",
            "",
        ]
    )
    return lines


def copy_evidence(package_dir: Path, bundle_dir: Path) -> list[dict[str, str]]:
    copied: list[dict[str, str]] = []
    evidence_root = bundle_dir / "evidence" / package_dir.name
    for path in evidence_sources(package_dir):
        if path.parent == package_dir:
            relative_path = path.name
        else:
            relative_path = path.name
        target = evidence_root / relative_path
        copy_file(path, target)
        copied.append(
            {
                "path": str(Path("evidence") / package_dir.name / relative_path),
                "source": str(path),
                "sha256": sha256_file(path),
            }
        )
    return copied


def write_handoff_readme(bundle_dir: Path, package_dir: Path) -> None:
    lines = [
        "# Quant Lab Connected Runner Handoff",
        "",
        "This bundle contains a safe source snapshot plus the latest release evidence package.",
        "It excludes `.env`, local databases, virtual environments, node modules, backups, and generated artifacts.",
        "",
        "## One-Command Runner Flow",
        "",
        "Export the real remote URL, then run the no-install/no-push preflight from the bundle root:",
        "",
        "```bash",
        "export GIT_ORIGIN_URL=https://github.com/OWNER/REPO.git",
        "PREFLIGHT_ONLY=true ./run-connected-runner-handoff.sh",
        "```",
        "",
        "After the preflight passes, run the full bundled script from the same bundle root:",
        "",
        "```bash",
        "./run-connected-runner-handoff.sh",
        "```",
        "",
        f"Inline commands with `GIT_ORIGIN_URL={REPO_URL_PLACEHOLDER}` are still supported, but the export-first form above makes placeholder replacement explicit before any runner script starts.",
        "",
        "Optional environment variables:",
        "",
        "- `BRANCH_NAME`: target branch name, default `codex/quant-lab-release`.",
        "- `ALLOW_ORIGIN_REWRITE=true`: replace an existing `origin` URL.",
        "- `PREFLIGHT_ONLY=true`: stop after remote URL guards, bundle verification, command/auth checks, git remote setup, and acceptance preflight.",
        "- `SETUP_GH_GIT_AUTH=false`: skip the default `gh auth setup-git` helper setup before `git ls-remote`.",
        "- `RUN_FINAL_LIVE_BETA_GATE=true`: run the final `--require-live-beta` gate after the normal strict gate.",
        "- If git user identity is missing, the script sets local fallback identity for this handoff repository only.",
        "",
        "The script rejects missing, placeholder, or malformed `GIT_ORIGIN_URL` values first, self-verifies the handoff bundle before external command/auth checks, fails fast before dependency installation if `git`, `python3`, `npm`, Docker Compose, GitHub CLI, or GitHub CLI auth are unavailable, then runs acceptance before installing backend/frontend dependencies.",
        "If this bundle was moved to a different absolute path, copied release status commands may still show the packaging-time path; run the script from the current bundle root.",
        "",
    ]
    lines.extend(handoff_completion_context_lines(package_dir))
    lines.extend(
        [
            "## Current Bundle Next Steps",
            "",
            "Replace `REPO_URL` with a real HTTPS, SSH, or scp-style git remote URL before running commands that include `--repo-url`; placeholder values are rejected.",
            "",
            "To print only the bundle manifest handoff context without rewriting verification reports:",
            "",
            "```bash",
            "python3 source/scripts/package_connected_runner_handoff.py --verify \"$(pwd)\" --handoff-context-json-only",
            "```",
            "",
            "To print only the ordered bundle-root commands from that handoff context:",
            "",
            "```bash",
            "python3 source/scripts/package_connected_runner_handoff.py --verify \"$(pwd)\" --handoff-command-sequence-only",
            "```",
            "",
            "From the current bundle root, print runner-specific commands using the copied evidence package and current bundle path:",
            "",
            "```bash",
            "python3 source/scripts/next_release_step.py --handoff-bundle \"$(pwd)\" --owner \"connected runner\" --repo-url REPO_URL --summary-by-owner --show-sequence --no-write",
            "```",
            "",
            "If `origin` already exists inside `source/`, print the same commands from that local remote:",
            "",
            "```bash",
            "python3 source/scripts/next_release_step.py --handoff-bundle \"$(pwd)\" --owner \"connected runner\" --repo-url-from-origin --summary-by-owner --show-sequence --no-write",
            "```",
            "",
            "If `GIT_ORIGIN_URL` is already exported, print the same commands from that environment variable:",
            "",
            "```bash",
            "python3 source/scripts/next_release_step.py --handoff-bundle \"$(pwd)\" --owner \"connected runner\" --repo-url-from-env GIT_ORIGIN_URL --summary-by-owner --show-sequence --no-write",
            "```",
            "",
            "To include local `origin`, Docker Compose, and GitHub CLI auth checks in the same output:",
            "",
            "```bash",
            "python3 source/scripts/next_release_step.py --handoff-bundle \"$(pwd)\" --owner \"connected runner\" --summary-by-owner --show-sequence --local-readiness --no-write",
            "```",
            "",
            "To use local readiness as an automation gate while still printing the JSON payload:",
            "",
            "```bash",
            "python3 source/scripts/next_release_step.py --handoff-bundle \"$(pwd)\" --owner \"connected runner\" --repo-url-from-env GIT_ORIGIN_URL --json-only --fail-if-repo-url-required --local-readiness --fail-if-local-readiness-not-pass",
            "```",
            "",
            "To print only unresolved local-readiness setup commands, one per line:",
            "",
            "```bash",
            "python3 source/scripts/next_release_step.py --handoff-bundle \"$(pwd)\" --owner \"connected runner\" --repo-url-from-env GIT_ORIGIN_URL --local-readiness-setup-sequence-only --fail-if-local-readiness-not-pass",
            "```",
            "",
            "To print unresolved setup commands followed by their matching verification commands:",
            "",
            "```bash",
            "python3 source/scripts/next_release_step.py --handoff-bundle \"$(pwd)\" --owner \"connected runner\" --repo-url-from-env GIT_ORIGIN_URL --local-readiness-command-sequence-only --fail-if-local-readiness-not-pass",
            "```",
            "",
            "To print every remaining connected-runner and operator item from the copied evidence package:",
            "",
            "```bash",
            "python3 source/scripts/next_release_step.py --handoff-bundle \"$(pwd)\" --summary-by-owner --show-sequence --no-write",
            "```",
            "",
            "## Suggested Connected-Runner Flow",
            "",
            "```bash",
            f"cd {bundle_dir.name}/source",
            "git init .",
            "git checkout -b codex/quant-lab-release",
            "git config user.email quant-lab-release@example.invalid",
            "git config user.name \"Quant Lab Release Bot\"",
            git_origin_setup_command(),
            "git remote get-url origin",
            "docker compose version",
            "gh auth status",
            "python3 scripts/connected_runner_acceptance.py --handoff-root .. --require-external --check-gh-auth",
            "python3 -m venv backend/.venv",
            "backend/.venv/bin/python -m pip install --upgrade pip",
            "backend/.venv/bin/python -m pip install -e \"backend[dev]\"",
            "npm ci --prefix frontend",
            "git ls-files --others --modified --deleted --exclude-standard -z | git add --pathspec-from-file=- --pathspec-file-nul",
            "git commit -m \"Prepare Quant Lab release handoff\"",
            "git push -u origin codex/quant-lab-release",
            CONNECTED_STRICT_GATE_COMMAND,
            "```",
            "",
            "After a live-beta closeout archive exists:",
            "",
            "```bash",
            LIVE_BETA_FINAL_GATE_COMMAND,
            "```",
            "",
            "## Included Evidence",
            "",
            f"- Evidence package: `{package_dir.name}`",
            f"- Evidence archive: `evidence/{package_dir.name}/{package_dir.name}.tgz` when present",
            "- Bundle self-verification report: `handoff-verification.json`.",
            "- Handoff tarball verification report: `../{BUNDLE_NAME}.tgz.verification.json` next to the `.tgz` archive.",
            "- Verify the copied evidence archive sidecar with `python3 scripts/connected_runner_acceptance.py --handoff-root PATH_TO_BUNDLE`; add `--json-only` for full parseable details or `--summary-json-only` for compact automation status.",
            "- After extracting the evidence archive itself, verify the full package with `scripts/write_evidence_checksums.py --package-dir EXTRACTED_PACKAGE --verify`; add `--json-only` when automation needs a parseable result.",
            "- Verify this bundle with `python3 scripts/package_connected_runner_handoff.py --verify PATH_TO_BUNDLE`; add `--json-only` for full parseable details or `--summary-json-only` for compact automation status. A path mismatch warning is expected if the bundle was moved after packaging.",
            "",
        ]
    )
    (bundle_dir / "HANDOFF.md").write_text("\n".join(lines), encoding="utf-8")


def write_runner_script(bundle_dir: Path) -> Path:
    script_path = bundle_dir / "run-connected-runner-handoff.sh"
    script = """#!/usr/bin/env bash
set -euo pipefail

if [ -z "${GIT_ORIGIN_URL:-}" ]; then
  echo "Set GIT_ORIGIN_URL to the target git remote URL before running this script." >&2
  echo "Example: GIT_ORIGIN_URL=https://github.com/OWNER/REPO.git ./run-connected-runner-handoff.sh" >&2
  exit 2
fi
if [ "${GIT_ORIGIN_URL}" = "__REPO_URL_PLACEHOLDER__" ] || [ "${GIT_ORIGIN_URL}" = "__LEGACY_REPO_URL_PLACEHOLDER__" ]; then
  echo "GIT_ORIGIN_URL must be a real remote URL, not a placeholder value." >&2
  exit 2
fi
if [ "${GIT_ORIGIN_URL}" = "REPO_URL" ] || [ "${GIT_ORIGIN_URL}" = "GIT_ORIGIN_URL" ]; then
  echo "GIT_ORIGIN_URL must be a real remote URL, not a placeholder value." >&2
  exit 2
fi
validate_git_origin_url() {
  local remote_target=""
  local remote_host=""
  local remote_path=""
  local remote_path_without_slashes=""

  case "${GIT_ORIGIN_URL}" in
    https://*/*)
      remote_target="${GIT_ORIGIN_URL#https://}"
      remote_host="${remote_target%%/*}"
      remote_path="${remote_target#*/}"
      ;;
    ssh://*/*)
      remote_target="${GIT_ORIGIN_URL#ssh://}"
      remote_host="${remote_target%%/*}"
      remote_path="${remote_target#*/}"
      ;;
    git@*:*)
      remote_target="${GIT_ORIGIN_URL#git@}"
      remote_host="${remote_target%%:*}"
      remote_path="${remote_target#*:}"
      ;;
    *)
      echo "GIT_ORIGIN_URL must be an HTTPS, SSH, or scp-style git remote URL." >&2
      echo "Examples: https://github.com/OWNER/REPO.git or git@github.com:OWNER/REPO.git" >&2
      exit 2
      ;;
  esac

  remote_path_without_slashes="${remote_path//\\//}"
  if [ -z "${remote_host}" ] || [ -z "${remote_path_without_slashes}" ]; then
    echo "GIT_ORIGIN_URL must be an HTTPS, SSH, or scp-style git remote URL." >&2
    echo "Examples: https://github.com/OWNER/REPO.git or git@github.com:OWNER/REPO.git" >&2
    exit 2
  fi
}
validate_git_origin_url

BRANCH_NAME="${BRANCH_NAME:-codex/quant-lab-release}"
ALLOW_ORIGIN_REWRITE="${ALLOW_ORIGIN_REWRITE:-false}"
PREFLIGHT_ONLY="${PREFLIGHT_ONLY:-false}"
SETUP_GH_GIT_AUTH="${SETUP_GH_GIT_AUTH:-true}"
RUN_FINAL_LIVE_BETA_GATE="${RUN_FINAL_LIVE_BETA_GATE:-false}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="${SCRIPT_DIR}/source"

if [ ! -d "${SOURCE_DIR}" ]; then
  echo "Expected source directory is missing: ${SOURCE_DIR}" >&2
  exit 2
fi

require_command() {
  local command_name="$1"
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "Required command is missing: ${command_name}" >&2
    exit 2
  fi
}

require_command git
require_command python3

python3 "${SOURCE_DIR}/scripts/package_connected_runner_handoff.py" --verify "${SCRIPT_DIR}"

require_command npm
require_command docker
require_command gh

docker compose version >/dev/null
gh auth status >/dev/null
if [ "${SETUP_GH_GIT_AUTH}" = "true" ]; then
  if ! gh auth setup-git >/dev/null; then
    echo "GitHub CLI git credential setup failed before git ls-remote." >&2
    echo "Run 'gh auth status' and 'gh auth setup-git' on the connected runner, or set SETUP_GH_GIT_AUTH=false if git credentials are already configured." >&2
    exit 2
  fi
fi
if ! git ls-remote "${GIT_ORIGIN_URL}" >/dev/null 2>&1; then
  echo "GIT_ORIGIN_URL could not be reached with git ls-remote before dependency installation." >&2
  echo "Check the remote URL, network access, repository permissions, and git credentials." >&2
  echo "For private GitHub HTTPS remotes, run 'gh auth setup-git' or leave SETUP_GH_GIT_AUTH=true." >&2
  exit 2
fi
echo "Connected-runner preflight passed."

cd "${SOURCE_DIR}"

SOURCE_GIT_TOPLEVEL=""
if SOURCE_GIT_TOPLEVEL="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  if [ "${SOURCE_GIT_TOPLEVEL}" != "${SOURCE_DIR}" ]; then
    git init "${SOURCE_DIR}"
  fi
else
  git init "${SOURCE_DIR}"
fi

if git show-ref --verify --quiet "refs/heads/${BRANCH_NAME}"; then
  git checkout "${BRANCH_NAME}"
else
  git checkout -b "${BRANCH_NAME}"
fi

if ! git config user.email >/dev/null 2>&1; then
  git config user.email "quant-lab-release@example.invalid"
fi
if ! git config user.name >/dev/null 2>&1; then
  git config user.name "Quant Lab Release Bot"
fi

if git remote get-url origin >/dev/null 2>&1; then
  CURRENT_ORIGIN="$(git remote get-url origin)"
  if [ "${CURRENT_ORIGIN}" != "${GIT_ORIGIN_URL}" ]; then
    if [ "${ALLOW_ORIGIN_REWRITE}" = "true" ]; then
      git remote set-url origin "${GIT_ORIGIN_URL}"
    else
      echo "origin already points to ${CURRENT_ORIGIN}." >&2
      echo "Set ALLOW_ORIGIN_REWRITE=true to replace it with ${GIT_ORIGIN_URL}." >&2
      exit 2
    fi
  fi
else
  git remote add origin "${GIT_ORIGIN_URL}"
fi

python3 scripts/connected_runner_acceptance.py --handoff-root .. --require-external --check-gh-auth

if [ "${PREFLIGHT_ONLY}" = "true" ]; then
  echo "Connected-runner preflight-only flow finished before dependency installation."
  exit 0
fi

python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install --upgrade pip
backend/.venv/bin/python -m pip install -e "backend[dev]"
npm ci --prefix frontend

git ls-files --others --modified --deleted --exclude-standard -z | git add --pathspec-from-file=- --pathspec-file-nul
if git diff --cached --quiet; then
  echo "No source changes staged for commit."
else
  git commit -m "Prepare Quant Lab release handoff"
fi
git push -u origin "${BRANCH_NAME}"

__CONNECTED_STRICT_GATE_COMMAND__

if [ "${RUN_FINAL_LIVE_BETA_GATE}" = "true" ]; then
  __LIVE_BETA_FINAL_GATE_COMMAND__
fi

echo "Connected-runner handoff flow finished."
"""
    script = script.replace("__REPO_URL_PLACEHOLDER__", REPO_URL_PLACEHOLDER).replace(
        "__LEGACY_REPO_URL_PLACEHOLDER__",
        LEGACY_REPO_URL_PLACEHOLDER,
    ).replace(
        "__CONNECTED_STRICT_GATE_COMMAND__",
        CONNECTED_STRICT_GATE_COMMAND,
    ).replace(
        "__LIVE_BETA_FINAL_GATE_COMMAND__",
        LIVE_BETA_FINAL_GATE_COMMAND,
    )
    script_path.write_text(script, encoding="utf-8")
    script_path.chmod(0o755)
    return script_path


def create_tarball(bundle_dir: Path) -> Path:
    tarball = bundle_dir.with_suffix(".tgz")
    with tarfile.open(tarball, "w:gz") as tar:
        tar.add(bundle_dir, arcname=bundle_dir.name)
    return tarball


def write_sha256_sidecar(path: Path) -> Path:
    sidecar = path.with_suffix(path.suffix + ".sha256")
    sidecar.write_text(f"{sha256_file(path)}  {path.name}\n", encoding="utf-8")
    return sidecar


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dict_payload(payload: Any) -> dict[str, Any]:
    return payload if isinstance(payload, dict) else {}


def list_payload(payload: Any) -> list[Any]:
    return payload if isinstance(payload, list) else []


def handoff_owner_lanes(progress_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    remaining_by_owner = dict_payload(progress_payload.get("remaining_by_owner"))
    next_by_owner = dict_payload(progress_payload.get("next_commands_by_owner"))
    local_readiness = dict_payload(progress_payload.get("local_readiness"))
    warning_review = dict_payload(progress_payload.get("warning_review"))
    completion_plan = [
        item for item in (dict_payload(entry) for entry in list_payload(progress_payload.get("completion_plan"))) if item
    ]
    return shared_owner_lanes_summary(
        remaining_by_owner=remaining_by_owner,
        next_commands_by_owner=next_by_owner,
        completion_plan=completion_plan,
        local_readiness=local_readiness,
        warning_review=warning_review,
    )


def handoff_bundle_commands(evidence_package: str) -> dict[str, str]:
    return {
        "verify_bundle_summary_json": (
            'python3 source/scripts/package_connected_runner_handoff.py --verify "$(pwd)" --summary-json-only'
        ),
        "show_handoff_context_json": (
            'python3 source/scripts/package_connected_runner_handoff.py --verify "$(pwd)" '
            "--handoff-context-json-only"
        ),
        "show_handoff_command_sequence": (
            'python3 source/scripts/package_connected_runner_handoff.py --verify "$(pwd)" '
            "--handoff-command-sequence-only"
        ),
        "audit_completion_context_json": (
            'python3 source/scripts/check_completion_audit.py --audit-path source/docs/completion-audit.md '
            '--handoff-bundle "$(pwd)" --json'
        ),
        "acceptance_summary_json": (
            "cd source && python3 scripts/connected_runner_acceptance.py --handoff-root .. "
            "--require-external --check-gh-auth --summary-json-only"
        ),
        "show_progress_json": (
            f'python3 source/scripts/report_release_status.py --package-dir "$(pwd)/{evidence_package}" '
            "--progress-json-only"
        ),
        "show_completion_plan_json": (
            f'python3 source/scripts/report_release_status.py --package-dir "$(pwd)/{evidence_package}" '
            "--completion-plan-json-only"
        ),
        "show_completion_requirements_json": (
            f'python3 source/scripts/report_release_status.py --package-dir "$(pwd)/{evidence_package}" '
            "--completion-requirements-json-only"
        ),
        "show_owner_lanes_json": (
            f'python3 source/scripts/report_release_status.py --package-dir "$(pwd)/{evidence_package}" '
            "--owner-lanes-json-only"
        ),
        "show_operator_review_sequence": (
            f'python3 source/scripts/next_release_step.py --package-dir "$(pwd)/{evidence_package}" '
            "--owner operator --command-sequence-only --skip-operator-approved "
            "--fail-if-repo-url-required"
        ),
        "show_warning_summary_json": (
            f'python3 source/scripts/review_release_warnings.py --package-dir "$(pwd)/{evidence_package}" '
            "--summary-json-only"
        ),
        "gate_warning_summary_json": (
            f'python3 source/scripts/review_release_warnings.py --package-dir "$(pwd)/{evidence_package}" '
            "--summary-json-only --fail-if-action-needed"
        ),
        "show_warning_artifacts": (
            f'python3 source/scripts/review_release_warnings.py --package-dir "$(pwd)/{evidence_package}" '
            "--review-artifacts-only"
        ),
    }


def handoff_bundle_command_sequence(bundle_commands: dict[str, str]) -> list[dict[str, Any]]:
    return [
        {
            "id": "verify_bundle",
            "owner": "connected runner",
            "command_key": "verify_bundle_summary_json",
            "command": bundle_commands["verify_bundle_summary_json"],
            "gate": True,
        },
        {
            "id": "show_handoff_context",
            "owner": "all",
            "command_key": "show_handoff_context_json",
            "command": bundle_commands["show_handoff_context_json"],
            "gate": False,
        },
        {
            "id": "show_handoff_command_sequence",
            "owner": "all",
            "command_key": "show_handoff_command_sequence",
            "command": bundle_commands["show_handoff_command_sequence"],
            "gate": False,
        },
        {
            "id": "audit_completion_context",
            "owner": "connected runner",
            "command_key": "audit_completion_context_json",
            "command": bundle_commands["audit_completion_context_json"],
            "gate": True,
        },
        {
            "id": "show_progress",
            "owner": "all",
            "command_key": "show_progress_json",
            "command": bundle_commands["show_progress_json"],
            "gate": False,
        },
        {
            "id": "show_completion_plan",
            "owner": "all",
            "command_key": "show_completion_plan_json",
            "command": bundle_commands["show_completion_plan_json"],
            "gate": False,
        },
        {
            "id": "show_completion_requirements",
            "owner": "all",
            "command_key": "show_completion_requirements_json",
            "command": bundle_commands["show_completion_requirements_json"],
            "gate": False,
        },
        {
            "id": "show_owner_lanes",
            "owner": "all",
            "command_key": "show_owner_lanes_json",
            "command": bundle_commands["show_owner_lanes_json"],
            "gate": False,
        },
        {
            "id": "export_repo_url",
            "owner": "connected runner",
            "command_key": "quickstart.export_repo_url",
            "command": "export GIT_ORIGIN_URL=https://github.com/OWNER/REPO.git",
            "gate": False,
        },
        {
            "id": "preflight",
            "owner": "connected runner",
            "command_key": "quickstart.preflight_command",
            "command": "PREFLIGHT_ONLY=true ./run-connected-runner-handoff.sh",
            "gate": True,
        },
        {
            "id": "acceptance_summary",
            "owner": "connected runner",
            "command_key": "acceptance_summary_json",
            "command": bundle_commands["acceptance_summary_json"],
            "gate": True,
        },
        {
            "id": "full_flow",
            "owner": "connected runner",
            "command_key": "quickstart.full_flow_command",
            "command": "./run-connected-runner-handoff.sh",
            "gate": True,
        },
        {
            "id": "show_operator_review_sequence",
            "owner": "operator",
            "command_key": "show_operator_review_sequence",
            "command": bundle_commands["show_operator_review_sequence"],
            "gate": False,
        },
        {
            "id": "show_warning_summary",
            "owner": "operator",
            "command_key": "show_warning_summary_json",
            "command": bundle_commands["show_warning_summary_json"],
            "gate": False,
        },
        {
            "id": "show_warning_artifacts",
            "owner": "operator",
            "command_key": "show_warning_artifacts",
            "command": bundle_commands["show_warning_artifacts"],
            "gate": False,
        },
        {
            "id": "gate_warning_summary",
            "owner": "operator",
            "command_key": "gate_warning_summary_json",
            "command": bundle_commands["gate_warning_summary_json"],
            "gate": True,
        },
    ]


def handoff_bundle_gate_summary(command_sequence: list[dict[str, Any]]) -> dict[str, Any]:
    gates = [step for step in command_sequence if step.get("gate")]
    gates_by_owner: dict[str, int] = {}
    for gate in gates:
        owner = str(gate.get("owner") or "unknown")
        gates_by_owner[owner] = gates_by_owner.get(owner, 0) + 1

    first_gate = gates[0] if gates else {}
    first_gate_by_owner: dict[str, dict[str, Any]] = {}
    for gate in gates:
        owner = str(gate.get("owner") or "unknown")
        if owner not in first_gate_by_owner:
            first_gate_by_owner[owner] = {
                "id": gate.get("id"),
                "command_key": gate.get("command_key"),
            }
    return {
        "step_count": len(command_sequence),
        "non_gate_count": len(command_sequence) - len(gates),
        "gate_count": len(gates),
        "gate_ids": [gate.get("id") for gate in gates if isinstance(gate.get("id"), str)],
        "gates_by_owner": gates_by_owner,
        "first_gate_by_owner": first_gate_by_owner,
        "connected_runner_gate_ids": [
            gate.get("id")
            for gate in gates
            if gate.get("owner") == "connected runner" and isinstance(gate.get("id"), str)
        ],
        "operator_gate_ids": [
            gate.get("id") for gate in gates if gate.get("owner") == "operator" and isinstance(gate.get("id"), str)
        ],
        "first_gate": {
            "id": first_gate.get("id"),
            "owner": first_gate.get("owner"),
            "command_key": first_gate.get("command_key"),
        }
        if first_gate
        else {},
        "requires_repo_url_export_before_preflight": True,
    }


def handoff_manifest_context(package_dir: Path) -> dict[str, Any]:
    release_status_path = package_dir / "release-status.json"
    release_status: dict[str, Any] = {}
    try:
        payload = read_json(release_status_path)
        if isinstance(payload, dict):
            release_status = payload
    except (OSError, json.JSONDecodeError):
        release_status = {}

    readiness_payload = dict_payload(release_status.get("readiness_estimate"))
    progress_payload = dict_payload(release_status.get("progress_summary"))
    completion_requirements = progress_payload.get("completion_requirements")
    remaining_ids = progress_payload.get("remaining_ids")
    evidence_package = str(Path("evidence") / package_dir.name)
    bundle_commands = handoff_bundle_commands(evidence_package)
    bundle_command_sequence = handoff_bundle_command_sequence(bundle_commands)
    return {
        "status": release_status.get("status", "unknown"),
        "percent": readiness_payload.get("percent"),
        "remaining_items": readiness_payload.get("remaining_items"),
        "remaining_ids": list_payload(remaining_ids),
        "remaining_by_owner": dict_payload(progress_payload.get("remaining_by_owner")),
        "next_item_id": progress_payload.get("next_item_id"),
        "next_item_owner": progress_payload.get("next_item_owner"),
        "owner_lanes": handoff_owner_lanes(progress_payload),
        "completion_requirements": list_payload(completion_requirements),
        "completion_plan": list_payload(progress_payload.get("completion_plan")),
        "repo_url": dict_payload(progress_payload.get("repo_url")),
        "local_readiness": dict_payload(progress_payload.get("local_readiness")),
        "warning_review": dict_payload(progress_payload.get("warning_review")),
        "quickstart": {
            "export_repo_url": "export GIT_ORIGIN_URL=https://github.com/OWNER/REPO.git",
            "preflight_command": "PREFLIGHT_ONLY=true ./run-connected-runner-handoff.sh",
            "full_flow_command": "./run-connected-runner-handoff.sh",
            "connected_runner_sequence": (
                'python3 source/scripts/next_release_step.py --handoff-bundle "$(pwd)" '
                '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL '
                "--summary-by-owner --show-sequence --no-write"
            ),
            "local_readiness_gate_json": (
                'python3 source/scripts/next_release_step.py --handoff-bundle "$(pwd)" '
                '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --json-only '
                "--fail-if-repo-url-required --local-readiness --fail-if-local-readiness-not-pass"
            ),
        },
        "bundle_commands": bundle_commands,
        "bundle_command_sequence": bundle_command_sequence,
        "bundle_gate_summary": handoff_bundle_gate_summary(bundle_command_sequence),
        "release_status": str(Path(evidence_package) / "release-status.json"),
        "next_step": str(Path(evidence_package) / "next-release-step.json"),
    }


def add_verification_check(
    checks: list[dict[str, Any]],
    *,
    check_id: str,
    status: str,
    message: str,
    evidence: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    checks.append(
        {
            "id": check_id,
            "status": status,
            "message": message,
            "evidence": evidence,
            "details": details or {},
        }
    )


def forbidden_source_paths(bundle_dir: Path) -> list[str]:
    source_dir = bundle_dir / "source"
    if not source_dir.exists():
        return []
    forbidden: list[str] = []
    for path in source_dir.rglob("*"):
        relative_path = path.relative_to(source_dir)
        if should_skip(relative_path):
            forbidden.append(str(relative_path))
    return sorted(forbidden)


def missing_gitignore_patterns(source_dir: Path) -> tuple[list[str], str | None]:
    gitignore_path = source_dir / ".gitignore"
    try:
        text = gitignore_path.read_text(encoding="utf-8")
    except OSError as exc:
        return list(REQUIRED_GITIGNORE_PATTERNS), str(exc)
    return missing_gitignore_patterns_from_text(text), None


def verify_sha256_sidecar(tarball: Path) -> tuple[bool, str]:
    sidecar = tarball.with_suffix(tarball.suffix + ".sha256")
    if not tarball.exists():
        return False, f"Tarball is missing: {tarball}"
    if not sidecar.exists():
        return False, f"SHA256 sidecar is missing: {sidecar}"
    expected_line = sidecar.read_text(encoding="utf-8").strip()
    expected_hash = expected_line.split()[0] if expected_line else ""
    actual_hash = sha256_file(tarball)
    if expected_hash != actual_hash:
        return False, f"Tarball SHA256 mismatch: expected {expected_hash}, got {actual_hash}"
    return True, "Tarball SHA256 sidecar matches."


def verify_runner_script_syntax(script_path: Path) -> tuple[bool, str]:
    bash = shutil.which("bash")
    if bash is None:
        return False, "bash is unavailable; runner script syntax cannot be checked."
    if not script_path.is_file():
        return False, "Runner script is missing."
    completed = subprocess.run([bash, "-n", str(script_path)], text=True, capture_output=True)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        return False, f"Runner script syntax check failed: {detail}"
    return True, "Runner script syntax check passed."


def verify_runner_script_text_syntax(script_text: str) -> tuple[bool, str]:
    bash = shutil.which("bash")
    if bash is None:
        return False, "bash is unavailable; runner script syntax cannot be checked."
    completed = subprocess.run([bash, "-n", "-s"], input=script_text, text=True, capture_output=True)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        return False, f"Runner script syntax check failed: {detail}"
    return True, "Runner script syntax check passed."


def missing_handoff_readme_markers(readme_text: str) -> list[str]:
    return [marker for marker in HANDOFF_NEXT_STEP_MARKERS if marker not in readme_text]


def manifest_handoff_context_errors(
    manifest: dict[str, Any],
    release_status: dict[str, Any] | None,
) -> list[str]:
    errors: list[str] = []
    context = manifest.get("handoff_context")
    if not isinstance(context, dict):
        return ["handoff_context"]
    quickstart = context.get("quickstart")
    if not isinstance(quickstart, dict):
        errors.append("handoff_context.quickstart")
    else:
        expected_quickstart = {
            "export_repo_url": "export GIT_ORIGIN_URL=https://github.com/OWNER/REPO.git",
            "preflight_command": "PREFLIGHT_ONLY=true ./run-connected-runner-handoff.sh",
            "full_flow_command": "./run-connected-runner-handoff.sh",
        }
        for key, expected in expected_quickstart.items():
            if quickstart.get(key) != expected:
                errors.append(f"handoff_context.quickstart.{key}")
    bundle_commands = context.get("bundle_commands")
    if not isinstance(bundle_commands, dict):
        errors.append("handoff_context.bundle_commands")
    else:
        release_status_path = context.get("release_status")
        evidence_package = str(PurePosixPath(str(release_status_path)).parent) if release_status_path else "evidence"
        expected_bundle_commands = handoff_bundle_commands(evidence_package)
        for key, expected in expected_bundle_commands.items():
            if bundle_commands.get(key) != expected:
                errors.append(f"handoff_context.bundle_commands.{key}")
        expected_sequence = handoff_bundle_command_sequence(expected_bundle_commands)
        if context.get("bundle_command_sequence") != expected_sequence:
            errors.append("handoff_context.bundle_command_sequence")
        if context.get("bundle_gate_summary") != handoff_bundle_gate_summary(expected_sequence):
            errors.append("handoff_context.bundle_gate_summary")
    if isinstance(release_status, dict):
        readiness = dict_payload(release_status.get("readiness_estimate"))
        progress = dict_payload(release_status.get("progress_summary"))
        expected_core = {
            "status": release_status.get("status", "unknown"),
            "percent": readiness.get("percent"),
            "remaining_items": readiness.get("remaining_items"),
            "remaining_ids": list_payload(progress.get("remaining_ids")),
        }
        for key, expected in expected_core.items():
            if context.get(key) != expected:
                errors.append(f"handoff_context.{key}")
        expected_requirements = list_payload(progress.get("completion_requirements"))
        if context.get("completion_requirements") != expected_requirements:
            errors.append("handoff_context.completion_requirements")
        for key in (
            "remaining_by_owner",
            "next_item_id",
            "next_item_owner",
            "owner_lanes",
            "completion_plan",
            "repo_url",
            "local_readiness",
            "warning_review",
        ):
            expected = progress.get(key)
            if key == "completion_plan":
                expected = list_payload(expected)
            elif key == "owner_lanes":
                expected = handoff_owner_lanes(progress)
            elif key in {"remaining_by_owner", "repo_url", "local_readiness", "warning_review"}:
                expected = dict_payload(expected)
            if context.get(key) != expected:
                errors.append(f"handoff_context.{key}")
    return errors


def copied_release_status_payload(bundle_dir: Path) -> tuple[dict[str, Any] | None, str | None, str | None]:
    evidence_dir = bundle_dir / "evidence"
    if not evidence_dir.is_dir():
        return None, "Copied evidence directory is missing.", str(evidence_dir)
    package_dirs = sorted(path for path in evidence_dir.iterdir() if path.is_dir())
    if len(package_dirs) != 1:
        return None, f"Expected exactly one copied evidence package, found {len(package_dirs)}.", str(evidence_dir)
    release_status_path = package_dirs[0] / "release-status.json"
    if not release_status_path.is_file():
        return None, "Copied release-status.json is missing.", str(release_status_path)
    try:
        payload = json.loads(release_status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"Copied release-status.json is unreadable: {exc}", str(release_status_path)
    if not isinstance(payload, dict):
        return None, "Copied release-status.json does not contain an object.", str(release_status_path)
    return payload, None, str(release_status_path)


def add_command_payload_check(
    checks: list[dict[str, Any]],
    *,
    check_id: str,
    expected: str,
    actual: Any = None,
    contains_text: str | None = None,
    require_when_contains: str | None = None,
) -> None:
    if contains_text is not None:
        if require_when_contains and require_when_contains not in contains_text:
            checks.append(
                {
                    "id": check_id,
                    "status": "skipped",
                    "expected": expected,
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

    if require_when_contains and isinstance(actual, str) and require_when_contains not in actual:
        checks.append(
            {
                "id": check_id,
                "status": "skipped",
                "expected": expected,
                "actual": actual,
            }
        )
        return
    if require_when_contains and not isinstance(actual, str):
        checks.append(
            {
                "id": check_id,
                "status": "skipped",
                "expected": expected,
                "actual": actual,
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


def add_connected_runner_item_command_checks(
    checks: list[dict[str, Any]],
    *,
    check_prefix: str,
    items: Any,
    expected_preflight: str,
    expected_full: str,
) -> None:
    if not isinstance(items, list):
        checks.append(
            {
                "id": f"{check_prefix}_remaining_items",
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
                "id": f"{check_prefix}_connected_runner_items",
                "status": "skipped",
                "expected": "connected runner item when connected-runner work remains",
                "actual": 0,
            }
        )
        return

    for index, item in enumerate(connected_runner_items):
        if "preferred_command" in item:
            add_command_payload_check(
                checks,
                check_id=f"{check_prefix}_item_{index}_preferred_command",
                expected=expected_preflight,
                actual=item.get("preferred_command"),
            )
        if "full_flow_command" in item:
            add_command_payload_check(
                checks,
                check_id=f"{check_prefix}_item_{index}_full_flow_command",
                expected=expected_full,
                actual=item.get("full_flow_command"),
            )


def add_handoff_command_list_check(
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


def add_progress_summary_checks(
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


def verify_copied_evidence_command_payloads_once(
    *,
    package_label: str,
    command_files: dict[str, str],
    expected_bundle_dir: Path | str,
) -> tuple[bool, str, dict[str, Any]]:
    expected_bundle = str(expected_bundle_dir)
    expected_tarball = str(Path(expected_bundle).with_suffix(".tgz"))
    expected_tarball_verification = f"{expected_tarball}.verification.json"
    expected_preflight = connected_runner_preflight_command(expected_bundle)
    expected_full = connected_runner_full_command(expected_bundle)
    expected_verify = connected_runner_verify_command(expected_bundle)
    expected_handoff_context_json = connected_runner_handoff_context_json_command(expected_bundle)
    expected_handoff_command_sequence = connected_runner_handoff_command_sequence_command(expected_bundle)
    checks: list[dict[str, Any]] = []
    details: dict[str, Any] = {
        "package": package_label,
        "expected_bundle_dir": expected_bundle,
        "expected_preflight_command": expected_preflight,
        "expected_full_command": expected_full,
        "files": sorted(command_files),
        "checks": checks,
    }

    for required_file in COPIED_EVIDENCE_COMMAND_FILES:
        checks.append(
            {
                "id": f"{required_file}_present",
                "status": "pass" if required_file in command_files else "fail",
                "expected": "present",
                "actual": "present" if required_file in command_files else "missing",
            }
        )

    release_status_md = command_files.get("release-status.md", "")
    next_release_step_md = command_files.get("next-release-step.md", "")
    if release_status_md:
        add_command_payload_check(
            checks,
            check_id="release_status_md_preflight_command",
            expected=expected_preflight,
            contains_text=release_status_md,
        )
        add_command_payload_check(
            checks,
            check_id="release_status_md_full_command",
            expected=expected_full,
            contains_text=release_status_md,
        )
        add_command_payload_check(
            checks,
            check_id="release_status_md_verify_command",
            expected=expected_verify,
            contains_text=release_status_md,
        )
    if next_release_step_md:
        add_command_payload_check(
            checks,
            check_id="next_release_step_md_preflight_command",
            expected=expected_preflight,
            contains_text=next_release_step_md,
            require_when_contains="run-connected-runner-handoff.sh",
        )
        add_command_payload_check(
            checks,
            check_id="next_release_step_md_full_command",
            expected=expected_full,
            contains_text=next_release_step_md,
            require_when_contains="run-connected-runner-handoff.sh",
        )

    release_status_payload: dict[str, Any] | None = None
    release_status_json = command_files.get("release-status.json")
    if release_status_json:
        try:
            parsed = json.loads(release_status_json)
            if isinstance(parsed, dict):
                release_status_payload = parsed
            else:
                checks.append(
                    {
                        "id": "release_status_json_object",
                        "status": "fail",
                        "expected": "object",
                        "actual": type(parsed).__name__,
                    }
                )
        except json.JSONDecodeError as exc:
            checks.append(
                {
                    "id": "release_status_json_parse",
                    "status": "fail",
                    "expected": "valid JSON",
                    "actual": str(exc),
                }
            )
    if release_status_payload is not None:
        add_command_payload_check(
            checks,
            check_id="release_status_json_bundle",
            expected=expected_bundle,
            actual=release_status_payload.get("connected_runner_handoff_bundle"),
        )
        add_command_payload_check(
            checks,
            check_id="release_status_json_tarball",
            expected=expected_tarball,
            actual=release_status_payload.get("connected_runner_handoff_tarball"),
        )
        add_command_payload_check(
            checks,
            check_id="release_status_json_tarball_verification",
            expected=expected_tarball_verification,
            actual=release_status_payload.get("connected_runner_handoff_tarball_verification"),
        )
        add_command_payload_check(
            checks,
            check_id="release_status_json_preflight_command",
            expected=expected_preflight,
            actual=release_status_payload.get("connected_runner_preflight_command"),
        )
        add_command_payload_check(
            checks,
            check_id="release_status_json_full_command",
            expected=expected_full,
            actual=release_status_payload.get("connected_runner_full_command"),
        )
        add_connected_runner_item_command_checks(
            checks,
            check_prefix="release_status_json",
            items=release_status_payload.get("remaining_items"),
            expected_preflight=expected_preflight,
            expected_full=expected_full,
        )
        package_dir = release_status_payload.get("package_dir")
        if isinstance(package_dir, str) and package_dir:
            expected_next_step = next_release_step_command(package_dir)
            expected_repo_next_step = next_release_step_repo_command(package_dir)
            expected_origin_next_step = next_release_step_origin_command(package_dir)
            expected_env_next_step = next_release_step_env_command(package_dir)
            expected_command_only_env = next_release_command_only_env_command(package_dir)
            expected_command_sequence_env = next_release_command_sequence_env_command(package_dir)
            expected_json_only_env = next_release_json_only_env_command(package_dir)
            expected_connected_json_only_env = next_release_connected_json_only_env_command(package_dir)
            expected_connected_command_only_env = next_release_connected_command_only_env_command(package_dir)
            expected_connected_command_sequence_env = next_release_connected_command_sequence_env_command(package_dir)
            expected_sequence = next_release_sequence_command(package_dir)
            expected_operator_sequence = next_release_operator_sequence_command(package_dir)
            expected_operator_command_only = next_release_operator_command_only_command(package_dir)
            expected_operator_command_sequence = next_release_operator_command_sequence_command(package_dir)
            expected_operator_review_sequence = next_release_operator_review_sequence_command(package_dir)
            expected_operator_json_only = next_release_operator_json_only_command(package_dir)
            expected_connected_sequence = next_release_connected_sequence_command(package_dir)
            expected_connected_sequence_origin = next_release_connected_sequence_origin_command(package_dir)
            expected_connected_sequence_env = next_release_connected_sequence_env_command(package_dir)
            expected_local_readiness = next_release_local_readiness_command(package_dir)
            expected_local_readiness_command_only = next_release_local_readiness_command_only_env_command(package_dir)
            expected_local_readiness_json = next_release_local_readiness_json_env_command(package_dir)
            expected_local_readiness_gate_json = next_release_local_readiness_gate_json_env_command(package_dir)
            expected_local_readiness_setup_sequence = next_release_local_readiness_setup_sequence_env_command(
                package_dir
            )
            expected_local_readiness_command_sequence = next_release_local_readiness_command_sequence_env_command(
                package_dir
            )
            expected_local_readiness_setup_sequence_preview = (
                next_release_local_readiness_setup_sequence_preview_command(package_dir)
            )
            expected_local_readiness_command_sequence_preview = (
                next_release_local_readiness_command_sequence_preview_command(package_dir)
            )
            expected_external_readiness_summary_json = external_readiness_summary_json_command()
            expected_external_readiness_strict_summary_json = external_readiness_strict_summary_json_command()
            release_gate_path = release_status_payload.get("release_gate_path")
            expected_release_status_progress = release_status_progress_command(
                package_dir,
                release_gate_path if isinstance(release_gate_path, str) else None,
            )
            expected_release_status_progress_json = release_status_progress_json_command(
                package_dir,
                release_gate_path if isinstance(release_gate_path, str) else None,
            )
            expected_release_status_completion_plan = release_status_completion_plan_command(
                package_dir,
                release_gate_path if isinstance(release_gate_path, str) else None,
            )
            expected_release_status_completion_plan_json = release_status_completion_plan_json_command(
                package_dir,
                release_gate_path if isinstance(release_gate_path, str) else None,
            )
            expected_release_status_completion_requirements = release_status_completion_requirements_command(
                package_dir,
                release_gate_path if isinstance(release_gate_path, str) else None,
            )
            expected_release_status_completion_requirements_json = (
                release_status_completion_requirements_json_command(
                    package_dir,
                    release_gate_path if isinstance(release_gate_path, str) else None,
                )
            )
            expected_release_status_owner_lanes = release_status_owner_lanes_command(
                package_dir,
                release_gate_path if isinstance(release_gate_path, str) else None,
            )
            expected_release_status_owner_lanes_json = release_status_owner_lanes_json_command(
                package_dir,
                release_gate_path if isinstance(release_gate_path, str) else None,
            )
            expected_read_only_evidence_check = read_only_evidence_check_command(package_dir)
            expected_read_only_warning_review = read_only_warning_review_command(package_dir)
            expected_warning_review_json = warning_review_json_command(package_dir)
            expected_warning_review_gate_json = warning_review_gate_json_command(package_dir)
            expected_warning_review_summary_json = warning_review_summary_json_command(package_dir)
            expected_warning_review_gate_summary_json = warning_review_gate_summary_json_command(package_dir)
            expected_warning_review_artifacts_only = warning_review_artifacts_only_command(package_dir)
            expected_warning_review_next_command_only = warning_review_next_command_only_command(package_dir)
            expected_warning_review_next_command_gate = warning_review_next_command_gate_command(package_dir)
            expected_warning_review_apply = warning_review_apply_command(package_dir)
            package_path = Path(package_dir)
            expected_warning_action_plan_path = str(package_path / "release-warning-actions.md")
            expected_warning_operator_checklist_path = str(package_path / "release-warning-operator-checklist.md")
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
            details["expected_handoff_command_sequence_command"] = expected_handoff_command_sequence
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
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_read_only_evidence_check_command",
                    expected=expected_read_only_evidence_check,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_progress_command",
                    expected=expected_release_status_progress,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_progress_json_command",
                    expected=expected_release_status_progress_json,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_completion_plan_command",
                    expected=expected_release_status_completion_plan,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_completion_plan_json_command",
                    expected=expected_release_status_completion_plan_json,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_owner_lanes_command",
                    expected=expected_release_status_owner_lanes,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_owner_lanes_json_command",
                    expected=expected_release_status_owner_lanes_json,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_read_only_warning_review_command",
                    expected=expected_read_only_warning_review,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_warning_review_json_command",
                    expected=expected_warning_review_json,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_warning_review_gate_json_command",
                    expected=expected_warning_review_gate_json,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_warning_review_artifacts_only_command",
                    expected=expected_warning_review_artifacts_only,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_warning_review_next_command_only_command",
                    expected=expected_warning_review_next_command_only,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_warning_review_next_command_gate_command",
                    expected=expected_warning_review_next_command_gate,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_warning_review_apply_command",
                    expected=expected_warning_review_apply,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_live_beta_preflight_command",
                    expected=expected_live_beta_preflight,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_live_beta_preflight_json_command",
                    expected=expected_live_beta_preflight_json,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_live_beta_next_command_only_command",
                    expected=expected_live_beta_next_command_only,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_live_beta_closeout_command",
                    expected=expected_live_beta_closeout,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_live_beta_final_gate_command",
                    expected=expected_live_beta_final_gate,
                    contains_text=release_status_md,
                )
                for support_name, support_command in expected_live_beta_support_commands.items():
                    add_command_payload_check(
                        checks,
                        check_id=f"release_status_md_live_beta_{support_name}_support_command",
                        expected=support_command,
                        contains_text=release_status_md,
                    )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_next_step_command",
                    expected=expected_next_step,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_next_step_repo_command",
                    expected=expected_repo_next_step,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_next_step_origin_command",
                    expected=expected_origin_next_step,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_next_step_env_command",
                    expected=expected_env_next_step,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_next_step_connected_json_env_command",
                    expected=expected_connected_json_only_env,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_next_step_local_readiness_json_command",
                    expected=expected_local_readiness_json,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_next_step_local_readiness_command_only_command",
                    expected=expected_local_readiness_command_only,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_next_step_local_readiness_setup_sequence_command",
                    expected=expected_local_readiness_setup_sequence,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_next_step_local_readiness_command_sequence_command",
                    expected=expected_local_readiness_command_sequence,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_next_step_local_readiness_setup_sequence_preview_command",
                    expected=expected_local_readiness_setup_sequence_preview,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_next_step_local_readiness_command_sequence_preview_command",
                    expected=expected_local_readiness_command_sequence_preview,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_next_step_local_readiness_gate_json_command",
                    expected=expected_local_readiness_gate_json,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_command_only_env_command",
                    expected=expected_command_only_env,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_json_only_env_command",
                    expected=expected_json_only_env,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_sequence_command",
                    expected=expected_sequence,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_operator_sequence_command",
                    expected=expected_operator_sequence,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_operator_command_only_command",
                    expected=expected_operator_command_only,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_operator_json_only_command",
                    expected=expected_operator_json_only,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_connected_sequence_command",
                    expected=expected_connected_sequence,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_connected_sequence_origin_command",
                    expected=expected_connected_sequence_origin,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_connected_sequence_env_command",
                    expected=expected_connected_sequence_env,
                    contains_text=release_status_md,
                )
                add_command_payload_check(
                    checks,
                    check_id="release_status_md_local_readiness_command",
                    expected=expected_local_readiness,
                    contains_text=release_status_md,
                )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_next_step_handoff_command",
                payload=release_status_payload,
                expected=expected_next_step,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_read_only_evidence_check_handoff_command",
                payload=release_status_payload,
                expected=expected_read_only_evidence_check,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_progress_handoff_command",
                payload=release_status_payload,
                expected=expected_release_status_progress,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_progress_json_handoff_command",
                payload=release_status_payload,
                expected=expected_release_status_progress_json,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_completion_plan_handoff_command",
                payload=release_status_payload,
                expected=expected_release_status_completion_plan,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_completion_plan_json_handoff_command",
                payload=release_status_payload,
                expected=expected_release_status_completion_plan_json,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_completion_requirements_handoff_command",
                payload=release_status_payload,
                expected=expected_release_status_completion_requirements,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_completion_requirements_json_handoff_command",
                payload=release_status_payload,
                expected=expected_release_status_completion_requirements_json,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_owner_lanes_handoff_command",
                payload=release_status_payload,
                expected=expected_release_status_owner_lanes,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_owner_lanes_json_handoff_command",
                payload=release_status_payload,
                expected=expected_release_status_owner_lanes_json,
            )
            add_progress_summary_checks(
                checks,
                payload=release_status_payload,
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
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_read_only_warning_review_handoff_command",
                payload=release_status_payload,
                expected=expected_read_only_warning_review,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_warning_review_apply_handoff_command",
                payload=release_status_payload,
                expected=expected_warning_review_apply,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_warning_review_artifacts_only_handoff_command",
                payload=release_status_payload,
                expected=expected_warning_review_artifacts_only,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_warning_review_next_command_only_handoff_command",
                payload=release_status_payload,
                expected=expected_warning_review_next_command_only,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_warning_review_next_command_gate_handoff_command",
                payload=release_status_payload,
                expected=expected_warning_review_next_command_gate,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_live_beta_preflight_handoff_command",
                payload=release_status_payload,
                expected=expected_live_beta_preflight,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_live_beta_preflight_json_handoff_command",
                payload=release_status_payload,
                expected=expected_live_beta_preflight_json,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_live_beta_next_command_only_handoff_command",
                payload=release_status_payload,
                expected=expected_live_beta_next_command_only,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_live_beta_closeout_handoff_command",
                payload=release_status_payload,
                expected=expected_live_beta_closeout,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_live_beta_final_gate_handoff_command",
                payload=release_status_payload,
                expected=expected_live_beta_final_gate,
            )
            for support_name, support_command in expected_live_beta_support_commands.items():
                add_handoff_command_list_check(
                    checks,
                    check_id=f"release_status_json_live_beta_{support_name}_support_handoff_command",
                    payload=release_status_payload,
                    expected=support_command,
                )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_next_step_repo_handoff_command",
                payload=release_status_payload,
                expected=expected_repo_next_step,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_next_step_origin_handoff_command",
                payload=release_status_payload,
                expected=expected_origin_next_step,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_next_step_env_handoff_command",
                payload=release_status_payload,
                expected=expected_env_next_step,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_command_only_env_handoff_command",
                payload=release_status_payload,
                expected=expected_command_only_env,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_json_only_env_handoff_command",
                payload=release_status_payload,
                expected=expected_json_only_env,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_sequence_handoff_command",
                payload=release_status_payload,
                expected=expected_sequence,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_operator_sequence_handoff_command",
                payload=release_status_payload,
                expected=expected_operator_sequence,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_operator_command_only_handoff_command",
                payload=release_status_payload,
                expected=expected_operator_command_only,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_operator_command_sequence_handoff_command",
                payload=release_status_payload,
                expected=expected_operator_command_sequence,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_operator_review_sequence_handoff_command",
                payload=release_status_payload,
                expected=expected_operator_review_sequence,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_operator_json_only_handoff_command",
                payload=release_status_payload,
                expected=expected_operator_json_only,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_connected_sequence_handoff_command",
                payload=release_status_payload,
                expected=expected_connected_sequence,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_connected_sequence_origin_handoff_command",
                payload=release_status_payload,
                expected=expected_connected_sequence_origin,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_connected_sequence_env_handoff_command",
                payload=release_status_payload,
                expected=expected_connected_sequence_env,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_local_readiness_handoff_command",
                payload=release_status_payload,
                expected=expected_local_readiness,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_local_readiness_json_handoff_command",
                payload=release_status_payload,
                expected=expected_local_readiness_json,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_local_readiness_command_only_handoff_command",
                payload=release_status_payload,
                expected=expected_local_readiness_command_only,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_local_readiness_setup_sequence_handoff_command",
                payload=release_status_payload,
                expected=expected_local_readiness_setup_sequence,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_local_readiness_command_sequence_handoff_command",
                payload=release_status_payload,
                expected=expected_local_readiness_command_sequence,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_local_readiness_setup_sequence_preview_handoff_command",
                payload=release_status_payload,
                expected=expected_local_readiness_setup_sequence_preview,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_local_readiness_command_sequence_preview_handoff_command",
                payload=release_status_payload,
                expected=expected_local_readiness_command_sequence_preview,
            )
            add_handoff_command_list_check(
                checks,
                check_id="release_status_json_local_readiness_gate_json_handoff_command",
                payload=release_status_payload,
                expected=expected_local_readiness_gate_json,
            )

    next_step_payload: dict[str, Any] | None = None
    next_step_json = command_files.get("next-release-step.json")
    if next_step_json:
        try:
            parsed = json.loads(next_step_json)
            if isinstance(parsed, dict):
                next_step_payload = parsed
            else:
                checks.append(
                    {
                        "id": "next_release_step_json_object",
                        "status": "fail",
                        "expected": "object",
                        "actual": type(parsed).__name__,
                    }
                )
        except json.JSONDecodeError as exc:
            checks.append(
                {
                    "id": "next_release_step_json_parse",
                    "status": "fail",
                    "expected": "valid JSON",
                    "actual": str(exc),
                }
            )
    if next_step_payload is not None:
        add_command_payload_check(
            checks,
            check_id="next_release_step_json_preflight_command",
            expected=expected_preflight,
            actual=next_step_payload.get("bundle_preflight_command"),
            require_when_contains="run-connected-runner-handoff.sh",
        )
        add_command_payload_check(
            checks,
            check_id="next_release_step_json_full_command",
            expected=expected_full,
            actual=next_step_payload.get("bundle_script_command"),
            require_when_contains="run-connected-runner-handoff.sh",
        )
        add_command_payload_check(
            checks,
            check_id="next_release_step_json_next_command",
            expected=expected_preflight,
            actual=next_step_payload.get("next_command"),
            require_when_contains="run-connected-runner-handoff.sh",
        )
        next_item = next_step_payload.get("next_item")
        if isinstance(next_item, dict) and next_item.get("owner") == "connected runner":
            add_command_payload_check(
                checks,
                check_id="next_release_step_json_next_item_preferred_command",
                expected=expected_preflight,
                actual=next_item.get("preferred_command"),
            )
            add_command_payload_check(
                checks,
                check_id="next_release_step_json_next_item_full_command",
                expected=expected_full,
                actual=next_item.get("full_flow_command"),
            )

    failures = [check for check in checks if check["status"] == "fail"]
    if failures:
        return (
            False,
            "Copied evidence release-status/next-release-step handoff commands are stale or incomplete.",
            details,
        )
    details["command_reference_bundle"] = expected_bundle
    return True, "Copied evidence release-status/next-release-step commands point to the expected handoff bundle.", details


def release_status_reference_bundle(command_files: dict[str, str]) -> str | None:
    try:
        payload = json.loads(command_files.get("release-status.json", ""))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    reference = payload.get("connected_runner_handoff_bundle")
    return reference if isinstance(reference, str) and reference else None


def verify_copied_evidence_command_payloads(
    *,
    package_label: str,
    command_files: dict[str, str],
    expected_bundle_dir: Path | str,
) -> tuple[bool, str, dict[str, Any]]:
    ok, message, details = verify_copied_evidence_command_payloads_once(
        package_label=package_label,
        command_files=command_files,
        expected_bundle_dir=expected_bundle_dir,
    )
    if ok:
        return ok, message, details

    reference_bundle = release_status_reference_bundle(command_files)
    if not reference_bundle or reference_bundle == str(expected_bundle_dir):
        return ok, message, details

    fallback_ok, fallback_message, fallback_details = verify_copied_evidence_command_payloads_once(
        package_label=package_label,
        command_files=command_files,
        expected_bundle_dir=reference_bundle,
    )
    fallback_details["requested_expected_bundle_dir"] = str(expected_bundle_dir)
    fallback_details["command_reference_bundle"] = reference_bundle
    if fallback_ok:
        return (
            True,
            (
                "Copied evidence release-status/next-release-step commands are internally consistent, "
                "but point to a different packaging-time handoff bundle path."
            ),
            fallback_details,
        )
    return ok, message, details


def verify_copied_evidence_handoff_commands(
    bundle_dir: Path,
    *,
    expected_bundle_dir: Path | str | None = None,
) -> tuple[bool, str, dict[str, Any]]:
    evidence_dir = bundle_dir / "evidence"
    details: dict[str, Any] = {"evidence_dir": str(evidence_dir)}
    if not evidence_dir.is_dir():
        return False, "Copied evidence directory is missing.", details

    package_dirs = sorted(path for path in evidence_dir.iterdir() if path.is_dir())
    details["packages"] = [str(path) for path in package_dirs]
    if len(package_dirs) != 1:
        return (
            False,
            f"Expected exactly one copied evidence package, found {len(package_dirs)}.",
            details,
        )

    package_dir = package_dirs[0]
    command_files: dict[str, str] = {}
    for filename in COPIED_EVIDENCE_COMMAND_FILES:
        path = package_dir / filename
        if path.is_file():
            command_files[filename] = path.read_text(encoding="utf-8")
    return verify_copied_evidence_command_payloads(
        package_label=str(package_dir),
        command_files=command_files,
        expected_bundle_dir=expected_bundle_dir or bundle_dir,
    )


def read_tar_member_text(
    archive: tarfile.TarFile,
    member_by_name: dict[str, tarfile.TarInfo],
    member_name: str,
) -> tuple[str | None, str | None]:
    member = member_by_name.get(member_name)
    if member is None or not member.isfile():
        return None, f"Tarball member is missing: {member_name}"
    handle = archive.extractfile(member)
    if handle is None:
        return None, f"Could not extract tarball member: {member_name}"
    try:
        return handle.read().decode("utf-8"), None
    except UnicodeDecodeError as exc:
        return None, f"Tarball member is not valid UTF-8: {member_name}: {exc}"


def verify_tarball_copied_evidence_handoff_commands(
    archive: tarfile.TarFile,
    member_names: list[str],
    member_by_name: dict[str, tarfile.TarInfo],
    bundle_name: str,
    expected_bundle_dir: Path | str,
) -> tuple[bool, str, dict[str, Any]]:
    package_names = sorted(
        {
            PurePosixPath(name).parts[2]
            for name in member_names
            if len(PurePosixPath(name).parts) >= 4
            and PurePosixPath(name).parts[0] == bundle_name
            and PurePosixPath(name).parts[1] == "evidence"
        }
    )
    details: dict[str, Any] = {
        "bundle_name": bundle_name,
        "expected_bundle_dir": str(expected_bundle_dir),
        "packages": package_names,
    }
    if len(package_names) != 1:
        return (
            False,
            f"Expected exactly one copied evidence package in handoff tarball, found {len(package_names)}.",
            details,
        )

    package_name = package_names[0]
    command_files: dict[str, str] = {}
    read_errors: list[str] = []
    for filename in COPIED_EVIDENCE_COMMAND_FILES:
        member_name = f"{bundle_name}/evidence/{package_name}/{filename}"
        text, error = read_tar_member_text(archive, member_by_name, member_name)
        if error:
            read_errors.append(error)
        elif text is not None:
            command_files[filename] = text
    if read_errors:
        details["read_errors"] = read_errors

    ok, message, payload_details = verify_copied_evidence_command_payloads(
        package_label=f"{bundle_name}/evidence/{package_name}",
        command_files=command_files,
        expected_bundle_dir=expected_bundle_dir,
    )
    details.update(payload_details)
    if read_errors:
        return False, "Copied evidence command files are missing or unreadable in handoff tarball.", details
    return ok, message, details


def verify_bundle(bundle_dir: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    manifest_path = bundle_dir / "manifest.json"
    handoff_path = bundle_dir / "HANDOFF.md"
    runner_script_path = bundle_dir / "run-connected-runner-handoff.sh"
    source_dir = bundle_dir / "source"
    evidence_dir = bundle_dir / "evidence"

    manifest: dict[str, Any] | None = None
    if manifest_path.exists():
        try:
            manifest = read_json(manifest_path)
            add_verification_check(
                checks,
                check_id="manifest",
                status="pass",
                message="Bundle manifest is present and readable.",
                evidence=str(manifest_path),
            )
        except (OSError, json.JSONDecodeError) as exc:
            add_verification_check(
                checks,
                check_id="manifest",
                status="fail",
                message=f"Bundle manifest is unreadable: {exc}",
                evidence=str(manifest_path),
            )
    else:
        add_verification_check(
            checks,
            check_id="manifest",
            status="fail",
            message="Bundle manifest is missing.",
            evidence=str(manifest_path),
        )

    missing_source = [path for path in HANDOFF_REQUIRED_SOURCE_FILES if not (source_dir / path).is_file()]
    add_verification_check(
        checks,
        check_id="required_source_files",
        status="pass" if not missing_source else "fail",
        message=(
            "Required source files are present."
            if not missing_source
            else "Missing required source files: " + ", ".join(missing_source)
        ),
        evidence=str(source_dir),
    )

    missing_gitignore, gitignore_error = missing_gitignore_patterns(source_dir)
    add_verification_check(
        checks,
        check_id="source_gitignore_guards",
        status="pass" if not missing_gitignore else "fail",
        message=(
            "Source .gitignore keeps generated, dependency, data, backup, and secret paths out of git add."
            if not missing_gitignore
            else "Source .gitignore is missing guard pattern(s): " + ", ".join(missing_gitignore)
        ),
        evidence=str(source_dir / ".gitignore"),
        details={
            "missing_patterns": missing_gitignore,
            "read_error": gitignore_error,
        },
    )

    forbidden = forbidden_source_paths(bundle_dir)
    add_verification_check(
        checks,
        check_id="source_safety_exclusions",
        status="pass" if not forbidden else "fail",
        message=(
            "Source snapshot excludes local secrets, dependency folders, databases, and generated artifacts."
            if not forbidden
            else "Forbidden source paths are present: " + ", ".join(forbidden[:20])
        ),
        evidence=str(source_dir),
    )

    add_verification_check(
        checks,
        check_id="handoff_readme",
        status="pass" if handoff_path.exists() else "fail",
        message="HANDOFF.md is present." if handoff_path.exists() else "HANDOFF.md is missing.",
        evidence=str(handoff_path),
    )
    if handoff_path.exists():
        try:
            handoff_text = handoff_path.read_text(encoding="utf-8")
            missing_markers = missing_handoff_readme_markers(handoff_text)
            add_verification_check(
                checks,
                check_id="handoff_readme_current_step_helpers",
                status="pass" if not missing_markers else "fail",
                message=(
                    "HANDOFF.md includes current-bundle next-step helper commands."
                    if not missing_markers
                    else "HANDOFF.md is missing current-bundle next-step markers: "
                    + ", ".join(missing_markers)
                ),
                evidence=str(handoff_path),
            )
            release_status_payload, release_status_error, release_status_evidence = copied_release_status_payload(bundle_dir)
            context_ok, context_message, context_details = verify_handoff_completion_context(
                handoff_text,
                release_status_payload,
            )
            if release_status_error:
                context_details["read_error"] = release_status_error
            add_verification_check(
                checks,
                check_id="handoff_readme_completion_context",
                status="pass" if context_ok and not release_status_error else "fail",
                message=release_status_error or context_message,
                evidence=release_status_evidence or str(handoff_path),
                details=context_details,
            )
            if manifest:
                manifest_context_errors = manifest_handoff_context_errors(manifest, release_status_payload)
                add_verification_check(
                    checks,
                    check_id="manifest_handoff_context",
                    status="pass" if not manifest_context_errors and not release_status_error else "fail",
                    message=(
                        "Bundle manifest exposes quickstart commands and completion requirements."
                        if not manifest_context_errors and not release_status_error
                        else (
                            release_status_error
                            or "Bundle manifest handoff context is missing or stale: "
                            + ", ".join(manifest_context_errors)
                        )
                    ),
                    evidence=str(manifest_path),
                    details={"errors": manifest_context_errors},
                )
        except OSError as exc:
            add_verification_check(
                checks,
                check_id="handoff_readme_current_step_helpers",
                status="fail",
                message=f"HANDOFF.md could not be read: {exc}",
                evidence=str(handoff_path),
            )
            add_verification_check(
                checks,
                check_id="handoff_readme_completion_context",
                status="fail",
                message=f"HANDOFF.md could not be read: {exc}",
                evidence=str(handoff_path),
            )
    runner_script_ok = runner_script_path.is_file() and bool(runner_script_path.stat().st_mode & 0o111)
    add_verification_check(
        checks,
        check_id="runner_script",
        status="pass" if runner_script_ok else "fail",
        message=(
            "Connected-runner script is present and executable."
            if runner_script_ok
            else "Connected-runner script is missing or not executable."
        ),
        evidence=str(runner_script_path),
    )
    syntax_ok, syntax_message = verify_runner_script_syntax(runner_script_path)
    add_verification_check(
        checks,
        check_id="runner_script_syntax",
        status="pass" if syntax_ok else "fail",
        message=syntax_message,
        evidence=str(runner_script_path),
    )
    runner_text = runner_script_path.read_text(encoding="utf-8") if runner_script_path.is_file() else ""
    missing_runner_markers = missing_runner_script_markers(runner_text)
    add_verification_check(
        checks,
        check_id="runner_script_preflight",
        status="pass" if not missing_runner_markers else "fail",
        message=(
            "Connected-runner script includes fail-fast command and auth preflight."
            if not missing_runner_markers
            else "Connected-runner script is missing preflight markers: " + ", ".join(missing_runner_markers)
        ),
        evidence=str(runner_script_path),
    )
    remote_guard_ok, remote_guard_message, remote_guard_details = verify_runner_script_remote_guard(runner_text)
    add_verification_check(
        checks,
        check_id="runner_script_remote_guard",
        status="pass" if remote_guard_ok else "fail",
        message=remote_guard_message,
        evidence=str(runner_script_path),
        details=remote_guard_details,
    )
    order_ok, order_message, order_details = verify_runner_script_order(runner_text)
    add_verification_check(
        checks,
        check_id="runner_script_order",
        status="pass" if order_ok else "fail",
        message=order_message,
        evidence=str(runner_script_path),
        details=order_details,
    )

    evidence_archives = sorted(evidence_dir.glob("*/*.tgz"))
    add_verification_check(
        checks,
        check_id="evidence_archive",
        status="pass" if evidence_archives else "fail",
        message=(
            f"Evidence archive is present: {evidence_archives[0]}"
            if evidence_archives
            else "Evidence archive is missing."
        ),
        evidence=str(evidence_archives[0]) if evidence_archives else str(evidence_dir),
    )

    if evidence_archives:
        ok, message = verify_sha256_sidecar(evidence_archives[0])
        add_verification_check(
            checks,
            check_id="evidence_archive_sha256",
            status="pass" if ok else "fail",
            message=message,
            evidence=str(evidence_archives[0].with_suffix(evidence_archives[0].suffix + ".sha256")),
        )

    expected_command_bundle: Path | str = bundle_dir
    if manifest and isinstance(manifest.get("bundle_dir"), str):
        expected_command_bundle = manifest["bundle_dir"]
        if manifest["bundle_dir"] != str(bundle_dir):
            add_verification_check(
                checks,
                check_id="bundle_path_manifest_mismatch",
                status="warn",
                message=(
                    "Bundle was verified from a different absolute path than the packaging-time path in "
                    "manifest.json; copied evidence commands are checked against the packaging-time path."
                ),
                evidence=str(manifest_path),
                details={
                    "current_bundle_dir": str(bundle_dir),
                    "manifest_bundle_dir": manifest["bundle_dir"],
                },
            )
    copied_commands_ok, copied_commands_message, copied_commands_details = verify_copied_evidence_handoff_commands(
        bundle_dir,
        expected_bundle_dir=expected_command_bundle,
    )
    add_verification_check(
        checks,
        check_id="copied_evidence_handoff_commands",
        status="pass" if copied_commands_ok else "fail",
        message=copied_commands_message,
        evidence=str(evidence_dir),
        details=copied_commands_details,
    )
    copied_reference_bundle = copied_commands_details.get("command_reference_bundle")
    requested_reference_bundle = copied_commands_details.get("requested_expected_bundle_dir")
    if copied_commands_ok and requested_reference_bundle and copied_reference_bundle != requested_reference_bundle:
        add_verification_check(
            checks,
            check_id="copied_evidence_handoff_command_path_mismatch",
            status="warn",
            message=(
                "Copied evidence commands are internally consistent, but reference a different "
                "packaging-time bundle path than this handoff bundle."
            ),
            evidence=str(evidence_dir),
            details={
                "current_or_manifest_bundle_dir": requested_reference_bundle,
                "copied_evidence_reference_bundle": copied_reference_bundle,
            },
        )

    if manifest:
        source_count = len(manifest.get("source_files", []))
        evidence_count = len(manifest.get("evidence_files", []))
        safety = manifest.get("safety", {})
        safety_ok = all(
            safety.get(key) is True
            for key in (
                "env_file_excluded",
                "local_database_excluded",
                "venv_excluded",
                "node_modules_excluded",
                "generated_artifacts_excluded_from_source_snapshot",
            )
        )
        add_verification_check(
            checks,
            check_id="manifest_counts",
            status="pass" if source_count > 0 and evidence_count > 0 else "fail",
            message=f"Manifest lists {source_count} source files and {evidence_count} evidence files.",
            evidence=str(manifest_path),
        )
        add_verification_check(
            checks,
            check_id="manifest_safety_flags",
            status="pass" if safety_ok else "fail",
            message="Manifest safety flags are locked." if safety_ok else "Manifest safety flags are incomplete.",
            evidence=str(manifest_path),
        )

    has_failures = any(check["status"] == "fail" for check in checks)
    has_warnings = any(check["status"] == "warn" for check in checks)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bundle_dir": str(bundle_dir),
        "status": "fail" if has_failures else ("warn" if has_warnings else "pass"),
        "checks": checks,
    }


def write_verification(bundle_dir: Path, verification: dict[str, Any]) -> Path:
    path = bundle_dir / "handoff-verification.json"
    path.write_text(json.dumps(verification, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def print_verification(verification: dict[str, Any], *, label: str = "Handoff verification") -> None:
    print(f"{label}: {verification['status']}")
    for check in verification["checks"]:
        print(f"{check['status'].upper():5} {check['id']}: {check['message']}")


def combined_verification_status(*verifications: dict[str, Any] | None) -> str:
    statuses = [str(verification.get("status")) for verification in verifications if verification]
    if any(status == "fail" for status in statuses):
        return "fail"
    if any(status == "warn" for status in statuses):
        return "warn"
    return "pass"


def verify_handoff_tarball(tarball: Path, bundle_name: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    runner_member_name = f"{bundle_name}/run-connected-runner-handoff.sh"
    runner_script_text: str | None = None
    runner_script_read_error: str | None = None
    handoff_readme_text: str | None = None
    handoff_readme_error: str | None = None
    release_status_text: str | None = None
    release_status_error: str | None = None
    release_status_member_name: str | None = None
    source_gitignore_text: str | None = None
    source_gitignore_error: str | None = None
    tarball_copied_commands_result: tuple[bool, str, dict[str, Any]] | None = None
    ok, message = verify_sha256_sidecar(tarball)
    add_verification_check(
        checks,
        check_id="tarball_sha256_sidecar",
        status="pass" if ok else "fail",
        message=message,
        evidence=str(tarball.with_suffix(tarball.suffix + ".sha256")),
    )

    try:
        with tarfile.open(tarball, "r:gz") as archive:
            members = archive.getmembers()
            member_names = [member.name for member in members]
            member_by_name = {member.name: member for member in members}
            handoff_readme_text, handoff_readme_error = read_tar_member_text(
                archive,
                member_by_name,
                f"{bundle_name}/HANDOFF.md",
            )
            source_gitignore_text, source_gitignore_error = read_tar_member_text(
                archive,
                member_by_name,
                f"{bundle_name}/source/.gitignore",
            )
            package_names = sorted(
                {
                    PurePosixPath(name).parts[2]
                    for name in member_names
                    if len(PurePosixPath(name).parts) >= 4
                    and PurePosixPath(name).parts[0] == bundle_name
                    and PurePosixPath(name).parts[1] == "evidence"
                }
            )
            if len(package_names) == 1:
                release_status_member_name = f"{bundle_name}/evidence/{package_names[0]}/release-status.json"
                release_status_text, release_status_error = read_tar_member_text(
                    archive,
                    member_by_name,
                    release_status_member_name,
                )
            else:
                release_status_error = (
                    f"Expected exactly one copied evidence package in handoff tarball, found {len(package_names)}."
                )
            runner_text_member = member_by_name.get(runner_member_name)
            if runner_text_member is not None and runner_text_member.isfile():
                handle = archive.extractfile(runner_text_member)
                if handle is None:
                    runner_script_read_error = "Could not extract runner script from tarball."
                else:
                    try:
                        runner_script_text = handle.read().decode("utf-8")
                    except UnicodeDecodeError as exc:
                        runner_script_read_error = f"Runner script is not valid UTF-8: {exc}."
            expected_bundle_dir = tarball.with_suffix("")
            manifest_text, manifest_error = read_tar_member_text(
                archive,
                member_by_name,
                f"{bundle_name}/manifest.json",
            )
            if manifest_text and not manifest_error:
                try:
                    manifest_payload = json.loads(manifest_text)
                    if isinstance(manifest_payload, dict) and isinstance(manifest_payload.get("bundle_dir"), str):
                        expected_bundle_dir = Path(manifest_payload["bundle_dir"])
                except json.JSONDecodeError:
                    expected_bundle_dir = tarball.with_suffix("")
            tarball_copied_commands_result = verify_tarball_copied_evidence_handoff_commands(
                archive,
                member_names,
                member_by_name,
                bundle_name,
                expected_bundle_dir,
            )
    except (OSError, tarfile.TarError) as exc:
        add_verification_check(
            checks,
            check_id="tarball_readable",
            status="fail",
            message=f"Handoff tarball is unreadable: {exc}",
            evidence=str(tarball),
        )
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tarball": str(tarball),
            "status": "fail",
            "checks": checks,
        }

    add_verification_check(
        checks,
        check_id="tarball_readable",
        status="pass",
        message=f"Handoff tarball contains {len(member_names)} members.",
        evidence=str(tarball),
    )

    required_members = (
        f"{bundle_name}/HANDOFF.md",
        f"{bundle_name}/run-connected-runner-handoff.sh",
        f"{bundle_name}/manifest.json",
        f"{bundle_name}/handoff-verification.json",
        *(f"{bundle_name}/source/{path}" for path in HANDOFF_REQUIRED_SOURCE_FILES),
    )
    missing_members = [member for member in required_members if member not in member_names]
    add_verification_check(
        checks,
        check_id="tarball_required_members",
        status="pass" if not missing_members else "fail",
        message=(
            "Handoff tarball includes required source and verification files."
            if not missing_members
            else "Handoff tarball is missing required members: " + ", ".join(missing_members)
        ),
        evidence=str(tarball),
    )
    if source_gitignore_text is None:
        add_verification_check(
            checks,
            check_id="tarball_source_gitignore_guards",
            status="fail",
            message=source_gitignore_error or "Handoff tarball source .gitignore could not be read.",
            evidence=f"{bundle_name}/source/.gitignore",
        )
    else:
        missing_gitignore = missing_gitignore_patterns_from_text(source_gitignore_text)
        add_verification_check(
            checks,
            check_id="tarball_source_gitignore_guards",
            status="pass" if not missing_gitignore else "fail",
            message=(
                "Handoff tarball source .gitignore preserves generated, dependency, data, backup, and secret guards."
                if not missing_gitignore
                else "Handoff tarball source .gitignore is missing guard pattern(s): "
                + ", ".join(missing_gitignore)
            ),
            evidence=f"{bundle_name}/source/.gitignore",
            details={"missing_patterns": missing_gitignore},
        )
    if handoff_readme_text is None:
        add_verification_check(
            checks,
            check_id="tarball_handoff_readme_current_step_helpers",
            status="fail",
            message=handoff_readme_error or "Handoff tarball HANDOFF.md could not be read.",
            evidence=f"{bundle_name}/HANDOFF.md",
        )
        add_verification_check(
            checks,
            check_id="tarball_handoff_readme_completion_context",
            status="fail",
            message=handoff_readme_error or "Handoff tarball HANDOFF.md could not be read.",
            evidence=f"{bundle_name}/HANDOFF.md",
        )
    else:
        missing_handoff_markers = missing_handoff_readme_markers(handoff_readme_text)
        add_verification_check(
            checks,
            check_id="tarball_handoff_readme_current_step_helpers",
            status="pass" if not missing_handoff_markers else "fail",
            message=(
                "Handoff tarball HANDOFF.md includes current-bundle next-step helper commands."
                if not missing_handoff_markers
                else "Handoff tarball HANDOFF.md is missing current-bundle next-step markers: "
                + ", ".join(missing_handoff_markers)
            ),
            evidence=f"{bundle_name}/HANDOFF.md",
        )
        release_status_payload: dict[str, Any] | None = None
        release_status_parse_error: str | None = None
        if release_status_text is not None:
            try:
                parsed_release_status = json.loads(release_status_text)
                if isinstance(parsed_release_status, dict):
                    release_status_payload = parsed_release_status
                else:
                    release_status_parse_error = (
                        f"Tarball release-status.json does not contain an object: {type(parsed_release_status).__name__}."
                    )
            except json.JSONDecodeError as exc:
                release_status_parse_error = f"Tarball release-status.json is invalid JSON: {exc}."
        context_ok, context_message, context_details = verify_handoff_completion_context(
            handoff_readme_text,
            release_status_payload,
        )
        read_error = release_status_error or release_status_parse_error
        if read_error:
            context_details["read_error"] = read_error
        add_verification_check(
            checks,
            check_id="tarball_handoff_readme_completion_context",
            status="pass" if context_ok and not read_error else "fail",
            message=read_error or context_message,
            evidence=release_status_member_name or f"{bundle_name}/HANDOFF.md",
            details=context_details,
        )
    runner_member = member_by_name.get(runner_member_name)
    runner_member_executable = runner_member is not None and bool(runner_member.mode & 0o111)
    add_verification_check(
        checks,
        check_id="tarball_runner_script_executable",
        status="pass" if runner_member_executable else "fail",
        message=(
            "Handoff tarball preserves runner script executable mode."
            if runner_member_executable
            else "Handoff tarball is missing an executable runner script."
        ),
        evidence=runner_member_name if runner_member else str(tarball),
    )
    if runner_script_text is None:
        add_verification_check(
            checks,
            check_id="tarball_runner_script_readable",
            status="fail",
            message=runner_script_read_error or "Handoff tarball runner script could not be read.",
            evidence=runner_member_name if runner_member else str(tarball),
        )
    else:
        syntax_ok, syntax_message = verify_runner_script_text_syntax(runner_script_text)
        add_verification_check(
            checks,
            check_id="tarball_runner_script_syntax",
            status="pass" if syntax_ok else "fail",
            message=(
                "Handoff tarball runner script syntax check passed."
                if syntax_ok
                else syntax_message
            ),
            evidence=runner_member_name,
        )
        missing_markers = missing_runner_script_markers(runner_script_text)
        add_verification_check(
            checks,
            check_id="tarball_runner_script_preflight",
            status="pass" if not missing_markers else "fail",
            message=(
                "Handoff tarball runner script preserves fail-fast command and auth preflight."
                if not missing_markers
                else "Handoff tarball runner script is missing preflight markers: "
                + ", ".join(missing_markers)
            ),
            evidence=runner_member_name,
        )
        remote_guard_ok, remote_guard_message, remote_guard_details = verify_runner_script_remote_guard(
            runner_script_text
        )
        add_verification_check(
            checks,
            check_id="tarball_runner_script_remote_guard",
            status="pass" if remote_guard_ok else "fail",
            message=remote_guard_message,
            evidence=runner_member_name,
            details=remote_guard_details,
        )
        order_ok, order_message, order_details = verify_runner_script_order(runner_script_text)
        add_verification_check(
            checks,
            check_id="tarball_runner_script_order",
            status="pass" if order_ok else "fail",
            message=order_message,
            evidence=runner_member_name,
            details=order_details,
        )

    unsafe_paths: list[str] = []
    forbidden_source_paths: list[str] = []
    expected_prefix = f"{bundle_name}/"
    for member_name in member_names:
        member_path = PurePosixPath(member_name)
        parts = member_path.parts
        if member_path.is_absolute() or ".." in parts or (
            member_name != bundle_name and not member_name.startswith(expected_prefix)
        ):
            unsafe_paths.append(member_name)
            continue
        if len(parts) >= 3 and parts[1] == "source":
            relative_source_path = Path(*parts[2:])
            if should_skip(relative_source_path):
                forbidden_source_paths.append(member_name)

    add_verification_check(
        checks,
        check_id="tarball_path_safety",
        status="pass" if not unsafe_paths else "fail",
        message=(
            "Handoff tarball paths are relative and scoped to the bundle root."
            if not unsafe_paths
            else "Unsafe handoff tarball paths are present: " + ", ".join(unsafe_paths[:20])
        ),
        evidence=str(tarball),
    )
    add_verification_check(
        checks,
        check_id="tarball_source_safety_exclusions",
        status="pass" if not forbidden_source_paths else "fail",
        message=(
            "Handoff tarball source snapshot excludes local secrets, dependency folders, databases, and generated artifacts."
            if not forbidden_source_paths
            else "Forbidden source paths are present in handoff tarball: " + ", ".join(forbidden_source_paths[:20])
        ),
        evidence=str(tarball),
    )

    evidence_archive_members = [
        name
        for name in member_names
        if name.startswith(f"{bundle_name}/evidence/") and name.endswith(".tgz")
    ]
    add_verification_check(
        checks,
        check_id="tarball_evidence_archive",
        status="pass" if evidence_archive_members else "fail",
        message=(
            "Handoff tarball includes an evidence archive."
            if evidence_archive_members
            else "Handoff tarball is missing an evidence archive."
        ),
        evidence=evidence_archive_members[0] if evidence_archive_members else str(tarball),
    )

    if tarball_copied_commands_result is None:
        add_verification_check(
            checks,
            check_id="tarball_copied_evidence_handoff_commands",
            status="fail",
            message="Copied evidence handoff commands could not be checked in the handoff tarball.",
            evidence=str(tarball),
        )
    else:
        copied_commands_ok, copied_commands_message, copied_commands_details = tarball_copied_commands_result
        add_verification_check(
            checks,
            check_id="tarball_copied_evidence_handoff_commands",
            status="pass" if copied_commands_ok else "fail",
            message=copied_commands_message,
            evidence=str(tarball),
            details=copied_commands_details,
        )
        copied_reference_bundle = copied_commands_details.get("command_reference_bundle")
        requested_reference_bundle = copied_commands_details.get("requested_expected_bundle_dir")
        if copied_commands_ok and requested_reference_bundle and copied_reference_bundle != requested_reference_bundle:
            add_verification_check(
                checks,
                check_id="tarball_copied_evidence_handoff_command_path_mismatch",
                status="warn",
                message=(
                    "Copied evidence commands in the handoff tarball are internally consistent, but "
                    "reference a different packaging-time bundle path than this handoff tarball."
                ),
                evidence=str(tarball),
                details={
                    "current_or_manifest_bundle_dir": requested_reference_bundle,
                    "copied_evidence_reference_bundle": copied_reference_bundle,
                },
            )

    has_failures = any(check["status"] == "fail" for check in checks)
    has_warnings = any(check["status"] == "warn" for check in checks)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tarball": str(tarball),
        "status": "fail" if has_failures else ("warn" if has_warnings else "pass"),
        "checks": checks,
    }


def write_tarball_verification(tarball: Path, verification: dict[str, Any]) -> Path:
    path = tarball.with_suffix(tarball.suffix + ".verification.json")
    path.write_text(json.dumps(verification, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def read_manifest_handoff_context(bundle_dir: Path) -> dict[str, Any]:
    manifest_path = bundle_dir / "manifest.json"
    manifest = read_json(manifest_path)
    if not isinstance(manifest, dict):
        raise ValueError(f"Bundle manifest is not a JSON object: {manifest_path}")
    context = manifest.get("handoff_context")
    if not isinstance(context, dict):
        raise ValueError(f"Bundle manifest does not contain handoff_context: {manifest_path}")
    return context


def handoff_context_for_args(args: argparse.Namespace, root: Path) -> dict[str, Any]:
    if args.verify:
        return read_manifest_handoff_context(Path(args.verify).absolute())
    package_dir = (
        Path(args.package_dir)
        if args.package_dir
        else latest_manifest_package_dir((root / args.packages_dir).absolute())
    ).absolute()
    return handoff_manifest_context(package_dir)


def handoff_command_sequence_from_context(context: dict[str, Any]) -> list[str]:
    sequence = context.get("bundle_command_sequence")
    if not isinstance(sequence, list):
        raise ValueError("handoff_context.bundle_command_sequence is missing or not a list")

    commands: list[str] = []
    for index, step in enumerate(sequence):
        if not isinstance(step, dict):
            raise ValueError(f"handoff_context.bundle_command_sequence[{index}] is not an object")
        command = step.get("command")
        if not isinstance(command, str) or not command.strip():
            raise ValueError(f"handoff_context.bundle_command_sequence[{index}].command is missing or empty")
        commands.append(command)
    return commands


def main() -> int:
    args = parse_args()
    root = Path(args.project_root).absolute()
    if args.handoff_context_json_only and args.handoff_command_sequence_only:
        print(
            "Choose only one of --handoff-context-json-only or --handoff-command-sequence-only.",
            file=sys.stderr,
        )
        return 1
    if args.handoff_context_json_only or args.handoff_command_sequence_only:
        try:
            context = handoff_context_for_args(args, root)
            command_sequence = (
                handoff_command_sequence_from_context(context) if args.handoff_command_sequence_only else []
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"Could not read handoff context: {exc}", file=sys.stderr)
            return 1
        if args.handoff_context_json_only:
            print(json.dumps(context, indent=2, sort_keys=True))
        else:
            print("\n".join(command_sequence))
        return 0
    if args.verify:
        bundle_dir = Path(args.verify).absolute()
        verification = verify_bundle(bundle_dir)
        verification_path = write_verification(bundle_dir, verification)
        tarball = bundle_dir.with_suffix(".tgz")
        tarball_verification: dict[str, Any] | None = None
        tarball_verification_path: Path | None = None
        if tarball.exists():
            tarball_verification = verify_handoff_tarball(tarball, bundle_dir.name)
            tarball_verification_path = write_tarball_verification(tarball, tarball_verification)
        status = combined_verification_status(verification, tarball_verification)
        summary = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "bundle_dir": str(bundle_dir),
            "bundle_verification_path": str(verification_path),
            "bundle_verification": verification,
            "tarball": str(tarball) if tarball.exists() else None,
            "tarball_verification_path": str(tarball_verification_path) if tarball_verification_path else None,
            "tarball_verification": tarball_verification,
        }
        if args.summary_json_only:
            compact_summary = {
                "generated_at": summary["generated_at"],
                "status": status,
                "bundle_dir": str(bundle_dir),
                "bundle_verification_path": str(verification_path),
                "bundle_verification_summary": compact_check_summary(verification),
                "tarball": str(tarball) if tarball.exists() else None,
                "tarball_verification_path": str(tarball_verification_path) if tarball_verification_path else None,
                "tarball_verification_summary": (
                    compact_check_summary(tarball_verification) if tarball_verification else None
                ),
            }
            print(json.dumps(compact_summary, indent=2, sort_keys=True))
        elif args.json_only:
            print(json.dumps(summary, indent=2, sort_keys=True))
        else:
            print_verification(verification)
            print(f"Handoff verification report: {verification_path}")
            if tarball_verification:
                print_verification(tarball_verification, label="Handoff tarball verification")
                print(f"Handoff tarball verification report: {tarball_verification_path}")
        return 1 if status == "fail" else 0

    package_dir = (
        Path(args.package_dir)
        if args.package_dir
        else latest_manifest_package_dir((root / args.packages_dir).absolute())
    ).absolute()
    output_dir = (root / args.output_dir).absolute()
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle_dir = Path(args.bundle_dir).absolute() if args.bundle_dir else next_bundle_dir(output_dir).absolute()
    bundle_dir.parent.mkdir(parents=True, exist_ok=True)
    bundle_dir.mkdir(parents=True, exist_ok=False)

    source_files = copy_source(root, bundle_dir)
    evidence_files = copy_evidence(package_dir, bundle_dir)
    write_handoff_readme(bundle_dir, package_dir)
    runner_script = write_runner_script(bundle_dir)

    manifest: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bundle_dir": str(bundle_dir),
        "package_dir": str(package_dir),
        "runner_script": str(runner_script),
        "handoff_context": handoff_manifest_context(package_dir),
        "source_file_count": len(source_files),
        "evidence_file_count": len(evidence_files),
        "source_files": source_files,
        "evidence_files": evidence_files,
        "safety": {
            "env_file_excluded": True,
            "local_database_excluded": True,
            "venv_excluded": True,
            "node_modules_excluded": True,
            "generated_artifacts_excluded_from_source_snapshot": True,
        },
    }
    manifest_path = bundle_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    verification = verify_bundle(bundle_dir)
    verification_path = write_verification(bundle_dir, verification)

    tarball = create_tarball(bundle_dir)
    sidecar = write_sha256_sidecar(tarball)
    tarball_verification = verify_handoff_tarball(tarball, bundle_dir.name)
    tarball_verification_path = write_tarball_verification(tarball, tarball_verification)
    status = combined_verification_status(verification, tarball_verification)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "bundle_dir": str(bundle_dir),
        "tarball": str(tarball),
        "sha256_sidecar": str(sidecar),
        "bundle_verification_path": str(verification_path),
        "tarball_verification_path": str(tarball_verification_path),
        "source_file_count": len(source_files),
        "evidence_file_count": len(evidence_files),
        "bundle_verification": verification,
        "tarball_verification": tarball_verification,
    }
    if args.summary_json_only:
        compact_summary = {
            "generated_at": summary["generated_at"],
            "status": status,
            "bundle_dir": str(bundle_dir),
            "tarball": str(tarball),
            "sha256_sidecar": str(sidecar),
            "bundle_verification_path": str(verification_path),
            "tarball_verification_path": str(tarball_verification_path),
            "source_file_count": len(source_files),
            "evidence_file_count": len(evidence_files),
            "bundle_verification_summary": compact_check_summary(verification),
            "tarball_verification_summary": compact_check_summary(tarball_verification),
        }
        print(json.dumps(compact_summary, indent=2, sort_keys=True))
    elif args.json_only:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"Handoff bundle: {bundle_dir}")
        print(f"Tarball: {tarball}")
        print(f"SHA256: {sidecar}")
        print(f"Bundle verification: {verification_path}")
        print(f"Tarball verification: {tarball_verification_path}")
        print(f"Source files: {len(source_files)}")
        print(f"Evidence files: {len(evidence_files)}")
        print_verification(verification)
        print_verification(tarball_verification, label="Handoff tarball verification")
    return 1 if status == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
