# Verification And Release Readiness

Use this checklist before handing Quant Lab to an operator for live-beta review.

## Verification Command

Run the bundled release gate:

```bash
python3 scripts/release_gate.py --run-smoke
```

If Docker is not installed on the machine:

```bash
python3 scripts/release_gate.py --skip-docker --run-smoke
```

On a connected runner or Docker-enabled handoff machine, make external prerequisites blocking:

```bash
python3 scripts/release_gate.py --run-smoke --strict-external --check-gh-auth
```

The release gate runs:

- `scripts/verify_project.py`.
- `scripts/check_external_readiness.py`.
- Optional managed local smoke drill when `--run-smoke` is provided.
- `scripts/package_evidence.py --symbol KRW-BTC --tar`.
- `scripts/check_release_evidence.py`.
- `scripts/package_connected_runner_handoff.py`.
- `scripts/report_release_status.py`.
- `scripts/next_release_step.py`.
- `scripts/write_evidence_checksums.py`.
- `scripts/connected_runner_acceptance.py`.
- `scripts/archive_live_beta_closeout.py`.
- A compact JSON summary under `artifacts/release-gate/`.

The verification step checks:

- Python script compilation.
- Next-release-step CLI smoke coverage for repo URL substitution, owner counts, and sequence output.
- Backend unit tests.
- Frontend TypeScript and Vite production build.
- Docker Compose config when Docker is available.
- Backend ops self-check coverage through the unit test suite.

It writes a timestamped JSON summary under `artifacts/verification/`.

Run the verification bundle by itself rather than in parallel with another full backend test run; several tests intentionally exercise shared SQLite/DuckDB cache paths and process environment variables.

## Evidence Package Command

After verification, package the latest available review evidence:

```bash
python3 scripts/release_gate.py --skip-docker --run-smoke
```

Or run the lower-level package/check commands directly:

```bash
python3 scripts/package_evidence.py --symbol KRW-BTC --tar
python3 scripts/check_release_evidence.py
```

The package command writes a timestamped package under `artifacts/evidence-packages/` and, with `--tar`, a sibling `.tgz` archive. It includes available verification summaries, ops smoke checks, crypto drill artifacts, local smoke checks, live-beta archives, runbooks, project docs, a manifest, and a package README. Missing smoke or drill artifacts are reported as optional gaps so the package can still be created before a running-backend smoke check exists. The packaging step and follow-up commands select source artifacts, evidence packages, release-gate summaries, and external-readiness JSON by generated metadata and timestamped artifact names first, with directory modification time only as a final fallback.

