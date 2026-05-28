#!/usr/bin/env python3
"""Shared helpers for selecting Quant Lab release artifacts."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


PACKAGE_NAME_RE = re.compile(r"^(?P<date>\d{8})-(?P<market>.+)-beta-(?P<sequence>\d+)$")
PATH_TIMESTAMP_RE = re.compile(r"(?P<date>\d{8})-(?P<time>\d{6})")


def read_json_or_none(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def parse_artifact_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def metadata_generated_at(package_dir: Path, metadata_files: Iterable[str]) -> datetime | None:
    for relative_path in metadata_files:
        payload = read_json_or_none(package_dir / relative_path)
        if not isinstance(payload, dict):
            continue
        generated_at = parse_artifact_timestamp(payload.get("generated_at"))
        if generated_at is not None:
            return generated_at
    return None


def package_name_key(package_dir: Path) -> tuple[str, int]:
    match = PACKAGE_NAME_RE.match(package_dir.name)
    if not match:
        return ("", -1)
    return (match.group("date"), int(match.group("sequence")))


def path_timestamp(path: Path) -> datetime | None:
    for part in (path.stem, path.name, *(parent.name for parent in path.parents)):
        match = PATH_TIMESTAMP_RE.search(part)
        if not match:
            continue
        try:
            return datetime.strptime(
                match.group("date") + match.group("time"),
                "%Y%m%d%H%M%S",
            ).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def package_sort_key(
    package_dir: Path,
    *,
    metadata_files: Iterable[str] = ("manifest.json",),
) -> tuple[int, float, str, int, str, float]:
    generated_at = metadata_generated_at(package_dir, metadata_files)
    generated_timestamp = generated_at.timestamp() if generated_at else 0.0
    name_date, sequence = package_name_key(package_dir)
    try:
        mtime = package_dir.stat().st_mtime
    except OSError:
        mtime = 0.0
    return (
        1 if generated_at else 0,
        generated_timestamp,
        name_date,
        sequence,
        package_dir.name,
        mtime,
    )


def latest_package_candidate(
    candidates: Iterable[Path],
    *,
    metadata_files: Iterable[str] = ("manifest.json",),
) -> Path | None:
    package_dirs = list(candidates)
    if not package_dirs:
        return None
    return max(package_dirs, key=lambda path: package_sort_key(path, metadata_files=metadata_files))


def latest_package_dir(
    packages_dir: Path,
    *,
    marker_file: str = "manifest.json",
    metadata_files: Iterable[str] = ("manifest.json",),
) -> Path:
    candidates = [path for path in packages_dir.glob("*") if (path / marker_file).is_file()]
    latest = latest_package_candidate(candidates, metadata_files=metadata_files)
    if latest is None:
        raise FileNotFoundError(f"No evidence packages with {marker_file} under {packages_dir}")
    return latest


def latest_manifest_package_dir(packages_dir: Path) -> Path:
    return latest_package_dir(packages_dir, marker_file="manifest.json")


def latest_release_status_package_dir(packages_dir: Path) -> Path:
    return latest_package_dir(
        packages_dir,
        marker_file="release-status.json",
        metadata_files=("manifest.json", "release-status.json"),
    )


def latest_warning_triage_package_dir(packages_dir: Path) -> Path:
    return latest_package_dir(
        packages_dir,
        marker_file="release-warning-triage.json",
        metadata_files=("manifest.json", "release-warning-triage.json"),
    )


def json_artifact_sort_key(path: Path) -> tuple[int, float, int, float, str, float]:
    payload = read_json_or_none(path)
    generated_at = parse_artifact_timestamp(payload.get("generated_at")) if isinstance(payload, dict) else None
    path_time = path_timestamp(path)
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0
    return (
        1 if generated_at else 0,
        generated_at.timestamp() if generated_at else 0.0,
        1 if path_time else 0,
        path_time.timestamp() if path_time else 0.0,
        path.as_posix(),
        mtime,
    )


def latest_json_artifact(candidates: Iterable[Path]) -> Path | None:
    paths = [path for path in candidates if path.is_file()]
    if not paths:
        return None
    return max(paths, key=json_artifact_sort_key)


def latest_json_file(root: Path, pattern: str) -> Path | None:
    return latest_json_artifact(root.glob(pattern))


def artifact_generated_at(path: Path) -> datetime | None:
    if path.is_file():
        payload = read_json_or_none(path) if path.suffix == ".json" else None
        if isinstance(payload, dict):
            return parse_artifact_timestamp(payload.get("generated_at"))
        return None
    if not path.is_dir():
        return None

    generated_times: list[datetime] = []
    for child in path.glob("*.json"):
        payload = read_json_or_none(child)
        if not isinstance(payload, dict):
            continue
        generated_at = parse_artifact_timestamp(payload.get("generated_at"))
        if generated_at is not None:
            generated_times.append(generated_at)
    return max(generated_times) if generated_times else None


def artifact_sort_key(path: Path) -> tuple[int, float, int, float, str, int, str, float]:
    generated_at = artifact_generated_at(path)
    path_time = path_timestamp(path)
    name_date, sequence = package_name_key(path)
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0
    return (
        1 if generated_at else 0,
        generated_at.timestamp() if generated_at else 0.0,
        1 if path_time else 0,
        path_time.timestamp() if path_time else 0.0,
        name_date,
        sequence,
        path.as_posix(),
        mtime,
    )


def latest_artifact_path(candidates: Iterable[Path]) -> Path | None:
    paths = list(candidates)
    if not paths:
        return None
    return max(paths, key=artifact_sort_key)
