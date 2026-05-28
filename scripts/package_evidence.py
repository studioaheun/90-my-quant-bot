#!/usr/bin/env python3
"""Package Quant Lab verification and operator evidence for review."""

from __future__ import annotations

import argparse
import glob
import json
import re
import shutil
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.release_artifacts import latest_artifact_path, latest_json_artifact
    from scripts.release_manifest import EVIDENCE_RUNBOOK_FILES
except ModuleNotFoundError:  # pragma: no cover - supports running from scripts/
    from release_artifacts import latest_artifact_path, latest_json_artifact
    from release_manifest import EVIDENCE_RUNBOOK_FILES


RUNBOOK_FILES = EVIDENCE_RUNBOOK_FILES


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Package Quant Lab review evidence.")
    parser.add_argument("--symbol", default="KRW-BTC", help="Target market symbol")
    parser.add_argument(
        "--project-root",
        default=".",
        help="Quant Lab project root containing artifacts/, docs/, and scripts/",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/evidence-packages",
        help="Directory where evidence packages are created",
    )
    parser.add_argument(
        "--tar",
        action="store_true",
        help="Also create a .tgz archive next to the package directory",
    )
    return parser.parse_args()


def market_slug(symbol: str) -> str:
    cleaned = re.sub(r"[^A-Z0-9-]+", "-", symbol.upper().replace("/", "-"))
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return cleaned or "MARKET"


def artifact_slug(symbol: str) -> str:
    return market_slug(symbol).lower()


def latest_path(pattern: str, *, dirs: bool = False) -> Path | None:
    paths = [Path(path) for path in glob.glob(pattern) if Path(path).is_dir() == dirs]
    return latest_artifact_path(paths)


def next_package_dir(output_dir: Path, symbol: str) -> Path:
    date_prefix = datetime.now().strftime("%Y%m%d")
    base_name = f"{date_prefix}-{market_slug(symbol)}-beta"
    for sequence in range(1, 1000):
        candidate = output_dir / f"{base_name}-{sequence:03d}"
        tar_candidate = candidate.with_suffix(".tgz")
        if not candidate.exists() and not tar_candidate.exists():
            return candidate
    raise RuntimeError(f"No available package sequence under {output_dir}")


def copy_evidence(
    *,
    source: Path,
    target: Path,
    label: str,
    included: list[dict[str, Any]],
) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, target)
        kind = "directory"
    else:
        shutil.copy2(source, target)
        kind = "file"
    included.append(
        {
            "label": label,
            "kind": kind,
            "source": str(source),
            "target": str(target),
        }
    )


