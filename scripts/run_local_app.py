#!/usr/bin/env python3
"""Start Quant Lab backend/frontend together and open the browser."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Quant Lab local web app.")
    parser.add_argument("--backend-host", default="127.0.0.1", help="Backend bind host.")
    parser.add_argument("--backend-port", type=int, default=8000, help="Backend port.")
    parser.add_argument("--frontend-host", default="127.0.0.1", help="Frontend bind host.")
    parser.add_argument("--frontend-port", type=int, default=5173, help="Frontend port.")
    parser.add_argument(
        "--api-base",
        default=None,
        help="Frontend API base URL. Defaults to http://BACKEND_HOST:BACKEND_PORT.",
    )
    parser.add_argument(
        "--frontend-url",
        default=None,
        help="Browser URL. Defaults to http://FRONTEND_HOST:FRONTEND_PORT.",
    )
    parser.add_argument(
        "--wait-seconds",
        type=int,
        default=60,
        help="Seconds to wait for backend/frontend readiness.",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/local-app",
        help="Directory for backend/frontend logs.",
    )
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser.")
    return parser.parse_args()


def request_ok(url: str, timeout: int = 5) -> bool:
    request = urllib.request.Request(url, headers={"Accept": "application/json,text/html"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return 200 <= response.status < 300
    except (urllib.error.URLError, TimeoutError):
        return False


def wait_for_url(
    *,
    label: str,
    url: str,
    wait_seconds: int,
    processes: dict[str, tuple[subprocess.Popen[Any], Path]],
) -> None:
    deadline = time.time() + wait_seconds
    while time.time() <= deadline:
        if request_ok(url):
            return
        for process_label, (process, log_path) in processes.items():
            if process.poll() is not None:
                raise RuntimeError(
                    f"{process_label} exited early with code {process.returncode}. "
                    f"Log: {log_path}"
                )
        time.sleep(1)
    raise RuntimeError(f"{label} did not become ready within {wait_seconds}s: {url}")


def backend_python() -> str:
    candidates = [
        REPO_ROOT / "backend" / ".venv" / "bin" / "python",
        REPO_ROOT / ".venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return sys.executable


def start_process(
    *,
    label: str,
    command: list[str],
    cwd: Path,
    env: Optional[dict[str, str]],
    log_path: Path,
) -> subprocess.Popen[Any]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = log_path.open("w", encoding="utf-8")
    print(f"Starting {label}: {' '.join(command)}")
    print(f"{label} log: {log_path}")
    return subprocess.Popen(
        command,
        cwd=str(cwd),
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
    )


def start_backend(args: argparse.Namespace, api_base: str, output_dir: Path) -> tuple[subprocess.Popen[Any], Path]:
    env = os.environ.copy()
    env.setdefault("QUANT_LAB_LIVE_TRADING_ENABLED", "false")
    env.setdefault("QUANT_LAB_DB_PATH", str((REPO_ROOT / "backend" / "data" / "quant_lab.sqlite3").resolve()))
    log_path = output_dir / "backend.log"
    command = [
        backend_python(),
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        args.backend_host,
        "--port",
        str(args.backend_port),
    ]
    process = start_process(
        label="backend",
        command=command,
        cwd=REPO_ROOT / "backend",
        env=env,
        log_path=log_path,
    )
    return process, log_path


def start_frontend(args: argparse.Namespace, api_base: str, output_dir: Path) -> tuple[subprocess.Popen[Any], Path]:
    env = os.environ.copy()
    env["VITE_API_BASE_URL"] = api_base
    log_path = output_dir / "frontend.log"
    command = [
        "npm",
        "run",
        "dev",
        "--",
        "--host",
        args.frontend_host,
        "--port",
        str(args.frontend_port),
    ]
    process = start_process(
        label="frontend",
        command=command,
        cwd=REPO_ROOT / "frontend",
        env=env,
        log_path=log_path,
    )
    return process, log_path


def stop_processes(processes: dict[str, tuple[subprocess.Popen[Any], Path]]) -> None:
    for label, (process, _) in processes.items():
        if process.poll() is None:
            print(f"Stopping {label}...")
            process.terminate()
    for label, (process, _) in processes.items():
        if process.poll() is not None:
            continue
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            print(f"Force stopping {label}...")
            process.kill()
            process.wait(timeout=5)


def keep_alive(processes: dict[str, tuple[subprocess.Popen[Any], Path]]) -> int:
    while True:
        for label, (process, log_path) in processes.items():
            if process.poll() is not None:
                print(f"{label} exited with code {process.returncode}. Log: {log_path}", file=sys.stderr)
                return 1
        time.sleep(1)


def main() -> int:
    args = parse_args()
    api_base = args.api_base or f"http://{args.backend_host}:{args.backend_port}"
    frontend_url = args.frontend_url or f"http://{args.frontend_host}:{args.frontend_port}"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    output_dir = REPO_ROOT / args.output_dir / timestamp
    processes: dict[str, tuple[subprocess.Popen[Any], Path]] = {}

    backend_health_url = api_base.rstrip("/") + "/api/health"
    try:
        if request_ok(backend_health_url):
            print(f"Reusing existing backend: {backend_health_url}")
        else:
            processes["backend"] = start_backend(args, api_base, output_dir)
            wait_for_url(
                label="backend",
                url=backend_health_url,
                wait_seconds=args.wait_seconds,
                processes=processes,
            )

        if request_ok(frontend_url):
            print(f"Reusing existing frontend: {frontend_url}")
        else:
            processes["frontend"] = start_frontend(args, api_base, output_dir)
            wait_for_url(
                label="frontend",
                url=frontend_url,
                wait_seconds=args.wait_seconds,
                processes=processes,
            )

        print(f"Quant Lab is ready: {frontend_url}")
        if not args.no_browser:
            webbrowser.open(frontend_url)
            print("Browser opened.")

        if processes:
            print("Press Ctrl+C to stop managed processes.")
            return keep_alive(processes)

        print("Both services were already running. Press Ctrl+C to exit this launcher.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down local app launcher.")
        return 0
    finally:
        stop_processes(processes)


if __name__ == "__main__":
    raise SystemExit(main())