The check command writes `release-evidence-check.json`, `release-warning-triage.json`, and `release-warning-triage.md` inside the latest package and refreshes the package tarball when one exists. Use `python3 scripts/check_release_evidence.py --package-dir PATH --no-write` after checksums are published when you need read-only review output that does not rewrite check/triage files or the tarball, or `--json-only` when automation needs the same evidence-check payload as JSON. It fails on missing required evidence, failed verification, unsafe live-lock evidence, missing smoke/drill files, blocking halt/error alerts, or unsafe generated handoff commands such as backup-reference placeholders, shell-unsafe repo URL placeholders, missing `report_release_status.py --json-only` automation, missing `check_release_evidence.py --json-only` automation, missing `write_evidence_checksums.py --verify --json-only` automation, missing external-readiness summary/strict summary JSON automation, missing live-beta `--preflight --json` automation, missing live-beta recommended-next command automation, missing live-beta backend start or health-check support commands, repo-url-from-env automation without `--fail-if-repo-url-required`, missing `--command-sequence-only` automation for command-only handoffs, missing repo URL export examples, warning `--apply` commands without `--operator-approved`, warning JSON or compact summary automation without `--fail-if-action-needed`, missing warning review artifact path automation, missing warning recommended-next command automation, missing warning recommended-next command gate, local-readiness JSON/command-only automation without `--fail-if-local-readiness-not-pass`, or missing local-readiness setup/setup-and-verify sequence automation. It returns warning status for review items such as warning-level alerts, missing external validation, or a missing live-beta archive outside an actual live window, and the triage report lists alert IDs plus recommended operator actions. The release gate also writes `release-warning-actions.md` in dry-run mode, `release-warning-operator-checklist.md` for the human decision path, `release-status.md` as a compact handoff summary with the approximate completion percentage, remaining handoff items by owner, exact local/connected-runner/warning-review/live-beta closeout commands, connected-runner bundle paths, first preflight/full-flow connected-runner commands, `next-release-step.md` as the nearest single command to run, remediation/final-verify commands for external gaps, checksum files for package integrity, and a connected-runner handoff bundle under `artifacts/handoff-bundles/`; command-safety checks are marked skipped before these artifacts exist, then the gate reruns the evidence check after they are generated so command safety is locked before checksums are written. After checksums are published, use `python3 scripts/report_release_status.py --package-dir PATH --no-write` for read-only status recalculation, `--json-only` for the same compact status report as parseable JSON, and `python3 scripts/write_evidence_checksums.py --package-dir PATH --verify --json-only` when automation needs a parseable transferred-package integrity result; intentional status rewrites require `--allow-post-checksum-write` and then `python3 scripts/write_evidence_checksums.py --package-dir PATH` to republish checksums. When a connected-runner handoff bundle exists, `next-release-step.md` promotes the bundle preflight as the primary command and keeps the manual setup command as a fallback; if connected-runner commands still contain `REPLACE_WITH_REPO_URL`, the next-step output includes a note and `export GIT_ORIGIN_URL=https://github.com/OWNER/REPO.git` example before the repo URL gates because literal placeholders are rejected. `release-status.md` also repeats that preferred preflight under each connected-runner remaining item before shell-quoted `source/`-scoped manual remediation, verify, and final-verify commands. `scripts/check_external_readiness.py` now includes macOS/Homebrew setup commands for missing Docker Desktop and GitHub CLI in its JSON/Markdown `setup_command` fields, so copied status reports can show the exact `brew install --cask docker ...` and `brew install gh ...` paths while the preflight still remains the preferred first command. To print a copy-paste-ready command on the connected runner without mutating archived evidence, run `python3 scripts/next_release_step.py --package-dir PATH --repo-url REPO_URL --no-write`; replace `REPO_URL` with a real HTTPS, SSH, or scp-style git remote URL because placeholder and invalid values are rejected. If the connected runner already has `origin` configured in the known handoff source, use `python3 scripts/next_release_step.py --package-dir PATH --repo-url-from-origin --no-write` to read and validate that remote automatically; pass `--repo-url-from-origin SOURCE_PATH` only when overriding the inferred source path. If `GIT_ORIGIN_URL` is exported, use `python3 scripts/next_release_step.py --package-dir PATH --repo-url-from-env GIT_ORIGIN_URL --no-write` to read the same remote URL from the environment. Add `--show-sequence` and optionally `--owner "connected runner"` or `--owner operator` to print every remaining command for a handoff owner, use `--command-sequence-only --fail-if-repo-url-required` when automation needs only those remaining commands one per line, add `--summary-by-owner` when a reviewer needs the remaining connected-runner/operator split before choosing the next lane, and add `--local-readiness --no-write` when the reviewer wants read-only local checks for `origin`, Docker Compose, and GitHub CLI auth in the same output. Local-readiness text and JSON include per-check remediation/setup fields for unresolved `origin`, Docker, and GitHub CLI gaps so automation can surface the concrete manual fix without scraping release-status; unresolved `origin` setup is idempotent and sets the URL when `origin` exists or adds it when it does not. Use `--local-readiness-setup-sequence-only` for just setup commands or `--local-readiness-command-sequence-only` for setup commands followed by their verify commands. Use `--command-only --local-readiness --fail-if-local-readiness-not-pass` when automation needs exactly one next command but should fail until those local checks pass. Local readiness checks the known handoff bundle `source/` by default; pass `--local-readiness-source SOURCE_PATH` only when overriding that inferred source path. From an extracted handoff bundle root, `--handoff-bundle "$(pwd)"` can omit `--package-dir`; the latest copied evidence package under `evidence/` is selected automatically. The checksum command refreshes `manifest.json` with a `post_package_artifacts` inventory for these generated handoff files before hashing the package. The handoff command verifies the unpacked bundle and writes a sibling `.tgz.verification.json` report that checks required tarball members, path safety, evidence archive presence, excluded local artifacts, runner executable mode, fail-fast command/auth preflight, missing/placeholder/invalid `GIT_ORIGIN_URL` guard behavior, default `gh auth setup-git` setup before `git ls-remote`, remote reachability preflight, command order for remote guards/bundle self-verification/acceptance/install/push/strict gate, `bash -n` syntax for `run-connected-runner-handoff.sh`, and copied evidence `release-status`/`next-release-step` commands against the packaging-time bundle path inside both the unpacked bundle and tarball. If the bundle is extracted to another absolute path, the verifier reports that current-path difference as a warning while still checking internal command consistency. The extracted `source/` snapshot is not a git repository; from the bundle root replace `REPLACE_WITH_REPO_URL` and run `PREFLIGHT_ONLY=true GIT_ORIGIN_URL=REPLACE_WITH_REPO_URL ./run-connected-runner-handoff.sh` for the first no-install/no-push connected-runner command; the runner first rejects missing/placeholder/invalid remote URLs, then self-verifies the bundle and performs external command/auth, remote, acceptance, and source checks before stopping. Run `GIT_ORIGIN_URL=REPLACE_WITH_REPO_URL ./run-connected-runner-handoff.sh` for the full automated connected-runner flow, or initialize git, create a branch, set or add `origin`, install dependencies, then run `python3 scripts/connected_runner_acceptance.py --handoff-root .. --require-external --check-gh-auth` from `source/` manually. If GitHub CLI credential setup fails, run `gh auth status` and `gh auth setup-git` directly on the connected runner; use `SETUP_GH_GIT_AUTH=false` only when the connected runner already has a git credential helper and should skip the default setup. After an actual live-beta window, run `python3 scripts/archive_live_beta_closeout.py --api-base http://localhost:8000 --symbol KRW-BTC --backup-reference /backups/quant-lab.sqlite3` once live flags are locked again; the backup reference may be a local path or external reference, but placeholders such as `PATH_TO_BACKUP` are rejected. The command publishes the final archive only after all required exports are written, and `check_release_evidence.py --require-live-beta` validates the archive manifest, closeout/drill/handoff/runbook files, raw settings, raw alerts, and live-lock safety. Use `python3 scripts/review_release_warnings.py --package-dir PATH --no-write` for post-checksum warning inspection, `python3 scripts/review_release_warnings.py --package-dir PATH --summary-json-only` when automation needs compact warning counts and recommended-next metadata, `python3 scripts/review_release_warnings.py --package-dir PATH --review-artifacts-only` when automation needs only the action-plan/checklist paths and should fail if either review artifact is missing, `python3 scripts/review_release_warnings.py --package-dir PATH --next-command-only` when automation needs only the selected warning-review next command, add `--fail-if-action-needed` to those warning JSON/summary/command-only modes when automation should still fail while warning actions remain unresolved, and use `python3 scripts/review_release_warnings.py --package-dir PATH --apply --operator-approved` only when an operator intentionally wants to acknowledge or dismiss those warning alerts in a running backend after checklist review.

