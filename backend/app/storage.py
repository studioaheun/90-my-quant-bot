import json
import os
import sqlite3
import uuid
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

from .backtester import compute_buy_and_hold_metrics
from .models import (
    AlertReviewAcknowledgeRequest,
    AlertReviewAcknowledgement,
    BacktestResponse,
    BacktestRun,
    BacktestRunSummary,
    BotProfile,
    BotProfileCreate,
    BotRun,
    BrokerOrderIntentEvaluation,
    BrokerOrderReconciliation,
    Candle,
    LivePaperTradingSession,
    MarketDataColumnarExport,
    MarketDataColumnarStatus,
    OperatorDecisionCreate,
    OperatorDecisionRecord,
    OrderAuditRecord,
    PaperFillOrderNote,
    PaperTradingSession,
    PortfolioPaperWatchlistCreate,
    PortfolioPaperWatchlistItem,
    PortfolioResearchAlert,
    PortfolioResearchResponse,
    PortfolioResearchScan,
    PortfolioResearchScenario,
    PortfolioResearchScenarioCreate,
    PortfolioResearchWatchlistCreate,
    PortfolioResearchWatchlistItem,
    StockPaperBrokerAdapterId,
)
from .paper import LivePaperRuntime, PaperState


DEFAULT_CANDLE_CACHE_TTL_SECONDS = 300


def default_database_path() -> Path:
    configured = os.environ.get("QUANT_LAB_DB_PATH")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1] / "data" / "quant_lab.sqlite3"


def default_columnar_database_path(sqlite_path: Optional[Path] = None) -> Path:
    configured = os.environ.get("QUANT_LAB_DUCKDB_PATH")
    if configured:
        return Path(configured)
    if sqlite_path is not None:
        return Path(sqlite_path).with_suffix(".duckdb")
    return Path(__file__).resolve().parents[1] / "data" / "quant_lab.duckdb"


def default_columnar_parquet_path(duckdb_path: Optional[Path] = None) -> Path:
    configured = os.environ.get("QUANT_LAB_CANDLE_PARQUET_PATH")
    if configured:
        return Path(configured)
    base_path = Path(duckdb_path) if duckdb_path is not None else default_columnar_database_path()
    return base_path.parent / f"{base_path.stem}_market_candles.parquet"


def _columnar_cache_enabled() -> bool:
    configured = os.environ.get("QUANT_LAB_COLUMNAR_CACHE_ENABLED", "true").lower()
    return configured not in {"0", "false", "no", "off", "disabled"}


def _duckdb_module():
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError(
            "duckdb is required for the columnar candle cache. "
            "Install backend dependencies with pip install -e '.[dev]'."
        ) from exc
    return duckdb


def _next_run_at(start_at: str, interval_minutes: int) -> str:
    parsed = datetime.fromisoformat(start_at)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return (parsed + timedelta(minutes=interval_minutes)).isoformat()


