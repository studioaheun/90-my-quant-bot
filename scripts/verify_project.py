#!/usr/bin/env python3
"""Run Quant Lab project verification checks."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.release_manifest import CORE_RELEASE_SCRIPT_FILES
except ModuleNotFoundError:
    from release_manifest import CORE_RELEASE_SCRIPT_FILES


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Quant Lab verification checks.")
    parser.add_argument(
        "--skip-docker",
        action="store_true",
        help="Skip docker compose config even if docker is installed",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/verification",
        help="Directory for verification summary",
    )
    return parser.parse_args()


def backend_python() -> str:
    candidate = Path("backend/.venv/bin/python")
    if candidate.exists():
        return str(candidate.absolute())
    return sys.executable


def run_check(
    *,
    name: str,
    command: list[str],
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc).isoformat()
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
    )
    return {
        "name": name,
        "command": command,
        "cwd": cwd or ".",
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "returncode": completed.returncode,
        "status": "pass" if completed.returncode == 0 else "fail",
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def main() -> int:
    args = parse_args()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    checks: list[dict[str, Any]] = []
    scripts = list(CORE_RELEASE_SCRIPT_FILES)
    pycache_env = dict(os.environ, PYTHONPYCACHEPREFIX=os.environ.get("PYTHONPYCACHEPREFIX", "/tmp/quant-pycache"))
    checks.append(
        run_check(
            name="script_compile",
            command=["python3", "-m", "py_compile", *scripts],
            env=pycache_env,
        )
    )
    checks.append(
        run_check(
            name="next_release_step_cli_smoke",
            command=[sys.executable, "scripts/test_next_release_step.py"],
            env=pycache_env,
        )
    )
    checks.append(
        run_check(
            name="release_artifact_selection_smoke",
            command=[sys.executable, "scripts/test_release_artifacts.py"],
            env=pycache_env,
        )
    )
    checks.append(
        run_check(
            name="release_manifest_smoke",
            command=[sys.executable, "scripts/test_release_manifest.py"],
            env=pycache_env,
        )
    )
    checks.append(
        run_check(
            name="release_gate_smoke",
            command=[sys.executable, "scripts/test_release_gate.py"],
            env=pycache_env,
        )
    )
    checks.append(
        run_check(
            name="package_evidence_selection_smoke",
            command=[sys.executable, "scripts/test_package_evidence.py"],
            env=pycache_env,
        )
    )
    checks.append(
        run_check(
            name="archive_live_beta_closeout_cli_smoke",
            command=[sys.executable, "scripts/test_archive_live_beta_closeout.py"],
            env=pycache_env,
        )
    )
    checks.append(
        run_check(
            name="release_status_report_cli_smoke",
            command=[sys.executable, "scripts/test_report_release_status.py"],
            env=pycache_env,
        )
    )
    checks.append(
        run_check(
            name="release_evidence_check_cli_smoke",
            command=[sys.executable, "scripts/test_check_release_evidence.py"],
            env=pycache_env,
        )
    )
    checks.append(
        run_check(
            name="release_warning_review_cli_smoke",
            command=[sys.executable, "scripts/test_review_release_warnings.py"],
            env=pycache_env,
        )
    )
    checks.append(
        run_check(
            name="connected_runner_handoff_cli_smoke",
            command=[sys.executable, "scripts/test_package_connected_runner_handoff.py"],
            env=pycache_env,
        )
    )
    checks.append(
        run_check(
            name="connected_runner_acceptance_cli_smoke",
            command=[sys.executable, "scripts/test_connected_runner_acceptance.py"],
            env=pycache_env,
        )
    )
    checks.append(
        run_check(
            name="frontend_theme_smoke",
            command=[sys.executable, "scripts/check_frontend_theme.py"],
            env=pycache_env,
        )
    )
    checks.append(
        run_check(
            name="completion_audit_smoke",
            command=[sys.executable, "scripts/check_completion_audit.py"],
            env=pycache_env,
        )
    )
    checks.append(
        run_check(
            name="backend_unittest",
            command=[backend_python(), "-m", "unittest", "discover", "-s", "backend/tests"],
        )
    )
    checks.append(
        run_check(
            name="frontend_build",
            command=["npm", "run", "build"],
            cwd="frontend",
        )
    )
    if args.skip_docker or shutil.which("docker") is None:
        checks.append(
            {
                "name": "docker_compose_config",
                "command": ["docker", "compose", "config"],
                "cwd": ".",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "returncode": None,
                "status": "skipped",
                "stdout": "",
                "stderr": "Docker is not installed or --skip-docker was provided.",
            }
        )
    else:
        checks.append(
            run_check(
                name="docker_compose_config",
                command=["docker", "compose", "config"],
            )
        )

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass" if all(check["status"] in {"pass", "skipped"} for check in checks) else "fail",
        "checks": checks,
    }
    summary_path = output_dir / f"verification-{timestamp}.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for check in checks:
        print(f"{check['status'].upper():7} {check['name']}")
    print(f"Verification summary: {summary_path}")
    return 0 if summary["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
