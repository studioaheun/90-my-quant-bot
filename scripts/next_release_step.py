#!/usr/bin/env python3
"""Print and archive the next Quant Lab release handoff step."""

from __future__ import annotations

import argparse
import copy
import json
import os
import shlex
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

try:
    from scripts.handoff_commands import (
        DOCKER_SETUP_COMMAND,
        ENV_REPO_URL_PLACEHOLDER,
        GENERIC_REPO_URL_PLACEHOLDER,
        GITHUB_CLI_SETUP_COMMAND,
        LEGACY_REPO_URL_PLACEHOLDER,
        LIVE_BETA_FINAL_GATE_COMMAND,
        REPO_URL_PLACEHOLDER,
        REPO_URL_PLACEHOLDERS,
        connected_runner_full_command,
        connected_runner_preflight_command,
        format_completion_deduction,
        git_origin_setup_command,
        next_release_command_only_env_command,
        next_release_connected_json_only_env_command,
        next_release_step_command,
        repo_url_export_example_command,
        shell_arg,
        source_scoped_command,
        warning_review_summary_json_command,
        with_completion_impacts,
    )
    from scripts.release_artifacts import latest_release_status_package_dir
except ModuleNotFoundError:  # pragma: no cover - supports running from scripts/
    from handoff_commands import (
        DOCKER_SETUP_COMMAND,
        ENV_REPO_URL_PLACEHOLDER,
        GENERIC_REPO_URL_PLACEHOLDER,
        GITHUB_CLI_SETUP_COMMAND,
        LEGACY_REPO_URL_PLACEHOLDER,
        LIVE_BETA_FINAL_GATE_COMMAND,
        REPO_URL_PLACEHOLDER,
        REPO_URL_PLACEHOLDERS,
        connected_runner_full_command,
        connected_runner_preflight_command,
        format_completion_deduction,
        git_origin_setup_command,
        next_release_command_only_env_command,
        next_release_connected_json_only_env_command,
        next_release_step_command,
        repo_url_export_example_command,
        shell_arg,
        source_scoped_command,
        warning_review_summary_json_command,
        with_completion_impacts,
    )
    from release_artifacts import latest_release_status_package_dir


OWNER_ORDER = ("connected runner", "operator")
AUTO_ORIGIN_SOURCE = "__auto_connected_runner_origin_source__"
REPO_URL_NOTE = (
    "Replace REPLACE_WITH_REPO_URL with a real HTTPS, SSH, or scp-style git remote URL before running "
    "connected-runner commands; literal placeholders are rejected."
)
REPO_URL_EXPORT_EXAMPLE = "Example: export {env_name}=https://github.com/OWNER/REPO.git"
OPERATOR_APPROVAL_NOTICE = "operator approval required after checklist review."
SUPPORTING_COMMAND_LABEL_ORDER = (
    "Export repo URL example",
    "Show external readiness summary JSON",
    "Gate external readiness summary JSON",
    "Show local readiness setup sequence",
    "Show local readiness command sequence",
    "Start local backend",
    "Start local backend without reload",
    "Start Docker backend",
    "Check backend health",
    "Show warning pre-approval sequence",
    "Show warning summary JSON",
    "Show warning review artifact paths",
    "Show warning recommended next command",
    "Gate warning summary JSON",
    "Gate warning recommended next command",
)
SUPPORTING_COMMAND_LABEL_PRIORITY = {
    label: index for index, label in enumerate(SUPPORTING_COMMAND_LABEL_ORDER)
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show the next actionable Quant Lab release step.")
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
        "--owner",
        choices=("all", "connected runner", "operator"),
        default="all",
        help="Limit the next-step view to a handoff owner.",
    )
    parser.add_argument(
        "--output-prefix",
        help="Output prefix. Defaults to next-release-step inside the evidence package.",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Only print the next step; do not write next-release-step files.",
    )
    parser.add_argument(
        "--command-only",
        action="store_true",
        help="Print only the next command for automation. Implies --no-write.",
    )
    parser.add_argument(
        "--command-sequence-only",
        action="store_true",
        help=(
            "Print only remaining handoff commands for the selected owner, one per line. "
            "Duplicate adjacent commands are printed once. Implies --no-write."
        ),
    )
    parser.add_argument(
        "--skip-operator-approved",
        action="store_true",
        help=(
            "When used with --command-sequence-only, omit commands that require explicit "
            "operator approval, such as --apply --operator-approved."
        ),
    )
    parser.add_argument(
        "--local-readiness-setup-sequence-only",
        action="store_true",
        help=(
            "Print only unresolved local-readiness setup commands in check order. "
            "Implies --local-readiness and --no-write."
        ),
    )
    parser.add_argument(
        "--local-readiness-command-sequence-only",
        action="store_true",
        help=(
            "Print unresolved local-readiness setup commands followed by their verification commands. "
            "Implies --local-readiness and --no-write."
        ),
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Print only the next-step report JSON for automation. Implies --no-write.",
    )
    parser.add_argument(
        "--fail-if-repo-url-required",
        action="store_true",
        help="Exit non-zero if the selected next command still contains a repository URL placeholder.",
    )
    parser.add_argument(
        "--fail-if-local-readiness-not-pass",
        action="store_true",
        help=(
            "Exit non-zero after printing output when --local-readiness checks are not all pass. "
            "Requires --local-readiness."
        ),
    )
    parser.add_argument(
        "--repo-url",
        help=(
            "Print connected-runner commands with this git remote URL substituted for REPLACE_WITH_REPO_URL. "
            "Must be an HTTPS, SSH, or scp-style git remote URL. "
            "Requires --no-write so evidence package command references stay portable."
        ),
    )
    parser.add_argument(
        "--repo-url-from-origin",
        nargs="?",
        const=AUTO_ORIGIN_SOURCE,
        metavar="PATH",
        help=(
            "Read `git remote get-url origin` from PATH, then substitute it into connected-runner commands. "
            "When PATH is omitted, defaults to the selected handoff bundle source when available, "
            "otherwise the current directory. Requires --no-write."
        ),
    )
    parser.add_argument(
        "--repo-url-from-env",
        nargs="?",
        const="GIT_ORIGIN_URL",
        metavar="ENV_VAR",
        help=(
            "Read the git remote URL from ENV_VAR, then substitute it into connected-runner commands. "
            "Defaults to GIT_ORIGIN_URL when ENV_VAR is omitted. Requires --no-write."
        ),
    )
    parser.add_argument(
        "--show-sequence",
        action="store_true",
        help="Print every remaining handoff item for the selected owner in execution order.",
    )
    parser.add_argument(
        "--summary-by-owner",
        action="store_true",
        help="Print remaining handoff counts grouped by owner, regardless of the selected owner filter.",
    )
    parser.add_argument(
        "--handoff-bundle",
        help=(
            "Override connected-runner handoff bundle paths when printing commands from a moved bundle. "
            "Requires --no-write so archived evidence command references stay unchanged."
        ),
    )
    parser.add_argument(
        "--local-readiness",
        action="store_true",
        help=(
            "Append read-only local connected-runner readiness checks for git origin, Docker Compose, "
            "and GitHub CLI auth. Requires read-only output via --no-write or --json-only."
        ),
    )
    parser.add_argument(
        "--local-readiness-source",
        help=(
            "Source directory to inspect for git origin when --local-readiness is used. "
            "Defaults to the selected connected-runner handoff bundle's source directory when available, "
            "otherwise the current directory."
        ),
    )
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def owner_rank(item: dict[str, str]) -> int:
    owner = item.get("owner", "")
    try:
        return OWNER_ORDER.index(owner)
    except ValueError:
        return len(OWNER_ORDER)