class SessionStore:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path) if db_path else default_database_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def save_paper_session(self, session: PaperTradingSession) -> None:
        updated_at = _utc_now()
        payload = session.model_dump_json()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO paper_sessions
                    (id, created_at, updated_at, symbol, source, strategy, status, payload)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    updated_at = excluded.updated_at,
                    symbol = excluded.symbol,
                    source = excluded.source,
                    strategy = excluded.strategy,
                    status = excluded.status,
                    payload = excluded.payload
                """,
                (
                    session.id,
                    session.created_at,
                    updated_at,
                    session.request.symbol,
                    session.request.source,
                    session.request.strategy,
                    session.summary.status,
                    payload,
                ),
            )

    def get_paper_session(self, session_id: str) -> Optional[PaperTradingSession]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM paper_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return PaperTradingSession.model_validate_json(row["payload"])

    def list_paper_sessions(self, limit: int = 20) -> List[PaperTradingSession]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload
                FROM paper_sessions
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [PaperTradingSession.model_validate_json(row["payload"]) for row in rows]

    def save_live_runtime(self, runtime: LivePaperRuntime) -> None:
        updated_at = _utc_now()
        payload = _serialize_live_runtime(runtime)
        session = runtime.session
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO live_paper_runtimes
                    (
                        id, created_at, updated_at, symbol, source,
                        strategy, status, mode, payload
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    updated_at = excluded.updated_at,
                    symbol = excluded.symbol,
                    source = excluded.source,
                    strategy = excluded.strategy,
                    status = excluded.status,
                    mode = excluded.mode,
                    payload = excluded.payload
                """,
                (
                    session.id,
                    session.created_at,
                    updated_at,
                    session.request.symbol,
                    session.request.source,
                    session.request.strategy,
                    session.summary.status,
                    runtime.mode,
                    payload,
                ),
            )

    def get_live_runtime(self, session_id: str) -> Optional[LivePaperRuntime]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM live_paper_runtimes WHERE id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return _deserialize_live_runtime(row["payload"])

    def list_live_sessions(self, limit: int = 20) -> List[LivePaperTradingSession]:
        runtimes = self.list_live_runtimes(limit=limit)
        return [runtime.session for runtime in runtimes]

    def list_live_runtimes(self, limit: int = 100) -> List[LivePaperRuntime]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload
                FROM live_paper_runtimes
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [_deserialize_live_runtime(row["payload"]) for row in rows]

    def clear(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM paper_sessions")
            conn.execute("DELETE FROM live_paper_runtimes")

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS paper_sessions (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    source TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_paper_sessions_updated_at
                ON paper_sessions(updated_at DESC)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS live_paper_runtimes (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    source TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    status TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_live_paper_runtimes_updated_at
                ON live_paper_runtimes(updated_at DESC)
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn


class BacktestRunStore:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path) if db_path else default_database_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def save_run(
        self,
        result: BacktestResponse,
        run_id: Optional[str] = None,
    ) -> BacktestRun:
        created_at = result.created_at or _utc_now()
        resolved_id = result.id or run_id or str(uuid.uuid4())
        run = BacktestRun(
            id=resolved_id,
            created_at=created_at,
            request=result.request,
            metrics=result.metrics,
            equity_curve=result.equity_curve,
            trades=result.trades,
            candles=result.candles,
            warnings=result.warnings,
        )
        updated_at = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO backtest_runs
                    (
                        id, created_at, updated_at, symbol, source, timeframe,
                        strategy, final_equity, total_return_pct,
                        max_drawdown_pct, sharpe, trades, payload
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    updated_at = excluded.updated_at,
                    symbol = excluded.symbol,
                    source = excluded.source,
                    timeframe = excluded.timeframe,
                    strategy = excluded.strategy,
                    final_equity = excluded.final_equity,
                    total_return_pct = excluded.total_return_pct,
                    max_drawdown_pct = excluded.max_drawdown_pct,
                    sharpe = excluded.sharpe,
                    trades = excluded.trades,
                    payload = excluded.payload
                """,
                (
                    run.id,
                    run.created_at,
                    updated_at,
                    run.request.symbol,
                    run.request.source,
                    run.request.timeframe,
                    run.request.strategy,
                    run.metrics.final_equity,
                    run.metrics.total_return_pct,
                    run.metrics.max_drawdown_pct,
                    run.metrics.sharpe,
                    run.metrics.trades,
                    run.model_dump_json(),
                ),
            )
        return run

    def get_run(self, run_id: str) -> Optional[BacktestRun]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM backtest_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return _load_backtest_run(row["payload"])

    def list_summaries(self, limit: int = 20) -> List[BacktestRunSummary]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload
                FROM backtest_runs
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            _backtest_summary(_load_backtest_run(row["payload"]))
            for row in rows
        ]

    def clear(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM backtest_runs")

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS backtest_runs (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    source TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    final_equity REAL NOT NULL,
                    total_return_pct REAL NOT NULL,
                    max_drawdown_pct REAL NOT NULL,
                    sharpe REAL NOT NULL,
                    trades INTEGER NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_backtest_runs_updated_at
                ON backtest_runs(updated_at DESC)
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn


class PortfolioScenarioStore:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path) if db_path else default_database_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def save_scenario(
        self,
        create: PortfolioResearchScenarioCreate,
        scenario_id: Optional[str] = None,
    ) -> PortfolioResearchScenario:
        resolved_id = scenario_id or str(uuid.uuid4())
        created_at = self._created_at_for(resolved_id) or _utc_now()
        updated_at = _utc_now()
        name = create.name.strip() or "Saved portfolio scenario"
        scenario = PortfolioResearchScenario(
            id=resolved_id,
            name=name,
            created_at=created_at,
            updated_at=updated_at,
            request=create.request,
        )
        symbols = json.dumps(create.request.symbols, separators=(",", ":"))
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO portfolio_scenarios
                    (
                        id, created_at, updated_at, name, source,
                        strategy, symbols, payload
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    updated_at = excluded.updated_at,
                    name = excluded.name,
                    source = excluded.source,
                    strategy = excluded.strategy,
                    symbols = excluded.symbols,
                    payload = excluded.payload
                """,
                (
                    scenario.id,
                    scenario.created_at,
                    scenario.updated_at,
                    scenario.name,
                    scenario.request.source,
                    scenario.request.strategy,
                    symbols,
                    scenario.model_dump_json(),
                ),
            )
        return scenario

    def get_scenario(self, scenario_id: str) -> Optional[PortfolioResearchScenario]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM portfolio_scenarios WHERE id = ?",
                (scenario_id,),
            ).fetchone()
        if row is None:
            return None
        return PortfolioResearchScenario.model_validate_json(row["payload"])

    def list_scenarios(self, limit: int = 20) -> List[PortfolioResearchScenario]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload
                FROM portfolio_scenarios
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            PortfolioResearchScenario.model_validate_json(row["payload"])
            for row in rows
        ]

    def delete_scenario(self, scenario_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM portfolio_scenarios WHERE id = ?",
                (scenario_id,),
            )
            return cursor.rowcount > 0

    def clear(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM portfolio_scenarios")

    def _created_at_for(self, scenario_id: str) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT created_at FROM portfolio_scenarios WHERE id = ?",
                (scenario_id,),
            ).fetchone()
        if row is None:
            return None
        return row["created_at"]

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS portfolio_scenarios (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    name TEXT NOT NULL,
                    source TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    symbols TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_portfolio_scenarios_updated_at
                ON portfolio_scenarios(updated_at DESC)
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn


class PortfolioScanStore:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path) if db_path else default_database_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def save_scan(
        self,
        scenario: PortfolioResearchScenario,
        result: PortfolioResearchResponse,
        scan_id: Optional[str] = None,
    ) -> PortfolioResearchScan:
        scan = PortfolioResearchScan(
            id=scan_id or str(uuid.uuid4()),
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            created_at=_utc_now(),
            result=result,
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO portfolio_scans
                    (
                        id, scenario_id, scenario_name, created_at,
                        source, strategy, final_equity, total_return_pct,
                        max_drawdown_pct, trades, payload
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    scenario_id = excluded.scenario_id,
                    scenario_name = excluded.scenario_name,
                    source = excluded.source,
                    strategy = excluded.strategy,
                    final_equity = excluded.final_equity,
                    total_return_pct = excluded.total_return_pct,
                    max_drawdown_pct = excluded.max_drawdown_pct,
                    trades = excluded.trades,
                    payload = excluded.payload
                """,
                (
                    scan.id,
                    scan.scenario_id,
                    scan.scenario_name,
                    scan.created_at,
                    scan.result.request.source,
                    scan.result.request.strategy,
                    scan.result.metrics.final_equity,
                    scan.result.metrics.total_return_pct,
                    scan.result.metrics.max_drawdown_pct,
                    scan.result.metrics.trades,
                    scan.model_dump_json(),
                ),
            )
        return scan

    def get_scan(self, scan_id: str) -> Optional[PortfolioResearchScan]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM portfolio_scans WHERE id = ?",
                (scan_id,),
            ).fetchone()
        if row is None:
            return None
        return PortfolioResearchScan.model_validate_json(row["payload"])

    def list_scans(self, limit: int = 20) -> List[PortfolioResearchScan]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload
                FROM portfolio_scans
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            PortfolioResearchScan.model_validate_json(row["payload"])
            for row in rows
        ]

    def clear(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM portfolio_scans")

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS portfolio_scans (
                    id TEXT PRIMARY KEY,
                    scenario_id TEXT NOT NULL,
                    scenario_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    final_equity REAL NOT NULL,
                    total_return_pct REAL NOT NULL,
                    max_drawdown_pct REAL NOT NULL,
                    trades INTEGER NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_portfolio_scans_created_at
                ON portfolio_scans(created_at DESC)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_portfolio_scans_scenario_id
                ON portfolio_scans(scenario_id, created_at DESC)
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn


class PortfolioWatchlistStore:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path) if db_path else default_database_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def save_item(
        self,
        create: PortfolioResearchWatchlistCreate,
        scenario: PortfolioResearchScenario,
    ) -> PortfolioResearchWatchlistItem:
        existing = self.get_item_for_scenario(scenario.id)
        now = _utc_now()
        item = PortfolioResearchWatchlistItem(
            id=existing.id if existing else str(uuid.uuid4()),
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            created_at=existing.created_at if existing else now,
            updated_at=now,
            interval_minutes=create.interval_minutes,
            active=create.active,
            next_run_at=now if create.active else _next_run_at(now, create.interval_minutes),
            alert_thresholds=create.alert_thresholds,
            last_run_at=existing.last_run_at if existing else None,
            last_scan_id=existing.last_scan_id if existing else None,
            last_alerts=existing.last_alerts if existing else [],
            last_error=None,
        )
        self._upsert_item(item)
        return item

    def get_item(self, item_id: str) -> Optional[PortfolioResearchWatchlistItem]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM portfolio_watchlist WHERE id = ?",
                (item_id,),
            ).fetchone()
        if row is None:
            return None
        return PortfolioResearchWatchlistItem.model_validate_json(row["payload"])

    def get_item_for_scenario(
        self,
        scenario_id: str,
    ) -> Optional[PortfolioResearchWatchlistItem]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM portfolio_watchlist WHERE scenario_id = ?",
                (scenario_id,),
            ).fetchone()
        if row is None:
            return None
        return PortfolioResearchWatchlistItem.model_validate_json(row["payload"])

    def list_items(self, limit: int = 50) -> List[PortfolioResearchWatchlistItem]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload
                FROM portfolio_watchlist
                ORDER BY active DESC, next_run_at ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            PortfolioResearchWatchlistItem.model_validate_json(row["payload"])
            for row in rows
        ]

    def due_items(self, now: Optional[str] = None) -> List[PortfolioResearchWatchlistItem]:
        checked_at = now or _utc_now()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload
                FROM portfolio_watchlist
                WHERE active = 1 AND next_run_at <= ?
                ORDER BY next_run_at ASC
                """,
                (checked_at,),
            ).fetchall()
        return [
            PortfolioResearchWatchlistItem.model_validate_json(row["payload"])
            for row in rows
        ]

    def record_scan(
        self,
        item: PortfolioResearchWatchlistItem,
        scan: PortfolioResearchScan,
        alerts: Optional[List[PortfolioResearchAlert]] = None,
    ) -> PortfolioResearchWatchlistItem:
        now = _utc_now()
        updated = item.model_copy(
            update={
                "scenario_name": scan.scenario_name,
                "updated_at": now,
                "next_run_at": _next_run_at(now, item.interval_minutes),
                "last_run_at": scan.created_at,
                "last_scan_id": scan.id,
                "last_alerts": alerts or [],
                "last_error": None,
            }
        )
        self._upsert_item(updated)
        return updated

    def record_error(
        self,
        item: PortfolioResearchWatchlistItem,
        error: str,
        active: Optional[bool] = None,
    ) -> PortfolioResearchWatchlistItem:
        now = _utc_now()
        updated = item.model_copy(
            update={
                "updated_at": now,
                "next_run_at": _next_run_at(now, item.interval_minutes),
                "last_run_at": now,
                "last_error": error,
                "active": item.active if active is None else active,
            }
        )
        self._upsert_item(updated)
        return updated

    def delete_item(self, item_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM portfolio_watchlist WHERE id = ?",
                (item_id,),
            )
            return cursor.rowcount > 0

    def delete_for_scenario(self, scenario_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM portfolio_watchlist WHERE scenario_id = ?",
                (scenario_id,),
            )

    def clear(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM portfolio_watchlist")

    def _upsert_item(self, item: PortfolioResearchWatchlistItem) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO portfolio_watchlist
                    (
                        id, scenario_id, scenario_name, created_at, updated_at,
                        interval_minutes, active, next_run_at, last_run_at,
                        last_scan_id, last_error, payload
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    scenario_id = excluded.scenario_id,
                    scenario_name = excluded.scenario_name,
                    updated_at = excluded.updated_at,
                    interval_minutes = excluded.interval_minutes,
                    active = excluded.active,
                    next_run_at = excluded.next_run_at,
                    last_run_at = excluded.last_run_at,
                    last_scan_id = excluded.last_scan_id,
                    last_error = excluded.last_error,
                    payload = excluded.payload
                """,
                (
                    item.id,
                    item.scenario_id,
                    item.scenario_name,
                    item.created_at,
                    item.updated_at,
                    item.interval_minutes,
                    1 if item.active else 0,
                    item.next_run_at,
                    item.last_run_at,
                    item.last_scan_id,
                    item.last_error,
                    item.model_dump_json(),
                ),
            )

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS portfolio_watchlist (
                    id TEXT PRIMARY KEY,
                    scenario_id TEXT NOT NULL UNIQUE,
                    scenario_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    interval_minutes INTEGER NOT NULL,
                    active INTEGER NOT NULL,
                    next_run_at TEXT NOT NULL,
                    last_run_at TEXT,
                    last_scan_id TEXT,
                    last_error TEXT,
                    payload TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_portfolio_watchlist_due
                ON portfolio_watchlist(active, next_run_at ASC)
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn


class PortfolioPaperWatchlistStore:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path) if db_path else default_database_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def save_item(
        self,
        create: PortfolioPaperWatchlistCreate,
        scenario: PortfolioResearchScenario,
    ) -> PortfolioPaperWatchlistItem:
        existing = self.get_item_for_scenario(scenario.id)
        now = _utc_now()
        item = PortfolioPaperWatchlistItem(
            id=existing.id if existing else str(uuid.uuid4()),
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            created_at=existing.created_at if existing else now,
            updated_at=now,
            interval_minutes=create.interval_minutes,
            active=create.active,
            next_run_at=now if create.active else _next_run_at(now, create.interval_minutes),
            risk_limits=create.risk_limits,
            last_run_at=existing.last_run_at if existing else None,
            last_session_ids=existing.last_session_ids if existing else [],
            last_error=None,
        )
        self._upsert_item(item)
        return item

    def get_item(self, item_id: str) -> Optional[PortfolioPaperWatchlistItem]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM portfolio_paper_watchlist WHERE id = ?",
                (item_id,),
            ).fetchone()
        if row is None:
            return None
        return PortfolioPaperWatchlistItem.model_validate_json(row["payload"])

    def get_item_for_scenario(
        self,
        scenario_id: str,
    ) -> Optional[PortfolioPaperWatchlistItem]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM portfolio_paper_watchlist WHERE scenario_id = ?",
                (scenario_id,),
            ).fetchone()
        if row is None:
            return None
        return PortfolioPaperWatchlistItem.model_validate_json(row["payload"])

    def list_items(self, limit: int = 50) -> List[PortfolioPaperWatchlistItem]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload
                FROM portfolio_paper_watchlist
                ORDER BY active DESC, next_run_at ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            PortfolioPaperWatchlistItem.model_validate_json(row["payload"])
            for row in rows
        ]

    def due_items(self, now: Optional[str] = None) -> List[PortfolioPaperWatchlistItem]:
        checked_at = now or _utc_now()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload
                FROM portfolio_paper_watchlist
                WHERE active = 1 AND next_run_at <= ?
                ORDER BY next_run_at ASC
                """,
                (checked_at,),
            ).fetchall()
        return [
            PortfolioPaperWatchlistItem.model_validate_json(row["payload"])
            for row in rows
        ]

    def record_run(
        self,
        item: PortfolioPaperWatchlistItem,
        sessions: List[PaperTradingSession],
    ) -> PortfolioPaperWatchlistItem:
        now = _utc_now()
        updated = item.model_copy(
            update={
                "updated_at": now,
                "next_run_at": _next_run_at(now, item.interval_minutes),
                "last_run_at": now,
                "last_session_ids": [session.id for session in sessions],
                "last_error": None,
            }
        )
        self._upsert_item(updated)
        return updated

    def record_error(
        self,
        item: PortfolioPaperWatchlistItem,
        error: str,
        active: Optional[bool] = None,
    ) -> PortfolioPaperWatchlistItem:
        now = _utc_now()
        updated = item.model_copy(
            update={
                "updated_at": now,
                "next_run_at": _next_run_at(now, item.interval_minutes),
                "last_run_at": now,
                "last_error": error,
                "active": item.active if active is None else active,
            }
        )
        self._upsert_item(updated)
        return updated

    def delete_item(self, item_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM portfolio_paper_watchlist WHERE id = ?",
                (item_id,),
            )
            return cursor.rowcount > 0

    def delete_for_scenario(self, scenario_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM portfolio_paper_watchlist WHERE scenario_id = ?",
                (scenario_id,),
            )

    def clear(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM portfolio_paper_watchlist")

    def _upsert_item(self, item: PortfolioPaperWatchlistItem) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO portfolio_paper_watchlist
                    (
                        id, scenario_id, scenario_name, created_at, updated_at,
                        interval_minutes, active, next_run_at, last_run_at,
                        last_session_ids, last_error, payload
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    scenario_id = excluded.scenario_id,
                    scenario_name = excluded.scenario_name,
                    updated_at = excluded.updated_at,
                    interval_minutes = excluded.interval_minutes,
                    active = excluded.active,
                    next_run_at = excluded.next_run_at,
                    last_run_at = excluded.last_run_at,
                    last_session_ids = excluded.last_session_ids,
                    last_error = excluded.last_error,
                    payload = excluded.payload
                """,
                (
                    item.id,
                    item.scenario_id,
                    item.scenario_name,
                    item.created_at,
                    item.updated_at,
                    item.interval_minutes,
                    1 if item.active else 0,
                    item.next_run_at,
                    item.last_run_at,
                    json.dumps(item.last_session_ids),
                    item.last_error,
                    item.model_dump_json(),
                ),
            )

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS portfolio_paper_watchlist (
                    id TEXT PRIMARY KEY,
                    scenario_id TEXT NOT NULL UNIQUE,
                    scenario_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    interval_minutes INTEGER NOT NULL,
                    active INTEGER NOT NULL,
                    next_run_at TEXT NOT NULL,
                    last_run_at TEXT,
                    last_session_ids TEXT NOT NULL,
                    last_error TEXT,
                    payload TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_portfolio_paper_watchlist_due
                ON portfolio_paper_watchlist(active, next_run_at ASC)
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn


class BotFleetStore:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path) if db_path else default_database_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def save_profile(self, create: BotProfileCreate) -> BotProfile:
        now = _utc_now()
        profile = BotProfile(
            id=str(uuid.uuid4()),
            name=create.name,
            description=create.description,
            operating_style=create.operating_style,
            request=create.request,
            execution_mode=create.execution_mode,
            interval_minutes=create.interval_minutes,
            active=create.active,
            priority=create.priority,
            max_intents_per_run=create.max_intents_per_run,
            conflict_policy=create.conflict_policy,
            created_at=now,
            updated_at=now,
            next_run_at=now if create.active else _next_run_at(now, create.interval_minutes),
        )
        self._upsert_profile(profile)
        return profile

    def get_profile(self, bot_id: str) -> Optional[BotProfile]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM bot_profiles WHERE id = ?",
                (bot_id,),
            ).fetchone()
        if row is None:
            return None
        return BotProfile.model_validate_json(row["payload"])

    def list_profiles(self, limit: int = 50) -> List[BotProfile]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload
                FROM bot_profiles
                ORDER BY active DESC, priority DESC, next_run_at ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [BotProfile.model_validate_json(row["payload"]) for row in rows]

    def due_profiles(self, now: Optional[str] = None) -> List[BotProfile]:
        checked_at = now or _utc_now()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload
                FROM bot_profiles
                WHERE active = 1 AND next_run_at <= ?
                ORDER BY priority DESC, next_run_at ASC
                """,
                (checked_at,),
            ).fetchall()
        return [BotProfile.model_validate_json(row["payload"]) for row in rows]

    def save_run(self, run: BotRun) -> None:
        session_id = run.session.id if run.session is not None else None
        queued_count = run.queued.created if run.queued is not None else 0
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO bot_runs
                    (
                        id, bot_id, checked_at, status, symbol, strategy,
                        execution_mode, session_id, queued_count, payload
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    session_id = excluded.session_id,
                    queued_count = excluded.queued_count,
                    payload = excluded.payload
                """,
                (
                    run.id,
                    run.bot_id,
                    run.checked_at,
                    run.status,
                    run.request.symbol,
                    run.request.strategy,
                    run.execution_mode,
                    session_id,
                    queued_count,
                    run.model_dump_json(),
                ),
            )

    def list_runs(self, limit: int = 20) -> List[BotRun]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload
                FROM bot_runs
                ORDER BY checked_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [BotRun.model_validate_json(row["payload"]) for row in rows]

    def record_run(self, profile: BotProfile, run: BotRun) -> BotProfile:
        now = _utc_now()
        updated = profile.model_copy(
            update={
                "updated_at": now,
                "next_run_at": _next_run_at(now, profile.interval_minutes),
                "last_run_at": run.checked_at,
                "last_run_id": run.id,
                "last_session_id": run.session.id if run.session is not None else None,
                "last_status": run.status,
                "last_error": " ".join(run.errors) if run.errors else None,
            }
        )
        self._upsert_profile(updated)
        return updated

    def update_profile_active(self, profile: BotProfile, active: bool) -> BotProfile:
        now = _utc_now()
        updated = profile.model_copy(
            update={
                "active": active,
                "updated_at": now,
                "next_run_at": profile.next_run_at if active else _next_run_at(now, profile.interval_minutes),
            }
        )
        self._upsert_profile(updated)
        return updated

    def delete_profile(self, bot_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM bot_profiles WHERE id = ?", (bot_id,))
            return cursor.rowcount > 0

    def clear(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM bot_runs")
            conn.execute("DELETE FROM bot_profiles")

    def _upsert_profile(self, profile: BotProfile) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO bot_profiles
                    (
                        id, name, operating_style, symbol, source, strategy,
                        execution_mode, active, priority, next_run_at,
                        last_run_at, last_status, payload
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    operating_style = excluded.operating_style,
                    symbol = excluded.symbol,
                    source = excluded.source,
                    strategy = excluded.strategy,
                    execution_mode = excluded.execution_mode,
                    active = excluded.active,
                    priority = excluded.priority,
                    next_run_at = excluded.next_run_at,
                    last_run_at = excluded.last_run_at,
                    last_status = excluded.last_status,
                    payload = excluded.payload
                """,
                (
                    profile.id,
                    profile.name,
                    profile.operating_style,
                    profile.request.symbol,
                    profile.request.source,
                    profile.request.strategy,
                    profile.execution_mode,
                    1 if profile.active else 0,
                    profile.priority,
                    profile.next_run_at,
                    profile.last_run_at,
                    profile.last_status,
                    profile.model_dump_json(),
                ),
            )

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS bot_profiles (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    operating_style TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    source TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    execution_mode TEXT NOT NULL,
                    active INTEGER NOT NULL,
                    priority INTEGER NOT NULL,
                    next_run_at TEXT NOT NULL,
                    last_run_at TEXT,
                    last_status TEXT,
                    payload TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_bot_profiles_due
                ON bot_profiles(active, next_run_at ASC, priority DESC)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS bot_runs (
                    id TEXT PRIMARY KEY,
                    bot_id TEXT NOT NULL,
                    checked_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    execution_mode TEXT NOT NULL,
                    session_id TEXT,
                    queued_count INTEGER NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_bot_runs_checked_at
                ON bot_runs(checked_at DESC)
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn


class AlertReviewStore:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path) if db_path else default_database_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def save_acknowledgement(
        self,
        alert_id: str,
        request: AlertReviewAcknowledgeRequest,
    ) -> AlertReviewAcknowledgement:
        acknowledgement = AlertReviewAcknowledgement(
            alert_id=alert_id,
            status=request.status,
            acknowledged_at=_utc_now(),
            note=request.note,
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO alert_review_acknowledgements
                    (alert_id, status, acknowledged_at, note, payload)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(alert_id) DO UPDATE SET
                    status = excluded.status,
                    acknowledged_at = excluded.acknowledged_at,
                    note = excluded.note,
                    payload = excluded.payload
                """,
                (
                    acknowledgement.alert_id,
                    acknowledgement.status,
                    acknowledgement.acknowledged_at,
                    acknowledgement.note,
                    acknowledgement.model_dump_json(),
                ),
            )
        return acknowledgement

    def get_acknowledgement(
        self,
        alert_id: str,
    ) -> Optional[AlertReviewAcknowledgement]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM alert_review_acknowledgements WHERE alert_id = ?",
                (alert_id,),
            ).fetchone()
        if row is None:
            return None
        return AlertReviewAcknowledgement.model_validate_json(row["payload"])

    def clear(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM alert_review_acknowledgements")

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS alert_review_acknowledgements (
                    alert_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    acknowledged_at TEXT NOT NULL,
                    note TEXT,
                    payload TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn


class OperatorDecisionStore:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path) if db_path else default_database_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def save_decision(self, request: OperatorDecisionCreate) -> OperatorDecisionRecord:
        record = OperatorDecisionRecord(
            id=str(uuid.uuid4()),
            created_at=_utc_now(),
            decision_type=request.decision_type,
            target_id=request.target_id,
            status=request.status,
            note=request.note,
            context=request.context,
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO operator_decisions
                    (id, created_at, decision_type, target_id, status, note, payload)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.created_at,
                    record.decision_type,
                    record.target_id,
                    record.status,
                    record.note,
                    record.model_dump_json(),
                ),
            )
        return record

    def list_decisions(
        self,
        limit: int = 20,
        decision_type: Optional[str] = None,
        target_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[OperatorDecisionRecord]:
        conditions: List[str] = []
        params: List[object] = []
        if decision_type:
            conditions.append("decision_type = ?")
            params.append(decision_type)
        if target_id:
            conditions.append("target_id = ?")
            params.append(target_id)
        if status:
            conditions.append("status = ?")
            params.append(status)
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT payload
                FROM operator_decisions
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [OperatorDecisionRecord.model_validate_json(row["payload"]) for row in rows]

    def clear(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM operator_decisions")

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS operator_decisions (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    decision_type TEXT NOT NULL,
                    target_id TEXT,
                    status TEXT NOT NULL,
                    note TEXT,
                    payload TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_operator_decisions_created_at
                ON operator_decisions(created_at DESC)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_operator_decisions_target
                ON operator_decisions(decision_type, target_id, created_at DESC)
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn


class BrokerIntentEvaluationStore:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path) if db_path else default_database_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def save_evaluation(
        self,
        record: BrokerOrderIntentEvaluation,
    ) -> BrokerOrderIntentEvaluation:
        symbol = record.normalized_symbol or record.request.symbol.upper()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO broker_intent_evaluations
                    (id, checked_at, adapter_id, symbol, validation_status, submission_status, payload)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.checked_at,
                    record.adapter_id,
                    symbol,
                    record.validation_status,
                    record.submission_status,
                    record.model_dump_json(),
                ),
            )
        return record

    def list_evaluations(
        self,
        limit: int = 20,
        adapter_id: Optional[str] = None,
        symbol: Optional[str] = None,
        submission_status: Optional[str] = None,
    ) -> List[BrokerOrderIntentEvaluation]:
        conditions: List[str] = []
        params: List[object] = []
        if adapter_id:
            conditions.append("adapter_id = ?")
            params.append(adapter_id)
        if symbol:
            conditions.append("symbol = ?")
            params.append(symbol.upper())
        if submission_status:
            conditions.append("submission_status = ?")
            params.append(submission_status)
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT payload
                FROM broker_intent_evaluations
                {where_clause}
                ORDER BY checked_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [BrokerOrderIntentEvaluation.model_validate_json(row["payload"]) for row in rows]

    def get_evaluation(self, evaluation_id: str) -> Optional[BrokerOrderIntentEvaluation]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM broker_intent_evaluations WHERE id = ?",
                (evaluation_id,),
            ).fetchone()
        if row is None:
            return None
        return BrokerOrderIntentEvaluation.model_validate_json(row["payload"])

    def clear(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM broker_intent_evaluations")

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS broker_intent_evaluations (
                    id TEXT PRIMARY KEY,
                    checked_at TEXT NOT NULL,
                    adapter_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    validation_status TEXT NOT NULL,
                    submission_status TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_broker_intent_evaluations_checked_at
                ON broker_intent_evaluations(checked_at DESC)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_broker_intent_evaluations_symbol
                ON broker_intent_evaluations(symbol, checked_at DESC)
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn


class BrokerOrderReconciliationStore:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path) if db_path else default_database_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def save_reconciliation(
        self,
        record: BrokerOrderReconciliation,
    ) -> BrokerOrderReconciliation:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO broker_order_reconciliations
                    (id, checked_at, evaluation_id, adapter_id, status, broker_status, payload)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.checked_at,
                    record.evaluation_id,
                    record.adapter_id,
                    record.status,
                    record.broker_status,
                    record.model_dump_json(),
                ),
            )
        return record

    def list_reconciliations(
        self,
        evaluation_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[BrokerOrderReconciliation]:
        conditions: List[str] = []
        params: List[object] = []
        if evaluation_id:
            conditions.append("evaluation_id = ?")
            params.append(evaluation_id)
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT payload
                FROM broker_order_reconciliations
                {where_clause}
                ORDER BY checked_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [BrokerOrderReconciliation.model_validate_json(row["payload"]) for row in rows]

    def clear(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM broker_order_reconciliations")

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS broker_order_reconciliations (
                    id TEXT PRIMARY KEY,
                    checked_at TEXT NOT NULL,
                    evaluation_id TEXT NOT NULL,
                    adapter_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    broker_status TEXT,
                    payload TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_broker_order_reconciliations_evaluation
                ON broker_order_reconciliations(evaluation_id, checked_at DESC)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_broker_order_reconciliations_checked_at
                ON broker_order_reconciliations(checked_at DESC)
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn


class PaperFillOrderNoteStore:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path) if db_path else default_database_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def save_note(self, note: PaperFillOrderNote) -> PaperFillOrderNote:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO paper_fill_order_notes
                    (id, created_at, session_id, evaluation_id, adapter_id, symbol, payload)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(evaluation_id) DO UPDATE SET
                    created_at = excluded.created_at,
                    session_id = excluded.session_id,
                    adapter_id = excluded.adapter_id,
                    symbol = excluded.symbol,
                    payload = excluded.payload
                """,
                (
                    note.id,
                    note.created_at,
                    note.session_id,
                    note.evaluation_id,
                    note.adapter_id,
                    note.symbol,
                    note.model_dump_json(),
                ),
            )
        return note

    def list_notes(
        self,
        *,
        adapter_id: Optional[StockPaperBrokerAdapterId] = None,
        session_id: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 20,
    ) -> List[PaperFillOrderNote]:
        conditions: List[str] = []
        params: List[object] = []
        if adapter_id:
            conditions.append("adapter_id = ?")
            params.append(adapter_id)
        if session_id:
            conditions.append("session_id = ?")
            params.append(session_id)
        if symbol:
            conditions.append("symbol = ?")
            params.append(symbol.upper())
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT payload
                FROM paper_fill_order_notes
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [PaperFillOrderNote.model_validate_json(row["payload"]) for row in rows]

    def get_note_for_evaluation(self, evaluation_id: str) -> Optional[PaperFillOrderNote]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM paper_fill_order_notes WHERE evaluation_id = ?",
                (evaluation_id,),
            ).fetchone()
        if row is None:
            return None
        return PaperFillOrderNote.model_validate_json(row["payload"])

    def clear(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM paper_fill_order_notes")

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS paper_fill_order_notes (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    evaluation_id TEXT NOT NULL UNIQUE,
                    adapter_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_paper_fill_order_notes_session
                ON paper_fill_order_notes(session_id, created_at DESC)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_paper_fill_order_notes_symbol
                ON paper_fill_order_notes(symbol, created_at DESC)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_paper_fill_order_notes_adapter
                ON paper_fill_order_notes(adapter_id, created_at DESC)
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn


class OrderAuditStore:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path) if db_path else default_database_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def save_record(self, record: OrderAuditRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO order_audits
                    (
                        id, created_at, exchange, market, side,
                        ord_type, status, reason, payload
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    reason = excluded.reason,
                    payload = excluded.payload
                """,
                (
                    record.id,
                    record.created_at,
                    record.exchange,
                    record.market,
                    record.side,
                    record.ord_type,
                    record.status,
                    record.reason,
                    record.model_dump_json(),
                ),
            )

    def get_record(self, record_id: str) -> Optional[OrderAuditRecord]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM order_audits WHERE id = ?",
                (record_id,),
            ).fetchone()
        if row is None:
            return None
        return OrderAuditRecord.model_validate_json(row["payload"])

    def list_records(self, limit: int = 20) -> List[OrderAuditRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload
                FROM order_audits
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [OrderAuditRecord.model_validate_json(row["payload"]) for row in rows]

    def clear(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM order_audits")

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS order_audits (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    exchange TEXT NOT NULL,
                    market TEXT NOT NULL,
                    side TEXT NOT NULL,
                    ord_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_order_audits_created_at
                ON order_audits(created_at DESC)
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn


class ColumnarMarketDataStore:
    def __init__(
        self,
        db_path: Optional[Path] = None,
        parquet_path: Optional[Path] = None,
    ) -> None:
        self.db_path = Path(db_path) if db_path else default_columnar_database_path()
        self.parquet_path = (
            Path(parquet_path)
            if parquet_path
            else default_columnar_parquet_path(self.db_path)
        )
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.parquet_path.parent.mkdir(parents=True, exist_ok=True)
        self.last_exported_at: Optional[str] = None
        self.last_error: Optional[str] = None
        self._initialize()

    def save_candles(
        self,
        source: str,
        symbol: str,
        timeframe: str,
        candles: List[Candle],
        fetched_at: Optional[str] = None,
    ) -> None:
        if not candles:
            return

        resolved_fetched_at = fetched_at or _utc_now()
        rows = [
            (
                source,
                symbol,
                timeframe,
                candle.timestamp,
                candle.open,
                candle.high,
                candle.low,
                candle.close,
                candle.volume,
                resolved_fetched_at,
            )
            for candle in candles
        ]

        conn = self._connect()
        try:
            conn.execute("BEGIN TRANSACTION")
            conn.execute(
                """
                CREATE TEMP TABLE incoming_market_candles (
                    source VARCHAR NOT NULL,
                    symbol VARCHAR NOT NULL,
                    timeframe VARCHAR NOT NULL,
                    timestamp VARCHAR NOT NULL,
                    open DOUBLE NOT NULL,
                    high DOUBLE NOT NULL,
                    low DOUBLE NOT NULL,
                    close DOUBLE NOT NULL,
                    volume DOUBLE NOT NULL,
                    fetched_at VARCHAR NOT NULL
                )
                """
            )
            conn.executemany(
                """
                INSERT INTO incoming_market_candles
                    (
                        source, symbol, timeframe, timestamp,
                        open, high, low, close, volume, fetched_at
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.execute(
                """
                DELETE FROM market_candles AS existing
                USING incoming_market_candles AS incoming
                WHERE existing.source = incoming.source
                    AND existing.symbol = incoming.symbol
                    AND existing.timeframe = incoming.timeframe
                    AND existing.timestamp = incoming.timestamp
                """
            )
            conn.execute(
                """
                INSERT INTO market_candles
                    (
                        source, symbol, timeframe, timestamp,
                        open, high, low, close, volume, fetched_at
                    )
                SELECT
                    source, symbol, timeframe, timestamp,
                    open, high, low, close, volume, fetched_at
                FROM incoming_market_candles
                """
            )
            conn.execute("COMMIT")
            self.last_error = None
        except Exception as exc:
            conn.execute("ROLLBACK")
            self.last_error = str(exc)
            raise
        finally:
            conn.close()

    def status(self) -> MarketDataColumnarStatus:
        checked_at = _utc_now()
        conn = self._connect()
        try:
            rows = int(
                conn.execute("SELECT COUNT(*) FROM market_candles").fetchone()[0]
            )
            sources = self._distinct_values(conn, "source")
            symbols = self._distinct_values(conn, "symbol")
            timeframes = self._distinct_values(conn, "timeframe")
            last_fetched_at = conn.execute(
                "SELECT MAX(fetched_at) FROM market_candles"
            ).fetchone()[0]
            last_exported_at = self.last_exported_at
            if last_exported_at is None and self.parquet_path.exists():
                last_exported_at = datetime.fromtimestamp(
                    self.parquet_path.stat().st_mtime,
                    tz=timezone.utc,
                ).isoformat()
            self.last_error = None
            return MarketDataColumnarStatus(
                enabled=True,
                checked_at=checked_at,
                duckdb_path=str(self.db_path),
                parquet_path=str(self.parquet_path),
                rows=rows,
                sources=sources,
                symbols=symbols,
                timeframes=timeframes,
                last_fetched_at=last_fetched_at,
                last_exported_at=last_exported_at,
            )
        except Exception as exc:
            self.last_error = str(exc)
            return MarketDataColumnarStatus(
                enabled=False,
                checked_at=checked_at,
                duckdb_path=str(self.db_path),
                parquet_path=str(self.parquet_path),
                last_error=self.last_error,
            )
        finally:
            conn.close()

    def export_parquet(
        self,
        output_path: Optional[Path] = None,
        source: Optional[str] = None,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
    ) -> MarketDataColumnarExport:
        parquet_path = Path(output_path) if output_path else self.parquet_path
        parquet_path.parent.mkdir(parents=True, exist_ok=True)
        where_clauses: List[str] = []
        params: List[str] = []
        if source:
            where_clauses.append("source = ?")
            params.append(source)
        if symbol:
            where_clauses.append("symbol = ?")
            params.append(symbol)
        if timeframe:
            where_clauses.append("timeframe = ?")
            params.append(timeframe)
        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        conn = self._connect()
        try:
            conn.execute(
                f"""
                CREATE TEMP TABLE export_market_candles AS
                SELECT
                    source, symbol, timeframe, timestamp,
                    open, high, low, close, volume, fetched_at
                FROM market_candles
                {where_sql}
                ORDER BY source, symbol, timeframe, timestamp
                """,
                params,
            )
            rows = int(
                conn.execute("SELECT COUNT(*) FROM export_market_candles").fetchone()[0]
            )
            conn.execute(
                """
                COPY export_market_candles
                TO ?
                (FORMAT PARQUET)
                """,
                [str(parquet_path)],
            )
            exported_at = _utc_now()
            self.last_exported_at = exported_at
            self.last_error = None
            return MarketDataColumnarExport(
                exported_at=exported_at,
                duckdb_path=str(self.db_path),
                parquet_path=str(parquet_path),
                rows=rows,
                source=source,
                symbol=symbol,
                timeframe=timeframe,
            )
        except Exception as exc:
            self.last_error = str(exc)
            raise
        finally:
            conn.close()

    def clear(self) -> None:
        conn = self._connect()
        try:
            conn.execute("DELETE FROM market_candles")
        finally:
            conn.close()
        if self.parquet_path.exists():
            self.parquet_path.unlink()

    def _initialize(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS market_candles (
                    source VARCHAR NOT NULL,
                    symbol VARCHAR NOT NULL,
                    timeframe VARCHAR NOT NULL,
                    timestamp VARCHAR NOT NULL,
                    open DOUBLE NOT NULL,
                    high DOUBLE NOT NULL,
                    low DOUBLE NOT NULL,
                    close DOUBLE NOT NULL,
                    volume DOUBLE NOT NULL,
                    fetched_at VARCHAR NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_columnar_market_candles_key
                ON market_candles(source, symbol, timeframe, timestamp)
                """
            )
            self.last_error = None
        except Exception as exc:
            self.last_error = str(exc)
            raise
        finally:
            conn.close()

    def _connect(self):
        return _duckdb_module().connect(str(self.db_path))

    def _distinct_values(self, conn, column: str) -> List[str]:
        rows = conn.execute(
            f"SELECT DISTINCT {column} FROM market_candles ORDER BY {column}"
        ).fetchall()
        return [str(row[0]) for row in rows]


class MarketDataStore:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path) if db_path else default_database_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._columnar_error: Optional[str] = None
        self.columnar_store = self._create_columnar_store()
        self._initialize()

    def save_candles(
        self,
        source: str,
        symbol: str,
        timeframe: str,
        candles: List[Candle],
    ) -> None:
        if not candles:
            return

        fetched_at = _utc_now()
        rows = [
            (
                source,
                symbol,
                timeframe,
                candle.timestamp,
                candle.open,
                candle.high,
                candle.low,
                candle.close,
                candle.volume,
                fetched_at,
            )
            for candle in candles
        ]
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO market_candles
                    (
                        source, symbol, timeframe, timestamp,
                        open, high, low, close, volume, fetched_at
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, symbol, timeframe, timestamp) DO UPDATE SET
                    open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    volume = excluded.volume,
                    fetched_at = excluded.fetched_at
                """,
                rows,
            )
        if self.columnar_store is not None:
            try:
                self.columnar_store.save_candles(
                    source=source,
                    symbol=symbol,
                    timeframe=timeframe,
                    candles=candles,
                    fetched_at=fetched_at,
                )
                self._columnar_error = None
            except Exception as exc:
                self._columnar_error = str(exc)

    def get_candles(
        self,
        source: str,
        symbol: str,
        timeframe: str,
        limit: int,
        max_age_seconds: Optional[int] = DEFAULT_CANDLE_CACHE_TTL_SECONDS,
    ) -> List[Candle]:
        if limit <= 0:
            return []

        if max_age_seconds is not None and self._cache_is_stale(
            source=source,
            symbol=symbol,
            timeframe=timeframe,
            max_age_seconds=max_age_seconds,
        ):
            return []

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT timestamp, open, high, low, close, volume
                FROM market_candles
                WHERE source = ? AND symbol = ? AND timeframe = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (source, symbol, timeframe, limit),
            ).fetchall()

        candles = [
            Candle(
                timestamp=row["timestamp"],
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
            )
            for row in rows
        ]
        candles.reverse()
        return candles

    def clear(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM market_candles")
        if self.columnar_store is not None:
            self.columnar_store.clear()

    def columnar_status(self) -> MarketDataColumnarStatus:
        if self.columnar_store is not None:
            status = self.columnar_store.status()
            if self._columnar_error and not status.last_error:
                status.last_error = self._columnar_error
            return status

        duckdb_path = default_columnar_database_path(self.db_path)
        return MarketDataColumnarStatus(
            enabled=False,
            checked_at=_utc_now(),
            duckdb_path=str(duckdb_path),
            parquet_path=str(default_columnar_parquet_path(duckdb_path)),
            last_error=self._columnar_error,
        )

    def export_columnar_parquet(
        self,
        source: Optional[str] = None,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
    ) -> MarketDataColumnarExport:
        if self.columnar_store is None:
            reason = self._columnar_error or "Columnar candle cache is disabled."
            raise RuntimeError(reason)
        return self.columnar_store.export_parquet(
            source=source,
            symbol=symbol,
            timeframe=timeframe,
        )

    def _cache_is_stale(
        self,
        source: str,
        symbol: str,
        timeframe: str,
        max_age_seconds: int,
    ) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT MAX(fetched_at) AS fetched_at
                FROM market_candles
                WHERE source = ? AND symbol = ? AND timeframe = ?
                """,
                (source, symbol, timeframe),
            ).fetchone()

        if row is None or row["fetched_at"] is None:
            return True

        fetched_at = datetime.fromisoformat(row["fetched_at"])
        age = datetime.now(timezone.utc) - fetched_at
        return age.total_seconds() > max_age_seconds

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS market_candles (
                    source TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    fetched_at TEXT NOT NULL,
                    PRIMARY KEY (source, symbol, timeframe, timestamp)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_market_candles_lookup
                ON market_candles(source, symbol, timeframe, timestamp DESC)
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _create_columnar_store(self) -> Optional[ColumnarMarketDataStore]:
        if not _columnar_cache_enabled():
            self._columnar_error = "Columnar candle cache is disabled by configuration."
            return None
        try:
            return ColumnarMarketDataStore(
                db_path=default_columnar_database_path(self.db_path),
            )
        except Exception as exc:
            self._columnar_error = str(exc)
            return None


def _serialize_live_runtime(runtime: LivePaperRuntime) -> str:
    payload = {
        "candles": [candle.model_dump(mode="json") for candle in runtime.candles],
        "session": runtime.session.model_dump(mode="json"),
        "state": asdict(runtime.state),
        "mode": runtime.mode,
    }
    return json.dumps(payload, separators=(",", ":"))


def _deserialize_live_runtime(payload: str) -> LivePaperRuntime:
    data = json.loads(payload)
    session = LivePaperTradingSession.model_validate(data["session"])
    candles = [Candle.model_validate(item) for item in data["candles"]]
    state = PaperState(**data["state"])
    mode = data.get("mode", session.mode)
    return LivePaperRuntime(candles=candles, session=session, state=state, mode=mode)


def _load_backtest_run(payload: str) -> BacktestRun:
    data = json.loads(payload)
    run = BacktestRun.model_validate(data)
    metrics = data.get("metrics", {})
    if "strategy_edge_pct" not in metrics and run.candles:
        benchmark = compute_buy_and_hold_metrics(
            initial_equity=run.metrics.initial_equity,
            candles=run.candles,
            fee_bps=run.request.fee_bps,
            slippage_bps=run.request.slippage_bps,
            strategy_return_pct=run.metrics.total_return_pct,
        )
        run.metrics.buy_and_hold_final_equity = benchmark.final_equity
        run.metrics.buy_and_hold_return_pct = benchmark.return_pct
        run.metrics.buy_and_hold_max_drawdown_pct = benchmark.max_drawdown_pct
        run.metrics.strategy_edge_pct = benchmark.strategy_edge_pct
    return run


def _backtest_summary(run: BacktestRun) -> BacktestRunSummary:
    return BacktestRunSummary(
        id=run.id,
        created_at=run.created_at,
        request=run.request,
        metrics=run.metrics,
        warnings=run.warnings,
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
