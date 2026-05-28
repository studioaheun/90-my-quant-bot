#!/usr/bin/env python3
"""Run the Quant Lab release gate and write a compact handoff summary."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.release_artifacts import (
        latest_json_file,
        latest_manifest_package_dir,
    )
except ModuleNotFoundError:  # pragma: no cover - supports running from scripts/
    from release_artifacts import latest_json_file, latest_manifest_package_dir


PACKAGE_RE = re.compile(r"^Evidence package:\s*(.+)$", re.MULTILINE)
TARBALL_RE = re.compile(r"^Tarball:\s*(.+)$", re.MULTILINE)
HANDOFF_BUNDLE_RE = re.compile(r"^Handoff bundle:\s*(.+)$", re.MULTILINE)
HANDOFF_BUNDLE_VERIFICATION_RE = re.compile(r"^Bundle verification:\s*(.+handoff-verification\.json)$", re.MULTILINE)
HANDOFF_TARBALL_RE = re.compile(r"^Tarball:\s*(.+handoff.+\.tgz)$", re.MULTILINE)
HANDOFF_TARBALL_VERIFICATION_RE = re.compile(r"^Tarball verification:\s*(.+\.verification\.json)$", re.MULTILINE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Quant Lab release gate checks.")
    parser.add_argument("--symbol", default="KRW-BTC", help="Target market symbol")
    parser.add_argument(
        "--skip-docker",
        action="store_true",
        help="Pass --skip-docker to scripts/verify_project.py",
    )
    parser.add_argument(
        "--run-smoke",
        action="store_true",
        help="Run the managed local smoke drill before packaging evidence",
    )
    parser.add_argument(
        "--require-docker",
        action="store_true",
        help="Fail external readiness when Docker is unavailable",
    )
    parser.add_argument(
        "--require-git-remote",
        action="store_true",
        help="Fail external readiness when no git origin remote exists",
    )
    parser.add_argument(
        "--require-gh",
        action="store_true",
        help="Fail external readiness when GitHub CLI is unavailable",
    )
    parser.add_argument(
        "--strict-external",
        action="store_true",
        help="Fail external readiness when Docker, git origin, or GitHub CLI checks are unavailable",
    )
    parser.add_argument(
        "--check-gh-auth",
        action="store_true",
        help="Run gh auth status when GitHub CLI is available",
    )
    parser.add_argument("--api-base", default="http://127.0.0.1:8000", help="Backend base URL for smoke checks")
    parser.add_argument(
        "--require-live-beta",
        action="store_true",
        help="Fail the release evidence check when no live beta archive exists",
    )
    parser.add_argument(
        "--no-tar",
        action="store_true",
        help="Do not create a .tgz evidence archive",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/release-gate",
        help="Directory for release gate summaries",
    )
    return parser.parse_args()


def run_step(name: str, command: list[str], *, env: dict[str, str] | None = None) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc).isoformat()
    completed = subprocess.run(
        command,
        env=env,
        text=True,
        capture_output=True,
    )
    return {
        "name": name,
        "command": command,
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "returncode": completed.returncode,
        "status": "pass" if completed.returncode == 0 else "fail",
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def latest_package_dir(packages_dir: Path = Path("artifacts/evidence-packages")) -> Path | None:
    try:
        return latest_manifest_package_dir(packages_dir)
    except FileNotFoundError:
        return None


def package_from_output(output: str) -> Path | None:
    match = PACKAGE_RE.search(output)
    if not match:
        return None
    return Path(match.group(1).strip())


def tarball_from_output(output: str) -> Path | None:
    match = TARBALL_RE.search(output)
    if not match:
        return None
    return Path(match.group(1).strip())


def handoff_bundle_from_output(output: str) -> Path | None:
    match = HANDOFF_BUNDLE_RE.search(output)
    if not match:
        return None
    return Path(match.group(1).strip())


def handoff_tarball_from_output(output: str) -> Path | None:
    match = HANDOFF_TARBALL_RE.search(output)
    if not match:
        return None
    return Path(match.group(1).strip())


def handoff_bundle_verification_from_output(output: str) -> Path | None:
    match = HANDOFF_BUNDLE_VERIFICATION_RE.search(output)
    if not match:
        return None
    return Path(match.group(1).strip())


def handoff_tarball_verification_from_output(output: str) -> Path | None:
    match = HANDOFF_TARBALL_VERIFICATION_RE.search(output)
    if not match:
        return None
    return Path(match.group(1).strip())


def completion_audit_handoff_bundle_command(handoff_bundle: Path) -> list[str]:
    return [
        sys.executable,
        "scripts/check_completion_audit.py",
        "--handoff-bundle",
        str(handoff_bundle),
    ]


def read_release_check_status(package_dir: Path | None) -> str | None:
    if package_dir is None:
        return None
    check_path = package_dir / "release-evidence-check.json"
    if not check_path.exists():
        return None
    try:
        payload = json.loads(check_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "unreadable"
    status = payload.get("status")
    return status if isinstance(status, str) else None


def release_warning_triage_path(package_dir: Path | None) -> str | None:
    if package_dir is None:
        return None
    triage_path = package_dir / "release-warning-triage.md"
    return str(triage_path) if triage_path.exists() else None


def release_warning_actions_path(package_dir: Path | None) -> str | None:
    if package_dir is None:
        return None
    actions_path = package_dir / "release-warning-actions.md"
    return str(actions_path) if actions_path.exists() else None


def release_status_report_path(package_dir: Path | None) -> str | None:
    if package_dir is None:
        return None
    status_path = package_dir / "release-status.md"
    return str(status_path) if status_path.exists() else None


def next_release_step_path(package_dir: Path | None) -> str | None:
    if package_dir is None:
        return None
    next_path = package_dir / "next-release-step.md"
    return str(next_path) if next_path.exists() else None


def evidence_checksums_path(package_dir: Path | None) -> str | None:
    if package_dir is None:
        return None
    checksums_path = package_dir / "evidence-checksums.json"
    return str(checksums_path) if checksums_path.exists() else None


def latest_external_readiness_status() -> str | None:
    latest = latest_json_file(Path("artifacts/external-readiness"), "*/external-readiness.json")
    if latest is None:
        return None
    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "unreadable"
    status = payload.get("status")
    return status if isinstance(status, str) else None


def main() -> int:
    args = parse_args()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / f"release-gate-{timestamp}.json"

    env = dict(os.environ, PYTHONPYCACHEPREFIX=os.environ.get("PYTHONPYCACHEPREFIX", "/private/tmp/quant-pycache"))
    steps: list[dict[str, Any]] = []

    verify_command = [sys.executable, "scripts/verify_project.py"]
    if args.skip_docker:
        verify_command.append("--skip-docker")
    steps.append(run_step("project_verification", verify_command, env=env))

    external_command = [sys.executable, "scripts/check_external_readiness.py"]
    require_docker = bool(args.require_docker or args.strict_external)
    require_git_remote = bool(args.require_git_remote or args.strict_external)
    require_gh = bool(args.require_gh or args.strict_external)
    if require_docker:
        external_command.append("--require-docker")
    if require_git_remote:
        external_command.append("--require-git-remote")
    if require_gh:
        external_command.append("--require-gh")
    if args.check_gh_auth:
        external_command.append("--check-gh-auth")
    steps.append(run_step("external_readiness", external_command, env=env))

    if args.run_smoke:
        smoke_command = [
            sys.executable,
            "scripts/run_local_smoke.py",
            "--start-backend",
            "--run-drill",
            "--api-base",
            args.api_base,
            "--symbol",
            args.symbol.upper(),
        ]
        steps.append(run_step("local_smoke_drill", smoke_command, env=env))
    else:
        steps.append(
            {
                "name": "local_smoke_drill",
                "command": [sys.executable, "scripts/run_local_smoke.py", "--start-backend", "--run-drill"],
                "started_at": datetime.now(timezone.utc).isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "returncode": None,
                "status": "skipped",
                "stdout": "",
                "stderr": "Skipped because --run-smoke was not provided.",
            }
        )

    package_command = [
        sys.executable,
        "scripts/package_evidence.py",
        "--symbol",
        args.symbol.upper(),
    ]
    if not args.no_tar:
        package_command.append("--tar")
    package_step = run_step("package_evidence", package_command, env=env)
    steps.append(package_step)
    package_dir = package_from_output(package_step["stdout"]) or latest_package_dir()
    tarball = tarball_from_output(package_step["stdout"])
    handoff_bundle: Path | None = None
    handoff_bundle_verification: Path | None = None
    handoff_tarball: Path | None = None
    handoff_tarball_verification: Path | None = None
    if package_dir is not None and package_step["returncode"] == 0:
        handoff_bundle = (Path("artifacts/handoff-bundles") / f"quant-lab-connected-runner-handoff-{timestamp}").absolute()
        handoff_bundle_verification = handoff_bundle / "handoff-verification.json"
        handoff_tarball = handoff_bundle.with_suffix(".tgz")
        handoff_tarball_verification = handoff_tarball.with_suffix(handoff_tarball.suffix + ".verification.json")

    if package_dir is not None and package_step["returncode"] == 0:
        check_command = [
            sys.executable,
            "scripts/check_release_evidence.py",
            "--package-dir",
            str(package_dir),
        ]
        if args.require_live_beta:
            check_command.append("--require-live-beta")
        steps.append(run_step("release_evidence_check", check_command, env=env))
        actions_command = [
            sys.executable,
            "scripts/review_release_warnings.py",
            "--package-dir",
            str(package_dir),
        ]
        steps.append(run_step("release_warning_review", actions_command, env=env))
    else:
        steps.append(
            {
                "name": "release_evidence_check",
                "command": [sys.executable, "scripts/check_release_evidence.py"],
                "started_at": datetime.now(timezone.utc).isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "returncode": None,
                "status": "skipped",
                "stdout": "",
                "stderr": "Skipped because evidence packaging did not produce a package directory.",
            }
        )
        steps.append(
            {
                "name": "release_warning_review",
                "command": [sys.executable, "scripts/review_release_warnings.py"],
                "started_at": datetime.now(timezone.utc).isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "returncode": None,
                "status": "skipped",
                "stdout": "",
                "stderr": "Skipped because evidence packaging did not produce a package directory.",
            }
        )

    release_check_status = read_release_check_status(package_dir)
    external_readiness_status = latest_external_readiness_status()

    def build_summary() -> dict[str, Any]:
        has_failures = any(step["status"] == "fail" for step in steps)
        has_warnings = release_check_status == "warn" or external_readiness_status == "warn"
        status = "fail" if has_failures else ("warn" if has_warnings else "pass")
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "symbol": args.symbol.upper(),
            "run_smoke": bool(args.run_smoke),
            "skip_docker": bool(args.skip_docker),
            "strict_external": bool(args.strict_external),
            "require_docker": require_docker,
            "require_git_remote": require_git_remote,
            "require_gh": require_gh,
            "check_gh_auth": bool(args.check_gh_auth),
            "require_live_beta": bool(args.require_live_beta),
            "external_readiness_status": external_readiness_status,
            "package_dir": str(package_dir) if package_dir else None,
            "tarball": str(tarball) if tarball else None,
            "release_check_status": release_check_status,
            "release_warning_triage": release_warning_triage_path(package_dir),
            "release_warning_actions": release_warning_actions_path(package_dir),
            "release_status_report": release_status_report_path(package_dir),
            "next_release_step": next_release_step_path(package_dir),
            "evidence_checksums": evidence_checksums_path(package_dir),
            "connected_runner_handoff_bundle": str(handoff_bundle) if handoff_bundle else None,
            "connected_runner_handoff_bundle_verification": (
                str(handoff_bundle_verification) if handoff_bundle_verification else None
            ),
            "connected_runner_handoff_tarball": str(handoff_tarball) if handoff_tarball else None,
            "connected_runner_handoff_tarball_verification": (
                str(handoff_tarball_verification) if handoff_tarball_verification else None
            ),
            "steps": steps,
        }

    summary = build_summary()
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if package_dir is not None and package_step["returncode"] == 0:
        status_command = [
            sys.executable,
            "scripts/report_release_status.py",
            "--package-dir",
            str(package_dir),
            "--release-gate",
            str(summary_path),
        ]
        steps.append(run_step("release_status_report", status_command, env=env))
        next_step_command = [
            sys.executable,
            "scripts/next_release_step.py",
            "--package-dir",
            str(package_dir),
        ]
        steps.append(run_step("next_release_step_report", next_step_command, env=env))
        final_check_command = [
            sys.executable,
            "scripts/check_release_evidence.py",
            "--package-dir",
            str(package_dir),
        ]
        if args.require_live_beta:
            final_check_command.append("--require-live-beta")
        steps.append(run_step("final_release_evidence_check", final_check_command, env=env))
        release_check_status = read_release_check_status(package_dir)
        checksum_command = [
            sys.executable,
            "scripts/write_evidence_checksums.py",
            "--package-dir",
            str(package_dir),
        ]
        steps.append(run_step("evidence_checksums", checksum_command, env=env))
        checksum_verify_command = [
            sys.executable,
            "scripts/write_evidence_checksums.py",
            "--package-dir",
            str(package_dir),
            "--verify",
        ]
        steps.append(run_step("evidence_checksum_verification", checksum_verify_command, env=env))
        handoff_command = [
            sys.executable,
            "scripts/package_connected_runner_handoff.py",
            "--package-dir",
            str(package_dir),
            "--bundle-dir",
            str(handoff_bundle),
        ]
        handoff_step = run_step("connected_runner_handoff_bundle", handoff_command, env=env)
        steps.append(handoff_step)
        handoff_bundle = handoff_bundle_from_output(handoff_step["stdout"]) or handoff_bundle
        handoff_bundle_verification = (
            handoff_bundle_verification_from_output(handoff_step["stdout"]) or handoff_bundle_verification
        )
        handoff_tarball = handoff_tarball_from_output(handoff_step["stdout"]) or handoff_tarball
        handoff_tarball_verification = (
            handoff_tarball_verification_from_output(handoff_step["stdout"]) or handoff_tarball_verification
        )
        if handoff_step["returncode"] == 0 and handoff_bundle is not None:
            steps.append(
                run_step(
                    "completion_audit_handoff_bundle",
                    completion_audit_handoff_bundle_command(handoff_bundle),
                    env=env,
                )
            )
        summary = build_summary()
        summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for step in steps:
        print(f"{step['status'].upper():7} {step['name']}")
    if package_dir is not None:
        print(f"Evidence package: {package_dir}")
    if tarball is not None:
        print(f"Tarball: {tarball}")
    print(f"Release check status: {release_check_status or 'not available'}")
    print(f"External readiness status: {external_readiness_status or 'not available'}")
    if summary["release_warning_triage"]:
        print(f"Warning triage: {summary['release_warning_triage']}")
    if summary["release_warning_actions"]:
        print(f"Warning actions: {summary['release_warning_actions']}")
    if summary["release_status_report"]:
        print(f"Release status report: {summary['release_status_report']}")
    if summary["next_release_step"]:
        print(f"Next release step: {summary['next_release_step']}")
    if summary["evidence_checksums"]:
        print(f"Evidence checksums: {summary['evidence_checksums']}")
    if summary["connected_runner_handoff_bundle"]:
        print(f"Connected-runner handoff bundle: {summary['connected_runner_handoff_bundle']}")
    if summary["connected_runner_handoff_bundle_verification"]:
        print(
            "Connected-runner handoff bundle verification: "
            f"{summary['connected_runner_handoff_bundle_verification']}"
        )
    if summary["connected_runner_handoff_tarball"]:
        print(f"Connected-runner handoff tarball: {summary['connected_runner_handoff_tarball']}")
    if summary["connected_runner_handoff_tarball_verification"]:
        print(
            "Connected-runner handoff tarball verification: "
            f"{summary['connected_runner_handoff_tarball_verification']}"
        )
    print(f"Release gate summary: {summary_path}")
    return 1 if any(step["status"] == "fail" for step in steps) else 0


if __name__ == "__main__":
    raise SystemExit(main())