def sorted_items(items: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(items, key=owner_rank)


def ordered_supporting_commands(supporting_commands: Any) -> list[tuple[str, Any]]:
    if not isinstance(supporting_commands, dict):
        return []
    fallback_priority = len(SUPPORTING_COMMAND_LABEL_PRIORITY)
    return sorted(
        supporting_commands.items(),
        key=lambda item: (SUPPORTING_COMMAND_LABEL_PRIORITY.get(str(item[0]), fallback_priority), str(item[0])),
    )


def owner_summary(items: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for item in sorted_items(items):
        owner = item.get("owner") or "unassigned"
        status = item.get("status") or "unknown"
        group = grouped.setdefault(owner, {"owner": owner, "count": 0, "statuses": {}, "items": []})
        group["count"] += 1
        group["statuses"][status] = group["statuses"].get(status, 0) + 1
        group["items"].append(item.get("id") or "unknown")
    return sorted(grouped.values(), key=lambda group: owner_rank({"owner": group["owner"]}))


def filtered_items(items: list[dict[str, str]], owner: str) -> list[dict[str, str]]:
    if owner == "all":
        return sorted_items(items)
    return sorted_items([item for item in items if item.get("owner") == owner])


def format_remaining_counts(report: dict[str, Any]) -> str:
    filtered_count = report.get("filtered_remaining_count")
    total_count = report.get("total_remaining_count", report.get("remaining_count"))
    owner = report.get("owner_filter")
    if owner and owner != "all":
        return f"{filtered_count} for {owner} ({total_count} total)"
    return str(total_count)


def validate_repo_url(repo_url: str) -> str | None:
    repo_url = repo_url.strip()
    if not repo_url:
        return "must not be empty."
    if repo_url in REPO_URL_PLACEHOLDERS:
        return "must be a real remote URL, not a placeholder."
    if any(char.isspace() for char in repo_url):
        return "must be an HTTPS, SSH, or scp-style git remote URL."
    if repo_url.startswith(("https://", "ssh://")):
        parsed = urlparse(repo_url)
        if parsed.scheme in {"https", "ssh"} and parsed.netloc and parsed.path.strip("/"):
            return None
        return "must be an HTTPS, SSH, or scp-style git remote URL."
    if repo_url.startswith("git@") and ":" in repo_url:
        host, path = repo_url.removeprefix("git@").split(":", 1)
        if host and path.strip("/"):
            return None
    return "must be an HTTPS, SSH, or scp-style git remote URL."


def normalize_repo_url(repo_url: str | None, *, label: str = "repo_url") -> str | None:
    if repo_url is None:
        return None
    normalized = repo_url.strip()
    error = validate_repo_url(normalized)
    if error:
        raise ValueError(f"{label} {error}")
    return normalized


def repo_url_env_error(env_name: str, message: str) -> ValueError:
    return ValueError(f"{message} {REPO_URL_EXPORT_EXAMPLE.format(env_name=env_name)}")


def git_origin_url(repo_path: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo_path), "remote", "get-url", "origin"],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout).strip() or "origin remote is not configured."
        raise ValueError(f"--repo-url-from-origin could not read origin from {repo_path}: {message}")
    origin = completed.stdout.strip()
    if not origin:
        raise ValueError(f"--repo-url-from-origin found an empty origin remote in {repo_path}.")
    return normalize_repo_url(origin, label="origin") or origin


def _run_probe(command: list[str], *, cwd: Path | None = None, timeout: int = 10) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )


def command_output_excerpt(completed: subprocess.CompletedProcess[str]) -> str:
    output = (completed.stdout or completed.stderr or "").strip()
    if not output:
        return ""
    return output.splitlines()[0].strip()


def collect_local_readiness(
    source_root: Path,
    *,
    which: Callable[[str], str | None] = shutil.which,
    runner: Callable[..., subprocess.CompletedProcess[str]] = _run_probe,
) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    origin_command = f"git -C {shell_arg(source_root)} remote get-url origin"
    origin_setup_command = git_origin_setup_command(
        git_command=f"git -C {shell_arg(source_root)}",
    )

    try:
        origin_check = runner(["git", "-C", str(source_root), "remote", "get-url", "origin"])
        origin = origin_check.stdout.strip() if origin_check.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired) as exc:
        origin_check = None
        origin = ""
        origin_message = f"Could not inspect git origin from {source_root}: {exc}"
    else:
        origin_message = command_output_excerpt(origin_check)

    if origin:
        origin_error = validate_repo_url(origin)
        checks.append(
            {
                "id": "git_origin_remote",
                "status": "warn" if origin_error else "pass",
                "message": (
                    f"Origin is configured but {origin_error}"
                    if origin_error
                    else f"Origin is configured: {origin}"
                ),
                "command": origin_command,
                **(
                    {
                        "setup_command": origin_setup_command,
                        "remediation": "Replace the existing origin with a real remote URL if it is invalid.",
                    }
                    if origin_error
                    else {}
                ),
            }
        )
    else:
        checks.append(
            {
                "id": "git_origin_remote",
                "status": "warn",
                "message": origin_message or f"No origin remote is configured in {source_root}.",
                "command": origin_command,
                "setup_command": origin_setup_command,
                "remediation": "Add a real HTTPS, SSH, or scp-style origin remote for the handoff source.",
            }
        )

    docker_path = which("docker")
    if not docker_path:
        checks.append(
            {
                "id": "docker_cli",
                "status": "warn",
                "message": "docker CLI was not found on PATH.",
                "command": "docker compose version",
                "setup_command": DOCKER_SETUP_COMMAND,
                "remediation": "Install and start Docker Desktop or Docker Engine on the connected runner.",
            }
        )
    else:
        try:
            docker_check = runner(["docker", "compose", "version"])
        except (OSError, subprocess.TimeoutExpired) as exc:
            docker_check = None
            docker_message = f"docker compose version could not run: {exc}"
        else:
            docker_message = command_output_excerpt(docker_check)
        docker_status = "pass" if docker_check and docker_check.returncode == 0 else "warn"
        checks.append(
            {
                "id": "docker_cli",
                "status": docker_status,
                "message": docker_message or f"docker was found at {docker_path}, but compose version did not return output.",
                "command": "docker compose version",
                **(
                    {
                        "setup_command": DOCKER_SETUP_COMMAND,
                        "remediation": "Fix Docker Compose or start Docker before rerunning the connected-runner preflight.",
                    }
                    if docker_status != "pass"
                    else {}
                ),
            }
        )

    gh_path = which("gh")
    if not gh_path:
        checks.append(
            {
                "id": "github_cli",
                "status": "warn",
                "message": "gh CLI was not found on PATH.",
                "command": "gh auth status",
                "setup_command": GITHUB_CLI_SETUP_COMMAND,
                "remediation": "Install GitHub CLI, authenticate, and configure git credentials on the connected runner.",
            }
        )
    else:
        try:
            gh_check = runner(["gh", "auth", "status"])
        except (OSError, subprocess.TimeoutExpired) as exc:
            gh_check = None
            gh_message = f"gh auth status could not run: {exc}"
        else:
            gh_message = command_output_excerpt(gh_check)
        gh_status = "pass" if gh_check and gh_check.returncode == 0 else "warn"
        checks.append(
            {
                "id": "github_cli",
                "status": gh_status,
                "message": gh_message or f"gh was found at {gh_path}, but auth status did not return output.",
                "command": "gh auth status",
                **(
                    {
                        "setup_command": GITHUB_CLI_SETUP_COMMAND,
                        "remediation": "Run GitHub CLI auth setup before rerunning the connected-runner preflight.",
                    }
                    if gh_status != "pass"
                    else {}
                ),
            }
        )

    return checks


