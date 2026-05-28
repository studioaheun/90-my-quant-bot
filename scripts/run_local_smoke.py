#!/usr/bin/env python3
"""Run a local Quant Lab smoke check, optionally managing the backend process."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Quant Lab local smoke verification.")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000", help="Backend base URL")
    parser.add_argument("--host", default="127.0.0.1", help="Managed backend host")
    parser.add_argument("--port", type=int, default=8000, help="Managed backend port")
    parser.add_argument("--symbol", default="KRW-BTC", help="KRW crypto drill symbol")
    parser.add_argument("--wait-seconds", type=int, default=45, help="Seconds to wait for health")
    parser.add_argument(
        "--start-backend",
        action="store_true",
        help="Start a local uvicorn backend before running smoke checks",
    )
    parser.add_argument(
        "--run-drill",
        action="store_true",
        help="Run the seeded crypto drill during smoke checks",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/local-smoke",
        help="Directory for logs and smoke-check artifacts",
    )
    return parser.parse_args()


def health_url(api_base: str) -> str:
    return api_base.rstrip("/") + "/api/health"


def wait_for_health(api_base: str, wait_seconds: int) -> None:
    deadline = time.time() + wait_seconds
    last_error = ""
    while time.time() <= deadline:
        try:
            with urllib.request.urlopen(health_url(api_base), timeout=5) as response:
                if 200 <= response.status < 300:
                    return
        except urllib.error.URLError as exc:
            last_error = str(exc)
        time.sleep(1)
    raise RuntimeError(f"Backend did not become healthy within {wait_seconds}s. {last_error}")


def backend_python() -> str:
    candidates = [
        Path("backend/.venv/bin/python"),
        Path(".venv/bin/python"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate.absolute())
    return sys.executable


def start_backend(
    *,
    host: str,
    port: int,
    output_dir: Path,
) -> subprocess.Popen:
    output_dir.mkdir(parents=True, exist_ok=True)
    log_file = (output_dir / "backend.log").open("w", encoding="utf-8")
    env = os.environ.copy()
    env.setdefault("QUANT_LAB_LIVE_TRADING_ENABLED", "false")
    env.setdefault("QUANT_LAB_DB_PATH", str(Path("backend/data/quant_lab.sqlite3").resolve()))
    command = [
        backend_python(),
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        host,
        "--port",
        str(port),
    ]
    return subprocess.Popen(
        command,
        cwd="backend",
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
    )


def run_ops_smoke(args: argparse.Namespace, output_dir: Path) -> None:
    command = [
        sys.executable,
        "scripts/ops_smoke_check.py",
        "--api-base",
        args.api_base,
        "--symbol",
        args.symbol.upper(),
        "--wait-seconds",
        str(args.wait_seconds),
        "--output-dir",
        str(output_dir / "ops-smoke"),
    ]
    if args.run_drill:
        command.append("--run-drill")
    subprocess.run(command, check=True)


def stop_backend(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def main() -> int:
    args = parse_args()
    args.symbol = args.symbol.upper()
    if not args.symbol.startswith("KRW-"):
        print("Local smoke symbol must be a KRW-* market.", file=sys.stderr)
        return 2

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    output_dir = Path(args.output_dir) / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    process: subprocess.Popen | None = None
    try:
        if args.start_backend:
            process = start_backend(host=args.host, port=args.port, output_dir=output_dir)
        wait_for_health(args.api_base, args.wait_seconds)
        run_ops_smoke(args, output_dir)
    finally:
        stop_backend(process)

    print(f"Local smoke verification completed: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
