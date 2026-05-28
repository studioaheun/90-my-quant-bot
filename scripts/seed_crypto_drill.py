#!/usr/bin/env python3
"""Create a KRW crypto paper-to-dry-run drill and export evidence.

The script talks to a running Quant Lab backend over HTTP. It does not set live
trading flags, submit live orders, or require private exchange credentials.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed and export a crypto live beta drill.")
    parser.add_argument("--api-base", default="http://localhost:8000", help="Backend base URL")
    parser.add_argument("--symbol", default="KRW-BTC", help="KRW crypto market to drill")
    parser.add_argument("--timeframe", default="day", help="Paper session timeframe")
    parser.add_argument("--strategy", default="sma_crossover", help="Paper strategy")
    parser.add_argument("--initial-cash", type=float, default=1_000_000, help="Starting KRW cash")
    parser.add_argument("--candle-limit", type=int, default=180, help="Paper session candle limit")
    parser.add_argument("--max-intents", type=int, default=2, help="Dry-run intents to queue")
    parser.add_argument(
        "--output-dir",
        default="artifacts/crypto-drills",
        help="Directory for JSON and Markdown evidence",
    )
    return parser.parse_args()


def request_json(
    *,
    api_base: str,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> Any:
    url = api_base.rstrip("/") + path
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed with {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc.reason}") from exc
    return json.loads(body) if body else None


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def paper_session_payload(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "symbol": args.symbol.upper(),
        "timeframe": args.timeframe,
        "source": "sample",
        "strategy": args.strategy,
        "initial_cash": args.initial_cash,
        "fee_bps": 5,
        "slippage_bps": 2,
        "candle_limit": args.candle_limit,
        "params": {"fast_window": 10, "slow_window": 30},
        "risk_limits": {
            "max_position_pct": 50,
            "max_order_notional": 500_000,
            "max_orders": 20,
            "max_session_loss_pct": 12,
            "kill_switch": False,
        },
    }


def main() -> int:
    args = parse_args()
    args.symbol = args.symbol.upper()
    if not args.symbol.startswith("KRW-"):
        print("Seeded crypto drill requires a KRW-* market.", file=sys.stderr)
        return 2

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    output_dir = Path(args.output_dir) / f"{args.symbol.lower()}-{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    health = request_json(api_base=args.api_base, method="GET", path="/api/health")
    session = request_json(
        api_base=args.api_base,
        method="POST",
        path="/api/paper/sessions",
        payload=paper_session_payload(args),
    )
    queue = request_json(
        api_base=args.api_base,
        method="POST",
        path=f"/api/paper/sessions/{urllib.parse.quote(session['id'])}/order-intents",
        payload={"max_intents": args.max_intents},
    )

    runbooks: list[dict[str, Any]] = []
    for record in queue.get("records", []):
        runbook = request_json(
            api_base=args.api_base,
            method="GET",
            path=f"/api/execution/order-audits/{urllib.parse.quote(record['id'])}/runbook",
        )
        runbooks.append(runbook)
        (output_dir / runbook["filename"]).write_text(runbook["markdown"], encoding="utf-8")

    drill_report = request_json(
        api_base=args.api_base,
        method="GET",
        path=(
            "/api/research/crypto-live-beta-drill/report?"
            + urllib.parse.urlencode({"symbol": args.symbol, "limit": 5})
        ),
    )

    write_json(output_dir / "health.json", health)
    write_json(output_dir / "paper-session.json", session)
    write_json(output_dir / "dry-run-queue.json", queue)
    write_json(output_dir / "runbooks.json", runbooks)
    write_json(output_dir / "crypto-live-beta-drill.json", drill_report)
    (output_dir / drill_report["filename"]).write_text(drill_report["markdown"], encoding="utf-8")

    print(f"Created paper session: {session['id']}")
    print(f"Queued dry-run intents: {queue.get('created', 0)}")
    print(f"Exported drill evidence: {output_dir}")
    print("Live routing remains controlled by backend environment gates; this script does not change them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