def local_readiness_summary_payload(checks: list[dict[str, str]]) -> tuple[dict[str, int], str, list[str]]:
    summary = {
        status: sum(1 for check in checks if check.get("status") == status)
        for status in sorted({check.get("status") for check in checks if check.get("status")})
    }
    if summary.get("fail"):
        overall_status = "fail"
    elif summary.get("warn"):
        overall_status = "warn"
    elif checks:
        overall_status = "pass"
    else:
        overall_status = "unknown"
    issue_ids = [
        str(check.get("id") or "unknown")
        for check in checks
        if check.get("status") in {"fail", "warn"}
    ]
    return summary, overall_status, issue_ids


def local_readiness_next_setup_payload(
    checks: list[dict[str, str]],
    *,
    repo_url: str | None = None,
) -> dict[str, str] | None:
    sequence = local_readiness_setup_sequence_payload(checks, repo_url=repo_url)
    return sequence[0] if sequence else None


def local_readiness_setup_sequence_payload(
    checks: list[dict[str, str]],
    *,
    repo_url: str | None = None,
) -> list[dict[str, str]]:
    sequence: list[dict[str, str]] = []
    for check in checks:
        if check.get("status") not in {"fail", "warn"}:
            continue
        setup_command = check.get("setup_command")
        if not setup_command:
            continue
        sequence.append(
            {
                "check_id": str(check.get("id") or "unknown"),
                "command": str(apply_repo_url(setup_command, repo_url)),
                "remediation": str(check.get("remediation") or ""),
                "status": str(check.get("status") or "unknown"),
                "verify_command": str(check.get("command") or ""),
            }
        )
    return sequence


def local_readiness_command_sequence_payload(setup_sequence: list[dict[str, str]]) -> list[str]:
    commands: list[str] = []
    last_command: str | None = None
    for setup in setup_sequence:
        for key in ("command", "verify_command"):
            command = setup.get(key)
            if not command or command == last_command:
                continue
            commands.append(command)
            last_command = command
    return commands


def resolve_package_dir(
    *,
    package_dir: str | None,
    packages_dir: str,
    handoff_bundle: str | None,
) -> Path:
    if package_dir:
        return Path(package_dir).absolute()
    if handoff_bundle:
        return latest_release_status_package_dir(Path(handoff_bundle).absolute() / "evidence").absolute()
    return latest_release_status_package_dir(Path(packages_dir)).absolute()


def resolve_local_readiness_source(
    *,
    local_readiness_source: str | None,
    handoff_bundle: str | None,
    fallback_handoff_bundle: str | None = None,
) -> Path:
    if local_readiness_source:
        return Path(local_readiness_source).absolute()
    selected_handoff_bundle = handoff_bundle or fallback_handoff_bundle
    if selected_handoff_bundle:
        return (Path(selected_handoff_bundle).absolute() / "source").absolute()
    return Path(".").absolute()


def resolve_origin_source(
    *,
    repo_url_from_origin: str,
    handoff_bundle: str | None,
    fallback_handoff_bundle: str | None = None,
) -> Path:
    if repo_url_from_origin != AUTO_ORIGIN_SOURCE:
        return Path(repo_url_from_origin).absolute()
    return resolve_local_readiness_source(
        local_readiness_source=None,
        handoff_bundle=handoff_bundle,
        fallback_handoff_bundle=fallback_handoff_bundle,
    )


def env_repo_url(env_var: str) -> str:
    env_name = env_var.strip()
    if not env_name:
        raise ValueError("--repo-url-from-env must name an environment variable.")
    if any(char.isspace() for char in env_name) or "=" in env_name:
        raise ValueError("--repo-url-from-env must name a single environment variable.")
    value = os.environ.get(env_name)
    if value is None:
        raise repo_url_env_error(
            env_name,
            f"--repo-url-from-env could not read ${env_name}; the variable is not set.",
        )
    if not value.strip():
        raise repo_url_env_error(env_name, f"--repo-url-from-env found an empty ${env_name}.")
    try:
        return normalize_repo_url(value, label=f"${env_name}") or value.strip()
    except ValueError as exc:
        raise repo_url_env_error(env_name, str(exc)) from exc


def apply_repo_url(command: str | None, repo_url: str | None) -> str | None:
    if not command or not repo_url:
        return command
    quoted_repo_url = shlex.quote(repo_url)
    replacements = (
        (f"{ENV_REPO_URL_PLACEHOLDER}={REPO_URL_PLACEHOLDER}", f"{ENV_REPO_URL_PLACEHOLDER}={quoted_repo_url}"),
        (
            f"{ENV_REPO_URL_PLACEHOLDER}={LEGACY_REPO_URL_PLACEHOLDER}",
            f"{ENV_REPO_URL_PLACEHOLDER}={quoted_repo_url}",
        ),
        (f"remote add origin {REPO_URL_PLACEHOLDER}", f"remote add origin {quoted_repo_url}"),
        (f"remote add origin {LEGACY_REPO_URL_PLACEHOLDER}", f"remote add origin {quoted_repo_url}"),
        (f"remote set-url origin {REPO_URL_PLACEHOLDER}", f"remote set-url origin {quoted_repo_url}"),
        (f"remote set-url origin {LEGACY_REPO_URL_PLACEHOLDER}", f"remote set-url origin {quoted_repo_url}"),
        (f"git remote add origin {REPO_URL_PLACEHOLDER}", f"git remote add origin {quoted_repo_url}"),
        (f"git remote add origin {LEGACY_REPO_URL_PLACEHOLDER}", f"git remote add origin {quoted_repo_url}"),
    )
    for old, new in replacements:
        command = command.replace(old, new)
    return command


