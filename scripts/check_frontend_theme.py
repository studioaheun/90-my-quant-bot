#!/usr/bin/env python3
"""Validate the frontend light/dark theme contract."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


REQUIRED_THEME_TOKENS: tuple[str, ...] = (
    "--app-bg",
    "--surface",
    "--surface-soft",
    "--surface-muted",
    "--border",
    "--text",
    "--body-text",
    "--muted",
    "--accent",
    "--accent-solid",
    "--accent-soft",
    "--warn",
    "--danger",
    "--shadow",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Quant Lab frontend theme implementation.")
    parser.add_argument(
        "--frontend-dir",
        default="frontend",
        help="Frontend project directory.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print a JSON report instead of human-readable checks.",
    )
    return parser.parse_args()


def read_file(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"Required frontend file is missing: {path}")
    return path.read_text(encoding="utf-8")


def css_block(css: str, selector: str) -> str:
    start = css.find(selector)
    if start == -1:
        return ""
    brace_start = css.find("{", start)
    if brace_start == -1:
        return ""
    depth = 0
    for index in range(brace_start, len(css)):
        char = css[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return css[brace_start + 1 : index]
    return ""


def css_tokens(block: str) -> dict[str, str]:
    return {
        f"--{name}": value.strip()
        for name, value in re.findall(r"--([a-z0-9-]+)\s*:\s*([^;]+);", block)
    }


def status_for(condition: bool) -> str:
    return "pass" if condition else "fail"


def theme_check(check_id: str, condition: bool, message: str) -> dict[str, str]:
    return {"id": check_id, "status": status_for(condition), "message": message}


def check_frontend_theme(frontend_dir: Path) -> dict[str, Any]:
    main_path = frontend_dir / "src" / "main.tsx"
    css_path = frontend_dir / "src" / "styles.css"
    main = read_file(main_path)
    css = read_file(css_path)
    light_block = css_block(css, ":root")
    dark_block = css_block(css, ':root[data-theme="dark"]')
    light_tokens = css_tokens(light_block)
    dark_tokens = css_tokens(dark_block)
    missing_light = [token for token in REQUIRED_THEME_TOKENS if token not in light_tokens]
    missing_dark = [token for token in REQUIRED_THEME_TOKENS if token not in dark_tokens]
    parity_missing = sorted(token for token in light_tokens if token.startswith("--") and token not in dark_tokens)
    has_theme_toggle_labels = (
        ("Switch to white theme" in main and "Switch to dark theme" in main)
        or ("라이트 테마로 전환" in main and "다크 테마로 전환" in main)
    )

    checks = [
        theme_check(
            "theme_storage_key",
            "THEME_STORAGE_KEY = 'quant-lab-theme'" in main,
            "Theme preference uses the documented localStorage key.",
        ),
        theme_check(
            "theme_mode_type",
            "type ThemeMode = 'light' | 'dark'" in main,
            "Theme mode is restricted to light and dark.",
        ),
        theme_check(
            "theme_initialization",
            (
                "initialThemeMode()" in main
                and "window.localStorage.getItem(THEME_STORAGE_KEY)" in main
                and "prefers-color-scheme: dark" in main
            ),
            "Initial theme reads persisted preference and falls back to system preference.",
        ),
        theme_check(
            "theme_dom_sync",
            (
                "document.documentElement.dataset.theme = theme" in main
                and "document.documentElement.style.colorScheme = theme" in main
                and "window.localStorage.setItem(THEME_STORAGE_KEY, theme)" in main
            ),
            "Selected theme is synchronized to DOM data-theme, color-scheme, and localStorage.",
        ),
        theme_check(
            "theme_toggle_control",
            (
                'className="theme-toggle"' in main
                and "setTheme((current) => (current === 'dark' ? 'light' : 'dark'))" in main
                and has_theme_toggle_labels
            ),
            "Topbar exposes a labelled dark/white theme toggle.",
        ),
        theme_check(
            "theme_icons",
            "Moon" in main and "Sun" in main,
            "Theme toggle uses explicit moon/sun icons.",
        ),
        theme_check(
            "light_theme_tokens",
            "color-scheme: light" in light_block and not missing_light,
            (
                "Light theme defines required CSS tokens."
                if not missing_light
                else "Light theme is missing tokens: " + ", ".join(missing_light)
            ),
        ),
        theme_check(
            "dark_theme_tokens",
            "color-scheme: dark" in dark_block and not missing_dark,
            (
                "Dark theme defines required CSS tokens."
                if not missing_dark
                else "Dark theme is missing tokens: " + ", ".join(missing_dark)
            ),
        ),
        theme_check(
            "theme_token_parity",
            not parity_missing,
            (
                "Dark theme covers all light theme CSS variables."
                if not parity_missing
                else "Dark theme is missing light tokens: " + ", ".join(parity_missing)
            ),
        ),
        theme_check(
            "theme_toggle_uses_tokens",
            (
                ".theme-toggle" in css
                and "background: var(--surface)" in css
                and "border-color: var(--border)" in css
                and "color: var(--text)" in css
            ),
            "Theme toggle styling is token-driven.",
        ),
    ]
    status = "pass" if all(check["status"] == "pass" for check in checks) else "fail"
    return {
        "status": status,
        "frontend_dir": str(frontend_dir),
        "checks": checks,
    }


def main() -> int:
    args = parse_args()
    report = check_frontend_theme(Path(args.frontend_dir))
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        for check in report["checks"]:
            print(f"{check['status'].upper():5} {check['id']}: {check['message']}")
        print(f"Frontend theme check: {report['status']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