Connected-runner automation can add `--json-only` to `scripts/package_connected_runner_handoff.py --verify PATH_TO_BUNDLE` and `scripts/connected_runner_acceptance.py ...` to parse bundle verification and acceptance reports directly from stdout while preserving their report files and failure exit codes. Use `--summary-json-only` when resume automation only needs compact status counts plus warning/failure IDs. For standalone external-readiness polling, `scripts/check_external_readiness.py --summary-json-only` prints the same compact shape plus setup/verify guidance while still writing JSON and Markdown evidence files; for operator warning polling, `scripts/review_release_warnings.py --summary-json-only` prints compact counts, action-needed reasons, review artifacts, and the recommended next command without mutating package files.

Before writing a live-beta closeout archive, run `python3 scripts/archive_live_beta_closeout.py --api-base http://localhost:8000 --symbol KRW-BTC --backup-reference /backups/quant-lab.sqlite3 --preflight`; it checks backend reachability, live-lock state, and blocking alerts without creating archive files. Add `--json` for machine-readable automation output, or `--next-command-only` when automation needs only the selected command from `recommended_next`. The preflight output includes local/Docker backend start commands, a no-reload local backend fallback for restricted runners, a backend health-check command, and `recommended_next` guidance alongside the archive and final-gate commands, and release evidence checks verify those support commands in generated handoff artifacts. If it passes after a real live-beta window, rerun the same command without `--preflight`.

## CI Automation

The GitHub Actions workflow at `.github/workflows/quant-lab-ci.yml` runs the same release evidence chain on pushes, pull requests, and manual dispatch:

- Install backend and frontend dependencies.
- Run `python3 scripts/release_gate.py --run-smoke --strict-external --check-gh-auth`, including Docker Compose config, external runner prerequisites, GitHub CLI auth, remote workflow visibility, and latest workflow run evidence.
- Run a final read-only `python3 scripts/check_release_evidence.py --no-write` against the latest package after the release gate has published checksums.
- Upload verification summaries, smoke/drill artifacts, external readiness reports, evidence packages, release gate summaries, connected-runner handoff bundles, and live-beta archives.

CI keeps `QUANT_LAB_LIVE_TRADING_ENABLED=false` and clears live ACK variables.

## Required Evidence Before Review

Archive these artifacts before a controlled live-beta review:

- Latest `scripts/package_evidence.py` package and optional `.tgz`.
- Latest `scripts/check_release_evidence.py` summary.
- Latest `scripts/release_gate.py` summary.
- Latest `scripts/check_external_readiness.py` summary.
- Latest `release-warning-triage.md` if the evidence check returns `warn`.
- Latest `release-warning-actions.md` if warning actions were generated.
- Latest `release-warning-operator-checklist.md` before applying warning actions.
- Latest `release-status.md`.
- Latest `next-release-step.md`.
- Latest connected-runner handoff bundle from `artifacts/handoff-bundles/`.
- Latest connected-runner handoff `handoff-verification.json` report and sibling `.tgz.verification.json` report.
- Executable connected-runner script `run-connected-runner-handoff.sh` inside the handoff bundle.
- Latest connected-runner acceptance report when a handoff bundle is used, including runner script executable/syntax/preflight, remote-guard, `gh auth setup-git`, `git ls-remote`, command-order checks, evidence archive integrity, and copied `release-status`/`next-release-step` command consistency.
- Latest live-beta closeout archive from `scripts/archive_live_beta_closeout.py` after an actual live-beta window.
- Latest `evidence-checksums.json`, `evidence-checksums.sha256`, and `.tgz.sha256` sidecar.
- `manifest.json` with `post_package_artifacts` listing generated gate, warning, status, and next-step files.
- Latest `scripts/verify_project.py` summary.
- Latest `scripts/ops_smoke_check.py` summary.
- Crypto live beta drill report.
- Strategy health handoff report.
- Dry-run order runbooks.
- Live cutover runbook.
- Post-cutover closeout report if a window has already run.
- Operations journal export.
- Database backup reference.

## Live Flag Lock Check

Before handoff, confirm:

```bash
grep -E 'QUANT_LAB_LIVE_TRADING_ENABLED|QUANT_LAB_LIVE_TRADING_ACK' .env
curl -fsS http://localhost:8000/api/execution/settings
```

Expected outside an approved cutover window:

```text
QUANT_LAB_LIVE_TRADING_ENABLED=false
QUANT_LAB_LIVE_TRADING_ACK=
```

The backend settings response should report `adapter_ready=false` unless the live window is explicitly approved and configured.

## Release Readiness Checklist

- Backend tests pass.
- Frontend build passes.
- Script compile checks pass.
- Docker Compose config is validated or explicitly skipped because Docker is unavailable.
- CI passes or a documented local verification/evidence package is attached when CI is not available.
- External readiness is pass on a connected runner or warning-only with documented Docker/GitHub gaps.
- `scripts/next_release_step.py --local-readiness --no-write` reports the first unresolved `local_readiness_next_setup_command`, its matching `verify_command`, the structured `local_readiness_setup_sequence`, and the flattened `local_readiness_command_sequence` for connected-runner setup gaps.
- `scripts/next_release_step.py --local-readiness-setup-sequence-only --fail-if-local-readiness-not-pass` prints only unresolved connected-runner setup commands and keeps the same fail-closed readiness gate.
- `scripts/next_release_step.py --local-readiness-command-sequence-only --fail-if-local-readiness-not-pass` prints unresolved setup commands followed by matching verification commands and keeps the same fail-closed readiness gate.
- `scripts/check_release_evidence.py --no-write` exits successfully for the attached evidence package after checksums are published.
- `.env` is based on `.env.example`.
- Live trading flags are locked by default.
- Active alert review queue contains no unresolved halt/error items for the target market.
- Warning alerts are either accepted in `release-warning-actions.md` with `release-warning-operator-checklist.md` reviewed, or acknowledged/dismissed through the alert review API by an operator.
- `/api/ops/self-check` returns expected scheduler, artifact, live-lock, and runbook metadata.
- `KRW-BTC` crypto live beta drill report can be generated.
- Readiness review, dry-run approval, and live cutover decisions are logged before any live arming.
- Backup is created before the live beta window.
- Closeout report is exported after the live beta window.

## Rollback And Restore Notes

If a local deployment behaves unexpectedly:

1. Stop the backend or Docker Compose stack.
2. Restore the latest known-good SQLite or Compose volume backup from `docs/deployment-hardening.md`.
3. Confirm `.env` live flags are locked.
4. Restart the backend.
5. Run `python3 scripts/ops_smoke_check.py --api-base http://localhost:8000 --symbol KRW-BTC`.
6. Review `/api/alerts/review` before re-enabling any scheduler or live-beta process.

If a live beta window is interrupted:

- Turn off `QUANT_LAB_LIVE_TRADING_ENABLED`.
- Remove `QUANT_LAB_LIVE_TRADING_ACK`.
- Export the post-cutover closeout report.
- Archive open order/private snapshot evidence.
- Log a `needs_work` or `rejected` operator decision with the reason.