def command_requires_repo_url(command: str | None) -> bool:
    return bool(
        command
        and (
            REPO_URL_PLACEHOLDER in command
            or LEGACY_REPO_URL_PLACEHOLDER in command
            or GENERIC_REPO_URL_PLACEHOLDER in command
        )
    )


def item_requires_repo_url(item: dict[str, Any] | None) -> bool:
    if not item:
        return False
    return any(
        command_requires_repo_url(str(item.get(key) or ""))
        for key in ("command", "preferred_command", "full_flow_command")
    )


def apply_repo_url_to_item(item: dict[str, str] | None, repo_url: str | None) -> dict[str, str] | None:
    if item is None or not repo_url:
        return item
    updated = dict(item)
    for key in ("command", "preferred_command", "full_flow_command"):
        if key in updated:
            updated[key] = str(apply_repo_url(updated.get(key), repo_url))
    return updated


def apply_handoff_bundle_to_item(item: dict[str, str] | None, handoff_bundle: str | None) -> dict[str, str] | None:
    if item is None or not handoff_bundle or item.get("owner") != "connected runner":
        return item
    updated = dict(item)
    updated["preferred_command"] = connected_runner_preflight_command(handoff_bundle)
    updated["full_flow_command"] = connected_runner_full_command(handoff_bundle)
    return updated


def item_command(item: dict[str, Any]) -> str | None:
    return item.get("preferred_command") or item.get("command")


def build_report(
    package_dir: Path,
    status: dict[str, Any],
    owner: str,
    repo_url: str | None = None,
    handoff_bundle: str | None = None,
) -> dict[str, Any]:
    repo_url = normalize_repo_url(repo_url)
    if handoff_bundle:
        status = copy.deepcopy(status)
        status["connected_runner_handoff_bundle"] = handoff_bundle
    all_items = sorted_items(status.get("remaining_items", []))
    items = filtered_items(all_items, owner)
    readiness = status.get("readiness_estimate", {})
    items = with_completion_impacts(items, readiness.get("deductions", []))
    items = [
        apply_repo_url_to_item(apply_handoff_bundle_to_item(item, handoff_bundle), repo_url) or item
        for item in items
    ]
    next_item = items[0] if items else None
    total_remaining_count = readiness.get("remaining_items", len(all_items))
    report_handoff_bundle = status.get("connected_runner_handoff_bundle")
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "package_dir": str(package_dir),
        "release_status_path": str(package_dir / "release-status.json"),
        "handoff_bundle": str(report_handoff_bundle) if report_handoff_bundle else None,
        "owner_filter": owner,
        "overall_status": status.get("status"),
        "completion_percent": readiness.get("percent"),
        "completion_deductions": readiness.get("deductions", []),
        "remaining_count": total_remaining_count,
        "total_remaining_count": total_remaining_count,
        "filtered_remaining_count": len(items),
        "next_item": next_item,
        "remaining_items": items,
        "owner_summary": owner_summary(all_items),
        "repo_url_substituted": bool(repo_url),
        "repo_url_required": False,
        "notes": [],
    }
    if next_item is None:
        if owner != "all" and all_items:
            report["next_command"] = next_release_step_command(package_dir, "--owner all", "--no-write")
            report["next_action"] = (
                f"No remaining handoff items are assigned to {owner}; switch to the all-owner view."
            )
        else:
            report["next_command"] = LIVE_BETA_FINAL_GATE_COMMAND
            report["next_action"] = "No remaining handoff items were listed; run the final strict release gate."
    else:
        report["next_command"] = item_command(next_item)
        report["next_action"] = next_item.get("preferred_action") or next_item.get("action")
        report["full_flow_command"] = next_item.get("full_flow_command")
        report["verify_command"] = next_item.get("verify_command")
        report["final_verify_command"] = next_item.get("final_verify_command")
        if next_item.get("owner") == "connected runner" and report_handoff_bundle:
            handoff_source_dir = Path(str(report_handoff_bundle)) / "source"
            bundle_script_command = connected_runner_full_command(str(report_handoff_bundle))
            bundle_preflight_command = connected_runner_preflight_command(str(report_handoff_bundle))
            report["bundle_script_command"] = apply_repo_url(bundle_script_command, repo_url)
            report["bundle_preflight_command"] = apply_repo_url(bundle_preflight_command, repo_url)
            report["manual_setup_command"] = source_scoped_command(next_item.get("command"), handoff_source_dir)
            report["manual_setup_action"] = next_item.get("action")
            report["verify_command"] = source_scoped_command(next_item.get("verify_command"), handoff_source_dir)
            report["final_verify_command"] = source_scoped_command(
                next_item.get("final_verify_command"),
                handoff_source_dir,
            )
            report["next_command"] = report["bundle_preflight_command"]
            report["next_action"] = (
                "Run the connected-runner bundle preflight before any manual setup; it rejects "
                "missing/placeholder/invalid remote URLs first, self-verifies the bundle, then validates "
                "remote reachability, Docker, GitHub CLI auth, source safety, and copied evidence before "
                "dependency installation or push."
            )
            report.pop("full_flow_command", None)
    if not repo_url and any(item_requires_repo_url(item) for item in items):
        report["repo_url_required"] = True
        report["notes"] = [REPO_URL_NOTE]
        report["repo_url_export_command"] = repo_url_export_example_command()
        report["repo_url_command_gate"] = next_release_command_only_env_command(package_dir)
        report["repo_url_json_gate"] = next_release_connected_json_only_env_command(package_dir)
    return report


