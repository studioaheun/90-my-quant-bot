#!/usr/bin/env python3
"""Check external release prerequisites that may not exist on this machine."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.connected_runner_contract import compact_check_summary
    from scripts.handoff_commands import (
        DOCKER_SETUP_COMMAND,
        GITHUB_CLI_SETUP_COMMAND,
        REPO_URL_PLACEHOLDER,
        git_origin_setup_command,
        repo_url_export_example_command,
    )
except ModuleNotFoundError:  # pragma: no cover - supports running from scripts/
    from connected_runner_contract import compact_check_summary
    from handoff_commands import (
        DOCKER_SETUP_COMMAND,
        GITHUB_CLI_SETUP_COMMAND,
        REPO_URL_PLACEHOLDER,
        git_origin_setup_command,
        repo_url_export_example_command,
    )


WORKFLOW_PATH = Path(".github/workflows/quant-lab-ci.yml")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check external Quant Lab release readiness.")
    parser.add_argument(
        "--output-dir",
        default="artifacts/external-readiness",
        help="Directory for external-readiness reports",
    )
    parser.add_argument("--require-docker", action="store_true", help="Fail when Docker is unavailable")
    parser.add_argument("--require-git-remote", action="store_true", help="Fail when no git origin remote exists")
    parser.add_argument("--require-gh", action="store_true", help="Fail when GitHub CLI is unavailable")
    parser.add_argument(
        "--check-gh-auth",
        action="store_true",
        help="Run gh auth status when GitHub CLI is available",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Print the full external-readiness report as JSON instead of human-readable lines.",
    )
    parser.add_argument(
        "--summary-json-only",
        action="store_true",
        help="Print compact external-readiness status/counts and warning/failure IDs as JSON.",
    )
    return parser.parse_args()


def run_command(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(command, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def add_check(
    checks: list[dict[str, Any]],
    *,
    check_id: str,
    label: str,
    status: str,
    message: str,
    evidence: str | None = None,
    remediation: str | None = None,
    setup_command: str | None = None,
    verify_command: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    checks.append(
        {
            "id": check_id,
            "label": label,
            "status": status,
            "message": message,
            "evidence": evidence,
            "remediation": remediation,
            "setup_command": setup_command,
            "verify_command": verify_command,
            "details": details or {},
        }
    )


def check_workflow(checks: list[dict[str, Any]]) -> None:
    if not WORKFLOW_PATH.exists():
        add_check(
            checks,
            check_id="github_actions_workflow",
            label="GitHub Actions workflow",
            status="fail",
            message=f"{WORKFLOW_PATH} is missing.",
        )
        return
    content = WORKFLOW_PATH.read_text(encoding="utf-8")
    expected_fragments = (
        "scripts/release_gate.py --run-smoke",
        "--strict-external",
        "scripts/check_release_evidence.py",
        "actions/upload-artifact",
        "artifacts/evidence-packages/",
        "artifacts/external-readiness/",
        "artifacts/release-gate/",
        "artifacts/handoff-bundles/",
        "artifacts/live-beta/",
        "GH_TOKEN:",
        "--check-gh-auth",
    )
    missing = [fragment for fragment in expected_fragments if fragment not in content]
    add_check(
        checks,
        check_id="github_actions_workflow",
        label="GitHub Actions workflow",
        status="pass" if not missing else "fail",
        message=(
            "Workflow contains strict release gate, evidence check, and artifact upload steps."
            if not missing
            else "Workflow is missing expected fragments: " + ", ".join(missing)
        ),
        evidence=str(WORKFLOW_PATH),
        remediation=(
            "No action required."
            if not missing
            else "Restore the strict release workflow fragments before relying on CI release evidence."
        ),
        verify_command="python3 scripts/check_external_readiness.py --require-git-remote --require-docker --require-gh",
        details={"missing_fragments": missing},
    )


def check_git_remote(checks: list[dict[str, Any]], *, require_git_remote: bool) -> None:
    git = shutil.which("git")
    if git is None:
        add_check(
            checks,
            check_id="git_cli",
            label="Git CLI",
            status="fail" if require_git_remote else "warn",
            message="git executable is not available.",
            remediation="Install git on the connected runner before running the strict release gate.",
            verify_command="git --version",
        )
        return
    repo = run_command([git, "rev-parse", "--is-inside-work-tree"])
    is_repo = repo["returncode"] == 0 and repo["stdout"].strip() == "true"
    add_check(
        checks,
        check_id="git_repository",
        label="Git repository",
        status="pass" if is_repo else ("fail" if require_git_remote else "warn"),
        message=(
            "Current directory is inside a git repository."
            if is_repo
            else "Current directory is not inside a git repository; initialize the handoff source before pushing."
        ),
        remediation=(
            "No action required."
            if is_repo
            else (
                "Initialize a repository in the handoff source, create a branch, commit the source snapshot, "
                "and set or add origin."
            )
        ),
        setup_command=(
            None
            if is_repo
            else "\n".join(
                [
                    "git init",
                    "git checkout -b codex/quant-lab-release",
                    "git add .",
                    "git commit -m \"Prepare Quant Lab release handoff\"",
                    git_origin_setup_command(),
                ]
            )
        ),
        verify_command="git rev-parse --is-inside-work-tree",
        details=repo,
    )
    if not is_repo:
        add_check(
            checks,
            check_id="git_origin_remote",
            label="Git origin remote",
            status="fail" if require_git_remote else "warn",
            message="Git origin remote cannot be checked until the handoff source is a git repository.",
            remediation=(
                "Initialize git in the handoff source and set or add origin before running the strict release gate."
            ),
            setup_command=git_origin_setup_command(),
            verify_command="git remote get-url origin",
            details=repo,
        )
        return
    remote = run_command([git, "remote", "get-url", "origin"])
    has_remote = remote["returncode"] == 0 and bool(remote["stdout"].strip())
    add_check(
        checks,
        check_id="git_origin_remote",
        label="Git origin remote",
        status="pass" if has_remote else ("fail" if require_git_remote else "warn"),
        message=(
            f"Git origin remote is configured: {remote['stdout'].strip()}"
            if has_remote
            else "Git origin remote is not configured; CI runner validation must happen after pushing to a remote."
        ),
        remediation=(
            "No action required."
            if has_remote
            else "Add the repository remote on the connected runner, then push the branch so GitHub Actions can run."
        ),
        setup_command=None if has_remote else git_origin_setup_command(),
        verify_command="git remote get-url origin",
        details=remote,
    )


def check_docker(checks: list[dict[str, Any]], *, require_docker: bool) -> None:
    docker = shutil.which("docker")
    if docker is None:
        add_check(
            checks,
            check_id="docker_cli",
            label="Docker CLI",
            status="fail" if require_docker else "warn",
            message="Docker is not installed on this machine.",
            remediation=(
                "Install and start Docker Desktop or Docker Engine on the connected runner. "
                "On macOS/Homebrew runners, use the setup command below."
            ),
            setup_command=DOCKER_SETUP_COMMAND,
            verify_command="docker compose version",
        )
        return
    version = run_command([docker, "compose", "version"])
    if version["returncode"] != 0:
        add_check(
            checks,
            check_id="docker_compose_available",
            label="Docker Compose",
            status="fail",
            message="Docker is installed but `docker compose version` failed.",
            remediation="Fix Docker Compose installation or PATH before running the strict release gate.",
            verify_command="docker compose version",
            details=version,
        )
        return
    compose_config = run_command([docker, "compose", "config"])
    add_check(
        checks,
        check_id="docker_compose_config",
        label="Docker Compose config",
        status="pass" if compose_config["returncode"] == 0 else "fail",
        message=(
            "Docker Compose config validated."
            if compose_config["returncode"] == 0
            else "Docker Compose config failed."
        ),
        remediation=(
            "No action required."
            if compose_config["returncode"] == 0
            else "Fix docker-compose.yml or environment-specific Compose configuration before handoff."
        ),
        verify_command="docker compose config",
        details={"version": version, "config": compose_config},
    )


def check_gh(checks: list[dict[str, Any]], *, require_gh: bool, check_auth: bool) -> None:
    gh = shutil.which("gh")
    if gh is None:
        add_check(
            checks,
            check_id="github_cli",
            label="GitHub CLI",
            status="fail" if require_gh else "warn",
            message="GitHub CLI is not installed; workflow status cannot be checked from this machine.",
            remediation=(
                "Install GitHub CLI and authenticate it on the connected runner. "
                "On macOS/Homebrew runners, use the setup command below."
            ),
            setup_command=GITHUB_CLI_SETUP_COMMAND,
            verify_command="gh auth status",
        )
        return
    version = run_command([gh, "--version"])
    add_check(
        checks,
        check_id="github_cli",
        label="GitHub CLI",
        status="pass" if version["returncode"] == 0 else "fail",
        message="GitHub CLI is available." if version["returncode"] == 0 else "GitHub CLI version check failed.",
        remediation="No action required." if version["returncode"] == 0 else "Fix GitHub CLI installation or PATH.",
        verify_command="gh --version",
        details=version,
    )
    if check_auth:
        auth = run_command([gh, "auth", "status"])
        auth_ok = auth["returncode"] == 0
        add_check(
            checks,
            check_id="github_cli_auth",
            label="GitHub CLI auth",
            status="pass" if auth_ok else "warn",
            message="GitHub CLI auth is available." if auth_ok else "GitHub CLI auth status is not available.",
            remediation="No action required." if auth_ok else "Authenticate GitHub CLI before checking workflow status.",
            verify_command="gh auth status",
            details=auth,
        )
        if not auth_ok:
            return

        workflow = run_command([gh, "workflow", "view", "quant-lab-ci.yml", "--json", "name,state,path"])
        add_check(
            checks,
            check_id="github_actions_workflow_remote",
            label="GitHub Actions workflow remote visibility",
            status="pass" if workflow["returncode"] == 0 else "warn",
            message=(
                "GitHub CLI can query the Quant Lab workflow on the remote."
                if workflow["returncode"] == 0
                else "GitHub CLI could not query the Quant Lab workflow on the remote."
            ),
            remediation=(
                "No action required."
                if workflow["returncode"] == 0
                else "Push the branch, confirm the workflow exists on GitHub, and rerun the external readiness check."
            ),
            verify_command="gh workflow view quant-lab-ci.yml --json name,state,path",
            details=workflow,
        )

        runs = run_command(
            [
                gh,
                "run",
                "list",
                "--workflow",
                "quant-lab-ci.yml",
                "--limit",
                "3",
                "--json",
                "status,conclusion,headBranch,createdAt,url",
            ]
        )
        run_status = "warn"
        run_message = "GitHub Actions run history is not available."
        run_details: dict[str, Any] = {"command": runs}
        if runs["returncode"] == 0:
            try:
                run_payload = json.loads(runs["stdout"] or "[]")
            except json.JSONDecodeError as exc:
                run_details["parse_error"] = str(exc)
                run_message = "GitHub Actions run history output was not valid JSON."
            else:
                run_details["runs"] = run_payload
                if run_payload:
                    latest = run_payload[0]
                    latest_status = latest.get("status")
                    latest_conclusion = latest.get("conclusion") or "not completed"
                    latest_branch = latest.get("headBranch") or "unknown branch"
                    run_message = (
                        "Latest GitHub Actions run: "
                        f"{latest_status}/{latest_conclusion} on {latest_branch}."
                    )
                    run_status = "pass" if latest_status == "completed" and latest_conclusion == "success" else "warn"
                else:
                    run_message = "GitHub Actions run query succeeded, but no workflow runs were returned."
        add_check(
            checks,
            check_id="github_actions_latest_run",
            label="GitHub Actions latest run",
            status=run_status,
            message=run_message,
            remediation=(
                "No action required."
                if run_status == "pass"
                else "Push the branch and wait for the Quant Lab CI workflow to complete successfully."
            ),
            verify_command="gh run list --workflow quant-lab-ci.yml --limit 3",
            details=run_details,
        )


def write_markdown(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# External Release Readiness",
        "",
        f"Generated at: {summary['generated_at']}",
        f"Status: {summary['status']}",
        "",
        "## Checks",
        "",
    ]
    for check in summary["checks"]:
        lines.extend(
            [
                f"### {check['label']}",
                "",
                f"- Status: {check['status']}",
                f"- Message: {check['message']}",
            ]
        )
        if check.get("evidence"):
            lines.append(f"- Evidence: {check['evidence']}")
        if check.get("remediation"):
            lines.append(f"- Remediation: {check['remediation']}")
        if check.get("setup_command"):
            lines.extend(["- Setup:", "", "```bash", check["setup_command"], "```"])
        if check.get("verify_command"):
            lines.extend(["- Verify:", "", "```bash", check["verify_command"], "```"])
        lines.append("")
    lines.extend(
        [
            "## Notes",
            "",
            "- `warn` means the current machine cannot prove the external gate, not that the application code failed.",
            "- Validate Docker Compose on a Docker-enabled host before production-like handoff.",
            "- Validate GitHub Actions on a connected runner after pushing this workflow to a remote.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def unresolved_guidance(summary: dict[str, Any]) -> dict[str, Any]:
    checks = summary.get("checks")
    if not isinstance(checks, list):
        checks = []

    setup_sequence: list[str] = []
    verify_sequence: list[str] = []
    command_sequence: list[str] = []
    next_setup: dict[str, str] | None = None

    for check in checks:
        if not isinstance(check, dict) or check.get("status") not in {"warn", "fail"}:
            continue
        setup_command = check.get("setup_command")
        verify_command = check.get("verify_command")
        if isinstance(setup_command, str) and setup_command:
            setup_sequence.append(setup_command)
            command_sequence.append(setup_command)
            if next_setup is None:
                next_setup = {
                    "id": str(check.get("id", "")),
                    "label": str(check.get("label", "")),
                    "status": str(check.get("status", "")),
                    "setup_command": setup_command,
                }
                if isinstance(verify_command, str) and verify_command:
                    next_setup["verify_command"] = verify_command
        if isinstance(verify_command, str) and verify_command:
            verify_sequence.append(verify_command)
            command_sequence.append(verify_command)

    requires_repo_url = any(REPO_URL_PLACEHOLDER in command for command in command_sequence)
    return {
        "next_setup": next_setup,
        "next_setup_command": next_setup.get("setup_command") if next_setup else None,
        "repo_url": {
            "required": requires_repo_url,
            "placeholder": REPO_URL_PLACEHOLDER if requires_repo_url else None,
            "export_command": repo_url_export_example_command() if requires_repo_url else None,
            "message": (
                f"Replace {REPO_URL_PLACEHOLDER} with the real git remote URL before running setup commands."
                if requires_repo_url
                else None
            ),
        },
        "setup_sequence": setup_sequence,
        "verify_sequence": verify_sequence,
        "command_sequence": command_sequence,
    }


def main() -> int:
    args = parse_args()
    if args.json_only and args.summary_json_only:
        raise SystemExit("--json-only cannot be combined with --summary-json-only.")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    output_dir = Path(args.output_dir) / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    checks: list[dict[str, Any]] = []

    check_workflow(checks)
    check_git_remote(checks, require_git_remote=args.require_git_remote)
    check_docker(checks, require_docker=args.require_docker)
    check_gh(checks, require_gh=args.require_gh, check_auth=args.check_gh_auth)

    has_failures = any(check["status"] == "fail" for check in checks)
    has_warnings = any(check["status"] == "warn" for check in checks)
    status = "fail" if has_failures else ("warn" if has_warnings else "pass")
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "checks": checks,
    }
    json_path = output_dir / "external-readiness.json"
    markdown_path = output_dir / "external-readiness.md"
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(markdown_path, summary)

    if args.summary_json_only:
        payload = {
            "generated_at": summary["generated_at"],
            "status": status,
            "json_path": str(json_path),
            "markdown_path": str(markdown_path),
            "check_summary": compact_check_summary(summary),
            "guidance": unresolved_guidance(summary),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif args.json_only:
        payload = dict(summary)
        payload["json_path"] = str(json_path)
        payload["markdown_path"] = str(markdown_path)
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for check in checks:
            print(f"{check['status'].upper():5} {check['id']}: {check['message']}")
        print(f"External readiness: {json_path}")
    return 1 if has_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