def collect_latest_artifacts(
    *,
    root: Path,
    package_dir: Path,
    symbol: str,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    included: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []
    symbol_lower = artifact_slug(symbol)

    specs: tuple[tuple[str, tuple[str, ...], str, bool], ...] = (
        (
            "external_readiness",
            ("artifacts/external-readiness/*",),
            "00-external-readiness",
            True,
        ),
        (
            "verification_summary",
            ("artifacts/verification/verification-*.json",),
            "01-verification",
            False,
        ),
        (
            "ops_smoke_check",
            (
                "artifacts/ops-smoke/*",
                "artifacts/local-smoke/*/ops-smoke/*",
            ),
            "02-ops-smoke",
            True,
        ),
        (
            "crypto_live_beta_drill",
            (
                f"artifacts/crypto-drills/{symbol_lower}-*",
                f"artifacts/local-smoke/*/ops-smoke/*/seeded-drill/{symbol_lower}-*",
            ),
            "03-crypto-drill",
            True,
        ),
        (
            "local_smoke_check",
            ("artifacts/local-smoke/*",),
            "04-local-smoke",
            True,
        ),
        (
            "live_beta_archive",
            ("artifacts/live-beta/*",),
            "05-live-beta",
            True,
        ),
    )

    for label, patterns, section, is_dir in specs:
        candidates = [
            path
            for pattern in patterns
            if (path := latest_path(str(root / pattern), dirs=is_dir)) is not None
        ]
        path = latest_artifact_path(candidates)
        if path is None:
            missing.append({"label": label, "pattern": " OR ".join(patterns)})
            continue
        copy_evidence(
            source=path,
            target=package_dir / section / path.name,
            label=label,
            included=included,
        )

    docs_dir = package_dir / "06-runbooks-and-docs"
    for relative_path in RUNBOOK_FILES:
        source = root / relative_path
        if not source.exists():
            missing.append({"label": "runbook_or_doc", "pattern": relative_path})
            continue
        copy_evidence(
            source=source,
            target=docs_dir / relative_path,
            label="runbook_or_doc",
            included=included,
        )

    return included, missing


def read_latest_verification_status(package_dir: Path) -> str | None:
    verification_file = latest_json_artifact((package_dir / "01-verification").glob("verification-*.json"))
    if verification_file is None:
        return None
    try:
        payload = json.loads(verification_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "unreadable"
    status = payload.get("status")
    return status if isinstance(status, str) else None


def write_package_readme(
    *,
    package_dir: Path,
    manifest: dict[str, Any],
) -> None:
    lines = [
        "# Quant Lab Evidence Package",
        "",
        f"Generated at: {manifest['generated_at']}",
        f"Symbol: {manifest['symbol']}",
        f"Package: {manifest['package_name']}",
        f"Latest verification status: {manifest.get('latest_verification_status') or 'not included'}",
        "",
        "## Contents",
        "",
    ]
    for item in manifest["included"]:
        lines.append(f"- {item['label']}: `{item['target']}`")
    if manifest["missing"]:
        lines.extend(["", "## Missing Optional Evidence", ""])
        for item in manifest["missing"]:
            lines.append(f"- {item['label']}: `{item['pattern']}`")
    lines.extend(
        [
            "",
            "## Safety Notes",
            "",
            "- This package is an evidence bundle only. It does not enable live trading.",
            "- `.env` is intentionally excluded because it may contain secrets.",
            "- Live crypto orders remain locked unless the backend live flags, ACK, credentials, operator decisions, and per-order confirmation are all present.",
            "- Stock/ETF routing remains paper-only in the current project scope.",
            "",
            "## Recommended Review Order",
            "",
            "1. Open `01-verification/` and confirm the latest verification status.",
            "2. Review `00-external-readiness/` and separate local machine gaps from application failures.",
            "3. Review `02-ops-smoke/` and `03-crypto-drill/` if they are present.",
            "4. Review `release-status.md` and `next-release-step.md` if the release gate generated them.",
            "5. Create or review the connected-runner handoff bundle if no git remote is available.",
            "6. Verify `evidence-checksums.json`, `evidence-checksums.sha256`, the evidence `.tgz.sha256` sidecar, `manifest.json` post-package artifact inventory, and any connected-runner `.tgz.verification.json` report if present.",
            "7. Review `release-evidence-check.json`, `release-warning-triage.md`, `release-warning-actions.md`, and `release-warning-operator-checklist.md` if they are present; after checksums are published, use `scripts/review_release_warnings.py --no-write` for command-line review.",
            "8. Review `06-runbooks-and-docs/docs/release-readiness.md`.",
            "9. Confirm live flags are locked before any live-beta preparation.",
            "",
        ]
    )
    (package_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def create_tarball(package_dir: Path) -> Path:
    tar_path = package_dir.with_suffix(".tgz")
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(package_dir, arcname=package_dir.name)
    return tar_path


def main() -> int:
    args = parse_args()
    root = Path(args.project_root).absolute()
    output_dir = (root / args.output_dir).absolute()
    output_dir.mkdir(parents=True, exist_ok=True)

    package_dir = next_package_dir(output_dir, args.symbol).absolute()
    package_dir.mkdir(parents=True, exist_ok=False)

    included, missing = collect_latest_artifacts(
        root=root,
        package_dir=package_dir,
        symbol=args.symbol,
    )
    manifest: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "symbol": args.symbol.upper(),
        "package_name": package_dir.name,
        "package_dir": str(package_dir),
        "tarball": None,
        "included": included,
        "missing": missing,
        "latest_verification_status": read_latest_verification_status(package_dir),
        "safety": {
            "env_file_excluded": True,
            "live_trading_enabled_by_script": False,
            "stock_etf_live_routing_enabled": False,
        },
    }

    if args.tar:
        manifest["tarball"] = str(package_dir.with_suffix(".tgz"))

    (package_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_package_readme(package_dir=package_dir, manifest=manifest)

    if args.tar:
        create_tarball(package_dir)

    print(f"Evidence package: {package_dir}")
    if manifest["tarball"]:
        print(f"Tarball: {manifest['tarball']}")
    if missing:
        print(f"Missing optional evidence: {len(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
