#!/usr/bin/env python3
"""Write or verify SHA-256 checksums for a Quant Lab evidence package."""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.release_artifacts import latest_manifest_package_dir
except ModuleNotFoundError:  # pragma: no cover - supports running from scripts/
    from release_artifacts import latest_manifest_package_dir


CHECKSUM_JSON = "evidence-checksums.json"
CHECKSUM_SHA256 = "evidence-checksums.sha256"
EXCLUDED_PACKAGE_FILES = {CHECKSUM_JSON, CHECKSUM_SHA256}
POST_PACKAGE_ARTIFACTS: tuple[tuple[str, str], ...] = (
    ("release-evidence-check.json", "Release evidence check summary"),
    ("release-warning-triage.md", "Release warning triage Markdown"),
    ("release-warning-triage.json", "Release warning triage JSON"),
    ("release-warning-actions.md", "Release warning action plan Markdown"),
    ("release-warning-actions.json", "Release warning action plan JSON"),
    ("release-warning-operator-checklist.md", "Release warning operator checklist"),
    ("release-status.md", "Release status Markdown"),
    ("release-status.json", "Release status JSON"),
    ("next-release-step.md", "Next release step Markdown"),
    ("next-release-step.json", "Next release step JSON"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write or verify Quant Lab evidence package checksums.")
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
        "--verify",
        action="store_true",
        help="Verify existing evidence-checksums.json instead of rewriting it.",
    )
    parser.add_argument(
        "--no-refresh-tarball",
        action="store_true",
        help="Do not refresh the package tarball after writing checksum files.",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Print the checksum write or verify result as JSON without human-readable lines.",
    )
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_files(package_dir: Path) -> list[Path]:
    files = [
        path
        for path in package_dir.rglob("*")
        if path.is_file() and path.name not in EXCLUDED_PACKAGE_FILES
    ]
    return sorted(files, key=lambda path: path.relative_to(package_dir).as_posix())


def checksum_entries(package_dir: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in package_files(package_dir):
        entries.append(
            {
                "path": path.relative_to(package_dir).as_posix(),
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
        )
    return entries


def refresh_manifest_post_artifacts(package_dir: Path) -> None:
    manifest_path = package_dir / "manifest.json"
    if not manifest_path.is_file():
        return
    manifest = read_json(manifest_path)
    artifacts: list[dict[str, Any]] = []
    for relative_path, description in POST_PACKAGE_ARTIFACTS:
        path = package_dir / relative_path
        if not path.is_file():
            continue
        artifacts.append(
            {
                "path": relative_path,
                "description": description,
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    manifest["post_package_artifacts"] = artifacts
    manifest["post_package_artifact_count"] = len(artifacts)
    manifest["post_package_artifacts_refreshed_at"] = datetime.now(timezone.utc).isoformat()
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_sha256_lines(path: Path, entries: list[dict[str, Any]]) -> None:
    lines = [f"{entry['sha256']}  {entry['path']}" for entry in entries]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def refresh_package_tarball(package_dir: Path) -> Path | None:
    manifest_path = package_dir / "manifest.json"
    if not manifest_path.exists():
        return None
    manifest = read_json(manifest_path)
    tarball = manifest.get("tarball")
    if not isinstance(tarball, str) or not tarball:
        return None
    tarball_path = Path(tarball)
    with tarfile.open(tarball_path, "w:gz") as tar:
        tar.add(package_dir, arcname=package_dir.name)
    return tarball_path


def write_tarball_sidecar(tarball_path: Path | None) -> Path | None:
    if tarball_path is None or not tarball_path.exists():
        return None
    sidecar = tarball_path.with_suffix(tarball_path.suffix + ".sha256")
    sidecar.write_text(f"{sha256_file(tarball_path)}  {tarball_path.name}\n", encoding="utf-8")
    return sidecar


def write_checksums(package_dir: Path, *, refresh_tarball: bool) -> dict[str, Any]:
    refresh_manifest_post_artifacts(package_dir)
    entries = checksum_entries(package_dir)
    checksum_json = package_dir / CHECKSUM_JSON
    checksum_sha256 = package_dir / CHECKSUM_SHA256
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "package_dir": str(package_dir),
        "file_count": len(entries),
        "files": entries,
    }
    checksum_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_sha256_lines(checksum_sha256, entries)
    tarball_path = refresh_package_tarball(package_dir) if refresh_tarball else None
    sidecar = write_tarball_sidecar(tarball_path)
    return {
        "status": "pass",
        "mode": "write",
        "checksum_json": str(checksum_json),
        "checksum_sha256": str(checksum_sha256),
        "tarball": str(tarball_path) if tarball_path else None,
        "tarball_sha256_sidecar": str(sidecar) if sidecar else None,
        "file_count": len(entries),
    }


def verify_checksums(package_dir: Path) -> dict[str, Any]:
    checksum_json = package_dir / CHECKSUM_JSON
    if not checksum_json.is_file():
        return {
            "checksum_json": str(checksum_json),
            "status": "fail",
            "mode": "verify",
            "file_count": 0,
            "failures": [{"path": CHECKSUM_JSON, "reason": "missing"}],
        }
    payload = read_json(checksum_json)
    failures: list[dict[str, Any]] = []
    expected_by_path = {
        str(entry.get("path")): entry.get("sha256")
        for entry in payload.get("files", [])
        if entry.get("path") is not None
    }
    checksum_sha256 = package_dir / CHECKSUM_SHA256
    if not checksum_sha256.is_file():
        failures.append({"path": CHECKSUM_SHA256, "reason": "missing"})
    else:
        listed_by_path: dict[str, str] = {}
        for line in checksum_sha256.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                digest, relative_path = line.split(maxsplit=1)
            except ValueError:
                failures.append({"path": CHECKSUM_SHA256, "reason": "malformed_line", "line": line})
                continue
            listed_by_path[relative_path.strip()] = digest.strip()
        if listed_by_path != expected_by_path:
            failures.append(
                {
                    "path": CHECKSUM_SHA256,
                    "reason": "sha256_list_mismatch",
                    "expected_count": len(expected_by_path),
                    "actual_count": len(listed_by_path),
                }
            )
    for entry in payload.get("files", []):
        relative_path = entry.get("path")
        expected = entry.get("sha256")
        path = package_dir / str(relative_path)
        if not path.is_file():
            failures.append({"path": relative_path, "reason": "missing"})
            continue
        actual = sha256_file(path)
        if actual != expected:
            failures.append({"path": relative_path, "expected": expected, "actual": actual})
    manifest_path = package_dir / "manifest.json"
    if manifest_path.is_file():
        manifest = read_json(manifest_path)
        tarball = manifest.get("tarball")
        if isinstance(tarball, str) and tarball:
            tarball_path = Path(tarball)
            sidecar_path = tarball_path.with_suffix(tarball_path.suffix + ".sha256")
            if not tarball_path.is_file():
                failures.append({"path": str(tarball_path), "reason": "tarball_missing"})
            elif not sidecar_path.is_file():
                failures.append({"path": str(sidecar_path), "reason": "tarball_sha256_sidecar_missing"})
            else:
                line = sidecar_path.read_text(encoding="utf-8").strip()
                try:
                    expected_tarball, listed_name = line.split(maxsplit=1)
                except ValueError:
                    failures.append({"path": str(sidecar_path), "reason": "tarball_sha256_malformed"})
                else:
                    actual_tarball = sha256_file(tarball_path)
                    if actual_tarball != expected_tarball:
                        failures.append(
                            {
                                "path": str(tarball_path),
                                "expected": expected_tarball,
                                "actual": actual_tarball,
                            }
                        )
                    if listed_name.strip() != tarball_path.name:
                        failures.append(
                            {
                                "path": str(sidecar_path),
                                "reason": "tarball_name_mismatch",
                                "expected": tarball_path.name,
                                "actual": listed_name.strip(),
                            }
                        )
    return {
        "checksum_json": str(checksum_json),
        "status": "fail" if failures else "pass",
        "mode": "verify",
        "file_count": len(payload.get("files", [])),
        "failures": failures,
    }


def main() -> int:
    args = parse_args()
    package_dir = Path(args.package_dir) if args.package_dir else latest_manifest_package_dir(Path(args.packages_dir))
    package_dir = package_dir.absolute()
    if args.verify:
        result = verify_checksums(package_dir)
        if args.json_only:
            print(json.dumps(result, indent=2, sort_keys=True))
            return 1 if result["status"] == "fail" else 0
        print(f"Checksum verification: {result['status']}")
        print(f"Checksum file: {result['checksum_json']}")
        if result["failures"]:
            for failure in result["failures"]:
                print(f"FAIL {failure}")
        return 1 if result["status"] == "fail" else 0

    result = write_checksums(package_dir, refresh_tarball=not args.no_refresh_tarball)
    if args.json_only:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    print(f"Checksums: {result['checksum_json']}")
    print(f"SHA256 list: {result['checksum_sha256']}")
    if result["tarball_sha256_sidecar"]:
        print(f"Tarball SHA256: {result['tarball_sha256_sidecar']}")
    print(f"Checksum files covered: {result['file_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
