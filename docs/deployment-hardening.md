# Deployment Hardening

This guide keeps Quant Lab runnable in a repeatable local or small-server setup while preserving the default live-order lock.

## 1. Environment

Create a local environment file from the template:

```bash
cp .env.example .env
```

Keep these defaults unless you are inside an approved live cutover window:

```bash
QUANT_LAB_LIVE_TRADING_ENABLED=false
QUANT_LAB_LIVE_TRADING_ACK=
ALPACA_PAPER_TRADING_ENABLED=false
ALPACA_PAPER_TRADING_ACK=
```

Only set `UPBIT_ACCESS_KEY` and `UPBIT_SECRET_KEY` when you need private read checks or an approved guarded live beta. Only set Alpaca paper credentials when testing the paper broker adapter.

## 2. Docker Compose

Build and run both services:

```bash
docker compose up --build
```

Open the dashboard at:

```text
http://localhost:5173
```

The frontend container proxies `/api/*` to the backend container. Backend data is stored in the Compose-managed `quant-backend-data` volume at `/app/data`.

Stop the stack:

```bash
docker compose down
```

Stop the stack and remove the persisted data volume only when you deliberately want a clean lab:

```bash
docker compose down --volumes
```

## 3. Health Checks

Run these checks after boot:

```bash
curl -fsS http://localhost:8000/api/health
curl -fsS http://localhost:8000/api/ops/self-check
curl -fsS http://localhost:8000/api/execution/settings
curl -fsS http://localhost:8000/api/readiness/live
curl -fsS http://localhost:8000/api/execution/broker-readiness
curl -fsS "http://localhost:8000/api/research/crypto-live-beta-drill/report?symbol=KRW-BTC"
```

Expected safe baseline:

- `/api/health` returns `ok`.
- `/api/ops/self-check` returns app version, DB paths, scheduler state, artifact paths, live-lock status, and runbook links.
- Live readiness may be `watch` or `blocked` in a fresh environment.
- Upbit live submission remains locked unless the live flag, ACK, credentials, operator decisions, and per-order confirmation are all present.
- Alpaca paper submission remains blocked unless paper credentials, paper flag, ACK, and per-request confirmation are present.

## 4. Backup And Restore

For Docker Compose, create a backup from the named volume:

```bash
mkdir -p backups
docker compose stop backend
docker compose run --rm --no-deps -v "$PWD/backups:/backups" backend sh -c 'cd /app/data && tar czf /backups/quant-backend-data-$(date +%Y%m%d-%H%M%S).tgz .'
docker compose start backend
```

For a direct local backend using the default paths:

```bash
mkdir -p backups
sqlite3 backend/data/quant_lab.sqlite3 ".backup 'backups/quant_lab-$(date +%Y%m%d-%H%M%S).sqlite3'"
cp backend/data/quant_lab.duckdb backups/quant_lab-$(date +%Y%m%d-%H%M%S).duckdb 2>/dev/null || true
cp backend/data/quant_lab_market_candles.parquet backups/quant_lab_market_candles-$(date +%Y%m%d-%H%M%S).parquet 2>/dev/null || true
```

Restore only while the backend is stopped:

```bash
docker compose stop backend
docker compose run --rm --no-deps -v "$PWD/backups:/backups" backend sh -c 'rm -rf /app/data/* && tar xzf /backups/YOUR_BACKUP_FILE.tgz -C /app/data'
docker compose start backend
```

For local SQLite restore, stop the backend process and copy the selected `.sqlite3` backup back to `backend/data/quant_lab.sqlite3`.

## 5. Pre-Market Operator Checklist

Before any live beta review:

- Confirm `.env` has `QUANT_LAB_LIVE_TRADING_ENABLED=false` during preparation.
- Run the health checks above.
- Review `GET /api/alerts/review` and acknowledge or resolve active halt/error items.
- Generate `GET /api/research/crypto-live-beta-drill/report?symbol=KRW-BTC`.
- Export dry-run runbooks for each candidate order audit.
- Log readiness review and dry-run approval decisions in the Operations journal.
- Run the live cutover simulation and confirm remaining blockers are understood.
- Confirm database backup was taken before the live beta window.
- Enable live flags only inside the approved window and lock them again before closeout.
- Export the post-cutover closeout archive after the window:

