#!/usr/bin/env python3
"""Run Quant Lab operational smoke checks against a running backend."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CHECKS: tuple[tuple[str, str], ...] = (
    ("health", "/api/health"),
    ("ops_self_check", "/api/ops/self-check"),
    ("execution_settings", "/api/execution/settings"),
    ("live_readiness", "/api/readiness/live"),
    ("cutover_checklist", "/api/execution/cutover-checklist"),
    ("post_cutover_monitor", "/api/execution/post-cutover-monitor"),
    ("broker_readiness", "/api/execution/broker-readiness"),
    ("alert_review", "/api/alerts/review"),
    ("strategy_health", "/api/research/strategy-health/traces?limit=5"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Quant Lab ops smoke checks.")
    parser.add_argument("--api-base", default="http://localhost:8000", help="Backend base URL")
    parser.add_argument("--symbol", default="KRW-BTC", help="KRW crypto drill symbol")
    parser.add_argument("--wait-seconds", type=int, default=30, help="Seconds to wait for /api/health")
    parser.add_argument(
        "--run-drill",
        action="store_true",
        help="Run scripts/seed_crypto_drill.py and verify exported drill artifacts",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/ops-smoke",
        help="Directory for smoke-check JSON output",
    )
    return parser.parse_args()


def request_json(api_base: str, path: str) -> Any:
    url = api_base.rstrip("/") + path
    request = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GET {url} failed with {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GET {url} failed: {exc.reason}") from exc
    return json.loads(body) if body else None


def wait_for_health(api_base: str, wait_seconds: int) -> dict[str, Any]:
    deadline = time.time() + wait_seconds
    last_error = ""
    while time.time() <= deadline:
        try:
            health = request_json(api_base, "/api/health")
            if isinstance(health, dict):
                return health
        except RuntimeError as exc:
            last_error = str(exc)
        time.sleep(1)
    raise RuntimeError(f"Backend did not become healthy within {wait_seconds}s. {last_error}")


def safe_filename(label: str) -> str:
    return label.replace("/", "-").replace("?", "-").replace("&", "-")


def run_seeded_drill(
    *,
    api_base: str,
    symbol: str,
    output_dir: Path,
) -> dict[str, Any]:
    drill_dir = output_dir / "seeded-drill"
    command = [
        sys.executable,
        "scripts/seed_crypto_drill.py",
        "--api-base",
        api_base,
        "--symbol",
        symbol,
        "--output-dir",
        str(drill_dir),
    ]
    completed = subprocess.run(command, check=True, text=True, capture_output=True)
    generated_dirs = sorted(drill_dir.glob(f"{symbol.lower()}-*"))
    latest_dir = generated_dirs[-1] if generated_dirs else None
    markdown_files = list(latest_dir.glob("*.md")) if latest_dir else []
    json_files = list(latest_dir.glob("*.json")) if latest_dir else []
    if latest_dir is None or not markdown_files or not json_files:
        raise RuntimeError("Seeded drill completed but expected JSON/Markdown artifacts were missing.")
    return {
        "command": command,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "artifact_dir": str(latest_dir),
        "markdown_files": [str(path) for path in markdown_files],
        "json_files": [str(path) for path in json_files],
    }


def main() -> int:
    args = parse_args()
    args.symbol = args.symbol.upper()
    if not args.symbol.startswith("KRW-"):
        print("Ops smoke check drill symbol must be a KRW-* market.", file=sys.stderr)
        return 2

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    output_dir = Path(args.output_dir) / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "api_base": args.api_base,
        "symbol": args.symbol,
        "checks": {},
    }
    results["checks"]["health"] = wait_for_health(args.api_base, args.wait_seconds)

    for label, path in CHECKS:
        payload = request_json(args.api_base, path)
        results["checks"][label] = payload
        (output_dir / f"{safe_filename(label)}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    drill_path = (
        "/api/research/crypto-live-beta-drill/report?"
        + urllib.parse.urlencode({"symbol": args.symbol, "limit": 5})
    )
    drill_report = request_json(args.api_base, drill_path)
    results["checks"]["crypto_live_beta_drill"] = drill_report
    (output_dir / "crypto-live-beta-drill.md").write_text(
        drill_report.get("markdown", ""),
        encoding="utf-8",
    )
    (output_dir / "crypto-live-beta-drill.json").write_text(
        json.dumps(drill_report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if args.run_drill:
        results["seeded_drill"] = run_seeded_drill(
            api_base=args.api_base,
            symbol=args.symbol,
            output_dir=output_dir,
        )

    (output_dir / "ops-smoke-summary.json").write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Ops smoke checks passed: {output_dir}")
    if args.run_drill:
        print(f"Seeded drill artifacts: {results['seeded_drill']['artifact_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
