#!/usr/bin/env python3
"""Smoke tests for frontend theme contract checks."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHECK_FRONTEND_THEME = PROJECT_ROOT / "scripts" / "check_frontend_theme.py"


def load_check_frontend_theme():
    spec = importlib.util.spec_from_file_location("check_frontend_theme", CHECK_FRONTEND_THEME)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {CHECK_FRONTEND_THEME}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FrontendThemeCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_check_frontend_theme()

    def test_current_frontend_theme_contract_passes(self) -> None:
        report = self.module.check_frontend_theme(PROJECT_ROOT / "frontend")

        self.assertEqual(report["status"], "pass")
        statuses = {check["id"]: check["status"] for check in report["checks"]}
        self.assertEqual(statuses["theme_dom_sync"], "pass")
        self.assertEqual(statuses["theme_token_parity"], "pass")

    def test_missing_dark_token_fails_parity(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-theme-check-") as tmp:
            frontend = Path(tmp)
            src = frontend / "src"
            src.mkdir()
            (src / "main.tsx").write_text(
                "\n".join(
                    [
                        "const THEME_STORAGE_KEY = 'quant-lab-theme';",
                        "type ThemeMode = 'light' | 'dark';",
                        "function initialThemeMode() {",
                        "window.localStorage.getItem(THEME_STORAGE_KEY);",
                        "window.matchMedia('(prefers-color-scheme: dark)');",
                        "}",
                        "document.documentElement.dataset.theme = theme;",
                        "document.documentElement.style.colorScheme = theme;",
                        "window.localStorage.setItem(THEME_STORAGE_KEY, theme);",
                        'className="theme-toggle"',
                        "setTheme((current) => (current === 'dark' ? 'light' : 'dark'))",
                        "Switch to white theme",
                        "Switch to dark theme",
                        "Moon",
                        "Sun",
                    ]
                ),
                encoding="utf-8",
            )
            light_tokens = "\n".join(f"  {token}: #111;" for token in self.module.REQUIRED_THEME_TOKENS)
            dark_tokens = "\n".join(
                f"  {token}: #eee;"
                for token in self.module.REQUIRED_THEME_TOKENS
                if token != "--shadow"
            )
            (src / "styles.css").write_text(
                "\n".join(
                    [
                        ":root {",
                        "  color-scheme: light;",
                        light_tokens,
                        "}",
                        ':root[data-theme="dark"] {',
                        "  color-scheme: dark;",
                        dark_tokens,
                        "}",
                        ".theme-toggle {",
                        "  background: var(--surface);",
                        "  border-color: var(--border);",
                        "  color: var(--text);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )

            report = self.module.check_frontend_theme(frontend)

        statuses = {check["id"]: check["status"] for check in report["checks"]}
        self.assertEqual(report["status"], "fail")
        self.assertEqual(statuses["dark_theme_tokens"], "fail")
        self.assertEqual(statuses["theme_token_parity"], "fail")


if __name__ == "__main__":
    unittest.main()