```bash
python3 scripts/archive_live_beta_closeout.py --api-base http://localhost:8000 --symbol KRW-BTC --backup-reference /backups/quant-lab.sqlite3 --preflight
python3 scripts/archive_live_beta_closeout.py --api-base http://localhost:8000 --symbol KRW-BTC --backup-reference /backups/quant-lab.sqlite3
```

## 6. Seeded Crypto Drill

After the backend is running, generate a repeatable `KRW-BTC` drill package:

```bash
python3 scripts/seed_crypto_drill.py --api-base http://localhost:8000 --symbol KRW-BTC
```

The script:

- Checks `/api/health`.
- Creates a sample `KRW-BTC` paper session.
- Queues dry-run order intents from that session.
- Exports each dry-run runbook.
- Exports the crypto live beta drill report.
- Writes JSON and Markdown evidence under `artifacts/crypto-drills/`.
- Leaves live routing controlled by the backend environment gates.

## 7. Operational Smoke Check

Collect core operating status into timestamped JSON/Markdown artifacts:

```bash
python3 scripts/ops_smoke_check.py --api-base http://localhost:8000 --symbol KRW-BTC
```

Run the smoke check plus a seeded drill:

```bash
python3 scripts/ops_smoke_check.py --api-base http://localhost:8000 --symbol KRW-BTC --run-drill
```

See [production-observability.md](production-observability.md) for daily cadence, alert review order, scheduler triage, disk checks, log retention, and closeout archive naming.

Start a local backend, run the same smoke checks, and stop the managed process:

```bash
python3 scripts/run_local_smoke.py --start-backend --run-drill
```

## 8. CI Verification

The GitHub Actions workflow at `.github/workflows/quant-lab-ci.yml` mirrors the local handoff chain:

- Backend editable install.
- `scripts/release_gate.py --run-smoke --strict-external --check-gh-auth`, which runs project verification, external readiness checks, managed local smoke drill, evidence packaging, release evidence checking, release status reporting, and checksum generation/verification with external prerequisites and GitHub CLI auth/workflow queries enforced.
- A final latest-package evidence check.
- Artifact upload for verification, smoke/drill, external readiness, evidence packages, release gate summaries, connected-runner handoff bundles, and live-beta archives.

Live-order and Alpaca paper submission flags are explicitly locked in the workflow environment.

## 9. Verification Commands

Run these before treating the deployment artifacts as current:

```bash
backend/.venv/bin/python -m unittest discover -s backend/tests
npm --prefix frontend run build
python3 -m py_compile scripts/seed_crypto_drill.py
python3 -m py_compile scripts/ops_smoke_check.py
python3 -m py_compile scripts/run_local_smoke.py
python3 -m py_compile scripts/check_external_readiness.py
python3 -m py_compile scripts/package_evidence.py
python3 -m py_compile scripts/check_release_evidence.py
python3 -m py_compile scripts/package_connected_runner_handoff.py
python3 -m py_compile scripts/release_gate.py
python3 -m py_compile scripts/next_release_step.py
python3 -m py_compile scripts/report_release_status.py
python3 -m py_compile scripts/verify_project.py
python3 -m py_compile scripts/write_evidence_checksums.py
docker compose config
```

For a bundled release gate, use:

```bash
python3 scripts/release_gate.py --run-smoke
```

For a connected runner or Docker-enabled handoff machine, enforce external prerequisites:

```bash
python3 scripts/release_gate.py --run-smoke --strict-external --check-gh-auth
```

If Docker is not installed locally:

```bash
python3 scripts/release_gate.py --skip-docker --run-smoke
```

When no git remote is available yet, create a source and evidence transfer bundle for a connected runner:

```bash
python3 scripts/package_connected_runner_handoff.py --package-dir PATH_TO_EVIDENCE_PACKAGE
python3 scripts/package_connected_runner_handoff.py --verify PATH_TO_HANDOFF_BUNDLE
python3 scripts/package_connected_runner_handoff.py --verify PATH_TO_HANDOFF_BUNDLE --json-only
python3 scripts/package_connected_runner_handoff.py --verify PATH_TO_HANDOFF_BUNDLE --summary-json-only
```

The verification command checks both the unpacked handoff bundle and, when the sibling `.tgz` exists, the transfer archive contents. It also checks runner script executable mode, shell syntax, fail-fast command/auth preflight markers, missing/placeholder/invalid `GIT_ORIGIN_URL` guard behavior, default `gh auth setup-git` setup before `git ls-remote`, remote reachability preflight, the order of remote guards, bundle self-verification, acceptance, install, push, and strict-gate commands, and copied evidence `release-status`/`next-release-step` handoff commands in both the unpacked bundle and the tarball before the bundle is considered transferable. It writes `handoff-verification.json` inside the bundle and a sibling `.tgz.verification.json` next to the tarball; keep both reports with the moved bundle. If the bundle is later extracted to a different absolute path, bundle verification keeps checking those copied commands against the packaging-time path from `manifest.json` and reports the current-path difference as a warning. Keep the generated `.tgz.sha256` and `.tgz.verification.json` files with the tarball when moving it to the connected runner.

The handoff `source/` snapshot intentionally excludes `.git`, dependency folders, local databases, and generated artifacts. On the connected runner, first run the generated preflight script from the bundle root. The script starts by running `scripts/package_connected_runner_handoff.py --verify` against the current bundle, then continues into external command/auth and remote checks:

```bash
PREFLIGHT_ONLY=true GIT_ORIGIN_URL=REPLACE_WITH_REPO_URL ./run-connected-runner-handoff.sh
```

Replace `REPLACE_WITH_REPO_URL` with the real HTTPS, SSH, or scp-style remote URL before running the command.

The runner calls `gh auth setup-git` by default before `git ls-remote`, which helps private GitHub HTTPS remotes use GitHub CLI credentials. If that setup fails, run `gh auth status` and `gh auth setup-git` directly on the connected runner to fix the GitHub CLI credential helper. Set `SETUP_GH_GIT_AUTH=false` only when the connected runner already manages git credentials another way.

After the preflight passes, run the full flow:

```bash
GIT_ORIGIN_URL=REPLACE_WITH_REPO_URL ./run-connected-runner-handoff.sh
```

Or initialize git inside `source/`, create a branch, set or add `origin`, run acceptance, then install dependencies manually.

After extracting the bundle on the connected runner, initializing git, adding the git origin, and confirming Docker/GitHub CLI, run the acceptance preflight from the extracted `source/` directory before dependency installation:

```bash
python3 scripts/connected_runner_acceptance.py --handoff-root .. --require-external --check-gh-auth
python3 scripts/connected_runner_acceptance.py --handoff-root .. --require-external --check-gh-auth --json-only
python3 scripts/connected_runner_acceptance.py --handoff-root .. --require-external --check-gh-auth --summary-json-only
```

The acceptance report records source safety, copied evidence archive integrity, copied `release-status`/`next-release-step` handoff command consistency, bundle runner script executable/syntax/preflight state, missing/placeholder/invalid remote guard behavior, runner command order, git repository/origin readiness, Docker Compose availability, and GitHub CLI/auth state before the strict release gate. Add `--json-only` when automation needs the full report from stdout, or `--summary-json-only` when it only needs compact status counts plus warning/failure IDs; both modes still write JSON and Markdown artifacts. If a bundle was extracted to a different absolute path on another runner, internally consistent copied commands that still point to the packaging-time path are reported as a warning with instructions to run the bundled script from the current bundle root. Expected connected-runner install folders such as `backend/.venv` and `frontend/node_modules` are allowed during acceptance; they remain excluded from the original handoff archive and ignored by git.

See [release-readiness.md](release-readiness.md) for the final handoff checklist.
