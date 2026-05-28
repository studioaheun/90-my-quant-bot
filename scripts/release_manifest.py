"""Shared file manifests for release evidence and handoff packaging."""

from __future__ import annotations


CORE_RELEASE_SCRIPT_FILES: tuple[str, ...] = (
    "scripts/archive_live_beta_closeout.py",
    "scripts/test_archive_live_beta_closeout.py",
    "scripts/check_completion_audit.py",
    "scripts/test_check_completion_audit.py",
    "scripts/check_frontend_theme.py",
    "scripts/test_check_frontend_theme.py",
    "scripts/connected_runner_acceptance.py",
    "scripts/test_connected_runner_acceptance.py",
    "scripts/check_external_readiness.py",
    "scripts/test_check_external_readiness.py",
    "scripts/package_evidence.py",
    "scripts/test_package_evidence.py",
    "scripts/check_release_evidence.py",
    "scripts/test_check_release_evidence.py",
    "scripts/package_connected_runner_handoff.py",
    "scripts/test_package_connected_runner_handoff.py",
    "scripts/release_gate.py",
    "scripts/test_release_gate.py",
    "scripts/next_release_step.py",
    "scripts/report_release_status.py",
    "scripts/test_report_release_status.py",
    "scripts/review_release_warnings.py",
    "scripts/test_review_release_warnings.py",
    "scripts/test_next_release_step.py",
    "scripts/handoff_commands.py",
    "scripts/connected_runner_contract.py",
    "scripts/test_connected_runner_contract.py",
    "scripts/release_manifest.py",
    "scripts/test_release_manifest.py",
    "scripts/release_artifacts.py",
    "scripts/test_release_artifacts.py",
    "scripts/verify_project.py",
    "scripts/run_local_smoke.py",
    "scripts/ops_smoke_check.py",
    "scripts/seed_crypto_drill.py",
    "scripts/write_evidence_checksums.py",
    "scripts/test_write_evidence_checksums.py",
)

REQUIRED_EVIDENCE_DOC_FILES: tuple[str, ...] = (
    "docs/quant-lab-guide.md",
    "docs/deployment-hardening.md",
    "docs/production-observability.md",
    "docs/release-readiness.md",
    "docs/completion-audit.md",
)

EXTRA_RUNBOOK_DOC_FILES: tuple[str, ...] = (
    "docs/quant-trading-proposal.md",
    "docs/upbit-private-setup.md",
    "docs/stock-etf-data-setup.md",
    "docs/mvp-implementation-notes.md",
)

EVIDENCE_RUNBOOK_FILES: tuple[str, ...] = (
    "README.md",
    ".env.example",
    ".github/workflows/quant-lab-ci.yml",
    *CORE_RELEASE_SCRIPT_FILES,
    *REQUIRED_EVIDENCE_DOC_FILES,
    *EXTRA_RUNBOOK_DOC_FILES,
)

REQUIRED_EVIDENCE_DOC_SUFFIXES: tuple[str, ...] = (
    "README.md",
    ".env.example",
    ".github/workflows/quant-lab-ci.yml",
    *CORE_RELEASE_SCRIPT_FILES,
    *REQUIRED_EVIDENCE_DOC_FILES,
)

HANDOFF_REQUIRED_SOURCE_FILES: tuple[str, ...] = (
    "README.md",
    ".env.example",
    "docker-compose.yml",
    ".github/workflows/quant-lab-ci.yml",
    "backend/pyproject.toml",
    "frontend/package.json",
    *CORE_RELEASE_SCRIPT_FILES,
)