def preserve_local_readiness_in_automation_commands(
    report: dict[str, Any],
    *,
    explicit_source: str | None = None,
    fail_if_not_pass: bool = False,
) -> None:
    for item in report.get("remaining_items") or []:
        command = str(item.get("automation_command") or "")
        if item.get("owner") != "connected runner" or "scripts/next_release_step.py" not in command:
            continue
        if "--json-only" not in command:
            continue
        if "--local-readiness" not in command:
            command += " --local-readiness"
        if fail_if_not_pass and "--fail-if-local-readiness-not-pass" not in command:
            command += " --fail-if-local-readiness-not-pass"
        if explicit_source and "--local-readiness-source" not in command:
            command += f" --local-readiness-source {shell_arg(Path(explicit_source).absolute())}"
        item["automation_command"] = command
        gate_command = command
        if "--fail-if-local-readiness-not-pass" not in gate_command:
            gate_command += " --fail-if-local-readiness-not-pass"
        item["local_readiness_gate_command"] = gate_command


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    next_item = report.get("next_item")
    lines = [
        "# Quant Lab Next Release Step",
        "",
        f"Generated at: {report['generated_at']}",
        f"Package: `{report['package_dir']}`",
        f"Handoff bundle: `{report.get('handoff_bundle')}`" if report.get("handoff_bundle") else "Handoff bundle: n/a",
        f"Overall status: {report.get('overall_status')}",
        f"Completion: {report.get('completion_percent')}%",
        f"Owner filter: {report.get('owner_filter')}",
        f"Remaining items: {format_remaining_counts(report)}",
        "",
        "## Completion Detail",
        "",
    ]
    deductions = report.get("completion_deductions") or []
    if deductions:
        for deduction in deductions:
            lines.append(f"- {format_completion_deduction(deduction)}")
    else:
        lines.append("- No completion deductions are currently listed.")
    lines.extend(
        [
            "",
            "## Next Step",
            "",
        ]
    )
    if next_item:
        next_command = str(report.get("next_command") or "")
        lines.extend(
            [
                f"- Item: {next_item.get('id')}",
                f"- Owner: {next_item.get('owner')}",
                f"- Status: {next_item.get('status')}",
                f"- Action: {report.get('next_action')}",
                f"- Approval: {OPERATOR_APPROVAL_NOTICE}"
                if command_requires_operator_approval(next_command, next_item)
                else None,
                "",
                "```bash",
                next_command,
                "```",
                "",
            ]
        )
        lines = [line for line in lines if line is not None]
        if next_item.get("completion_impact"):
            lines.extend([f"- Completion impact: {next_item.get('completion_impact')}", ""])
        if report.get("full_flow_command") and report.get("full_flow_command") != report.get("next_command"):
            lines.extend(
                [
                    "- Full flow after preflight:",
                    "",
                    "```bash",
                    str(report.get("full_flow_command")),
                    "```",
                    "",
                ]
            )
        if report.get("manual_setup_command") and report.get("manual_setup_command") != report.get("next_command"):
            lines.extend(
                [
                    "- Manual setup fallback:",
                    "",
                    "```bash",
                    str(report.get("manual_setup_command")),
                    "```",
                    "",
                ]
            )
        if next_item.get("automation_command") and next_item.get("automation_command") != report.get("next_command"):
            lines.extend(
                [
                    "- Automation JSON:",
                    "",
                    "```bash",
                    str(next_item.get("automation_command")),
                    "```",
                    "",
                ]
            )
        if next_item.get("supporting_commands"):
            lines.extend(["- Supporting commands:", ""])
            for label, command in ordered_supporting_commands(next_item["supporting_commands"]):
                lines.extend(
                    [
                        f"  - {label}:",
                        "",
                        "```bash",
                        str(command),
                        "```",
                        "",
                    ]
                )
        if report.get("repo_url_command_gate"):
            if report.get("repo_url_export_command") and not item_supporting_commands_include(
                next_item,
                report.get("repo_url_export_command"),
            ):
                lines.extend(
                    [
                        "- Repo URL export example:",
                        "",
                        "```bash",
                        str(report.get("repo_url_export_command")),
                        "```",
                        "",
                    ]
                )
            lines.extend(
                [
                    "- Repo URL command gate:",
                    "",
                    "```bash",
                    str(report.get("repo_url_command_gate")),
                    "```",
                    "",
                ]
            )
        if report.get("repo_url_json_gate"):
            lines.extend(
                [
                    "- Repo URL JSON gate:",
                    "",
                    "```bash",
                    str(report.get("repo_url_json_gate")),
                    "```",
                    "",
                ]
            )
        if (
            next_item.get("local_readiness_gate_command")
            and next_item.get("local_readiness_gate_command") != next_item.get("automation_command")
            and next_item.get("local_readiness_gate_command") != report.get("next_command")
        ):
            lines.extend(
                [
                    "- Automation JSON gate:",
                    "",
                    "```bash",
                    str(next_item.get("local_readiness_gate_command")),
                    "```",
                    "",
                ]
            )
        if report.get("final_verify_command") and report.get("final_verify_command") != report.get("next_command"):
            if report.get("verify_command") and report.get("verify_command") != report.get("next_command"):
                lines.extend(
                    [
                        "- Verify:",
                        "",
                        "```bash",
                        str(report.get("verify_command")),
                        "```",
                        "",
                    ]
                )
            lines.extend(
                [
                    "- Final verify:",
                    "",
                    "```bash",
                    str(report.get("final_verify_command")),
                    "```",
                    "",
                ]
            )
        if report.get("bundle_script_command"):
            lines.extend(
                [
                    "- Full flow after preflight:",
                    "",
                    "```bash",
                    str(report.get("bundle_script_command")),
                    "```",
                    "",
                ]
            )
    else:
        action = report.get("next_action") or "No remaining handoff item is listed in release-status.json."
        lines.extend(
            [
                f"- {action}",
                "",
                "```bash",
                str(report.get("next_command")),
                "```",
                "",
            ]
        )

    if report.get("notes"):
        lines.extend(["## Notes", ""])
        for note in report["notes"]:
            lines.append(f"- {note}")
        lines.append("")

    if report["remaining_items"]:
        owner_groups = report.get("owner_summary") or []
        if owner_groups:
            lines.extend(["## Remaining By Owner", ""])
            for group in owner_groups:
                statuses = ", ".join(
                    f"{status}: {count}" for status, count in sorted(group.get("statuses", {}).items())
                )
                items = ", ".join(group.get("items") or [])
                lines.append(f"- {group.get('owner')}: {group.get('count')} ({statuses})")
                if items:
                    lines.append(f"  Items: {items}")
            lines.append("")
        lines.extend(["## Remaining Items", ""])
        for item in report["remaining_items"]:
            lines.append(f"- {item.get('id')} ({item.get('owner')}, {item.get('status')}): {item.get('action')}")
            if item.get("completion_impact"):
                lines.append(f"  Completion impact: {item.get('completion_impact')}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def print_summary(report: dict[str, Any]) -> None:
    print(f"Status: {report.get('overall_status')}")
    print(f"Package: {report.get('package_dir')}")
    if report.get("handoff_bundle"):
        print(f"Handoff bundle: {report.get('handoff_bundle')}")
    print(f"Completion: {report.get('completion_percent')}%")
    print(f"Remaining items: {format_remaining_counts(report)}")
    if report.get("completion_deductions"):
        print("Completion deductions:")
        for deduction in report["completion_deductions"]:
            print(f"- {format_completion_deduction(deduction)}")
    next_item = report.get("next_item")
    if next_item:
        print(f"Next item: {next_item.get('id')} ({next_item.get('owner')})")
        print(f"Action: {report.get('next_action')}")
        if next_item.get("completion_impact"):
            print(f"Completion impact: {next_item.get('completion_impact')}")
        if command_requires_operator_approval(str(report.get("next_command") or ""), next_item):
            print(f"Approval: {OPERATOR_APPROVAL_NOTICE}")
    else:
        if report.get("owner_filter") != "all" and report.get("total_remaining_count"):
            print(f"Next item: none for {report.get('owner_filter')}")
        else:
            print("Next item: final strict gate")
        print(f"Action: {report.get('next_action')}")
    print("Command:")
    print(report.get("next_command"))
    if report.get("bundle_script_command"):
        print("Full flow after preflight:")
        print(report.get("bundle_script_command"))
    if report.get("full_flow_command") and report.get("full_flow_command") != report.get("next_command"):
        print("Full flow after preflight:")
        print(report.get("full_flow_command"))
    if report.get("manual_setup_command") and report.get("manual_setup_command") != report.get("next_command"):
        print("Manual setup fallback:")
        print(report.get("manual_setup_command"))
    if next_item and next_item.get("automation_command") and next_item.get("automation_command") != report.get("next_command"):
        print("Automation JSON:")
        print(next_item.get("automation_command"))
    if next_item and next_item.get("supporting_commands"):
        print("Supporting commands:")
        for label, command in ordered_supporting_commands(next_item["supporting_commands"]):
            print(f"- {label}: {command}")
    if report.get("repo_url_command_gate"):
        if report.get("repo_url_export_command") and not item_supporting_commands_include(
            next_item,
            report.get("repo_url_export_command"),
        ):
            print("Repo URL export example:")
            print(report.get("repo_url_export_command"))
        print("Repo URL command gate:")
        print(report.get("repo_url_command_gate"))
    if report.get("repo_url_json_gate"):
        print("Repo URL JSON gate:")
        print(report.get("repo_url_json_gate"))
    if (
        next_item
        and next_item.get("local_readiness_gate_command")
        and next_item.get("local_readiness_gate_command") != next_item.get("automation_command")
        and next_item.get("local_readiness_gate_command") != report.get("next_command")
    ):
        print("Automation JSON gate:")
        print(next_item.get("local_readiness_gate_command"))
    if report.get("verify_command") and report.get("verify_command") != report.get("next_command"):
        print("Verify:")
        print(report.get("verify_command"))
    if report.get("final_verify_command") and report.get("final_verify_command") != report.get("next_command"):
        print("Final verify:")
        print(report.get("final_verify_command"))
    if report.get("notes"):
        print("Notes:")
        for note in report["notes"]:
            print(f"- {note}")


def item_supporting_commands_include(item: dict[str, Any] | None, command: Any) -> bool:
    if not item or not command:
        return False
    supporting_commands = item.get("supporting_commands")
    if not isinstance(supporting_commands, dict):
        return False
    command_text = str(command)
    return any(str(value or "") == command_text for value in supporting_commands.values())


def print_sequence(report: dict[str, Any], *, compact_next_item: bool = False) -> None:
    items = report.get("remaining_items") or []
    print("Remaining sequence:")
    if not items:
        print("No remaining items for this owner filter.")
        return
    printed_commands: set[str] = set()
    printed_actions: set[str] = set()
    next_item_id = (report.get("next_item") or {}).get("id")
    for index, item in enumerate(items, start=1):
        print(f"{index}. {item.get('id')} ({item.get('owner')}, {item.get('status')})")
        if compact_next_item and index == 1 and item.get("id") == next_item_id:
            print("Same as Next item above.")
            command = item_command(item)
            if command:
                printed_commands.add(str(command))
            for key in (
                "full_flow_command",
                "automation_command",
                "local_readiness_gate_command",
                "verify_command",
                "final_verify_command",
            ):
                if item.get(key):
                    printed_commands.add(str(item.get(key)))
            for _, command_value in ordered_supporting_commands(item.get("supporting_commands")):
                if command_value:
                    printed_commands.add(str(command_value))
            action = item.get("preferred_action") or item.get("action")
            if action:
                printed_actions.add(str(action))
            continue
        print_sequence_text("Action", item.get("preferred_action") or item.get("action"), printed_actions)
        if item.get("completion_impact"):
            print(f"Completion impact: {item.get('completion_impact')}")
        command = item_command(item)
        if command_requires_operator_approval(str(command) if command else None, item):
            print(f"Approval: {OPERATOR_APPROVAL_NOTICE}")
        print_sequence_command("Command", command, printed_commands)
        if item.get("full_flow_command"):
            print_sequence_command("Full flow after preflight", item.get("full_flow_command"), printed_commands)
        if item.get("automation_command") and item.get("automation_command") != command:
            print_sequence_command("Automation JSON", item.get("automation_command"), printed_commands)
        if item.get("supporting_commands"):
            print_sequence_supporting_commands(item["supporting_commands"], printed_commands)
        if (
            item.get("local_readiness_gate_command")
            and item.get("local_readiness_gate_command") != item.get("automation_command")
            and item.get("local_readiness_gate_command") != command
        ):
            print_sequence_command("Automation JSON gate", item.get("local_readiness_gate_command"), printed_commands)
        if item.get("verify_command") and item.get("verify_command") != command:
            print_sequence_command("Verify", item.get("verify_command"), printed_commands)
        if item.get("final_verify_command") and item.get("final_verify_command") != command:
            print_sequence_command("Final verify", item.get("final_verify_command"), printed_commands)


def mark_sequence_command_seen(command: Any, printed_commands: set[str]) -> tuple[str, bool]:
    command_text = str(command or "")
    if not command_text:
        return "", False
    if command_text in printed_commands:
        return command_text, True
    printed_commands.add(command_text)
    return command_text, False


def print_sequence_command(label: str, command: Any, printed_commands: set[str]) -> None:
    command_text, repeated = mark_sequence_command_seen(command, printed_commands)
    if not command_text:
        return
    if repeated:
        print(f"{label}: same as earlier in sequence.")
        return
    print(f"{label}:")
    print(command_text)


def print_sequence_text(label: str, text: Any, printed_texts: set[str]) -> None:
    text_value = str(text or "")
    if not text_value:
        return
    if text_value in printed_texts:
        print(f"{label}: same as earlier in sequence.")
        return
    printed_texts.add(text_value)
    print(f"{label}: {text_value}")


def print_sequence_inline_command(label: str, command: Any, printed_commands: set[str]) -> None:
    command_text, repeated = mark_sequence_command_seen(command, printed_commands)
    if not command_text:
        return
    if repeated:
        print(f"{label}: same as earlier in sequence.")
        return
    print(f"{label}: {command_text}")


def print_sequence_supporting_commands(supporting_commands: Any, printed_commands: set[str]) -> None:
    commands = [
        (label, command)
        for label, command in ordered_supporting_commands(supporting_commands)
        if str(command or "")
    ]
    if not commands:
        return
    if all(str(command) in printed_commands for _, command in commands):
        print("Supporting commands: same as earlier in sequence.")
        return
    print("Supporting commands:")
    for label, command in commands:
        print_sequence_inline_command(f"- {label}", command, printed_commands)


def print_owner_summary(report: dict[str, Any]) -> None:
    print("Remaining by owner:")
    for group in report.get("owner_summary") or []:
        statuses = ", ".join(
            f"{status}: {count}" for status, count in sorted(group.get("statuses", {}).items())
        )
        items = ", ".join(group.get("items") or [])
        print(f"- {group.get('owner')}: {group.get('count')} ({statuses})")
        if items:
            print(f"  Items: {items}")


def print_local_readiness(report: dict[str, Any]) -> None:
    checks = report.get("local_readiness") or []
    if not checks:
        return
    print("Local connected-runner readiness:")
    if report.get("local_readiness_source"):
        print(f"Source: {report.get('local_readiness_source')}")
    summary = report.get("local_readiness_summary") or {}
    if summary:
        ordered_statuses = ["fail", "warn", "pass", "skipped"]
        statuses = [status for status in ordered_statuses if status in summary]
        statuses.extend(sorted(status for status in summary if status not in ordered_statuses))
        print(f"Summary: {', '.join(f'{status}: {summary[status]}' for status in statuses)}")
    if report.get("local_readiness_status"):
        print(f"Overall: {report.get('local_readiness_status')}")
    if report.get("local_readiness_issue_ids"):
        print(f"Issues: {', '.join(report.get('local_readiness_issue_ids') or [])}")
    next_setup = report.get("local_readiness_next_setup") or {}
    if report.get("local_readiness_next_setup_command"):
        check_id = report.get("local_readiness_next_setup_check_id") or "unknown"
        print(f"Next local setup ({check_id}): {report.get('local_readiness_next_setup_command')}")
        if next_setup.get("remediation"):
            print(f"Next local remediation: {next_setup.get('remediation')}")
        if next_setup.get("verify_command"):
            print(f"Next local verification: {next_setup.get('verify_command')}")
    setup_sequence = report.get("local_readiness_setup_sequence") or []
    local_sequence_commands: set[str] = set()
    if len(setup_sequence) > 1:
        print("Local setup sequence:")
        for index, setup in enumerate(setup_sequence, start=1):
            check_id = setup.get("check_id") or "unknown"
            setup_command = str(setup.get("command") or "")
            repeats_next_setup = (
                index == 1
                and setup_command
                and setup_command == report.get("local_readiness_next_setup_command")
            )
            print(
                f"{index}. {check_id}: "
                + ("same as next local setup above." if repeats_next_setup else setup_command)
            )
            if setup_command:
                local_sequence_commands.add(setup_command)
            verify_command = str(setup.get("verify_command") or "")
            if verify_command:
                local_sequence_commands.add(verify_command)
                repeats_next_verification = (
                    repeats_next_setup
                    and verify_command == str(next_setup.get("verify_command") or "")
                )
                print(
                    "   Verify: "
                    + ("same as next local verification above." if repeats_next_verification else verify_command)
                )
        print("Setup and verification commands are listed in the local setup sequence above.")
    for check in checks:
        print(f"- {check.get('id')}: {check.get('status')} - {check.get('message')}")
        if check.get("remediation"):
            print(f"  Remediation: {check.get('remediation')}")
        if check.get("setup_command"):
            setup_command = str(check.get("setup_command"))
            if setup_command not in local_sequence_commands:
                print(f"  Setup: {setup_command}")
        if check.get("command"):
            command = str(check.get("command"))
            if command not in local_sequence_commands:
                print(f"  Command: {command}")


def print_local_readiness_setup_sequence_only(report: dict[str, Any]) -> None:
    for setup in report.get("local_readiness_setup_sequence") or []:
        command = setup.get("command")
        if command:
            print(command)


def print_local_readiness_command_sequence_only(report: dict[str, Any]) -> None:
    for command in report.get("local_readiness_command_sequence") or []:
        print(command)


def command_requires_operator_approval(command: str | None, item: dict[str, Any]) -> bool:
    if item.get("requires_operator_approval"):
        return True
    return bool(command and "--operator-approved" in command)


def command_sequence_commands_for_item(
    item: dict[str, Any],
    package_dir: Path | str | None = None,
    *,
    skip_operator_approved: bool = False,
) -> list[str]:
    command = item_command(item)
    commands: list[str] = []
    supporting_commands = item.get("supporting_commands") or {}
    if (
        command
        and "--apply" in command
        and "--operator-approved" in command
        and isinstance(supporting_commands, dict)
    ):
        if package_dir is not None:
            commands.append(warning_review_summary_json_command(package_dir))
        review_artifacts_command = supporting_commands.get("Show warning review artifact paths")
        if isinstance(review_artifacts_command, str) and review_artifacts_command:
            commands.append(review_artifacts_command)
    if command and not (skip_operator_approved and command_requires_operator_approval(command, item)):
        commands.append(command)
    return commands


def print_command_sequence_only(report: dict[str, Any], *, skip_operator_approved: bool = False) -> None:
    last_command: str | None = None
    package_dir = report.get("package_dir")
    for item in report.get("remaining_items") or []:
        for command in command_sequence_commands_for_item(
            item,
            package_dir,
            skip_operator_approved=skip_operator_approved,
        ):
            if not command or command == last_command:
                continue
            print(command)
            last_command = command


def reject_conflicting_options(primary: str, conflicts: list[tuple[str, bool]]) -> None:
    enabled = [name for name, is_enabled in conflicts if is_enabled]
    if enabled:
        raise SystemExit(f"{primary} cannot be combined with {', '.join(enabled)}.")


def main() -> int:
    args = parse_args()
    if args.local_readiness_setup_sequence_only or args.local_readiness_command_sequence_only:
        args.local_readiness = True
    if args.command_only and args.json_only:
        raise SystemExit("--command-only cannot be combined with --json-only.")
    if args.command_only and args.command_sequence_only:
        raise SystemExit("--command-only cannot be combined with --command-sequence-only.")
    if args.command_sequence_only and args.json_only:
        raise SystemExit("--command-sequence-only cannot be combined with --json-only.")
    if args.skip_operator_approved and not args.command_sequence_only:
        raise SystemExit("--skip-operator-approved requires --command-sequence-only.")
    if args.local_readiness_setup_sequence_only:
        reject_conflicting_options(
            "--local-readiness-setup-sequence-only",
            [
                ("--command-only", args.command_only),
                ("--command-sequence-only", args.command_sequence_only),
                ("--local-readiness-command-sequence-only", args.local_readiness_command_sequence_only),
                ("--json-only", args.json_only),
                ("--show-sequence", args.show_sequence),
                ("--summary-by-owner", args.summary_by_owner),
                ("--output-prefix", bool(args.output_prefix)),
            ],
        )
    if args.local_readiness_command_sequence_only:
        reject_conflicting_options(
            "--local-readiness-command-sequence-only",
            [
                ("--command-only", args.command_only),
                ("--command-sequence-only", args.command_sequence_only),
                ("--local-readiness-setup-sequence-only", args.local_readiness_setup_sequence_only),
                ("--json-only", args.json_only),
                ("--show-sequence", args.show_sequence),
                ("--summary-by-owner", args.summary_by_owner),
                ("--output-prefix", bool(args.output_prefix)),
            ],
        )
    if args.command_only:
        reject_conflicting_options(
            "--command-only",
            [
                ("--show-sequence", args.show_sequence),
                ("--summary-by-owner", args.summary_by_owner),
                ("--output-prefix", bool(args.output_prefix)),
            ],
        )
    if args.command_sequence_only:
        reject_conflicting_options(
            "--command-sequence-only",
            [
                ("--show-sequence", args.show_sequence),
                ("--summary-by-owner", args.summary_by_owner),
                ("--output-prefix", bool(args.output_prefix)),
            ],
        )
    if args.json_only:
        reject_conflicting_options(
            "--json-only",
            [
                ("--output-prefix", bool(args.output_prefix)),
            ],
        )
    read_only = (
        args.no_write
        or args.command_only
        or args.command_sequence_only
        or args.json_only
        or args.local_readiness_setup_sequence_only
        or args.local_readiness_command_sequence_only
    )
    if args.repo_url is not None and not read_only:
        raise SystemExit("--repo-url requires --no-write to keep archived evidence commands portable.")
    if args.repo_url_from_origin is not None and not read_only:
        raise SystemExit("--repo-url-from-origin requires --no-write to keep archived evidence commands portable.")
    if args.repo_url_from_env is not None and not read_only:
        raise SystemExit("--repo-url-from-env requires --no-write to keep archived evidence commands portable.")
    repo_url_sources = [
        args.repo_url is not None,
        args.repo_url_from_origin is not None,
        args.repo_url_from_env is not None,
    ]
    if sum(repo_url_sources) > 1:
        raise SystemExit("--repo-url, --repo-url-from-origin, and --repo-url-from-env cannot be used together.")
    if args.handoff_bundle is not None and not read_only:
        raise SystemExit("--handoff-bundle requires --no-write to keep archived evidence commands portable.")
    if args.local_readiness and not read_only:
        raise SystemExit(
            "--local-readiness requires --no-write or --json-only to keep archived evidence commands portable."
        )
    if args.local_readiness_source is not None and not args.local_readiness:
        raise SystemExit("--local-readiness-source requires --local-readiness.")
    if args.fail_if_local_readiness_not_pass and not args.local_readiness:
        raise SystemExit("--fail-if-local-readiness-not-pass requires --local-readiness.")
    handoff_bundle = str(Path(args.handoff_bundle).absolute()) if args.handoff_bundle is not None else None
    package_dir = resolve_package_dir(
        package_dir=args.package_dir,
        packages_dir=args.packages_dir,
        handoff_bundle=handoff_bundle,
    )
    status = read_json(package_dir / "release-status.json")
    repo_url_error = None
    try:
        if args.repo_url_from_origin is not None:
            origin_source = resolve_origin_source(
                repo_url_from_origin=args.repo_url_from_origin,
                handoff_bundle=handoff_bundle,
                fallback_handoff_bundle=status.get("connected_runner_handoff_bundle"),
            )
            repo_url = git_origin_url(origin_source)
        elif args.repo_url_from_env is not None:
            repo_url = env_repo_url(args.repo_url_from_env)
        else:
            repo_url = normalize_repo_url(args.repo_url, label="--repo-url")
    except ValueError as exc:
        if args.json_only and args.fail_if_repo_url_required:
            repo_url = None
            repo_url_error = str(exc)
        else:
            raise SystemExit(str(exc)) from exc
    report = build_report(package_dir, status, args.owner, repo_url, handoff_bundle)
    if repo_url_error:
        report["repo_url_error"] = repo_url_error
    if args.local_readiness:
        local_readiness_source = resolve_local_readiness_source(
            local_readiness_source=args.local_readiness_source,
            handoff_bundle=handoff_bundle,
            fallback_handoff_bundle=report.get("handoff_bundle"),
        )
        local_checks = collect_local_readiness(local_readiness_source)
        for check in local_checks:
            if check.get("setup_command"):
                check["setup_command"] = str(apply_repo_url(check.get("setup_command"), repo_url))
        local_summary, local_status, local_issue_ids = local_readiness_summary_payload(local_checks)
        local_setup_sequence = local_readiness_setup_sequence_payload(local_checks)
        local_next_setup = local_setup_sequence[0] if local_setup_sequence else None
        report["local_readiness"] = local_checks
        report["local_readiness_source"] = str(local_readiness_source)
        report["local_readiness_summary"] = local_summary
        report["local_readiness_status"] = local_status
        report["local_readiness_issue_ids"] = local_issue_ids
        report["local_readiness_setup_sequence"] = local_setup_sequence
        report["local_readiness_command_sequence"] = local_readiness_command_sequence_payload(local_setup_sequence)
        if local_next_setup:
            report["local_readiness_next_setup"] = local_next_setup
            report["local_readiness_next_setup_command"] = local_next_setup["command"]
            report["local_readiness_next_setup_check_id"] = local_next_setup["check_id"]
        preserve_local_readiness_in_automation_commands(
            report,
            explicit_source=args.local_readiness_source,
            fail_if_not_pass=args.fail_if_local_readiness_not_pass,
        )

    exit_code = 0
    if args.fail_if_repo_url_required and report.get("repo_url_required"):
        report["repo_url_gate_message"] = repo_url_error or REPO_URL_NOTE
        if args.json_only:
            exit_code = 1
        else:
            raise SystemExit(report["repo_url_gate_message"])
    if args.fail_if_local_readiness_not_pass and report.get("local_readiness_status") != "pass":
        exit_code = 1

    if not read_only:
        output_prefix = Path(args.output_prefix) if args.output_prefix else package_dir / "next-release-step"
        output_prefix.with_suffix(".json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        write_markdown(output_prefix.with_suffix(".md"), report)

    if args.command_only:
        print(report.get("next_command") or "")
        return exit_code
    if args.command_sequence_only:
        print_command_sequence_only(report, skip_operator_approved=args.skip_operator_approved)
        return exit_code
    if args.local_readiness_setup_sequence_only:
        print_local_readiness_setup_sequence_only(report)
        return exit_code
    if args.local_readiness_command_sequence_only:
        print_local_readiness_command_sequence_only(report)
        return exit_code
    if args.json_only:
        print(json.dumps(report, indent=2, sort_keys=True))
        return exit_code

    print_summary(report)
    print_local_readiness(report)
    if args.summary_by_owner:
        print_owner_summary(report)
    if args.show_sequence:
        print_sequence(report, compact_next_item=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
