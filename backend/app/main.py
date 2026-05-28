import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from .backtester import run_backtest
from .data import (
    MarketDataError,
    export_market_data_columnar_parquet,
    get_candles,
    get_market_data_columnar_status,
    get_market_data_provider_statuses,
    get_market_ticker,
)
from .execution import (
    approve_dry_run_order_intent,
    evaluate_broker_order_intent,
    get_broker_readiness,
    get_execution_settings,
    get_execution_status,
    get_order_precheck,
    get_private_snapshot,
    paper_to_live_adapter_profiles,
    paper_to_live_route,
    queue_strategy_order_intents,
    reconcile_broker_order_evaluation,
    submit_order_intent,
)
from .models import (
    AlertReviewAcknowledgeRequest,
    AlertReviewAcknowledgement,
    AlertReviewItem,
    AlertReviewResponse,
    BacktestRequest,
    BacktestRun,
    BacktestRunSummary,
    BacktestSweepCandidate,
    BacktestSweepRequest,
    BacktestSweepResponse,
    BacktestValidationRequest,
    BacktestValidationResponse,
    BacktestValidationSegment,
    BacktestWalkForwardFold,
    BacktestWalkForwardRequest,
    BacktestWalkForwardResponse,
    BrokerIntentEvaluationReport,
    BrokerOrderIntentEvaluation,
    BrokerOrderIntentRequest,
    BrokerOrderReconciliation,
    BrokerReadinessResponse,
    CryptoLiveBetaDrillReport,
    ExecutionRunbook,
    ExecutionSettings,
    ExecutionStatus,
    HealthResponse,
    LiveArmingSimulationChange,
    LiveArmingSimulationRequest,
    LiveArmingSimulationResponse,
    LiveReadinessBreakdown,
    LiveCutoverChecklistItem,
    LiveCutoverChecklistResponse,
    LiveCutoverRunbook,
    LiveReadinessCheck,
    LiveReadinessResponse,
    LivePaperTradingRequest,
    LivePaperTradingSession,
    MarketDefaults,
    MarketDataColumnarExport,
    MarketDataColumnarStatus,
    MarketDataProviderStatus,
    MarketTicker,
    OperatorDecisionCreate,
    OperatorDecisionRecord,
    OperatorDecisionReport,
    OrderApprovalRequest,
    OrderAuditRecord,
    OrderIntentRequest,
    OrderPrecheckResult,
    PaperAdvanceRequest,
    PaperFillOrderNote,
    PaperFillOrderNoteAnalytics,
    PaperFillOrderNoteDriftRow,
    PaperFillOrderNoteQualityGate,
    PaperFillOrderNoteQualityGateRow,
    PaperToLiveAdapterProfile,
    PaperToLiveHandoff,
    PaperToLiveRoute,
    PaperTradingRequest,
    PaperTradingSession,
    PostCutoverCloseoutReport,
    PostCutoverMonitorItem,
    PostCutoverOrderMonitor,
    OpsRunbookLink,
    OpsSelfCheckResponse,
    OpsLiveLockStatus,
    OpsSchedulerStatus,
    PortfolioPaperPromotionRequest,
    PortfolioPaperPromotionResponse,
    PortfolioPaperPromotionRules,
    PortfolioPaperSchedulerRun,
    PortfolioPaperWatchlistCreate,
    PortfolioPaperWatchlistItem,
    PortfolioPaperWatchlistRun,
    PortfolioResearchAlert,
    PortfolioResearchPreset,
    PortfolioResearchRequest,
    PortfolioResearchResponse,
    PortfolioResearchSchedulerRun,
    PortfolioResearchScan,
    PortfolioResearchScenario,
    PortfolioResearchScenarioCreate,
    PortfolioResearchWatchlistCreate,
    PortfolioResearchWatchlistItem,
    StrategyOrderQueueRequest,
    StrategyOrderQueueResponse,
    StrategyHealthHandoffReport,
    StrategyHealthMilestone,
    StrategyHealthTrace,
    StrategyHealthTraceResponse,
    StockEtfBrokerExpansionCandidate,
    StockEtfBrokerExpansionOrderPayload,
    StockEtfBrokerExpansionPackage,
    StockEtfBrokerExpansionPreflight,
    StockEtfBrokerExpansionPreflightCheck,
    StockEtfBrokerExpansionRehearsal,
    StockEtfBrokerExpansionRehearsalOrder,
    StockEtfBrokerExpansionReadiness,
    StockEtfBrokerExpansionReport,
    StockPaperBrokerAdapterId,
    UpbitPrivateSnapshot,
)
from .paper import (
    LivePaperRuntime,
    advance_live_paper_runtime,
    advance_live_paper_runtime_with_ticker,
    create_live_paper_runtime,
    create_ticker_paper_runtime,
    run_paper_session,
)
from .portfolio import portfolio_research_presets, run_portfolio_research
from .storage import (
    AlertReviewStore,
    BacktestRunStore,
    BrokerIntentEvaluationStore,
    BrokerOrderReconciliationStore,
    OperatorDecisionStore,
    OrderAuditStore,
    PaperFillOrderNoteStore,
    PortfolioPaperWatchlistStore,
    PortfolioScanStore,
    PortfolioScenarioStore,
    PortfolioWatchlistStore,
    SessionStore,
)


APP_VERSION = "0.1.0"

app = FastAPI(title="Quant Lab API", version=APP_VERSION)
backtest_run_store = BacktestRunStore()
order_audit_store = OrderAuditStore()
broker_intent_evaluation_store = BrokerIntentEvaluationStore()
broker_order_reconciliation_store = BrokerOrderReconciliationStore()
paper_fill_order_note_store = PaperFillOrderNoteStore()
portfolio_scenario_store = PortfolioScenarioStore()
portfolio_scan_store = PortfolioScanStore()
portfolio_watchlist_store = PortfolioWatchlistStore()
portfolio_paper_watchlist_store = PortfolioPaperWatchlistStore()
alert_review_store = AlertReviewStore()
operator_decision_store = OperatorDecisionStore()
session_store = SessionStore()
live_paper_runtimes = {
    runtime.session.id: runtime for runtime in session_store.list_live_runtimes(limit=200)
}

PAPER_FILL_GATE_DEFAULT_LIMIT = 200
PAPER_FILL_GATE_DEFAULT_MIN_NOTES = 3
PAPER_FILL_GATE_DEFAULT_MAX_AVG_ABS_DELTA_PCT = 0.35
PAPER_FILL_GATE_DEFAULT_MAX_WORST_ABS_DELTA_PCT = 1.0
PAPER_FILL_GATE_DEFAULT_REQUIRE_NO_EXTERNAL = True
_scheduler_stop = threading.Event()
_scheduler_thread: Optional[threading.Thread] = None
OPS_RUNBOOK_SPECS = [
    (
        "quant-lab-guide",
        "Quant Lab guide",
        "docs/quant-lab-guide.md",
        "Current runbook, boundaries, and recommended next work.",
    ),
    (
        "deployment-hardening",
        "Deployment hardening",
        "docs/deployment-hardening.md",
        "Docker Compose, health checks, backup/restore, and pre-market checklist.",
    ),
    (
        "production-observability",
        "Production observability",
        "docs/production-observability.md",
        "Daily cadence, alert review, scheduler triage, disk checks, and log retention.",
    ),
    (
        "release-readiness",
        "Release readiness",
        "docs/release-readiness.md",
        "Verification bundle, evidence archive, live flag lock check, and rollback notes.",
    ),
    (
        "completion-audit",
        "Completion audit",
        "docs/completion-audit.md",
        "Requirement-to-evidence map, verification status, boundaries, and remaining optional work.",
    ),
]


@app.on_event("startup")
def start_research_scheduler() -> None:
    global _scheduler_thread
    if not _research_scheduler_enabled():
        return
    if _scheduler_thread is not None and _scheduler_thread.is_alive():
        return
    _scheduler_stop.clear()
    _scheduler_thread = threading.Thread(
        target=_research_scheduler_loop,
        name="quant-lab-research-scheduler",
        daemon=True,
    )
    _scheduler_thread.start()


@app.on_event("shutdown")
def stop_research_scheduler() -> None:
    _scheduler_stop.set()
    if _scheduler_thread is not None:
        _scheduler_thread.join(timeout=2)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="quant-lab-api",
        version=APP_VERSION,
        note="Backtest MVP is available; live trading is intentionally disabled.",
    )


@app.get("/api/ops/self-check", response_model=OpsSelfCheckResponse)
def ops_self_check() -> OpsSelfCheckResponse:
    settings = get_execution_settings()
    duckdb_path = os.environ.get(
        "QUANT_LAB_DUCKDB_PATH",
        str(session_store.db_path.with_suffix(".duckdb")),
    )
    parquet_path = os.environ.get(
        "QUANT_LAB_CANDLE_PARQUET_PATH",
        str(session_store.db_path.parent / f"{session_store.db_path.stem}_market_candles.parquet"),
    )
    columnar_enabled = os.environ.get("QUANT_LAB_COLUMNAR_CACHE_ENABLED", "true").lower() not in {
        "0",
        "false",
        "no",
        "off",
        "disabled",
    }
    scheduler_thread_alive = bool(_scheduler_thread is not None and _scheduler_thread.is_alive())
    return OpsSelfCheckResponse(
        checked_at=datetime.now(timezone.utc).isoformat(),
        service="quant-lab-api",
        version=APP_VERSION,
        status="ok",
        database_path=str(session_store.db_path),
        duckdb_path=duckdb_path,
        parquet_path=parquet_path,
        columnar_cache_enabled=columnar_enabled,
        artifact_paths={
            "crypto_drills": "artifacts/crypto-drills",
            "ops_smoke": "artifacts/ops-smoke",
            "local_smoke": "artifacts/local-smoke",
            "verification": "artifacts/verification",
            "live_beta": "artifacts/live-beta",
            "backups": "backups",
        },
        scheduler=OpsSchedulerStatus(
            enabled=_research_scheduler_enabled(),
            thread_alive=scheduler_thread_alive,
            poll_seconds=_research_scheduler_poll_seconds(),
            stop_requested=_scheduler_stop.is_set(),
        ),
        live_lock=OpsLiveLockStatus(
            live_trading_enabled=settings.live_trading_enabled,
            live_ack_configured=settings.live_ack_configured,
            credential_configured=settings.credential_configured,
            adapter_ready=settings.adapter_ready,
            live_locked=not settings.adapter_ready,
            reason=settings.reason,
        ),
        runbooks=_ops_runbook_links(),
    )


@app.get("/api/ops/runbooks", response_model=list[OpsRunbookLink])
def list_ops_runbooks() -> list[OpsRunbookLink]:
    return _ops_runbook_links()


@app.get("/api/ops/runbooks/{runbook_id}", response_class=PlainTextResponse)
def get_ops_runbook(runbook_id: str) -> PlainTextResponse:
    spec = next((item for item in OPS_RUNBOOK_SPECS if item[0] == runbook_id), None)
    if spec is None:
        raise HTTPException(status_code=404, detail="Runbook not found")
    path = _project_root() / spec[2]
    if not path.exists():
        raise HTTPException(status_code=404, detail="Runbook file is not available")
    return PlainTextResponse(path.read_text(encoding="utf-8"))


def _project_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "docs").exists():
            return parent
    return current.parents[1]


def _ops_runbook_links() -> list[OpsRunbookLink]:
    return [
        OpsRunbookLink(
            id=runbook_id,
            title=title,
            path=path,
            api_path=f"/api/ops/runbooks/{runbook_id}",
            description=description,
        )
        for runbook_id, title, path, description in OPS_RUNBOOK_SPECS
    ]


@app.get("/api/alerts/review", response_model=AlertReviewResponse)
def alert_review_queue(
    include_acknowledged: bool = False,
    severity: Optional[str] = None,
    source: Optional[str] = None,
    scenario: Optional[str] = None,
) -> AlertReviewResponse:
    return _alert_review_queue(
        include_acknowledged=include_acknowledged,
        severity=severity,
        source=source,
        scenario=scenario,
    )


@app.post(
    "/api/alerts/review/{alert_id}/acknowledge",
    response_model=AlertReviewAcknowledgement,
)
def acknowledge_alert_review_item(
    alert_id: str,
    request: AlertReviewAcknowledgeRequest,
) -> AlertReviewAcknowledgement:
    return alert_review_store.save_acknowledgement(alert_id=alert_id, request=request)


@app.get("/api/readiness/live", response_model=LiveReadinessResponse)
def live_readiness() -> LiveReadinessResponse:
    return _live_readiness()


@app.get("/api/execution/cutover-checklist", response_model=LiveCutoverChecklistResponse)
def execution_cutover_checklist() -> LiveCutoverChecklistResponse:
    return _live_cutover_checklist()


@app.get("/api/execution/cutover-checklist/runbook", response_model=LiveCutoverRunbook)
def execution_cutover_runbook() -> LiveCutoverRunbook:
    return _cutover_runbook(_live_cutover_checklist())


@app.post(
    "/api/execution/cutover-checklist/simulate-arming",
    response_model=LiveArmingSimulationResponse,
)
def simulate_execution_cutover_arming(
    request: Optional[LiveArmingSimulationRequest] = None,
) -> LiveArmingSimulationResponse:
    return _simulate_live_arming(request or LiveArmingSimulationRequest())


@app.get("/api/operator/decisions", response_model=list[OperatorDecisionRecord])
def list_operator_decisions(
    decision_type: Optional[str] = None,
    target_id: Optional[str] = None,
    status: Optional[str] = None,
    route_status: Optional[str] = None,
    limit: int = 20,
) -> list[OperatorDecisionRecord]:
    safe_limit = min(max(limit, 1), 100)
    fetch_limit = 200 if route_status else safe_limit
    decisions = operator_decision_store.list_decisions(
        decision_type=decision_type,
        target_id=target_id,
        status=status,
        limit=fetch_limit,
    )
    if route_status:
        decisions = [
            decision
            for decision in decisions
            if decision.context.get("route_status") == route_status
        ]
    return decisions[:safe_limit]


@app.get("/api/research/strategy-health/traces", response_model=StrategyHealthTraceResponse)
def strategy_health_traces(limit: int = 20) -> StrategyHealthTraceResponse:
    return _strategy_health_traces(limit=min(max(limit, 1), 100))


@app.get(
    "/api/research/strategy-health/handoff-report",
    response_model=StrategyHealthHandoffReport,
)
def strategy_health_handoff_report(
    limit: int = 20,
    route_status: Optional[str] = None,
) -> StrategyHealthHandoffReport:
    return _strategy_health_handoff_report(
        limit=min(max(limit, 1), 100),
        route_status=route_status,
    )


@app.get(
    "/api/research/crypto-live-beta-drill/report",
    response_model=CryptoLiveBetaDrillReport,
)
def crypto_live_beta_drill_report(
    symbol: str = "KRW-BTC",
    limit: int = 5,
) -> CryptoLiveBetaDrillReport:
    normalized_symbol = symbol.strip().upper()
    if not normalized_symbol.startswith("KRW-"):
        raise HTTPException(status_code=400, detail="Crypto live beta drill requires a KRW-* market")
    return _crypto_live_beta_drill_report(
        symbol=normalized_symbol,
        limit=min(max(limit, 1), 20),
    )


@app.get(
    "/api/paper/stock-etf/broker-expansion-readiness",
    response_model=StockEtfBrokerExpansionReadiness,
)
def stock_etf_broker_expansion_readiness(limit: int = 20) -> StockEtfBrokerExpansionReadiness:
    return _stock_etf_broker_expansion_readiness(limit=min(max(limit, 1), 100))


@app.get(
    "/api/paper/stock-etf/broker-expansion-readiness/report",
    response_model=StockEtfBrokerExpansionReport,
)
def stock_etf_broker_expansion_readiness_report(
    limit: int = 50,
) -> StockEtfBrokerExpansionReport:
    readiness = _stock_etf_broker_expansion_readiness(limit=min(max(limit, 1), 200))
    return _stock_etf_broker_expansion_report(readiness)


@app.get(
    "/api/paper/stock-etf/broker-expansion-readiness/package/{decision_id}",
    response_model=StockEtfBrokerExpansionPackage,
)
def stock_etf_broker_expansion_package(decision_id: str) -> StockEtfBrokerExpansionPackage:
    try:
        return _stock_etf_broker_expansion_package(decision_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get(
    "/api/paper/stock-etf/broker-expansion-readiness/package/{decision_id}/preflight",
    response_model=StockEtfBrokerExpansionPreflight,
)
def stock_etf_broker_expansion_preflight(decision_id: str) -> StockEtfBrokerExpansionPreflight:
    try:
        return _stock_etf_broker_expansion_preflight(decision_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get(
    "/api/paper/stock-etf/broker-expansion-readiness/package/{decision_id}/rehearsal",
    response_model=StockEtfBrokerExpansionRehearsal,
)
def stock_etf_broker_expansion_rehearsal(decision_id: str) -> StockEtfBrokerExpansionRehearsal:
    try:
        return _stock_etf_broker_expansion_rehearsal(decision_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/operator/decisions/report", response_model=OperatorDecisionReport)
def get_operator_decision_report(
    decision_type: Optional[str] = None,
    target_id: Optional[str] = None,
    status: Optional[str] = None,
    route_status: Optional[str] = None,
    limit: int = 100,
) -> OperatorDecisionReport:
    safe_limit = min(max(limit, 1), 200)
    fetch_limit = 500 if route_status else safe_limit
    decisions = operator_decision_store.list_decisions(
        decision_type=decision_type,
        target_id=target_id,
        status=status,
        limit=fetch_limit,
    )
    if route_status:
        decisions = [
            decision
            for decision in decisions
            if decision.context.get("route_status") == route_status
        ][:safe_limit]
    return _operator_decision_report(
        decisions=decisions,
        decision_type=decision_type,
        target_id=target_id,
        status=status,
        route_status=route_status,
    )


@app.post("/api/operator/decisions", response_model=OperatorDecisionRecord)
def create_operator_decision(
    request: OperatorDecisionCreate,
) -> OperatorDecisionRecord:
    try:
        checked_request = _operator_decision_with_paper_fill_quality_gate(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return operator_decision_store.save_decision(checked_request)


@app.get("/api/markets/defaults", response_model=MarketDefaults)
def market_defaults() -> MarketDefaults:
    return MarketDefaults(
        symbols=["KRW-BTC", "KRW-ETH", "KRW-SOL", "SPY", "QQQ", "AAPL", "MSFT", "NVDA"],
        timeframes=["day", "minute60"],
        strategies=["sma_crossover", "donchian_breakout", "rsi_mean_reversion"],
        default_request=BacktestRequest(),
    )


@app.get("/api/markets/ticker", response_model=MarketTicker)
def market_ticker(symbol: str = "KRW-BTC", source: str = "sample") -> MarketTicker:
    try:
        return get_market_ticker(symbol=symbol, source=source)
    except MarketDataError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/markets/providers/status", response_model=list[MarketDataProviderStatus])
def market_data_provider_status() -> list[MarketDataProviderStatus]:
    return get_market_data_provider_statuses()


@app.get(
    "/api/markets/cache/columnar/status",
    response_model=MarketDataColumnarStatus,
)
def market_data_columnar_status() -> MarketDataColumnarStatus:
    return get_market_data_columnar_status()


@app.post(
    "/api/markets/cache/columnar/export",
    response_model=MarketDataColumnarExport,
)
def export_market_data_columnar_cache(
    source: Optional[str] = None,
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
) -> MarketDataColumnarExport:
    try:
        return export_market_data_columnar_parquet(
            source=source,
            symbol=symbol,
            timeframe=timeframe,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/backtests/run", response_model=BacktestRun)
def run_backtest_endpoint(request: BacktestRequest) -> BacktestRun:
    try:
        candles = get_candles(
            symbol=request.symbol,
            timeframe=request.timeframe,
            source=request.source,
            limit=request.candle_limit,
        )
        result = run_backtest(request=request, candles=candles)
    except (MarketDataError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if request.source == "sample":
        result.warnings.append(
            "Using deterministic sample candles. Switch source to upbit for public KRW market data."
        )
    if request.source == "sample_us":
        result.warnings.append(
            "Using deterministic US stock/ETF sample candles. This is for paper trading research only."
        )
    if request.source == "alpha_vantage":
        result.warnings.append(
            "Using Alpha Vantage compact daily stock/ETF candles. Paper trading only."
        )
        if len(candles) < request.candle_limit:
            result.warnings.append(
                f"Alpha Vantage compact daily data returned {len(candles)} rows for this request."
            )
    if request.source == "upbit" and request.candle_limit > 200:
        result.warnings.append("Upbit public candle endpoint is capped to 200 rows per call.")
    return backtest_run_store.save_run(result)


@app.post("/api/backtests/sweep", response_model=BacktestSweepResponse)
def run_backtest_sweep_endpoint(request: BacktestSweepRequest) -> BacktestSweepResponse:
    try:
        return _run_backtest_sweep(request)
    except (MarketDataError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/backtests/validate", response_model=BacktestValidationResponse)
def validate_backtest_endpoint(
    request: BacktestValidationRequest,
) -> BacktestValidationResponse:
    try:
        return _validate_backtest_split(request)
    except (MarketDataError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/backtests/walk-forward", response_model=BacktestWalkForwardResponse)
def walk_forward_backtest_endpoint(
    request: BacktestWalkForwardRequest,
) -> BacktestWalkForwardResponse:
    try:
        return _walk_forward_backtest(request)
    except (MarketDataError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/backtests/runs", response_model=list[BacktestRunSummary])
def list_backtest_runs() -> list[BacktestRunSummary]:
    return backtest_run_store.list_summaries(limit=20)


@app.get("/api/backtests/runs/{run_id}", response_model=BacktestRun)
def get_backtest_run(run_id: str) -> BacktestRun:
    run = backtest_run_store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Backtest run not found")
    return run


def _run_backtest_sweep(request: BacktestSweepRequest) -> BacktestSweepResponse:
    candles = get_candles(
        symbol=request.symbol,
        timeframe=request.timeframe,
        source=request.source,
        limit=request.candle_limit,
    )
    candidate_params = _backtest_sweep_candidates(request)
    scored: list[BacktestSweepCandidate] = []
    warnings: list[str] = []

    for params in candidate_params:
        candidate_request = BacktestRequest(
            symbol=request.symbol,
            timeframe=request.timeframe,
            source=request.source,
            strategy=request.strategy,
            initial_cash=request.initial_cash,
            fee_bps=request.fee_bps,
            slippage_bps=request.slippage_bps,
            candle_limit=request.candle_limit,
            params=params,
        )
        try:
            result = run_backtest(request=candidate_request, candles=candles)
        except ValueError as exc:
            warnings.append(f"Skipped {params}: {exc}")
            continue

        scored.append(
            BacktestSweepCandidate(
                rank=0,
                score=_backtest_sweep_score(result.metrics),
                params=params,
                metrics=result.metrics,
                trades=len(result.trades),
                warnings=result.warnings,
            )
        )

    if not scored:
        raise ValueError("No valid backtest sweep candidates were available.")

    ranked = [
        candidate.model_copy(update={"rank": index + 1})
        for index, candidate in enumerate(
            sorted(scored, key=lambda item: item.score, reverse=True)
        )
    ]
    warnings.extend(_backtest_source_warnings(request, candles, label="Sweep"))
    return BacktestSweepResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        request=request.model_copy(update={"candidates": candidate_params}),
        candidates=ranked,
        best=ranked[0],
        warnings=warnings,
    )


def _backtest_sweep_candidates(request: BacktestSweepRequest) -> list[dict[str, float]]:
    candidates = request.candidates or _default_backtest_sweep_candidates(request)
    deduped: list[dict[str, float]] = []
    seen: set[str] = set()
    for params in [request.params, *candidates]:
        normalized = {
            key: float(value) if isinstance(value, float) else int(value)
            for key, value in sorted(params.items())
        }
        key = json.dumps(normalized, sort_keys=True)
        if key not in seen:
            seen.add(key)
            deduped.append(normalized)
    return deduped[:16]


def _default_backtest_sweep_candidates(request: BacktestSweepRequest) -> list[dict[str, float]]:
    if request.strategy == "sma_crossover":
        return [
            {"fast_window": 8, "slow_window": 24},
            {"fast_window": 10, "slow_window": 30},
            {"fast_window": 12, "slow_window": 36},
            {"fast_window": 15, "slow_window": 45},
        ]
    if request.strategy == "donchian_breakout":
        return [
            {"lookback": 15, "exit_lookback": 7},
            {"lookback": 20, "exit_lookback": 10},
            {"lookback": 30, "exit_lookback": 15},
            {"lookback": 40, "exit_lookback": 20},
        ]
    return [
        {"rsi_window": 10, "buy_below": 30, "sell_above": 55},
        {"rsi_window": 14, "buy_below": 30, "sell_above": 55},
        {"rsi_window": 14, "buy_below": 35, "sell_above": 58},
        {"rsi_window": 21, "buy_below": 35, "sell_above": 60},
    ]


def _backtest_sweep_score(metrics) -> float:
    score = (
        metrics.strategy_edge_pct
        + metrics.sharpe * 2
        + metrics.total_return_pct * 0.25
        + metrics.max_drawdown_pct * 0.25
    )
    return round(score, 4)


def _backtest_source_warnings(
    request: BacktestRequest,
    candles: list,
    label: str,
) -> list[str]:
    if request.source == "sample":
        return [f"{label} uses deterministic local crypto candles."]
    if request.source == "sample_us":
        return [f"{label} uses deterministic US stock/ETF sample candles for paper research."]
    if request.source == "alpha_vantage":
        warnings = [f"{label} uses Alpha Vantage compact daily stock/ETF candles; paper only."]
        if len(candles) < request.candle_limit:
            warnings.append(
                f"Alpha Vantage compact daily data returned {len(candles)} rows for this request."
            )
        return warnings
    if request.source == "upbit" and request.candle_limit > 200:
        return ["Upbit public candle endpoint is capped to 200 rows per call."]
    return []


def _validate_backtest_split(
    request: BacktestValidationRequest,
) -> BacktestValidationResponse:
    candles = sorted(
        get_candles(
            symbol=request.symbol,
            timeframe=request.timeframe,
            source=request.source,
            limit=request.candle_limit,
        ),
        key=lambda candle: candle.timestamp,
    )
    if len(candles) < 50:
        raise ValueError("Validation requires at least 50 candles.")

    split_index = int(len(candles) * request.train_fraction)
    split_index = min(max(split_index, 2), len(candles) - 2)
    train_candles = candles[:split_index]
    test_candles = candles[split_index:]

    train_request = BacktestRequest(
        symbol=request.symbol,
        timeframe=request.timeframe,
        source=request.source,
        strategy=request.strategy,
        initial_cash=request.initial_cash,
        fee_bps=request.fee_bps,
        slippage_bps=request.slippage_bps,
        candle_limit=len(train_candles),
        params=request.params,
    )
    test_request = train_request.model_copy(update={"candle_limit": len(test_candles)})

    train_result = run_backtest(request=train_request, candles=train_candles)
    test_result = run_backtest(request=test_request, candles=test_candles)
    edge_gap = round(
        train_result.metrics.strategy_edge_pct - test_result.metrics.strategy_edge_pct,
        4,
    )
    return_gap = round(
        train_result.metrics.total_return_pct - test_result.metrics.total_return_pct,
        4,
    )
    robustness_score = _validation_robustness_score(
        test_metrics=test_result.metrics,
        edge_gap_pct=edge_gap,
    )
    verdict, reason = _validation_verdict(
        test_edge_pct=test_result.metrics.strategy_edge_pct,
        test_return_pct=test_result.metrics.total_return_pct,
        test_drawdown_pct=test_result.metrics.max_drawdown_pct,
        edge_gap_pct=edge_gap,
    )
    warnings = _backtest_source_warnings(request, candles, label="Validation")
    if len(test_candles) < 60:
        warnings.append("Test split has fewer than 60 candles; treat validation as provisional.")

    return BacktestValidationResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        request=request,
        total_candles=len(candles),
        train=_validation_segment("train", train_candles, train_result),
        test=_validation_segment("test", test_candles, test_result),
        edge_gap_pct=edge_gap,
        return_gap_pct=return_gap,
        robustness_score=robustness_score,
        verdict=verdict,
        reason=reason,
        warnings=warnings,
    )


def _validation_segment(
    label: Literal["train", "test"],
    candles: list,
    result,
) -> BacktestValidationSegment:
    return BacktestValidationSegment(
        label=label,
        candle_count=len(candles),
        start_timestamp=candles[0].timestamp,
        end_timestamp=candles[-1].timestamp,
        metrics=result.metrics,
        trades=len(result.trades),
    )


def _validation_verdict(
    test_edge_pct: float,
    test_return_pct: float,
    test_drawdown_pct: float,
    edge_gap_pct: float,
) -> tuple[Literal["pass", "watch", "fail"], str]:
    if test_return_pct < 0 or test_edge_pct < -2 or test_drawdown_pct < -25:
        return (
            "fail",
            "Test split performance is negative or drawdown breached the validation guardrail.",
        )
    if edge_gap_pct > 15 or test_edge_pct < 0:
        return (
            "watch",
            "Train/test edge gap is wide or test split edge is not yet positive.",
        )
    return (
        "pass",
        "Test split retained positive return and edge without a large train/test gap.",
    )


def _walk_forward_backtest(
    request: BacktestWalkForwardRequest,
) -> BacktestWalkForwardResponse:
    candles = sorted(
        get_candles(
            symbol=request.symbol,
            timeframe=request.timeframe,
            source=request.source,
            limit=request.candle_limit,
        ),
        key=lambda candle: candle.timestamp,
    )
    required = request.train_window + request.test_window
    if len(candles) < required:
        raise ValueError("Walk-forward validation requires enough candles for one train/test fold.")

    folds: list[BacktestWalkForwardFold] = []
    last_start = len(candles) - required
    for fold_index, start in enumerate(range(0, last_start + 1, request.step_size), start=1):
        train_candles = candles[start : start + request.train_window]
        test_candles = candles[
            start + request.train_window : start + request.train_window + request.test_window
        ]
        train_request = BacktestRequest(
            symbol=request.symbol,
            timeframe=request.timeframe,
            source=request.source,
            strategy=request.strategy,
            initial_cash=request.initial_cash,
            fee_bps=request.fee_bps,
            slippage_bps=request.slippage_bps,
            candle_limit=len(train_candles),
            params=request.params,
        )
        test_request = train_request.model_copy(update={"candle_limit": len(test_candles)})
        train_result = run_backtest(request=train_request, candles=train_candles)
        test_result = run_backtest(request=test_request, candles=test_candles)
        edge_gap = round(
            train_result.metrics.strategy_edge_pct - test_result.metrics.strategy_edge_pct,
            4,
        )
        return_gap = round(
            train_result.metrics.total_return_pct - test_result.metrics.total_return_pct,
            4,
        )
        robustness_score = _validation_robustness_score(
            test_metrics=test_result.metrics,
            edge_gap_pct=edge_gap,
        )
        verdict, reason = _validation_verdict(
            test_edge_pct=test_result.metrics.strategy_edge_pct,
            test_return_pct=test_result.metrics.total_return_pct,
            test_drawdown_pct=test_result.metrics.max_drawdown_pct,
            edge_gap_pct=edge_gap,
        )
        folds.append(
            BacktestWalkForwardFold(
                index=fold_index,
                train=_validation_segment("train", train_candles, train_result),
                test=_validation_segment("test", test_candles, test_result),
                edge_gap_pct=edge_gap,
                return_gap_pct=return_gap,
                robustness_score=robustness_score,
                verdict=verdict,
                reason=reason,
            )
        )

    pass_count = sum(1 for fold in folds if fold.verdict == "pass")
    watch_count = sum(1 for fold in folds if fold.verdict == "watch")
    fail_count = sum(1 for fold in folds if fold.verdict == "fail")
    average_return = round(
        sum(fold.test.metrics.total_return_pct for fold in folds) / len(folds),
        4,
    )
    average_edge = round(
        sum(fold.test.metrics.strategy_edge_pct for fold in folds) / len(folds),
        4,
    )
    average_score = round(
        sum(fold.robustness_score for fold in folds) / len(folds),
        4,
    )
    verdict, reason = _walk_forward_verdict(
        pass_count=pass_count,
        watch_count=watch_count,
        fail_count=fail_count,
        average_test_return_pct=average_return,
        average_test_edge_pct=average_edge,
    )
    warnings = _backtest_source_warnings(request, candles, label="Walk-forward")
    if len(folds) < 3:
        warnings.append("Fewer than three walk-forward folds were available; treat verdict as provisional.")

    return BacktestWalkForwardResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        request=request,
        total_candles=len(candles),
        folds=folds,
        pass_count=pass_count,
        watch_count=watch_count,
        fail_count=fail_count,
        average_test_return_pct=average_return,
        average_test_edge_pct=average_edge,
        average_robustness_score=average_score,
        verdict=verdict,
        reason=reason,
        warnings=warnings,
    )


def _validation_robustness_score(test_metrics, edge_gap_pct: float) -> float:
    return round(
        test_metrics.strategy_edge_pct
        + test_metrics.sharpe
        - max(0.0, edge_gap_pct) * 0.5
        + test_metrics.max_drawdown_pct * 0.1,
        4,
    )


def _walk_forward_verdict(
    pass_count: int,
    watch_count: int,
    fail_count: int,
    average_test_return_pct: float,
    average_test_edge_pct: float,
) -> tuple[Literal["pass", "watch", "fail"], str]:
    if fail_count > 0 or average_test_return_pct < 0:
        return (
            "fail",
            "At least one walk-forward fold failed or average test return is negative.",
        )
    if watch_count > 0 or average_test_edge_pct < 0:
        return (
            "watch",
            "Some folds need review or average out-of-sample edge is not positive.",
        )
    return (
        "pass",
        "All walk-forward folds retained positive out-of-sample behavior.",
    )


@app.post("/api/research/portfolio", response_model=PortfolioResearchResponse)
def run_portfolio_research_endpoint(
    request: PortfolioResearchRequest,
) -> PortfolioResearchResponse:
    try:
        return _run_portfolio_research_request(request)
    except (MarketDataError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _run_portfolio_research_request(
    request: PortfolioResearchRequest,
) -> PortfolioResearchResponse:
    try:
        symbols = []
        seen = set()
        for symbol in request.symbols:
            normalized = symbol.strip().upper()
            if normalized and normalized not in seen:
                seen.add(normalized)
                symbols.append(normalized)
        candles_by_symbol = {
            symbol: get_candles(
                symbol=symbol,
                timeframe=request.timeframe,
                source=request.source,
                limit=request.candle_limit,
            )
            for symbol in symbols
        }
        result = run_portfolio_research(
            request=request.model_copy(update={"symbols": symbols}),
            candles_by_symbol=candles_by_symbol,
        )
    except (MarketDataError, ValueError):
        raise

    if request.source == "sample_us":
        result.warnings.append(
            "Portfolio research uses deterministic US stock/ETF sample candles."
        )
    if request.source == "alpha_vantage":
        result.warnings.append(
            "Portfolio research uses Alpha Vantage compact daily data and remains paper-only."
        )
    if request.source == "sample":
        result.warnings.append(
            "Portfolio research uses deterministic local crypto candles."
        )
    if request.source == "upbit":
        result.warnings.append(
            "Portfolio research uses Upbit public candles only; no execution is performed."
        )
    return result


@app.get(
    "/api/research/portfolio/presets",
    response_model=list[PortfolioResearchPreset],
)
def list_portfolio_research_presets() -> list[PortfolioResearchPreset]:
    return portfolio_research_presets()


@app.post(
    "/api/research/portfolio/scenarios",
    response_model=PortfolioResearchScenario,
)
def create_portfolio_research_scenario(
    request: PortfolioResearchScenarioCreate,
) -> PortfolioResearchScenario:
    return portfolio_scenario_store.save_scenario(request)


@app.get(
    "/api/research/portfolio/scenarios",
    response_model=list[PortfolioResearchScenario],
)
def list_portfolio_research_scenarios() -> list[PortfolioResearchScenario]:
    return portfolio_scenario_store.list_scenarios(limit=20)


@app.get(
    "/api/research/portfolio/scenarios/{scenario_id}",
    response_model=PortfolioResearchScenario,
)
def get_portfolio_research_scenario(scenario_id: str) -> PortfolioResearchScenario:
    scenario = portfolio_scenario_store.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Portfolio scenario not found")
    return scenario


@app.delete("/api/research/portfolio/scenarios/{scenario_id}")
def delete_portfolio_research_scenario(scenario_id: str) -> dict[str, str]:
    deleted = portfolio_scenario_store.delete_scenario(scenario_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Portfolio scenario not found")
    portfolio_watchlist_store.delete_for_scenario(scenario_id)
    portfolio_paper_watchlist_store.delete_for_scenario(scenario_id)
    return {"status": "deleted", "id": scenario_id}


@app.get(
    "/api/research/portfolio/watchlist",
    response_model=list[PortfolioResearchWatchlistItem],
)
def list_portfolio_research_watchlist() -> list[PortfolioResearchWatchlistItem]:
    return portfolio_watchlist_store.list_items(limit=50)


@app.post(
    "/api/research/portfolio/watchlist",
    response_model=PortfolioResearchWatchlistItem,
)
def create_portfolio_research_watchlist_item(
    request: PortfolioResearchWatchlistCreate,
) -> PortfolioResearchWatchlistItem:
    scenario = portfolio_scenario_store.get_scenario(request.scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Portfolio scenario not found")
    return portfolio_watchlist_store.save_item(create=request, scenario=scenario)


@app.post(
    "/api/research/portfolio/watchlist/run-due",
    response_model=PortfolioResearchSchedulerRun,
)
def run_due_portfolio_research_watchlist() -> PortfolioResearchSchedulerRun:
    return _run_due_portfolio_watchlist()


@app.delete("/api/research/portfolio/watchlist/{item_id}")
def delete_portfolio_research_watchlist_item(item_id: str) -> dict[str, str]:
    deleted = portfolio_watchlist_store.delete_item(item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Portfolio watchlist item not found")
    return {"status": "deleted", "id": item_id}


@app.post(
    "/api/research/portfolio/scenarios/{scenario_id}/scan",
    response_model=PortfolioResearchScan,
)
def scan_portfolio_research_scenario(scenario_id: str) -> PortfolioResearchScan:
    scenario = portfolio_scenario_store.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Portfolio scenario not found")
    try:
        result = _run_portfolio_research_request(scenario.request)
    except (MarketDataError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return portfolio_scan_store.save_scan(scenario=scenario, result=result)


@app.get(
    "/api/research/portfolio/scans",
    response_model=list[PortfolioResearchScan],
)
def list_portfolio_research_scans() -> list[PortfolioResearchScan]:
    return portfolio_scan_store.list_scans(limit=20)


@app.get(
    "/api/research/portfolio/scans/{scan_id}",
    response_model=PortfolioResearchScan,
)
def get_portfolio_research_scan(scan_id: str) -> PortfolioResearchScan:
    scan = portfolio_scan_store.get_scan(scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Portfolio scan not found")
    return scan


@app.get("/api/execution/status", response_model=ExecutionStatus)
def execution_status() -> ExecutionStatus:
    return get_execution_status()


@app.get("/api/execution/settings", response_model=ExecutionSettings)
def execution_settings() -> ExecutionSettings:
    return get_execution_settings()


@app.get(
    "/api/execution/paper-live-adapters",
    response_model=list[PaperToLiveAdapterProfile],
)
def execution_paper_live_adapters() -> list[PaperToLiveAdapterProfile]:
    return paper_to_live_adapter_profiles()


@app.get("/api/execution/broker-readiness", response_model=BrokerReadinessResponse)
def execution_broker_readiness() -> BrokerReadinessResponse:
    return get_broker_readiness()


@app.post(
    "/api/execution/broker-intents/evaluate",
    response_model=BrokerOrderIntentEvaluation,
)
def execution_broker_intent_evaluation(
    request: BrokerOrderIntentRequest,
) -> BrokerOrderIntentEvaluation:
    try:
        linked_session: Optional[PaperTradingSession] = None
        if request.paper_session_id:
            linked_session = session_store.get_paper_session(request.paper_session_id)
            if linked_session is None:
                raise HTTPException(status_code=404, detail="Paper session not found")
            if linked_session.request.symbol.upper() != request.symbol.strip().upper():
                raise HTTPException(
                    status_code=400,
                    detail="Broker intent symbol must match the linked paper session symbol.",
                )
        evaluation = evaluate_broker_order_intent(request)
        saved_evaluation = broker_intent_evaluation_store.save_evaluation(evaluation)
        if linked_session is not None:
            note = _paper_fill_order_note_from_evaluation(
                evaluation=saved_evaluation,
                session=linked_session,
            )
            if note is not None:
                paper_fill_order_note_store.save_note(note)
        return saved_evaluation
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get(
    "/api/execution/broker-intents/evaluations",
    response_model=list[BrokerOrderIntentEvaluation],
)
def list_execution_broker_intent_evaluations(
    adapter_id: Optional[StockPaperBrokerAdapterId] = None,
    symbol: Optional[str] = None,
    submission_status: Optional[str] = None,
    limit: int = 20,
) -> list[BrokerOrderIntentEvaluation]:
    safe_limit = min(max(limit, 1), 100)
    return broker_intent_evaluation_store.list_evaluations(
        adapter_id=adapter_id,
        symbol=symbol,
        submission_status=submission_status,
        limit=safe_limit,
    )


@app.get(
    "/api/execution/broker-intents/evaluations/{evaluation_id}/reconcile",
    response_model=BrokerOrderReconciliation,
)
def reconcile_execution_broker_intent_evaluation(
    evaluation_id: str,
) -> BrokerOrderReconciliation:
    evaluation = broker_intent_evaluation_store.get_evaluation(evaluation_id)
    if evaluation is None:
        raise HTTPException(status_code=404, detail="Broker intent evaluation not found")
    reconciliation = reconcile_broker_order_evaluation(evaluation)
    reconciliation = _attach_paper_fill_reconciliation(reconciliation)
    return broker_order_reconciliation_store.save_reconciliation(reconciliation)


def _attach_paper_fill_reconciliation(
    reconciliation: BrokerOrderReconciliation,
) -> BrokerOrderReconciliation:
    note = paper_fill_order_note_store.get_note_for_evaluation(reconciliation.evaluation_id)
    if note is None:
        return reconciliation

    price_delta = None
    price_delta_pct = None
    if reconciliation.broker_avg_fill_price is not None:
        price_delta = reconciliation.broker_avg_fill_price - note.intended_fill_price
        if note.intended_fill_price:
            price_delta_pct = (price_delta / note.intended_fill_price) * 100

    notional_delta = (
        reconciliation.broker_filled_notional - note.intended_notional
        if reconciliation.broker_filled_notional is not None
        else None
    )
    fee_delta = (
        reconciliation.broker_fee - note.intended_fee
        if reconciliation.broker_fee is not None
        else None
    )
    if reconciliation.broker_avg_fill_price is None:
        comparison_status = "missing_broker_fill"
    elif reconciliation.broker_partial_fill:
        comparison_status = "partial_fill"
    elif (
        price_delta_pct is not None
        and abs(price_delta_pct) > PAPER_FILL_GATE_DEFAULT_MAX_WORST_ABS_DELTA_PCT
    ):
        comparison_status = "drift"
    else:
        comparison_status = "matched"

    return reconciliation.model_copy(
        update={
            "linked_paper_fill_note_id": note.id,
            "paper_fill_comparison_status": comparison_status,
            "paper_fill_price_delta": price_delta,
            "paper_fill_price_delta_pct": price_delta_pct,
            "paper_fill_notional_delta": notional_delta,
            "paper_fill_fee_delta": fee_delta,
        }
    )


@app.get(
    "/api/execution/broker-intents/evaluations/report",
    response_model=BrokerIntentEvaluationReport,
)
def get_execution_broker_intent_evaluation_report(
    adapter_id: Optional[StockPaperBrokerAdapterId] = None,
    symbol: Optional[str] = None,
    submission_status: Optional[str] = None,
    limit: int = 50,
) -> BrokerIntentEvaluationReport:
    safe_limit = min(max(limit, 1), 200)
    evaluations = broker_intent_evaluation_store.list_evaluations(
        adapter_id=adapter_id,
        symbol=symbol,
        submission_status=submission_status,
        limit=safe_limit,
    )
    return _broker_intent_evaluation_report(
        evaluations=evaluations,
        adapter_id=adapter_id,
        symbol=symbol,
        submission_status=submission_status,
    )


@app.get(
    "/api/paper/sessions/{session_id}/order-notes",
    response_model=list[PaperFillOrderNote],
)
def list_paper_session_order_notes(session_id: str, limit: int = 20) -> list[PaperFillOrderNote]:
    if session_store.get_paper_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Paper session not found")
    safe_limit = min(max(limit, 1), 100)
    return paper_fill_order_note_store.list_notes(session_id=session_id, limit=safe_limit)


@app.get(
    "/api/paper/order-notes/analytics",
    response_model=PaperFillOrderNoteAnalytics,
)
def get_paper_order_note_analytics(
    adapter_id: Optional[StockPaperBrokerAdapterId] = None,
    symbol: Optional[str] = None,
    limit: int = 200,
) -> PaperFillOrderNoteAnalytics:
    safe_limit = min(max(limit, 1), 500)
    normalized_symbol = symbol.strip().upper() if symbol else None
    notes = paper_fill_order_note_store.list_notes(
        adapter_id=adapter_id,
        symbol=normalized_symbol,
        limit=safe_limit,
    )
    return _paper_fill_order_note_analytics(
        notes=notes,
        limit=safe_limit,
        adapter_id=adapter_id,
        symbol=normalized_symbol,
    )


@app.get(
    "/api/paper/order-notes/quality-gate",
    response_model=PaperFillOrderNoteQualityGate,
)
def get_paper_order_note_quality_gate(
    adapter_id: Optional[StockPaperBrokerAdapterId] = None,
    symbol: Optional[str] = None,
    limit: int = PAPER_FILL_GATE_DEFAULT_LIMIT,
    min_notes: int = PAPER_FILL_GATE_DEFAULT_MIN_NOTES,
    max_avg_abs_price_delta_pct: float = PAPER_FILL_GATE_DEFAULT_MAX_AVG_ABS_DELTA_PCT,
    max_worst_abs_price_delta_pct: float = PAPER_FILL_GATE_DEFAULT_MAX_WORST_ABS_DELTA_PCT,
    require_no_external_submission: bool = PAPER_FILL_GATE_DEFAULT_REQUIRE_NO_EXTERNAL,
) -> PaperFillOrderNoteQualityGate:
    safe_limit = min(max(limit, 1), 500)
    safe_min_notes = min(max(min_notes, 1), safe_limit)
    if max_avg_abs_price_delta_pct < 0:
        raise HTTPException(status_code=400, detail="Average drift threshold must be non-negative")
    if max_worst_abs_price_delta_pct < 0:
        raise HTTPException(status_code=400, detail="Worst drift threshold must be non-negative")
    normalized_symbol = symbol.strip().upper() if symbol else None
    notes = paper_fill_order_note_store.list_notes(
        adapter_id=adapter_id,
        symbol=normalized_symbol,
        limit=safe_limit,
    )
    analytics = _paper_fill_order_note_analytics(
        notes=notes,
        limit=safe_limit,
        adapter_id=adapter_id,
        symbol=normalized_symbol,
    )
    return _paper_fill_quality_gate(
        analytics=analytics,
        min_notes=safe_min_notes,
        max_avg_abs_price_delta_pct=max_avg_abs_price_delta_pct,
        max_worst_abs_price_delta_pct=max_worst_abs_price_delta_pct,
        require_no_external_submission=require_no_external_submission,
    )


@app.get("/api/execution/private-snapshot", response_model=UpbitPrivateSnapshot)
def execution_private_snapshot() -> UpbitPrivateSnapshot:
    try:
        return get_private_snapshot()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/execution/post-cutover-monitor", response_model=PostCutoverOrderMonitor)
def execution_post_cutover_monitor() -> PostCutoverOrderMonitor:
    return _post_cutover_monitor()


@app.get(
    "/api/execution/post-cutover-monitor/closeout-report",
    response_model=PostCutoverCloseoutReport,
)
def execution_post_cutover_closeout_report() -> PostCutoverCloseoutReport:
    return _post_cutover_closeout_report(_post_cutover_monitor())


@app.post("/api/execution/order-intents", response_model=OrderAuditRecord)
def create_order_intent(request: OrderIntentRequest) -> OrderAuditRecord:
    try:
        return submit_order_intent(request=request, audit_store=order_audit_store)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/execution/order-audits", response_model=list[OrderAuditRecord])
def list_order_audits() -> list[OrderAuditRecord]:
    return order_audit_store.list_records(limit=20)


@app.get("/api/execution/order-audits/{record_id}", response_model=OrderAuditRecord)
def get_order_audit(record_id: str) -> OrderAuditRecord:
    record = order_audit_store.get_record(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Order audit record not found")
    return record


@app.get(
    "/api/execution/order-audits/{record_id}/precheck",
    response_model=OrderPrecheckResult,
)
def get_order_audit_precheck(record_id: str) -> OrderPrecheckResult:
    try:
        return get_order_precheck(record_id=record_id, audit_store=order_audit_store)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get(
    "/api/execution/order-audits/{record_id}/runbook",
    response_model=ExecutionRunbook,
)
def get_order_audit_runbook(record_id: str) -> ExecutionRunbook:
    record = order_audit_store.get_record(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Order audit record not found")
    if record.status != "dry_run":
        raise HTTPException(
            status_code=400,
            detail="Runbooks can only be generated for dry-run order audit records.",
        )
    try:
        precheck = get_order_precheck(record_id=record_id, audit_store=order_audit_store)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _execution_runbook(record=record, precheck=precheck)


@app.post(
    "/api/execution/order-audits/{record_id}/approve",
    response_model=OrderAuditRecord,
)
def approve_order_audit(
    record_id: str,
    request: OrderApprovalRequest,
) -> OrderAuditRecord:
    try:
        return approve_dry_run_order_intent(
            record_id=record_id,
            request=request,
            audit_store=order_audit_store,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get(
    "/api/paper/watchlist",
    response_model=list[PortfolioPaperWatchlistItem],
)
def list_portfolio_paper_watchlist() -> list[PortfolioPaperWatchlistItem]:
    return portfolio_paper_watchlist_store.list_items(limit=50)


@app.post(
    "/api/paper/watchlist",
    response_model=PortfolioPaperWatchlistItem,
)
def create_portfolio_paper_watchlist_item(
    request: PortfolioPaperWatchlistCreate,
) -> PortfolioPaperWatchlistItem:
    scenario = portfolio_scenario_store.get_scenario(request.scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Portfolio scenario not found")
    return portfolio_paper_watchlist_store.save_item(create=request, scenario=scenario)


@app.post(
    "/api/paper/watchlist/run-due",
    response_model=PortfolioPaperSchedulerRun,
)
def run_due_portfolio_paper_watchlist() -> PortfolioPaperSchedulerRun:
    return _run_due_portfolio_paper_watchlist()


@app.post(
    "/api/paper/watchlist/{item_id}/run",
    response_model=PortfolioPaperWatchlistRun,
)
def run_portfolio_paper_watchlist_item(item_id: str) -> PortfolioPaperWatchlistRun:
    item = portfolio_paper_watchlist_store.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Portfolio paper watchlist item not found")
    return _run_portfolio_paper_watchlist_item(item=item)


@app.post(
    "/api/paper/watchlist/{item_id}/promote-order-intents",
    response_model=PortfolioPaperPromotionResponse,
)
def promote_portfolio_paper_watchlist_order_intents(
    item_id: str,
    request: PortfolioPaperPromotionRequest,
) -> PortfolioPaperPromotionResponse:
    item = portfolio_paper_watchlist_store.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Portfolio paper watchlist item not found")
    return _promote_portfolio_paper_watchlist_order_intents(item=item, request=request)


@app.delete("/api/paper/watchlist/{item_id}")
def delete_portfolio_paper_watchlist_item(item_id: str) -> dict[str, str]:
    deleted = portfolio_paper_watchlist_store.delete_item(item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Portfolio paper watchlist item not found")
    return {"status": "deleted", "id": item_id}


@app.post("/api/paper/sessions", response_model=PaperTradingSession)
def create_paper_session(request: PaperTradingRequest) -> PaperTradingSession:
    try:
        candles = get_candles(
            symbol=request.symbol,
            timeframe=request.timeframe,
            source=request.source,
            limit=request.candle_limit,
        )
        session = run_paper_session(request=request, candles=candles)
    except (MarketDataError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _annotate_paper_session_warnings(session=session, candle_count=len(candles))
    session_store.save_paper_session(session)
    return session


@app.get("/api/paper/sessions", response_model=list[PaperTradingSession])
def list_paper_sessions() -> list[PaperTradingSession]:
    return session_store.list_paper_sessions(limit=20)


@app.get("/api/paper/sessions/{session_id}", response_model=PaperTradingSession)
def get_paper_session(session_id: str) -> PaperTradingSession:
    session = session_store.get_paper_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Paper session not found")
    return session


@app.post(
    "/api/paper/sessions/{session_id}/order-intents",
    response_model=StrategyOrderQueueResponse,
)
def queue_paper_session_order_intents(
    session_id: str,
    request: StrategyOrderQueueRequest,
) -> StrategyOrderQueueResponse:
    session = session_store.get_paper_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Paper session not found")
    try:
        return queue_strategy_order_intents(
            session=session,
            audit_store=order_audit_store,
            source="paper_session",
            max_intents=request.max_intents,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/paper/live-sessions", response_model=LivePaperTradingSession)
def create_live_paper_session(
    request: LivePaperTradingRequest,
) -> LivePaperTradingSession:
    try:
        candles = get_candles(
            symbol=request.symbol,
            timeframe=request.timeframe,
            source=request.source,
            limit=request.candle_limit,
        )
        runtime = create_live_paper_runtime(request=request, candles=candles)
    except (MarketDataError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if request.source == "sample":
        runtime.session.warnings.append(
            "Live replay uses deterministic sample candles. Switch source to upbit for public KRW market data."
        )
    if request.source == "sample_us":
        runtime.session.warnings.append(
            "Live replay uses deterministic US stock/ETF sample candles."
        )
    if request.source == "alpha_vantage":
        runtime.session.warnings.append(
            "Live replay uses Alpha Vantage compact daily stock/ETF candles."
        )
        if len(candles) < request.candle_limit:
            runtime.session.warnings.append(
                f"Alpha Vantage compact daily data returned {len(candles)} rows for this request."
            )
    if request.source == "upbit" and request.candle_limit > 200:
        runtime.session.warnings.append("Upbit public candle endpoint is capped to 200 rows per call.")
    live_paper_runtimes[runtime.session.id] = runtime
    session_store.save_live_runtime(runtime)
    return runtime.session


@app.post("/api/paper/ticker-sessions", response_model=LivePaperTradingSession)
def create_ticker_paper_session(
    request: LivePaperTradingRequest,
) -> LivePaperTradingSession:
    try:
        candles = get_candles(
            symbol=request.symbol,
            timeframe=request.timeframe,
            source=request.source,
            limit=request.candle_limit,
        )
        runtime = create_ticker_paper_runtime(request=request, candles=candles)
    except (MarketDataError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if request.source == "sample":
        runtime.session.warnings.append(
            "Ticker paper session uses deterministic sample ticker data."
        )
    if request.source == "sample_us":
        runtime.session.warnings.append(
            "Ticker paper session uses deterministic US stock/ETF sample ticker data."
        )
    if request.source == "alpha_vantage":
        runtime.session.warnings.append(
            "Ticker paper session uses Alpha Vantage daily close updates."
        )
    if request.source == "upbit":
        runtime.session.warnings.append(
            "Ticker paper session uses Upbit public ticker data and simulated orders only."
        )
    live_paper_runtimes[runtime.session.id] = runtime
    session_store.save_live_runtime(runtime)
    return runtime.session


@app.post(
    "/api/paper/live-sessions/{session_id}/advance",
    response_model=LivePaperTradingSession,
)
def advance_live_paper_session(
    session_id: str,
    request: PaperAdvanceRequest,
) -> LivePaperTradingSession:
    runtime = _get_live_runtime(session_id)
    if runtime is None:
        raise HTTPException(status_code=404, detail="Live paper session not found")
    if runtime.mode != "replay":
        raise HTTPException(
            status_code=400,
            detail="Ticker paper sessions advance with the tick endpoint.",
        )
    session = advance_live_paper_runtime(runtime=runtime, request=request)
    session_store.save_live_runtime(runtime)
    return session


@app.post(
    "/api/paper/live-sessions/{session_id}/tick",
    response_model=LivePaperTradingSession,
)
def tick_live_paper_session(session_id: str) -> LivePaperTradingSession:
    runtime = _get_live_runtime(session_id)
    if runtime is None:
        raise HTTPException(status_code=404, detail="Live paper session not found")
    if runtime.mode != "ticker":
        raise HTTPException(
            status_code=400,
            detail="Replay paper sessions advance with the replay endpoint.",
        )

    try:
        ticker = get_market_ticker(
            symbol=runtime.session.request.symbol,
            source=runtime.session.request.source,
        )
    except MarketDataError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    session = advance_live_paper_runtime_with_ticker(runtime=runtime, ticker=ticker)
    session_store.save_live_runtime(runtime)
    return session


@app.get("/api/paper/live-sessions", response_model=list[LivePaperTradingSession])
def list_live_paper_sessions() -> list[LivePaperTradingSession]:
    return session_store.list_live_sessions(limit=20)


@app.get(
    "/api/paper/live-sessions/{session_id}",
    response_model=LivePaperTradingSession,
)
def get_live_paper_session(session_id: str) -> LivePaperTradingSession:
    runtime = _get_live_runtime(session_id)
    if runtime is None:
        raise HTTPException(status_code=404, detail="Live paper session not found")
    return runtime.session


@app.post(
    "/api/paper/live-sessions/{session_id}/order-intents",
    response_model=StrategyOrderQueueResponse,
)
def queue_live_paper_session_order_intents(
    session_id: str,
    request: StrategyOrderQueueRequest,
) -> StrategyOrderQueueResponse:
    runtime = _get_live_runtime(session_id)
    if runtime is None:
        raise HTTPException(status_code=404, detail="Live paper session not found")
    try:
        return queue_strategy_order_intents(
            session=runtime.session,
            audit_store=order_audit_store,
            source="live_paper_session",
            max_intents=request.max_intents,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _get_live_runtime(session_id: str) -> Optional[LivePaperRuntime]:
    runtime = live_paper_runtimes.get(session_id)
    if runtime is not None:
        return runtime

    runtime = session_store.get_live_runtime(session_id)
    if runtime is not None:
        live_paper_runtimes[session_id] = runtime
    return runtime


def _execution_runbook(
    record: OrderAuditRecord,
    precheck: OrderPrecheckResult,
) -> ExecutionRunbook:
    generated_at = datetime.now(timezone.utc).isoformat()
    settings = get_execution_settings()
    context = (record.response_payload or {}).get("context")
    context = context if isinstance(context, dict) else {}
    title = f"Dry-run approval runbook: {record.side.upper()} {record.market}"
    filename = f"runbook-{record.market}-{record.id[:8]}.md".replace("/", "-")
    lines = [
        f"# {title}",
        "",
        f"- Generated: {generated_at}",
        f"- Audit id: {record.id}",
        f"- Market: {record.market}",
        f"- Side: {record.side}",
        f"- Order type: {record.ord_type}",
        f"- Dry-run reason: {record.reason}",
        "",
        "## Source Context",
        "",
        f"- Source: {context.get('source', 'paper_session')}",
        f"- Scenario: {context.get('scenario_name', '-')}",
        f"- Scenario id: {context.get('scenario_id', '-')}",
        f"- Watchlist id: {context.get('watchlist_id', '-')}",
        f"- Source session id: {(record.response_payload or {}).get('source_session_id', '-')}",
        f"- Source trade timestamp: {(record.response_payload or {}).get('source_trade_timestamp', '-')}",
        f"- Simulated notional: {(record.response_payload or {}).get('simulated_notional', '-')}",
        "",
        "## Promotion Rules",
        "",
    ]
    rules = context.get("promotion_rules")
    if isinstance(rules, dict):
        lines.extend(
            [
                f"- Minimum return: {rules.get('min_total_return_pct', '-')}",
                f"- Maximum drawdown: {rules.get('max_drawdown_pct', '-')}",
                f"- Minimum orders: {rules.get('min_orders', '-')}",
            ]
        )
    else:
        lines.append("- No paper-watchlist promotion rules were attached.")

    lines.extend(
        [
            "",
            "## Execution Guard",
            "",
            f"- Live trading flag: {'on' if settings.live_trading_enabled else 'off'}",
            f"- Live ACK configured: {'yes' if settings.live_ack_configured else 'no'}",
            f"- Credential configured: {'yes' if settings.credential_configured else 'no'}",
            f"- Private reads enabled: {'yes' if settings.private_reads_enabled else 'no'}",
            f"- Adapter ready: {'yes' if settings.adapter_ready else 'no'}",
            f"- Live confirmation required: {'yes' if settings.live_confirmation_required else 'no'}",
            f"- Guard reason: {settings.reason}",
            "",
            "## Pre-Approval Checks",
            "",
            f"- Overall status: {precheck.status}",
            f"- Order info source: {precheck.order_info_source}",
            f"- Estimated notional: {precheck.estimated_notional}",
            f"- Minimum notional: {precheck.min_order_notional}",
            f"- Fee rate: {precheck.fee_rate}",
            f"- Credential ready: {'yes' if precheck.credential_ready else 'no'}",
            f"- Available quote balance: {precheck.available_quote_balance if precheck.available_quote_balance is not None else '-'}",
            f"- Available base balance: {precheck.available_base_balance if precheck.available_base_balance is not None else '-'}",
            f"- Post-order exposure: {precheck.post_order_exposure_pct if precheck.post_order_exposure_pct is not None else '-'}",
            "",
        ]
    )
    for check in precheck.checks:
        lines.append(
            f"- [{_runbook_check_marker(check.status)}] {check.name}: {check.message}"
        )

    decisions = operator_decision_store.list_decisions(
        decision_type="dry_run_approval",
        target_id=record.id,
        limit=10,
    )
    lines.extend(["", "## Operator Decisions", ""])
    if decisions:
        for decision in decisions:
            lines.extend(
                [
                    f"- {decision.created_at}: {decision.status.replace('_', ' ')}",
                    f"  - Decision id: {decision.id}",
                    f"  - Note: {decision.note or '-'}",
                ]
            )
    else:
        lines.append("- No operator decisions have been logged for this dry-run audit.")

    lines.extend(
        [
            "",
            "## Approval Procedure",
            "",
            "1. Confirm the dry-run source context matches the intended strategy and scenario.",
            "2. Confirm every pre-approval check is pass or an explicitly accepted warning.",
            "3. Confirm account balances and exposure outside Quant Lab before live submission.",
            "4. Set the backend live guard only when ready: QUANT_LAB_LIVE_TRADING_ENABLED=true and QUANT_LAB_LIVE_TRADING_ACK=REAL_ORDERS_OK.",
            "5. Approve from the Order review panel with live confirmation enabled.",
            "6. Re-check the resulting order audit record after submission or block.",
            "",
            "## Stop Conditions",
            "",
            "- Do not approve if the market, side, price, volume, or notional is unexpected.",
            "- Do not approve if the precheck status is fail.",
            "- Do not approve if private balances cannot be verified for the intended account.",
            "- Do not approve stock/ETF paper sessions; this Upbit adapter is crypto-only.",
        ]
    )
    markdown = "\n".join(lines)
    return ExecutionRunbook(
        generated_at=generated_at,
        title=title,
        record_id=record.id,
        filename=filename,
        audit=record,
        precheck=precheck,
        markdown=markdown,
    )


def _runbook_check_marker(status: str) -> str:
    if status == "pass":
        return "x"
    return " "


def _cutover_runbook(
    checklist: LiveCutoverChecklistResponse,
) -> LiveCutoverRunbook:
    generated_at = datetime.now(timezone.utc).isoformat()
    settings = get_execution_settings()
    title = "Live adapter arming runbook"
    filename = f"live-cutover-runbook-{generated_at[:10]}.md"
    lines = [
        f"# {title}",
        "",
        f"- Generated: {generated_at}",
        f"- Cutover checklist status: {checklist.status}",
        f"- Cutover checklist checked at: {checklist.checked_at}",
        f"- Readiness status: {checklist.readiness.status}",
        f"- Readiness score: {checklist.readiness.score:.1f}/100",
        "",
        "## Cutover Checklist",
        "",
    ]
    for item in checklist.items:
        lines.append(
            f"- [{_runbook_check_marker(item.status)}] {item.label}: {item.status} - {item.message}"
        )
        if item.evidence_id:
            lines.append(f"  - Evidence id: {item.evidence_id}")

    lines.extend(
        [
            "",
            "## Execution Guard Environment",
            "",
            f"- Exchange: {settings.exchange}",
            f"- Base URL: {settings.base_url}",
            f"- Settings checked at: {settings.checked_at}",
            f"- QUANT_LAB_LIVE_TRADING_ENABLED: {'on' if settings.live_trading_enabled else 'off'}",
            f"- QUANT_LAB_LIVE_TRADING_ACK configured: {'yes' if settings.live_ack_configured else 'no'}",
            f"- Required ACK value: {settings.live_ack_required_value}",
            f"- UPBIT_ACCESS_KEY / UPBIT_SECRET_KEY configured: {'yes' if settings.credential_configured else 'no'}",
            f"- Private reads enabled: {'yes' if settings.private_reads_enabled else 'no'}",
            f"- Adapter ready: {'yes' if settings.adapter_ready else 'no'}",
            f"- Per-order live confirmation required: {'yes' if settings.live_confirmation_required else 'no'}",
            f"- Order info source: {settings.order_info_source}",
            f"- Minimum order notional KRW: {settings.min_order_notional_krw}",
            f"- Approval fee bps: {settings.approval_fee_bps}",
            f"- Maximum approval exposure pct: {settings.max_approval_exposure_pct}",
            f"- Guard reason: {settings.reason}",
            "",
            "## Live Readiness Detail",
            "",
        ]
    )
    if checklist.readiness.breakdowns:
        lines.extend(["### Readiness Views", ""])
        for breakdown in checklist.readiness.breakdowns:
            lines.extend(
                [
                    f"- {breakdown.label}: {breakdown.status} at {breakdown.score:.1f}/100",
                    f"  - Blocking checks: {', '.join(breakdown.blocking_checks) if breakdown.blocking_checks else '-'}",
                    f"  - Warning checks: {', '.join(breakdown.warning_checks) if breakdown.warning_checks else '-'}",
                    f"  - Summary: {breakdown.message}",
                ]
            )
        lines.append("")
    for check in checklist.readiness.checks:
        lines.append(
            f"- [{_runbook_check_marker(check.status)}] {check.label} ({check.category}): {check.status} - {check.message}"
        )

    lines.extend(["", "## Operator Decisions", ""])
    if checklist.latest_operator_decisions:
        for decision in checklist.latest_operator_decisions:
            lines.extend(
                [
                    f"### {decision.decision_type.replace('_', ' ')}",
                    "",
                    f"- Decision id: {decision.id}",
                    f"- Created at: {decision.created_at}",
                    f"- Status: {decision.status.replace('_', ' ')}",
                    f"- Target: {decision.target_id or '-'}",
                    f"- Note: {decision.note or '-'}",
                ]
            )
            if decision.context:
                lines.append("- Context:")
                for key, value in decision.context.items():
                    lines.append(f"  - {key}: {value}")
            lines.append("")
    else:
        lines.append("- No cutover-related operator decisions have been logged.")

    lines.extend(
        [
            "",
            "## Arming Procedure",
            "",
            "1. Confirm the cutover checklist is ready; do not arm if any item is fail.",
            "2. Confirm the latest approved readiness review, dry-run approval, and live cutover decisions are present in this runbook.",
            "3. Configure UPBIT_ACCESS_KEY and UPBIT_SECRET_KEY for the intended account only.",
            "4. Set QUANT_LAB_LIVE_TRADING_ENABLED=true and QUANT_LAB_LIVE_TRADING_ACK=REAL_ORDERS_OK only during the approved cutover window.",
            "5. Restart the backend process and re-fetch execution status, private snapshot, readiness, and this checklist.",
            "6. Approve individual dry-run orders from the Order review panel; each order must still carry live_confirmation=true.",
            "7. Re-check order audit records after every approval attempt and lock live routing again after the window.",
            "",
            "## Stop Conditions",
            "",
            "- Stop if private balances or order availability cannot be read from the intended Upbit account.",
            "- Stop if any active halt/error alert remains open.",
            "- Stop if the approved dry-run audit does not match the intended market, side, price, volume, or strategy context.",
            "- Stop if the adapter is already armed before the required operator decisions are logged.",
            "- Stop if any stock/ETF paper session is being promoted; the live adapter is KRW crypto spot only.",
        ]
    )
    markdown = "\n".join(lines)
    return LiveCutoverRunbook(
        generated_at=generated_at,
        title=title,
        filename=filename,
        checklist=checklist,
        settings=settings,
        markdown=markdown,
    )


def _simulated_execution_settings(
    request: LiveArmingSimulationRequest,
) -> ExecutionSettings:
    base = get_execution_settings()
    private_reads_enabled = request.credential_configured
    adapter_ready = (
        request.live_trading_enabled
        and request.live_ack_configured
        and request.credential_configured
    )
    if not request.live_trading_enabled:
        reason = "Simulation keeps live order routing disabled by QUANT_LAB_LIVE_TRADING_ENABLED."
    elif not request.live_ack_configured:
        reason = "Simulation keeps live orders locked because QUANT_LAB_LIVE_TRADING_ACK is missing."
    elif not request.credential_configured:
        reason = "Simulation keeps live orders locked because Upbit credentials are missing."
    else:
        reason = "Simulation assumes live routing flags, ACK, and Upbit credentials are configured; per-order confirmation is still required."

    return base.model_copy(
        update={
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "live_trading_enabled": request.live_trading_enabled,
            "live_ack_configured": request.live_ack_configured,
            "credential_configured": request.credential_configured,
            "private_reads_enabled": private_reads_enabled,
            "adapter_ready": adapter_ready,
            "order_info_source": (
                "upbit_orders_chance"
                if request.credential_configured
                else "local_defaults"
            ),
            "reason": reason,
        }
    )


def _simulation_changes(
    current: LiveCutoverChecklistResponse,
    simulated: LiveCutoverChecklistResponse,
) -> list[LiveArmingSimulationChange]:
    simulated_items = {item.id: item for item in simulated.items}
    changes: list[LiveArmingSimulationChange] = []
    for current_item in current.items:
        simulated_item = simulated_items.get(current_item.id)
        if simulated_item is None:
            continue
        changes.append(
            LiveArmingSimulationChange(
                id=current_item.id,
                label=current_item.label,
                current_status=current_item.status,
                simulated_status=simulated_item.status,
                current_message=current_item.message,
                simulated_message=simulated_item.message,
                changed=(
                    current_item.status != simulated_item.status
                    or current_item.message != simulated_item.message
                ),
            )
        )
    return changes


def _arming_simulation_summary(
    *,
    current: LiveCutoverChecklistResponse,
    simulated: LiveCutoverChecklistResponse,
    changes: list[LiveArmingSimulationChange],
) -> str:
    current_failures = sum(1 for item in current.items if item.status == "fail")
    simulated_failures = sum(1 for item in simulated.items if item.status == "fail")
    changed_count = sum(1 for change in changes if change.changed)
    if simulated.status == "ready":
        return (
            "Simulated arming clears all cutover blockers; no exchange order is submitted by this preview."
        )
    if simulated_failures < current_failures:
        return (
            f"Simulated arming reduces blockers from {current_failures} to {simulated_failures}; "
            "remaining failures still block live order routing."
        )
    if simulated_failures > current_failures:
        return (
            f"Simulated arming exposes {simulated_failures} blocker(s), including guard or approval gaps; "
            "no exchange order is submitted by this preview."
        )
    return (
        f"Simulated arming changes {changed_count} checklist item(s) but leaves "
        f"{simulated_failures} blocker(s); no exchange order is submitted by this preview."
    )


def _simulate_live_arming(
    request: LiveArmingSimulationRequest,
) -> LiveArmingSimulationResponse:
    generated_at = datetime.now(timezone.utc).isoformat()
    current = _live_cutover_checklist()
    simulated = _live_cutover_checklist(
        settings=_simulated_execution_settings(request),
        assume_required_operator_decisions=request.assume_required_operator_decisions,
        simulated=True,
    )
    changes = _simulation_changes(current=current, simulated=simulated)
    current_blockers = [item for item in current.items if item.status == "fail"]
    simulated_blockers = [item for item in simulated.items if item.status == "fail"]
    return LiveArmingSimulationResponse(
        generated_at=generated_at,
        no_order_submission=True,
        assumptions=request,
        current=current,
        simulated=simulated,
        changes=changes,
        current_blockers=current_blockers,
        simulated_blockers=simulated_blockers,
        summary=_arming_simulation_summary(
            current=current,
            simulated=simulated,
            changes=changes,
        ),
    )


def _monitor_item(
    *,
    id: str,
    label: str,
    status: str,
    message: str,
    evidence_id: Optional[str] = None,
) -> PostCutoverMonitorItem:
    return PostCutoverMonitorItem(
        id=id,
        label=label,
        status=status,
        message=message,
        evidence_id=evidence_id,
    )


def _is_approval_attempt(record: OrderAuditRecord) -> bool:
    response_payload = record.response_payload or {}
    identifier = record.request_payload.get("identifier")
    return bool(
        response_payload.get("approved_from_record_id")
        or (isinstance(identifier, str) and identifier.startswith("approved-"))
    )


def _post_cutover_monitor() -> PostCutoverOrderMonitor:
    checked_at = datetime.now(timezone.utc).isoformat()
    settings = get_execution_settings()
    snapshot: Optional[UpbitPrivateSnapshot]
    snapshot_error: Optional[str] = None
    try:
        snapshot = get_private_snapshot()
    except RuntimeError as exc:
        snapshot = None
        snapshot_error = str(exc)

    open_orders = snapshot.open_orders if snapshot else []
    approval_attempts = [
        record for record in order_audit_store.list_records(limit=100) if _is_approval_attempt(record)
    ][:12]
    latest_audit = approval_attempts[0] if approval_attempts else None
    counts = {
        "approval_attempts": len(approval_attempts),
        "submitted": sum(1 for record in approval_attempts if record.status == "submitted"),
        "blocked": sum(1 for record in approval_attempts if record.status == "blocked"),
        "failed": sum(1 for record in approval_attempts if record.status == "failed"),
        "open_orders": len(open_orders),
    }

    items: list[PostCutoverMonitorItem] = [
        _monitor_item(
            id="live_window",
            label="Live window",
            status="pass" if settings.adapter_ready else "warn",
            message=(
                "Upbit adapter is armed; monitor approval attempts and open orders continuously."
                if settings.adapter_ready
                else "Live adapter is locked; monitor remains idle until the approved cutover window."
            ),
        )
    ]

    private_snapshot_status = "pass" if snapshot and snapshot.credential_ready else "warn"
    if settings.adapter_ready and (snapshot_error or not (snapshot and snapshot.credential_ready)):
        private_snapshot_status = "fail"
    items.append(
        _monitor_item(
            id="private_snapshot",
            label="Private account snapshot",
            status=private_snapshot_status,
            message=(
                snapshot_error
                if snapshot_error
                else snapshot.reason
                if snapshot
                else "Private account snapshot is unavailable."
            ),
            evidence_id=snapshot.checked_at if snapshot else None,
        )
    )

    if latest_audit is None:
        approval_status = "warn"
        approval_message = "No approved dry-run live attempts have been recorded yet."
    elif latest_audit.status in {"blocked", "failed"}:
        approval_status = "fail"
        approval_message = (
            f"Latest approval attempt is {latest_audit.status}: {latest_audit.reason}"
        )
    else:
        approval_status = "pass"
        approval_message = (
            f"Latest approval attempt is {latest_audit.status} for {latest_audit.market}."
        )
    items.append(
        _monitor_item(
            id="latest_approval_attempt",
            label="Latest approval attempt",
            status=approval_status,
            message=approval_message,
            evidence_id=latest_audit.id if latest_audit else None,
        )
    )

    items.append(
        _monitor_item(
            id="open_orders",
            label="Private open orders",
            status="warn" if open_orders else "pass",
            message=(
                f"{len(open_orders)} open order(s) are visible on the private account."
                if open_orders
                else "No private open orders are visible."
            ),
            evidence_id=snapshot.checked_at if snapshot else None,
        )
    )

    if counts["failed"] > 0:
        failure_status = "fail"
        failure_message = f"{counts['failed']} failed approval attempt(s) require review."
    elif counts["blocked"] > 0:
        failure_status = "warn"
        failure_message = f"{counts['blocked']} blocked approval attempt(s) are recorded."
    else:
        failure_status = "pass"
        failure_message = "No failed approval attempts are recorded."
    items.append(
        _monitor_item(
            id="failed_or_blocked_attempts",
            label="Failed or blocked attempts",
            status=failure_status,
            message=failure_message,
        )
    )

    if any(item.status == "fail" for item in items):
        status = "blocked" if settings.adapter_ready and private_snapshot_status == "fail" else "attention"
    elif settings.adapter_ready or counts["submitted"] > 0 or open_orders:
        status = "watch"
    elif counts["approval_attempts"] > 0:
        status = "attention"
    else:
        status = "idle"

    return PostCutoverOrderMonitor(
        checked_at=checked_at,
        status=status,
        settings=settings,
        private_snapshot=snapshot,
        private_snapshot_error=snapshot_error,
        open_orders=open_orders,
        recent_approval_attempts=approval_attempts,
        latest_audit=latest_audit,
        counts=counts,
        items=items,
    )


def _post_cutover_closeout_report(
    monitor: PostCutoverOrderMonitor,
) -> PostCutoverCloseoutReport:
    generated_at = datetime.now(timezone.utc).isoformat()
    title = "Live window closeout report"
    filename = f"live-window-closeout-{generated_at[:10]}.md"
    decisions = _latest_relevant_operator_decisions(limit=20)
    settings = monitor.settings
    lines = [
        f"# {title}",
        "",
        f"- Generated: {generated_at}",
        f"- Monitor checked at: {monitor.checked_at}",
        f"- Monitor status: {monitor.status}",
        f"- Live trading flag: {'on' if settings.live_trading_enabled else 'off'}",
        f"- Adapter ready: {'yes' if settings.adapter_ready else 'no'}",
        f"- Private reads enabled: {'yes' if settings.private_reads_enabled else 'no'}",
        f"- Approval attempts: {monitor.counts.get('approval_attempts', 0)}",
        f"- Submitted attempts: {monitor.counts.get('submitted', 0)}",
        f"- Blocked attempts: {monitor.counts.get('blocked', 0)}",
        f"- Failed attempts: {monitor.counts.get('failed', 0)}",
        f"- Private open orders: {monitor.counts.get('open_orders', 0)}",
        "",
        "## Monitor Checks",
        "",
    ]
    for item in monitor.items:
        lines.append(f"- [{_runbook_check_marker(item.status)}] {item.label}: {item.status} - {item.message}")
        if item.evidence_id:
            lines.append(f"  - Evidence id: {item.evidence_id}")

    lines.extend(
        [
            "",
            "## Final Audit State",
            "",
        ]
    )
    if monitor.latest_audit:
        audit = monitor.latest_audit
        lines.extend(
            [
                f"- Latest audit id: {audit.id}",
                f"- Created at: {audit.created_at}",
                f"- Market: {audit.market}",
                f"- Side: {audit.side}",
                f"- Status: {audit.status}",
                f"- Reason: {audit.reason}",
            ]
        )
    else:
        lines.append("- No approved live attempts were recorded.")

    lines.extend(["", "## Approval Attempts", ""])
    if monitor.recent_approval_attempts:
        for index, audit in enumerate(monitor.recent_approval_attempts, start=1):
            response_payload = audit.response_payload or {}
            source_id = response_payload.get("approved_from_record_id", "-")
            lines.extend(
                [
                    f"### {index}. {audit.market} {audit.side}",
                    "",
                    f"- Audit id: {audit.id}",
                    f"- Created at: {audit.created_at}",
                    f"- Status: {audit.status}",
                    f"- Reason: {audit.reason}",
                    f"- Approved from: {source_id}",
                ]
            )
            precheck = response_payload.get("precheck")
            if isinstance(precheck, dict):
                lines.append(f"- Precheck status: {precheck.get('status', '-')}")
                lines.append(f"- Estimated notional: {precheck.get('estimated_notional', '-')}")
            lines.append("")
    else:
        lines.append("- No approved live attempts were recorded.")

    lines.extend(["", "## Private Account Snapshot", ""])
    if monitor.private_snapshot_error:
        lines.append(f"- Snapshot error: {monitor.private_snapshot_error}")
    elif monitor.private_snapshot:
        snapshot = monitor.private_snapshot
        lines.extend(
            [
                f"- Snapshot checked at: {snapshot.checked_at}",
                f"- Credential ready: {'yes' if snapshot.credential_ready else 'no'}",
                f"- Balance rows: {len(snapshot.balances)}",
                f"- Open orders: {len(snapshot.open_orders)}",
                f"- Snapshot reason: {snapshot.reason}",
            ]
        )
    else:
        lines.append("- Private account snapshot was unavailable.")

    lines.extend(["", "## Open Orders", ""])
    if monitor.open_orders:
        for order in monitor.open_orders:
            lines.extend(
                [
                    f"- {order.market} {order.side} {order.state}",
                    f"  - UUID: {order.uuid}",
                    f"  - Remaining volume: {order.remaining_volume if order.remaining_volume is not None else '-'}",
                    f"  - Price: {order.price if order.price is not None else '-'}",
                    f"  - Identifier: {order.identifier or '-'}",
                ]
            )
    else:
        lines.append("- No private open orders were visible at closeout.")

    lines.extend(["", "## Operator Decisions", ""])
    if decisions:
        for decision in decisions:
            lines.extend(
                [
                    f"- {decision.created_at}: {decision.decision_type.replace('_', ' ')} / {decision.status.replace('_', ' ')}",
                    f"  - Decision id: {decision.id}",
                    f"  - Target: {decision.target_id or '-'}",
                    f"  - Note: {decision.note or '-'}",
                ]
            )
    else:
        lines.append("- No cutover-related operator decisions were logged.")

    lines.extend(
        [
            "",
            "## Closeout Procedure",
            "",
            "1. Confirm QUANT_LAB_LIVE_TRADING_ENABLED has been turned off after the live window.",
            "2. Confirm no failed or blocked approval attempts require additional operator review.",
            "3. Confirm private open orders are expected; cancel or resolve unexpected orders outside Quant Lab.",
            "4. Archive this report with the live adapter arming runbook and dry-run approval runbooks.",
            "5. Record any follow-up action in the Operations journal.",
        ]
    )
    markdown = "\n".join(lines)
    return PostCutoverCloseoutReport(
        generated_at=generated_at,
        title=title,
        filename=filename,
        monitor=monitor,
        operator_decisions=decisions,
        markdown=markdown,
    )


def _strategy_health_milestone(
    *,
    id: str,
    label: str,
    status: str,
    message: str,
    evidence_id: Optional[str] = None,
) -> StrategyHealthMilestone:
    return StrategyHealthMilestone(
        id=id,
        label=label,
        status=status,
        message=message,
        evidence_id=evidence_id,
    )


def _strategy_health_status(
    milestones: list[StrategyHealthMilestone],
    approval_attempts: list[OrderAuditRecord],
    decisions: list[OperatorDecisionRecord],
) -> str:
    if any(milestone.status == "fail" for milestone in milestones):
        return "blocked"
    if any(decision.status in {"rejected", "needs_work"} for decision in decisions):
        return "attention"
    if approval_attempts:
        latest = approval_attempts[0]
        if latest.status == "submitted":
            return "healthy"
        return "attention"
    if any(decision.status == "approved" for decision in decisions):
        return "watch"
    return "watch"


def _strategy_health_traces(limit: int = 20) -> StrategyHealthTraceResponse:
    checked_at = datetime.now(timezone.utc).isoformat()
    records = order_audit_store.list_records(limit=200)
    dry_run_records = [
        record
        for record in records
        if record.status == "dry_run"
        and record.response_payload
        and record.response_payload.get("dry_run")
    ][:limit]
    approval_attempts_by_source: dict[str, list[OrderAuditRecord]] = {}
    for record in records:
        if not _is_approval_attempt(record):
            continue
        source_id = (record.response_payload or {}).get("approved_from_record_id")
        if isinstance(source_id, str):
            approval_attempts_by_source.setdefault(source_id, []).append(record)

    monitor = _post_cutover_monitor()
    traces: list[StrategyHealthTrace] = []
    for dry_run in dry_run_records:
        payload = dry_run.response_payload or {}
        context = payload.get("context")
        context = context if isinstance(context, dict) else {}
        promotion_rules = context.get("promotion_rules")
        promotion_rules = promotion_rules if isinstance(promotion_rules, dict) else {}
        decisions = operator_decision_store.list_decisions(
            decision_type="dry_run_approval",
            target_id=dry_run.id,
            limit=10,
        )
        approval_attempts = approval_attempts_by_source.get(dry_run.id, [])
        latest_attempt = approval_attempts[0] if approval_attempts else None
        milestones: list[StrategyHealthMilestone] = []

        if context.get("source") == "portfolio_paper_watchlist_promotion":
            milestones.append(
                _strategy_health_milestone(
                    id="promotion_rules",
                    label="Portfolio promotion rules",
                    status="pass" if promotion_rules else "warn",
                    message=(
                        f"{context.get('scenario_name', 'Scenario')} promoted with watchlist rules."
                        if promotion_rules
                        else "Portfolio promotion context is present without rule details."
                    ),
                    evidence_id=str(context.get("watchlist_id") or ""),
                )
            )
        else:
            milestones.append(
                _strategy_health_milestone(
                    id="promotion_rules",
                    label="Portfolio promotion rules",
                    status="warn",
                    message="Dry-run audit came from a paper session without portfolio watchlist promotion context.",
                )
            )

        source_session_id = payload.get("source_session_id")
        source_trade_timestamp = payload.get("source_trade_timestamp")
        milestones.append(
            _strategy_health_milestone(
                id="paper_trade",
                label="Paper trade source",
                status="pass" if source_session_id and source_trade_timestamp else "fail",
                message=(
                    f"Paper trade at {source_trade_timestamp} generated this dry-run signal."
                    if source_session_id and source_trade_timestamp
                    else "Paper trade metadata is missing from the dry-run audit."
                ),
                evidence_id=str(source_session_id) if source_session_id else None,
            )
        )

        milestones.append(
            _strategy_health_milestone(
                id="dry_run_audit",
                label="Dry-run audit",
                status="pass",
                message=f"Dry-run audit is queued for {dry_run.market} {dry_run.side}.",
                evidence_id=dry_run.id,
            )
        )

        approved_decisions = [decision for decision in decisions if decision.status == "approved"]
        needs_work_decisions = [
            decision for decision in decisions if decision.status in {"needs_work", "rejected"}
        ]
        if approved_decisions:
            decision_status = "pass"
            decision_message = f"{len(approved_decisions)} approved operator review(s) logged."
        elif needs_work_decisions:
            decision_status = "fail"
            decision_message = "Operator review marked this dry-run audit as needing work or rejected."
        elif decisions:
            decision_status = "warn"
            decision_message = "Operator review is logged but not approved yet."
        else:
            decision_status = "warn"
            decision_message = "No dry-run approval decision has been logged."
        milestones.append(
            _strategy_health_milestone(
                id="approval_decision",
                label="Dry-run approval decision",
                status=decision_status,
                message=decision_message,
                evidence_id=decisions[0].id if decisions else None,
            )
        )

        if latest_attempt is None:
            attempt_status = "warn"
            attempt_message = "No live approval attempt has been recorded for this dry-run audit."
        elif latest_attempt.status == "submitted":
            attempt_status = "pass"
            attempt_message = "Latest approval attempt was submitted to the exchange adapter."
        elif latest_attempt.status == "failed":
            attempt_status = "fail"
            attempt_message = f"Latest approval attempt failed: {latest_attempt.reason}"
        else:
            attempt_status = "warn"
            attempt_message = f"Latest approval attempt is {latest_attempt.status}: {latest_attempt.reason}"
        milestones.append(
            _strategy_health_milestone(
                id="approval_attempt",
                label="Live approval attempt",
                status=attempt_status,
                message=attempt_message,
                evidence_id=latest_attempt.id if latest_attempt else None,
            )
        )

        closeout_status = None
        if latest_attempt:
            closeout_status = latest_attempt.status
            closeout_message = (
                f"Closeout monitor includes approval attempt {latest_attempt.id} with status {latest_attempt.status}."
            )
            closeout_milestone_status = "pass" if latest_attempt.status == "submitted" else "warn"
            if latest_attempt.status == "failed":
                closeout_milestone_status = "fail"
        else:
            closeout_message = "Closeout monitor has no approval attempt for this dry-run audit yet."
            closeout_milestone_status = "warn"
        milestones.append(
            _strategy_health_milestone(
                id="closeout_outcome",
                label="Closeout outcome",
                status=closeout_milestone_status,
                message=closeout_message,
                evidence_id=monitor.checked_at,
            )
        )

        traces.append(
            StrategyHealthTrace(
                id=dry_run.id,
                status=_strategy_health_status(
                    milestones=milestones,
                    approval_attempts=approval_attempts,
                    decisions=decisions,
                ),
                market=dry_run.market,
                side=dry_run.side,
                scenario_id=context.get("scenario_id") if isinstance(context.get("scenario_id"), str) else None,
                scenario_name=context.get("scenario_name") if isinstance(context.get("scenario_name"), str) else None,
                watchlist_id=context.get("watchlist_id") if isinstance(context.get("watchlist_id"), str) else None,
                source_session_id=str(source_session_id) if source_session_id else None,
                source_trade_timestamp=str(source_trade_timestamp) if source_trade_timestamp else None,
                simulated_notional=payload.get("simulated_notional") if isinstance(payload.get("simulated_notional"), (int, float)) else None,
                promotion_rules=promotion_rules,
                dry_run_audit=dry_run,
                approval_decisions=decisions,
                approval_attempts=approval_attempts,
                latest_approval_attempt=latest_attempt,
                closeout_status=closeout_status,
                milestones=milestones,
            )
        )

    counts = {
        "traces": len(traces),
        "healthy": sum(1 for trace in traces if trace.status == "healthy"),
        "watch": sum(1 for trace in traces if trace.status == "watch"),
        "attention": sum(1 for trace in traces if trace.status == "attention"),
        "blocked": sum(1 for trace in traces if trace.status == "blocked"),
    }
    return StrategyHealthTraceResponse(
        checked_at=checked_at,
        traces=traces,
        counts=counts,
    )


def _handoff_value(value: object) -> str:
    if value is None or value == "":
        return "-"
    return str(value)


def _strategy_health_handoff_report(
    limit: int = 20,
    route_status: Optional[str] = None,
) -> StrategyHealthHandoffReport:
    generated_at = datetime.now(timezone.utc).isoformat()
    title = "Strategy Health Handoff Report"
    filename = f"strategy-health-handoff-{generated_at[:10]}.md"
    traces = _strategy_health_traces(limit=limit)
    closeout_report = _post_cutover_closeout_report(_post_cutover_monitor())
    closeout_monitor = closeout_report.monitor
    active_alerts = _alert_review_queue(include_acknowledged=False).items
    counts = traces.counts
    lines = [
        f"# {title}",
        "",
        f"- Generated: {generated_at}",
        f"- Strategy trace checked at: {traces.checked_at}",
        f"- Trace rows included: {counts.get('traces', 0)}",
        f"- Healthy: {counts.get('healthy', 0)}",
        f"- Watch: {counts.get('watch', 0)}",
        f"- Attention: {counts.get('attention', 0)}",
        f"- Blocked: {counts.get('blocked', 0)}",
        f"- Closeout monitor status: {closeout_monitor.status}",
        f"- Closeout report file: {closeout_report.filename}",
        f"- Active alerts: {len(active_alerts)}",
        "",
        "## Strategy Trace Summary",
        "",
        f"- Healthy traces: {counts.get('healthy', 0)}",
        f"- Watch traces: {counts.get('watch', 0)}",
        f"- Attention traces: {counts.get('attention', 0)}",
        f"- Blocked traces: {counts.get('blocked', 0)}",
        f"- Approval attempts: {closeout_monitor.counts.get('approval_attempts', 0)}",
        f"- Submitted attempts: {closeout_monitor.counts.get('submitted', 0)}",
        f"- Blocked attempts: {closeout_monitor.counts.get('blocked', 0)}",
        f"- Failed attempts: {closeout_monitor.counts.get('failed', 0)}",
        f"- Private open orders: {closeout_monitor.counts.get('open_orders', 0)}",
        "",
        "## Active Alert Review Items",
        "",
    ]
    if active_alerts:
        for alert in active_alerts[:20]:
            lines.extend(
                [
                    f"- [{alert.level}] {alert.title}",
                    f"  - Source: {alert.source}",
                    f"  - Message: {alert.message}",
                    f"  - Evaluation id: {_handoff_value(alert.evaluation_id)}",
                    f"  - Reconciliation id: {_handoff_value(alert.reconciliation_id)}",
                    f"  - Symbol: {_handoff_value(alert.symbol)}",
                ]
            )
    else:
        lines.append("- No active alert review items.")
    lines.extend(
        [
            "",
            "## Trace Rows",
            "",
        ]
    )

    if not traces.traces:
        lines.append("- No dry-run strategy traces were available for this handoff.")

    for index, trace in enumerate(traces.traces, start=1):
        latest_attempt = trace.latest_approval_attempt
        lines.extend(
            [
                f"### {index}. {trace.scenario_name or trace.market}",
                "",
                f"- Trace id: {trace.id}",
                f"- Status: {trace.status}",
                f"- Market: {trace.market}",
                f"- Side: {trace.side}",
                f"- Scenario id: {_handoff_value(trace.scenario_id)}",
                f"- Watchlist id: {_handoff_value(trace.watchlist_id)}",
                f"- Source session id: {_handoff_value(trace.source_session_id)}",
                f"- Source trade timestamp: {_handoff_value(trace.source_trade_timestamp)}",
                f"- Simulated notional: {_handoff_value(trace.simulated_notional)}",
                f"- Dry-run audit id: {trace.dry_run_audit.id}",
                f"- Dry-run runbook: /api/execution/order-audits/{trace.id}/runbook",
                f"- Latest approval attempt id: {_handoff_value(latest_attempt.id if latest_attempt else None)}",
                f"- Latest approval attempt status: {_handoff_value(latest_attempt.status if latest_attempt else None)}",
                f"- Latest approval attempt reason: {_handoff_value(latest_attempt.reason if latest_attempt else None)}",
                f"- Closeout status: {_handoff_value(trace.closeout_status)}",
                "",
                "#### Promotion Rules",
                "",
            ]
        )
        if trace.promotion_rules:
            for key, value in sorted(trace.promotion_rules.items()):
                lines.append(f"- {key}: {value}")
        else:
            lines.append("- No promotion rules were attached.")

        lines.extend(["", "#### Operator Decisions", ""])
        if trace.approval_decisions:
            for decision in trace.approval_decisions:
                lines.extend(
                    [
                        f"- {decision.created_at}: {decision.status.replace('_', ' ')}",
                        f"  - Decision id: {decision.id}",
                        f"  - Note: {decision.note or '-'}",
                    ]
                )
        else:
            lines.append("- No dry-run approval decisions were logged.")

        lines.extend(["", "#### Approval Attempts", ""])
        if trace.approval_attempts:
            for attempt in trace.approval_attempts:
                lines.extend(
                    [
                        f"- {attempt.created_at}: {attempt.status}",
                        f"  - Attempt id: {attempt.id}",
                        f"  - Reason: {attempt.reason}",
                    ]
                )
        else:
            lines.append("- No live approval attempts were recorded.")

        lines.extend(["", "#### Milestones", ""])
        for milestone in trace.milestones:
            lines.append(
                f"- [{_runbook_check_marker(milestone.status)}] {milestone.label}: {milestone.status} - {milestone.message}"
            )
            if milestone.evidence_id:
                lines.append(f"  - Evidence id: {milestone.evidence_id}")
        lines.append("")

    paper_only_decisions = [
        decision
        for decision in operator_decision_store.list_decisions(
            decision_type="dry_run_promotion",
            limit=50,
        )
        if decision.context.get("route_status") == "paper_only_review"
        and (route_status is None or decision.context.get("route_status") == route_status)
    ][:limit]
    lines.extend(["## Paper-Only Strategy Handoffs", ""])
    if route_status:
        lines.extend([f"- Route status filter: {route_status}", ""])
    if paper_only_decisions:
        for index, decision in enumerate(paper_only_decisions, start=1):
            context = decision.context
            symbol = str(context.get("symbol", decision.target_id or "")).upper()
            session_id = str(context.get("session_id", "") or "")
            broker_evaluations = (
                broker_intent_evaluation_store.list_evaluations(
                    symbol=symbol,
                    limit=3,
                )
                if symbol and symbol != "-"
                else []
            )
            order_notes = (
                paper_fill_order_note_store.list_notes(session_id=session_id, limit=3)
                if session_id
                else []
            )
            lines.extend(
                [
                    f"### {index}. {symbol or '-'}",
                    "",
                    f"- Decision id: {decision.id}",
                    f"- Handoff id: {context.get('handoff_id', decision.target_id or '-')}",
                    f"- Created at: {decision.created_at}",
                    f"- Status: {decision.status.replace('_', ' ')}",
                    f"- Scenario: {context.get('scenario_name', '-')}",
                    f"- Session id: {session_id or '-'}",
                    f"- Source: {context.get('source', '-')}",
                    f"- Adapter: {context.get('adapter_label', '-')}",
                    f"- Execution mode: {context.get('execution_mode', '-')}",
                    f"- Live order supported: {context.get('live_order_supported', '-')}",
                    f"- Total return: {context.get('total_return_pct', '-')}",
                    f"- Max drawdown: {context.get('max_drawdown_pct', '-')}",
                    f"- Orders: {context.get('orders', '-')}",
                    f"- Note: {decision.note or '-'}",
                    "",
                ]
            )
            if broker_evaluations:
                lines.extend(["#### Broker Intent Evaluations", ""])
                for evaluation in broker_evaluations:
                    fill = evaluation.paper_fill_estimate
                    fill_status = fill.status.replace("_", " ") if fill else "-"
                    fill_price = (
                        f"${fill.fill_price:,.2f}"
                        if fill and fill.fill_price is not None
                        else "-"
                    )
                    cash_after = (
                        f"${fill.cash_after:,.2f}"
                        if fill and fill.cash_after is not None
                        else "-"
                    )
                    exposure_after = (
                        f"{fill.exposure_pct_after:.2f}%"
                        if fill and fill.exposure_pct_after is not None
                        else "-"
                    )
                    lines.extend(
                        [
                            f"- {evaluation.checked_at}: {evaluation.submission_status.replace('_', ' ')}",
                            f"  - Evaluation id: {evaluation.id}",
                            f"  - Adapter id: {evaluation.adapter_id}",
                            f"  - Broker contract: {evaluation.broker_contract.id}",
                            f"  - Paper fill status: {fill_status}",
                            f"  - Paper fill price: {fill_price}",
                            f"  - Paper cash after: {cash_after}",
                            f"  - Paper exposure after: {exposure_after}",
                            f"  - External submission attempted: {evaluation.external_submission_attempted}",
                        ]
                    )
                lines.append("")
            else:
                lines.extend(["#### Broker Intent Evaluations", "", "- No broker intent evaluations were found for this symbol.", ""])
            if order_notes:
                lines.extend(["#### Paper Fill Order Notes", ""])
                for note in order_notes:
                    simulated_fill = (
                        f"${note.simulated_fill_price:,.2f}"
                        if note.simulated_fill_price is not None
                        else "-"
                    )
                    price_delta_pct = (
                        f"{note.price_delta_pct:.2f}%"
                        if note.price_delta_pct is not None
                        else "-"
                    )
                    lines.extend(
                        [
                            f"- {note.created_at}: {note.adapter_id}",
                            f"  - Evaluation id: {note.evaluation_id}",
                            f"  - Intended fill: ${note.intended_fill_price:,.2f}",
                            f"  - Simulated fill: {simulated_fill}",
                            f"  - Price delta: {price_delta_pct}",
                            f"  - Comparison status: {note.comparison_status.replace('_', ' ')}",
                        ]
                    )
                lines.append("")
            else:
                lines.extend(["#### Paper Fill Order Notes", "", "- No linked paper fill order notes were found for this session.", ""])
    else:
        lines.append("- No stock/ETF paper-only handoffs have been logged yet.")
        lines.append("")

    lines.extend(
        [
            "## Closeout Snapshot",
            "",
            f"- Closeout report title: {closeout_report.title}",
            f"- Closeout report file: {closeout_report.filename}",
            "- Closeout report endpoint: /api/execution/post-cutover-monitor/closeout-report",
            f"- Monitor checked at: {closeout_monitor.checked_at}",
            f"- Monitor status: {closeout_monitor.status}",
            f"- Live trading flag: {'on' if closeout_monitor.settings.live_trading_enabled else 'off'}",
            f"- Adapter ready: {'yes' if closeout_monitor.settings.adapter_ready else 'no'}",
            f"- Private reads enabled: {'yes' if closeout_monitor.settings.private_reads_enabled else 'no'}",
            "",
        ]
    )
    for item in closeout_monitor.items:
        lines.append(f"- [{_runbook_check_marker(item.status)}] {item.label}: {item.status} - {item.message}")
        if item.evidence_id:
            lines.append(f"  - Evidence id: {item.evidence_id}")

    lines.extend(
        [
            "",
            "## Handoff Actions",
            "",
            "1. Review each trace whose status is attention or blocked before the next cutover window.",
            "2. Export each linked dry-run runbook for traces that will be considered for live approval.",
            "3. Export the live-window closeout report and archive it with this strategy handoff.",
            "4. Record follow-up approvals, rejections, or needs-work notes in the Operations journal.",
            "5. Keep QUANT_LAB_LIVE_TRADING_ENABLED off until the next approved cutover window.",
        ]
    )
    markdown = "\n".join(lines)
    return StrategyHealthHandoffReport(
        generated_at=generated_at,
        title=title,
        filename=filename,
        traces=traces,
        closeout_report=closeout_report,
        markdown=markdown,
    )


def _strategy_health_for_symbol(
    *,
    symbol: str,
    limit: int,
) -> StrategyHealthTraceResponse:
    traces = _strategy_health_traces(limit=100)
    filtered = [trace for trace in traces.traces if trace.market.upper() == symbol][:limit]
    counts = {
        "traces": len(filtered),
        "healthy": sum(1 for trace in filtered if trace.status == "healthy"),
        "watch": sum(1 for trace in filtered if trace.status == "watch"),
        "attention": sum(1 for trace in filtered if trace.status == "attention"),
        "blocked": sum(1 for trace in filtered if trace.status == "blocked"),
    }
    return StrategyHealthTraceResponse(
        checked_at=traces.checked_at,
        traces=filtered,
        counts=counts,
    )


def _crypto_live_beta_drill_report(
    *,
    symbol: str,
    limit: int,
) -> CryptoLiveBetaDrillReport:
    generated_at = datetime.now(timezone.utc).isoformat()
    title = "Crypto Live Beta Drill Report"
    filename = f"crypto-live-beta-drill-{symbol.lower()}-{generated_at[:10]}.md".replace("/", "-")
    paper_sessions = [
        session
        for session in session_store.list_paper_sessions(limit=200)
        if session.request.symbol.upper() == symbol
    ][:limit]
    dry_run_audits = [
        record
        for record in order_audit_store.list_records(limit=200)
        if record.market.upper() == symbol and record.status == "dry_run"
    ][:limit]
    prechecks: dict[str, OrderPrecheckResult] = {}
    runbooks: list[ExecutionRunbook] = []
    for record in dry_run_audits:
        try:
            precheck = get_order_precheck(record_id=record.id, audit_store=order_audit_store)
        except (LookupError, ValueError):
            continue
        prechecks[record.id] = precheck
        runbooks.append(_execution_runbook(record=record, precheck=precheck))

    readiness = _live_readiness()
    cutover_simulation = _simulate_live_arming(
        LiveArmingSimulationRequest(
            live_trading_enabled=True,
            live_ack_configured=True,
            credential_configured=True,
            assume_required_operator_decisions=False,
        )
    )
    closeout_report = _post_cutover_closeout_report(_post_cutover_monitor())
    strategy_health = _strategy_health_for_symbol(symbol=symbol, limit=limit)

    lines = [
        f"# {title}",
        "",
        f"- Generated: {generated_at}",
        f"- Market: {symbol}",
        "- Drill mode: evidence-only; no live order submission is performed by this report.",
        f"- Paper sessions included: {len(paper_sessions)}",
        f"- Dry-run audits included: {len(dry_run_audits)}",
        f"- Prechecks generated: {len(prechecks)}",
        f"- Runbooks generated: {len(runbooks)}",
        f"- Readiness status: {readiness.status} ({readiness.score:.1f}/100)",
        f"- Cutover simulation summary: {cutover_simulation.summary}",
        f"- Closeout status: {closeout_report.monitor.status}",
        "",
        "## Safety Boundary",
        "",
        "- This report reads existing paper, dry-run, readiness, cutover, and closeout evidence.",
        "- The cutover preview is simulated and does not change environment variables.",
        "- Live submission remains blocked unless the explicit Upbit live env gates and per-order confirmation are set outside this report.",
        "- Stock/ETF paper broker routes are excluded from this crypto drill.",
        "",
        "## Paper Sessions",
        "",
    ]
    if paper_sessions:
        for session in paper_sessions:
            lines.extend(
                [
                    f"- Session id: {session.id}",
                    f"  - Created at: {session.created_at}",
                    f"  - Strategy: {session.request.strategy}",
                    f"  - Source: {session.request.source}",
                    f"  - Status: {session.summary.status}",
                    f"  - Total return: {session.summary.total_return_pct:.2f}%",
                    f"  - Max drawdown: {session.summary.max_drawdown_pct:.2f}%",
                    f"  - Orders: {session.summary.orders}",
                ]
            )
    else:
        lines.append("- No paper sessions were found for this market.")

    lines.extend(["", "## Dry-Run Audits And Prechecks", ""])
    if dry_run_audits:
        for record in dry_run_audits:
            precheck = prechecks.get(record.id)
            lines.extend(
                [
                    f"### {record.id}",
                    "",
                    f"- Created at: {record.created_at}",
                    f"- Side: {record.side}",
                    f"- Order type: {record.ord_type}",
                    f"- Status: {record.status}",
                    f"- Reason: {record.reason}",
                    f"- Runbook endpoint: /api/execution/order-audits/{record.id}/runbook",
                ]
            )
            if precheck:
                lines.extend(
                    [
                        f"- Precheck status: {precheck.status}",
                        f"- Estimated notional: {precheck.estimated_notional}",
                        f"- Credential ready: {precheck.credential_ready}",
                    ]
                )
                for check in precheck.checks:
                    lines.append(
                        f"  - [{_runbook_check_marker(check.status)}] {check.name}: {check.status} - {check.message}"
                    )
            else:
                lines.append("- Precheck status: unavailable")
            lines.append("")
    else:
        lines.append("- No dry-run audits were found for this market.")

    lines.extend(["", "## Readiness Review", ""])
    if readiness.breakdowns:
        for breakdown in readiness.breakdowns:
            lines.extend(
                [
                    f"- {breakdown.label}: {breakdown.status} ({breakdown.score:.1f}/100)",
                    f"  - Blocking checks: {', '.join(breakdown.blocking_checks) if breakdown.blocking_checks else '-'}",
                    f"  - Warning checks: {', '.join(breakdown.warning_checks) if breakdown.warning_checks else '-'}",
                    f"  - Summary: {breakdown.message}",
                ]
            )
    for check in readiness.checks:
        lines.append(
            f"- [{_runbook_check_marker(check.status)}] {check.label} ({check.category}): {check.status} - {check.message}"
        )

    lines.extend(["", "## Cutover Simulation", ""])
    lines.extend(
        [
            f"- No order submission: {cutover_simulation.no_order_submission}",
            f"- Current checklist: {cutover_simulation.current.status}",
            f"- Simulated checklist: {cutover_simulation.simulated.status}",
            f"- Current blockers: {len(cutover_simulation.current_blockers)}",
            f"- Simulated blockers: {len(cutover_simulation.simulated_blockers)}",
            f"- Summary: {cutover_simulation.summary}",
        ]
    )
    if cutover_simulation.simulated_blockers:
        lines.extend(["", "### Simulated Blockers", ""])
        for item in cutover_simulation.simulated_blockers:
            lines.append(f"- {item.label}: {item.message}")

    lines.extend(["", "## Closeout Evidence", ""])
    monitor = closeout_report.monitor
    lines.extend(
        [
            f"- Closeout report file: {closeout_report.filename}",
            f"- Monitor checked at: {monitor.checked_at}",
            f"- Monitor status: {monitor.status}",
            f"- Approval attempts: {monitor.counts.get('approval_attempts', 0)}",
            f"- Submitted attempts: {monitor.counts.get('submitted', 0)}",
            f"- Blocked attempts: {monitor.counts.get('blocked', 0)}",
            f"- Private open orders: {monitor.counts.get('open_orders', 0)}",
        ]
    )
    for item in monitor.items:
        lines.append(f"- [{_runbook_check_marker(item.status)}] {item.label}: {item.status} - {item.message}")

    lines.extend(["", "## Strategy Health", ""])
    if strategy_health.traces:
        for trace in strategy_health.traces:
            lines.extend(
                [
                    f"- Trace id: {trace.id}",
                    f"  - Status: {trace.status}",
                    f"  - Scenario: {trace.scenario_name or '-'}",
                    f"  - Dry-run audit: {trace.dry_run_audit.id}",
                    f"  - Closeout status: {trace.closeout_status or '-'}",
                ]
            )
    else:
        lines.append("- No strategy-health traces were found for this market.")

    lines.extend(
        [
            "",
            "## Drill Actions",
            "",
            "1. Create or select a fresh KRW crypto paper session for the beta market.",
            "2. Queue dry-run order intents from the paper session and export each dry-run runbook.",
            "3. Log readiness review and dry-run approval decisions in the Operations journal.",
            "4. Re-run this report and confirm paper, dry-run, readiness, simulation, and closeout sections all contain expected evidence.",
            "5. Keep live env gates disabled until a separate, approved small-size cutover window.",
        ]
    )
    return CryptoLiveBetaDrillReport(
        generated_at=generated_at,
        title=title,
        filename=filename,
        symbol=symbol,
        paper_sessions=paper_sessions,
        dry_run_audits=dry_run_audits,
        prechecks=prechecks,
        runbooks=runbooks,
        readiness=readiness,
        cutover_simulation=cutover_simulation,
        closeout_report=closeout_report,
        strategy_health=strategy_health,
        markdown="\n".join(lines),
    )


def _operator_decision_with_paper_fill_quality_gate(
    request: OperatorDecisionCreate,
) -> OperatorDecisionCreate:
    if (
        request.decision_type != "dry_run_promotion"
        or request.status != "approved"
        or request.context.get("route_status") != "paper_only_review"
    ):
        return request

    symbol_value = request.context.get("symbol")
    if not isinstance(symbol_value, str) or not symbol_value.strip():
        raise ValueError(
            "Stock/ETF paper handoff approval requires a symbol in the decision context."
        )
    symbol = symbol_value.strip().upper()
    notes = paper_fill_order_note_store.list_notes(
        symbol=symbol,
        limit=PAPER_FILL_GATE_DEFAULT_LIMIT,
    )
    analytics = _paper_fill_order_note_analytics(
        notes=notes,
        limit=PAPER_FILL_GATE_DEFAULT_LIMIT,
        adapter_id=None,
        symbol=symbol,
    )
    quality_gate = _paper_fill_quality_gate(
        analytics=analytics,
        min_notes=PAPER_FILL_GATE_DEFAULT_MIN_NOTES,
        max_avg_abs_price_delta_pct=PAPER_FILL_GATE_DEFAULT_MAX_AVG_ABS_DELTA_PCT,
        max_worst_abs_price_delta_pct=PAPER_FILL_GATE_DEFAULT_MAX_WORST_ABS_DELTA_PCT,
        require_no_external_submission=PAPER_FILL_GATE_DEFAULT_REQUIRE_NO_EXTERNAL,
    )
    if quality_gate.status != "ready":
        raise ValueError(
            "Stock/ETF paper handoff approval requires paper fill quality gate "
            f"ready; current status is {quality_gate.status}: {quality_gate.reason}"
        )

    gate_rows = [
        {
            "adapter_id": row.adapter_id,
            "symbol": row.symbol,
            "status": row.status,
            "note_count": row.note_count,
            "matched_trade_count": row.matched_trade_count,
            "avg_abs_price_delta_pct": row.avg_abs_price_delta_pct,
            "worst_abs_price_delta_pct": row.worst_abs_price_delta_pct,
            "latest_evaluation_id": row.latest_evaluation_id,
        }
        for row in quality_gate.rows
    ]
    return request.model_copy(
        update={
            "context": {
                **request.context,
                "paper_fill_quality_gate_status": quality_gate.status,
                "paper_fill_quality_gate_reason": quality_gate.reason,
                "paper_fill_quality_gate_checked_at": quality_gate.generated_at,
                "paper_fill_quality_gate_min_notes": quality_gate.min_notes,
                "paper_fill_quality_gate_max_avg_abs_price_delta_pct": (
                    quality_gate.max_avg_abs_price_delta_pct
                ),
                "paper_fill_quality_gate_max_worst_abs_price_delta_pct": (
                    quality_gate.max_worst_abs_price_delta_pct
                ),
                "paper_fill_quality_gate_require_no_external_submission": (
                    quality_gate.require_no_external_submission
                ),
                "paper_fill_quality_gate_rows": gate_rows,
            },
        }
    )


def _stock_etf_broker_expansion_readiness(limit: int = 20) -> StockEtfBrokerExpansionReadiness:
    generated_at = datetime.now(timezone.utc).isoformat()
    paper_only_decisions = [
        decision
        for decision in operator_decision_store.list_decisions(
            decision_type="dry_run_promotion",
            limit=500,
        )
        if decision.context.get("route_status") == "paper_only_review"
    ]
    latest_by_handoff: dict[str, OperatorDecisionRecord] = {}
    for decision in paper_only_decisions:
        handoff_key = str(decision.context.get("handoff_id") or decision.target_id or decision.id)
        if handoff_key not in latest_by_handoff:
            latest_by_handoff[handoff_key] = decision

    candidates: list[StockEtfBrokerExpansionCandidate] = []
    for decision in list(latest_by_handoff.values())[:limit]:
        context = decision.context
        symbol = str(context.get("symbol") or "").strip().upper()
        if not symbol:
            symbol = str(decision.target_id or "-").upper()
        quality_gate = _paper_fill_quality_gate_for_symbol(symbol)
        first_row = quality_gate.rows[0] if quality_gate.rows else None
        approved = decision.status == "approved" and quality_gate.status == "ready"
        if approved:
            message = "Approved paper-only handoff has ready fill-quality evidence for broker-paper expansion."
        elif decision.status in {"rejected", "needs_work"}:
            message = f"Latest handoff review is {decision.status.replace('_', ' ')}."
        elif quality_gate.status != "ready":
            message = quality_gate.reason
        else:
            message = "Quality gate is ready, but the latest handoff review is not approved yet."
        candidates.append(
            StockEtfBrokerExpansionCandidate(
                decision_id=decision.id,
                target_id=decision.target_id,
                created_at=decision.created_at,
                decision_status=decision.status,
                symbol=symbol,
                session_id=str(context.get("session_id")) if context.get("session_id") else None,
                scenario_name=(
                    str(context.get("scenario_name")) if context.get("scenario_name") else None
                ),
                source=str(context.get("source")) if context.get("source") else None,
                adapter_id=str(context.get("adapter_id")) if context.get("adapter_id") else None,
                adapter_label=(
                    str(context.get("adapter_label")) if context.get("adapter_label") else None
                ),
                quality_gate_status=quality_gate.status,
                quality_gate_reason=quality_gate.reason,
                quality_gate_checked_at=quality_gate.generated_at,
                note_count=first_row.note_count if first_row else 0,
                matched_trade_count=first_row.matched_trade_count if first_row else 0,
                avg_abs_price_delta_pct=(
                    first_row.avg_abs_price_delta_pct if first_row else None
                ),
                worst_abs_price_delta_pct=(
                    first_row.worst_abs_price_delta_pct if first_row else None
                ),
                approved_for_broker_expansion=approved,
                message=message,
            )
        )

    counts = {
        "candidates": len(candidates),
        "approved_ready": sum(1 for candidate in candidates if candidate.approved_for_broker_expansion),
        "approved": sum(1 for candidate in candidates if candidate.decision_status == "approved"),
        "watch": sum(1 for candidate in candidates if candidate.quality_gate_status == "watch"),
        "blocked": sum(1 for candidate in candidates if candidate.quality_gate_status == "blocked"),
        "needs_work": sum(1 for candidate in candidates if candidate.decision_status == "needs_work"),
        "rejected": sum(1 for candidate in candidates if candidate.decision_status == "rejected"),
    }
    if counts["approved_ready"] > 0:
        status = "ready"
        reason = "At least one approved stock/ETF handoff has ready paper-fill evidence."
    elif counts["blocked"] > 0 or counts["rejected"] > 0:
        status = "blocked"
        reason = "No approved-ready stock/ETF handoff is available, and at least one candidate is blocked or rejected."
    elif candidates:
        status = "watch"
        reason = "Stock/ETF handoffs exist, but none are both approved and quality-gate ready."
    else:
        status = "watch"
        reason = "No stock/ETF paper-only handoffs have been logged yet."

    return StockEtfBrokerExpansionReadiness(
        generated_at=generated_at,
        status=status,
        reason=reason,
        counts=counts,
        candidates=candidates,
    )


def _paper_fill_quality_gate_for_symbol(symbol: str) -> PaperFillOrderNoteQualityGate:
    normalized_symbol = symbol.strip().upper()
    notes = paper_fill_order_note_store.list_notes(
        symbol=normalized_symbol,
        limit=PAPER_FILL_GATE_DEFAULT_LIMIT,
    )
    analytics = _paper_fill_order_note_analytics(
        notes=notes,
        limit=PAPER_FILL_GATE_DEFAULT_LIMIT,
        adapter_id=None,
        symbol=normalized_symbol,
    )
    return _paper_fill_quality_gate(
        analytics=analytics,
        min_notes=PAPER_FILL_GATE_DEFAULT_MIN_NOTES,
        max_avg_abs_price_delta_pct=PAPER_FILL_GATE_DEFAULT_MAX_AVG_ABS_DELTA_PCT,
        max_worst_abs_price_delta_pct=PAPER_FILL_GATE_DEFAULT_MAX_WORST_ABS_DELTA_PCT,
        require_no_external_submission=PAPER_FILL_GATE_DEFAULT_REQUIRE_NO_EXTERNAL,
    )


def _stock_etf_broker_expansion_report(
    readiness: StockEtfBrokerExpansionReadiness,
) -> StockEtfBrokerExpansionReport:
    generated_at = datetime.now(timezone.utc).isoformat()
    filename = f"stock-etf-broker-expansion-readiness-{generated_at[:10]}.md"
    lines = [
        "# Stock/ETF Broker Expansion Readiness",
        "",
        f"- Generated at: {generated_at}",
        f"- Status: {readiness.status}",
        f"- Reason: {readiness.reason}",
        f"- Candidates: {readiness.counts.get('candidates', 0)}",
        f"- Approved-ready candidates: {readiness.counts.get('approved_ready', 0)}",
        f"- Watch candidates: {readiness.counts.get('watch', 0)}",
        f"- Blocked candidates: {readiness.counts.get('blocked', 0)}",
        "",
        "## Candidates",
        "",
    ]
    if not readiness.candidates:
        lines.append("- No stock/ETF paper-only handoffs were available.")
    for index, candidate in enumerate(readiness.candidates, start=1):
        avg_delta = (
            f"{candidate.avg_abs_price_delta_pct:.4f}%"
            if candidate.avg_abs_price_delta_pct is not None
            else "-"
        )
        worst_delta = (
            f"{candidate.worst_abs_price_delta_pct:.4f}%"
            if candidate.worst_abs_price_delta_pct is not None
            else "-"
        )
        lines.extend(
            [
                f"### {index}. {candidate.symbol}",
                "",
                f"- Decision id: {candidate.decision_id}",
                f"- Target id: {candidate.target_id or '-'}",
                f"- Decision status: {candidate.decision_status.replace('_', ' ')}",
                f"- Approved for broker expansion: {candidate.approved_for_broker_expansion}",
                f"- Session id: {candidate.session_id or '-'}",
                f"- Scenario: {candidate.scenario_name or '-'}",
                f"- Source: {candidate.source or '-'}",
                f"- Adapter: {candidate.adapter_label or candidate.adapter_id or '-'}",
                f"- Quality gate status: {candidate.quality_gate_status}",
                f"- Quality gate reason: {candidate.quality_gate_reason}",
                f"- Linked notes: {candidate.note_count}",
                f"- Matched trades: {candidate.matched_trade_count}",
                f"- Avg absolute fill drift: {avg_delta}",
                f"- Worst absolute fill drift: {worst_delta}",
                f"- Message: {candidate.message}",
                "",
            ]
        )
    markdown = "\n".join(lines)
    return StockEtfBrokerExpansionReport(
        generated_at=generated_at,
        title="Stock/ETF Broker Expansion Readiness",
        filename=filename,
        readiness=readiness,
        markdown=markdown,
    )


def _stock_etf_broker_expansion_package(decision_id: str) -> StockEtfBrokerExpansionPackage:
    decision = next(
        (
            item
            for item in operator_decision_store.list_decisions(
                decision_type="dry_run_promotion",
                limit=500,
            )
            if item.id == decision_id
        ),
        None,
    )
    if decision is None:
        raise LookupError("Stock/ETF broker expansion candidate decision not found")

    readiness = _stock_etf_broker_expansion_readiness(limit=500)
    candidate = next(
        (item for item in readiness.candidates if item.decision_id == decision_id),
        None,
    )
    if candidate is None or decision.context.get("route_status") != "paper_only_review":
        raise LookupError("Stock/ETF broker expansion candidate not found")
    if not candidate.approved_for_broker_expansion:
        raise ValueError("Broker expansion packages require an approved-ready stock/ETF handoff.")

    generated_at = datetime.now(timezone.utc).isoformat()
    quality_gate = _paper_fill_quality_gate_for_symbol(candidate.symbol)
    broker_evaluations = broker_intent_evaluation_store.list_evaluations(
        symbol=candidate.symbol,
        limit=10,
    )
    order_notes = paper_fill_order_note_store.list_notes(
        symbol=candidate.symbol,
        limit=10,
    )
    order_payloads = [
        _stock_etf_expansion_order_payload(note)
        for note in order_notes
        if not note.external_submission_attempted
    ]
    filename = (
        f"stock-etf-broker-expansion-package-{candidate.symbol}-{decision_id[:8]}.md"
        .replace("/", "-")
    )
    title = f"Stock/ETF broker expansion package: {candidate.symbol}"
    markdown = _stock_etf_broker_expansion_package_markdown(
        generated_at=generated_at,
        title=title,
        candidate=candidate,
        quality_gate=quality_gate,
        broker_evaluations=broker_evaluations,
        order_notes=order_notes,
        order_payloads=order_payloads,
    )
    return StockEtfBrokerExpansionPackage(
        generated_at=generated_at,
        title=title,
        filename=filename,
        candidate=candidate,
        quality_gate=quality_gate,
        broker_evaluations=broker_evaluations,
        order_notes=order_notes,
        order_payloads=order_payloads,
        markdown=markdown,
    )


def _stock_etf_expansion_order_payload(
    note: PaperFillOrderNote,
) -> StockEtfBrokerExpansionOrderPayload:
    client_order_id = f"quant-lab-{note.evaluation_id[:8]}"
    payload: dict[str, object] = {
        "symbol": note.symbol,
        "qty": f"{note.quantity:.8f}".rstrip("0").rstrip("."),
        "side": note.side,
        "type": note.order_type,
        "time_in_force": "day",
        "client_order_id": client_order_id,
    }
    if note.order_type == "limit":
        payload["limit_price"] = round(note.intended_fill_price, 2)
    return StockEtfBrokerExpansionOrderPayload(
        adapter_id=note.adapter_id,
        symbol=note.symbol,
        side=note.side,
        quantity=note.quantity,
        order_type=note.order_type,
        expected_fill_price=note.intended_fill_price,
        estimated_notional=note.intended_notional,
        evaluation_id=note.evaluation_id,
        paper_session_id=note.session_id,
        external_submission_attempted=note.external_submission_attempted,
        payload=payload,
    )


def _stock_etf_broker_expansion_package_markdown(
    *,
    generated_at: str,
    title: str,
    candidate: StockEtfBrokerExpansionCandidate,
    quality_gate: PaperFillOrderNoteQualityGate,
    broker_evaluations: list[BrokerOrderIntentEvaluation],
    order_notes: list[PaperFillOrderNote],
    order_payloads: list[StockEtfBrokerExpansionOrderPayload],
) -> str:
    lines = [
        f"# {title}",
        "",
        f"- Generated at: {generated_at}",
        f"- Candidate decision id: {candidate.decision_id}",
        f"- Symbol: {candidate.symbol}",
        f"- Decision status: {candidate.decision_status.replace('_', ' ')}",
        f"- Approved for broker expansion: {candidate.approved_for_broker_expansion}",
        f"- Session id: {candidate.session_id or '-'}",
        f"- Scenario: {candidate.scenario_name or '-'}",
        f"- Adapter: {candidate.adapter_label or candidate.adapter_id or '-'}",
        "",
        "## Quality Gate",
        "",
        f"- Status: {quality_gate.status}",
        f"- Reason: {quality_gate.reason}",
        f"- Minimum notes: {quality_gate.min_notes}",
        f"- Avg drift limit: {quality_gate.max_avg_abs_price_delta_pct:.2f}%",
        f"- Worst drift limit: {quality_gate.max_worst_abs_price_delta_pct:.2f}%",
        f"- Require no external submission: {quality_gate.require_no_external_submission}",
        "",
    ]
    for row in quality_gate.rows:
        avg_delta = (
            f"{row.avg_abs_price_delta_pct:.4f}%"
            if row.avg_abs_price_delta_pct is not None
            else "-"
        )
        worst_delta = (
            f"{row.worst_abs_price_delta_pct:.4f}%"
            if row.worst_abs_price_delta_pct is not None
            else "-"
        )
        lines.extend(
            [
                f"- {row.symbol} / {row.adapter_id}: {row.status}",
                f"  - Notes: {row.note_count}",
                f"  - Matched trades: {row.matched_trade_count}",
                f"  - Avg absolute fill drift: {avg_delta}",
                f"  - Worst absolute fill drift: {worst_delta}",
            ]
        )

    lines.extend(["", "## Alpaca-Style Paper Order Payloads", ""])
    if not order_payloads:
        lines.append("- No payloads were generated from linked paper fill order notes.")
    for index, payload in enumerate(order_payloads[:5], start=1):
        lines.extend(
            [
                f"### Payload {index}",
                "",
                f"- Adapter id: {payload.adapter_id}",
                f"- Evaluation id: {payload.evaluation_id}",
                f"- Paper session id: {payload.paper_session_id}",
                f"- Expected fill price: ${payload.expected_fill_price:,.2f}",
                f"- Estimated notional: ${payload.estimated_notional:,.2f}",
                "- External submission attempted: false",
                "",
                "```json",
                json.dumps(payload.payload, indent=2, sort_keys=True),
                "```",
                "",
            ]
        )

    lines.extend(["## Evidence", ""])
    lines.append(f"- Broker evaluations included: {len(broker_evaluations)}")
    for evaluation in broker_evaluations[:5]:
        fill = evaluation.paper_fill_estimate
        lines.extend(
            [
                f"- {evaluation.checked_at}: {evaluation.adapter_id}",
                f"  - Evaluation id: {evaluation.id}",
                f"  - Submission status: {evaluation.submission_status.replace('_', ' ')}",
                f"  - Fill status: {fill.status.replace('_', ' ') if fill else '-'}",
                f"  - External submission attempted: {evaluation.external_submission_attempted}",
            ]
        )
    lines.append(f"- Paper fill order notes included: {len(order_notes)}")
    for note in order_notes[:5]:
        delta = f"{note.price_delta_pct:.4f}%" if note.price_delta_pct is not None else "-"
        lines.extend(
            [
                f"- {note.created_at}: {note.adapter_id}",
                f"  - Evaluation id: {note.evaluation_id}",
                f"  - Intended fill: ${note.intended_fill_price:,.2f}",
                f"  - Comparison status: {note.comparison_status.replace('_', ' ')}",
                f"  - Price delta: {delta}",
            ]
        )

    lines.extend(
        [
            "",
            "## Stop Conditions",
            "",
            "- Do not submit these payloads to an external broker from this application yet.",
            "- Keep stock/ETF routing paper-only until a dedicated credentialed broker adapter is implemented and reviewed.",
            "- Re-run the quality gate after changing fee, slippage, or broker adapter assumptions.",
            "- Stop if any external submission flag appears in the evidence.",
        ]
    )
    return "\n".join(lines)


def _stock_etf_broker_expansion_preflight(decision_id: str) -> StockEtfBrokerExpansionPreflight:
    expansion_package = _stock_etf_broker_expansion_package(decision_id)
    checks = _stock_etf_broker_expansion_preflight_checks(expansion_package)
    if any(check.status == "fail" for check in checks):
        status = "fail"
        reason = "One or more package preflight checks failed."
    elif any(check.status == "warn" for check in checks):
        status = "warn"
        reason = "Package is usable for review, but at least one warning remains."
    else:
        status = "pass"
        reason = "Package preflight passed; keep it paper-only until a credentialed adapter is implemented."

    generated_at = datetime.now(timezone.utc).isoformat()
    title = f"Stock/ETF broker expansion preflight: {expansion_package.candidate.symbol}"
    filename = (
        f"stock-etf-broker-expansion-preflight-"
        f"{expansion_package.candidate.symbol}-{decision_id[:8]}.md"
    ).replace("/", "-")
    markdown = _stock_etf_broker_expansion_preflight_markdown(
        generated_at=generated_at,
        title=title,
        status=status,
        reason=reason,
        expansion_package=expansion_package,
        checks=checks,
    )
    return StockEtfBrokerExpansionPreflight(
        generated_at=generated_at,
        title=title,
        filename=filename,
        status=status,
        reason=reason,
        package=expansion_package,
        checks=checks,
        markdown=markdown,
    )


def _stock_etf_broker_expansion_preflight_checks(
    expansion_package: StockEtfBrokerExpansionPackage,
) -> list[StockEtfBrokerExpansionPreflightCheck]:
    candidate = expansion_package.candidate
    checks: list[StockEtfBrokerExpansionPreflightCheck] = [
        StockEtfBrokerExpansionPreflightCheck(
            id="candidate_approved_ready",
            label="Approved-ready candidate",
            status="pass" if candidate.approved_for_broker_expansion else "fail",
            message=(
                "Candidate is approved and quality-gate ready."
                if candidate.approved_for_broker_expansion
                else "Candidate must be approved and quality-gate ready before packaging."
            ),
            evidence_id=candidate.decision_id,
        ),
        StockEtfBrokerExpansionPreflightCheck(
            id="quality_gate_ready",
            label="Paper fill quality gate",
            status="pass" if expansion_package.quality_gate.status == "ready" else "fail",
            message=expansion_package.quality_gate.reason,
            evidence_id=expansion_package.quality_gate.generated_at,
        ),
    ]

    payloads = expansion_package.order_payloads
    checks.append(
        StockEtfBrokerExpansionPreflightCheck(
            id="payload_count",
            label="Payload count",
            status="pass" if payloads else "fail",
            message=(
                f"{len(payloads)} Alpaca-style paper payload draft(s) generated."
                if payloads
                else "At least one payload draft is required."
            ),
            evidence_id=candidate.session_id,
        )
    )
    schema_errors: list[str] = []
    required_keys = {"symbol", "qty", "side", "type", "time_in_force", "client_order_id"}
    for payload in payloads:
        raw = payload.payload
        missing = sorted(required_keys - set(raw.keys()))
        if missing:
            schema_errors.append(f"{payload.evaluation_id}: missing {', '.join(missing)}")
        if raw.get("symbol") != candidate.symbol:
            schema_errors.append(f"{payload.evaluation_id}: symbol mismatch")
        try:
            qty = float(str(raw.get("qty", "0")))
        except ValueError:
            qty = 0
        if qty <= 0:
            schema_errors.append(f"{payload.evaluation_id}: qty must be positive")
        if raw.get("side") not in {"buy", "sell"}:
            schema_errors.append(f"{payload.evaluation_id}: invalid side")
        if raw.get("type") not in {"market", "limit"}:
            schema_errors.append(f"{payload.evaluation_id}: invalid order type")
        if raw.get("type") == "limit" and "limit_price" not in raw:
            schema_errors.append(f"{payload.evaluation_id}: limit order missing limit_price")
    checks.append(
        StockEtfBrokerExpansionPreflightCheck(
            id="payload_schema",
            label="Payload schema",
            status="fail" if schema_errors else "pass",
            message=(
                "; ".join(schema_errors)
                if schema_errors
                else "All payload drafts contain the required paper broker fields."
            ),
        )
    )

    external_attempts = [
        evaluation.id
        for evaluation in expansion_package.broker_evaluations
        if evaluation.external_submission_attempted
    ]
    external_attempts.extend(
        note.evaluation_id
        for note in expansion_package.order_notes
        if note.external_submission_attempted
    )
    external_attempts.extend(
        payload.evaluation_id
        for payload in payloads
        if payload.external_submission_attempted
    )
    checks.append(
        StockEtfBrokerExpansionPreflightCheck(
            id="no_external_submission",
            label="No external submission",
            status="fail" if external_attempts else "pass",
            message=(
                f"External submission evidence found: {', '.join(external_attempts)}"
                if external_attempts
                else "No broker evaluation, order note, or payload attempted external submission."
            ),
        )
    )

    has_alpaca_preview = any(
        payload.adapter_id == "alpaca_us_equity_paper_preview" for payload in payloads
    )
    checks.append(
        StockEtfBrokerExpansionPreflightCheck(
            id="alpaca_preview_payload",
            label="Alpaca preview payload",
            status="pass" if has_alpaca_preview else "warn",
            message=(
                "At least one payload is tied to the Alpaca-style paper preview adapter."
                if has_alpaca_preview
                else "No Alpaca-style payload was found; generate preview evidence before implementation."
            ),
        )
    )
    return checks


def _stock_etf_broker_expansion_preflight_markdown(
    *,
    generated_at: str,
    title: str,
    status: str,
    reason: str,
    expansion_package: StockEtfBrokerExpansionPackage,
    checks: list[StockEtfBrokerExpansionPreflightCheck],
) -> str:
    candidate = expansion_package.candidate
    lines = [
        f"# {title}",
        "",
        f"- Generated at: {generated_at}",
        f"- Status: {status}",
        f"- Reason: {reason}",
        f"- Candidate decision id: {candidate.decision_id}",
        f"- Symbol: {candidate.symbol}",
        f"- Package file: {expansion_package.filename}",
        "",
        "## Preflight Checks",
        "",
    ]
    for check in checks:
        lines.extend(
            [
                f"- [{_runbook_check_marker(check.status)}] {check.label}: {check.status}",
                f"  - {check.message}",
            ]
        )
        if check.evidence_id:
            lines.append(f"  - Evidence id: {check.evidence_id}")
    lines.extend(
        [
            "",
            "## Next Actions",
            "",
            "1. Keep stock/ETF routing paper-only in this application.",
            "2. Implement the credentialed broker adapter behind an explicit paper-trading flag.",
            "3. Replay these payloads only in the broker's paper environment after code review.",
            "4. Re-run this preflight after changing order schema, fee, slippage, or adapter assumptions.",
        ]
    )
    return "\n".join(lines)


def _stock_etf_broker_expansion_rehearsal(decision_id: str) -> StockEtfBrokerExpansionRehearsal:
    preflight = _stock_etf_broker_expansion_preflight(decision_id)
    orders = [
        _stock_etf_broker_expansion_rehearsal_order(payload=payload, preflight=preflight)
        for payload in preflight.package.order_payloads
    ]
    accepted = sum(1 for order in orders if order.status == "accepted")
    rejected = len(orders) - accepted
    if preflight.status == "fail" or rejected > 0:
        status = "fail"
        reason = "Rehearsal found rejected paper broker payloads."
    elif preflight.status == "warn":
        status = "warn"
        reason = "Rehearsal accepted payloads, but preflight warnings remain."
    else:
        status = "pass"
        reason = "All package payloads were accepted by the local paper broker rehearsal."

    generated_at = datetime.now(timezone.utc).isoformat()
    title = f"Stock/ETF broker expansion rehearsal: {preflight.package.candidate.symbol}"
    filename = (
        f"stock-etf-broker-expansion-rehearsal-"
        f"{preflight.package.candidate.symbol}-{decision_id[:8]}.md"
    ).replace("/", "-")
    markdown = _stock_etf_broker_expansion_rehearsal_markdown(
        generated_at=generated_at,
        title=title,
        status=status,
        reason=reason,
        preflight=preflight,
        orders=orders,
    )
    return StockEtfBrokerExpansionRehearsal(
        generated_at=generated_at,
        title=title,
        filename=filename,
        status=status,
        reason=reason,
        preflight=preflight,
        accepted_orders=accepted,
        rejected_orders=rejected,
        orders=orders,
        markdown=markdown,
    )


def _stock_etf_broker_expansion_rehearsal_order(
    *,
    payload: StockEtfBrokerExpansionOrderPayload,
    preflight: StockEtfBrokerExpansionPreflight,
) -> StockEtfBrokerExpansionRehearsalOrder:
    raw = payload.payload
    status: Literal["accepted", "rejected"] = "accepted"
    reason = "Payload accepted by local paper broker rehearsal; no external submission attempted."
    try:
        qty = float(str(raw.get("qty", "0")))
    except ValueError:
        qty = 0
    if preflight.status == "fail":
        status = "rejected"
        reason = "Preflight failed, so the local paper broker rehearsal rejected the payload."
    elif payload.external_submission_attempted:
        status = "rejected"
        reason = "Payload is linked to external-submission evidence."
    elif raw.get("symbol") != payload.symbol or raw.get("symbol") != preflight.package.candidate.symbol:
        status = "rejected"
        reason = "Payload symbol does not match the approved-ready candidate."
    elif qty <= 0:
        status = "rejected"
        reason = "Payload quantity must be positive."
    elif raw.get("side") != payload.side or raw.get("side") not in {"buy", "sell"}:
        status = "rejected"
        reason = "Payload side is invalid or mismatched."
    elif raw.get("type") != payload.order_type or raw.get("type") not in {"market", "limit"}:
        status = "rejected"
        reason = "Payload order type is invalid or mismatched."
    elif raw.get("type") == "limit" and "limit_price" not in raw:
        status = "rejected"
        reason = "Limit payload requires limit_price."

    return StockEtfBrokerExpansionRehearsalOrder(
        id=f"rehearsal-{payload.evaluation_id[:8]}",
        evaluation_id=payload.evaluation_id,
        adapter_id=payload.adapter_id,
        symbol=payload.symbol,
        side=payload.side,
        quantity=payload.quantity,
        order_type=payload.order_type,
        status=status,
        reason=reason,
        expected_fill_price=payload.expected_fill_price,
        estimated_notional=payload.estimated_notional,
        paper_session_id=payload.paper_session_id,
        external_submission_attempted=False,
        payload=raw,
    )


def _stock_etf_broker_expansion_rehearsal_markdown(
    *,
    generated_at: str,
    title: str,
    status: str,
    reason: str,
    preflight: StockEtfBrokerExpansionPreflight,
    orders: list[StockEtfBrokerExpansionRehearsalOrder],
) -> str:
    lines = [
        f"# {title}",
        "",
        f"- Generated at: {generated_at}",
        f"- Status: {status}",
        f"- Reason: {reason}",
        f"- Preflight status: {preflight.status}",
        f"- Candidate decision id: {preflight.package.candidate.decision_id}",
        f"- Symbol: {preflight.package.candidate.symbol}",
        f"- Accepted orders: {sum(1 for order in orders if order.status == 'accepted')}",
        f"- Rejected orders: {sum(1 for order in orders if order.status == 'rejected')}",
        "",
        "## Rehearsed Orders",
        "",
    ]
    if not orders:
        lines.append("- No payloads were available to rehearse.")
    for order in orders:
        lines.extend(
            [
                f"- {order.id}: {order.status}",
                f"  - Evaluation id: {order.evaluation_id}",
                f"  - Adapter id: {order.adapter_id}",
                f"  - Side: {order.side}",
                f"  - Quantity: {order.quantity}",
                f"  - Order type: {order.order_type}",
                f"  - Expected fill price: ${order.expected_fill_price:,.2f}",
                f"  - Estimated notional: ${order.estimated_notional:,.2f}",
                f"  - External submission attempted: {order.external_submission_attempted}",
                f"  - Reason: {order.reason}",
            ]
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- This rehearsal is local and paper-only.",
            "- It does not call Alpaca or any external broker endpoint.",
            "- It is intended to validate adapter implementation inputs before credentialed paper integration work.",
        ]
    )
    return "\n".join(lines)


def _operator_decision_report(
    *,
    decisions: list[OperatorDecisionRecord],
    decision_type: Optional[str],
    target_id: Optional[str],
    status: Optional[str],
    route_status: Optional[str],
) -> OperatorDecisionReport:
    generated_at = datetime.now(timezone.utc).isoformat()
    filename = f"operations-journal-{generated_at[:10]}.md"
    type_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    for decision in decisions:
        type_counts[decision.decision_type] = type_counts.get(decision.decision_type, 0) + 1
        status_counts[decision.status] = status_counts.get(decision.status, 0) + 1

    lines = [
        "# Operations Journal Report",
        "",
        f"- Generated at: {generated_at}",
        f"- Decision type filter: {decision_type or 'all'}",
        f"- Status filter: {status or 'all'}",
        f"- Target filter: {target_id or 'all'}",
        f"- Route status filter: {route_status or 'all'}",
        f"- Decisions included: {len(decisions)}",
        "",
        "## Summary",
        "",
        "### By Decision Type",
        "",
    ]
    if type_counts:
        lines.extend(
            f"- {decision_type_key.replace('_', ' ')}: {count}"
            for decision_type_key, count in sorted(type_counts.items())
        )
    else:
        lines.append("- No decisions matched the selected filters.")
    lines.extend(["", "### By Status", ""])
    if status_counts:
        lines.extend(
            f"- {status_key.replace('_', ' ')}: {count}"
            for status_key, count in sorted(status_counts.items())
        )
    else:
        lines.append("- No decisions matched the selected filters.")
    lines.extend(["", "## Decisions", ""])

    for index, decision in enumerate(decisions, start=1):
        lines.extend(
            [
                f"### {index}. {decision.decision_type.replace('_', ' ')}",
                "",
                f"- ID: {decision.id}",
                f"- Created at: {decision.created_at}",
                f"- Status: {decision.status.replace('_', ' ')}",
                f"- Target: {decision.target_id or '-'}",
                f"- Note: {decision.note or '-'}",
            ]
        )
        if decision.context:
            lines.append("- Context:")
            for key, value in decision.context.items():
                lines.append(f"  - {key}: {value}")
        lines.append("")

    markdown = "\n".join(lines)
    return OperatorDecisionReport(
        generated_at=generated_at,
        title="Operations Journal Report",
        filename=filename,
        decisions=decisions,
        markdown=markdown,
    )


def _broker_intent_evaluation_report(
    *,
    evaluations: list[BrokerOrderIntentEvaluation],
    adapter_id: Optional[StockPaperBrokerAdapterId],
    symbol: Optional[str],
    submission_status: Optional[str],
) -> BrokerIntentEvaluationReport:
    generated_at = datetime.now(timezone.utc).isoformat()
    filename = f"broker-intent-evaluations-{generated_at[:10]}.md"
    status_counts: dict[str, int] = {}
    adapter_counts: dict[str, int] = {}
    external_attempts = 0
    live_capable = 0
    fill_status_counts: dict[str, int] = {}
    for evaluation in evaluations:
        adapter_counts[evaluation.adapter_id] = adapter_counts.get(evaluation.adapter_id, 0) + 1
        status_counts[evaluation.submission_status] = (
            status_counts.get(evaluation.submission_status, 0) + 1
        )
        if evaluation.paper_fill_estimate:
            fill_status = evaluation.paper_fill_estimate.status
            fill_status_counts[fill_status] = fill_status_counts.get(fill_status, 0) + 1
        if evaluation.external_submission_attempted:
            external_attempts += 1
        if evaluation.live_submission_supported:
            live_capable += 1
    summary = {
        "evaluations": len(evaluations),
        "external_submission_attempted": external_attempts,
        "live_submission_supported": live_capable,
        **{f"adapter_{key}": value for key, value in sorted(adapter_counts.items())},
        **{f"submission_{key}": value for key, value in sorted(status_counts.items())},
        **{f"fill_{key}": value for key, value in sorted(fill_status_counts.items())},
    }

    lines = [
        "# US Paper Broker Intent Evaluation Report",
        "",
        f"- Generated at: {generated_at}",
        f"- Adapter filter: {adapter_id or 'all stock/ETF paper adapters'}",
        "- Broker contracts: mock_us_equity_paper, alpaca_us_equity_paper_preview, alpaca_us_equity_paper",
        "- Submission mode: paper_record_only or credential-gated external_paper",
        f"- Symbol filter: {symbol.upper() if symbol else 'all'}",
        f"- Submission status filter: {submission_status or 'all'}",
        f"- Evaluations included: {len(evaluations)}",
        f"- External broker submissions attempted: {external_attempts}",
        "",
        "## Safety Boundary",
        "",
        "- US stock/ETF checks remain paper-only.",
        "- Live brokerage credentials are not accepted by this route.",
        "- Credentialed Alpaca paper submissions require the paper flag, ACK, endpoint, credentials, and per-request confirmation.",
    ]
    if external_attempts == 0:
        lines.append("- No external broker submissions were attempted.")
    else:
        lines.append("- Review immediately: one or more evaluations reported external submission attempts.")

    lines.extend(["", "## Summary", ""])
    if status_counts:
        if adapter_counts:
            lines.extend(["### Adapter Coverage", ""])
            for adapter_key, count in sorted(adapter_counts.items()):
                lines.append(f"- {adapter_key}: {count}")
            lines.append("")
        for status_key, count in sorted(status_counts.items()):
            lines.append(f"- {status_key.replace('_', ' ')}: {count}")
    else:
        lines.append("- No broker intent evaluations matched the selected filters.")
    if fill_status_counts:
        lines.extend(["", "### Paper Fill Estimates", ""])
        for status_key, count in sorted(fill_status_counts.items()):
            lines.append(f"- {status_key.replace('_', ' ')}: {count}")

    lines.extend(["", "## Evaluations", ""])
    for index, evaluation in enumerate(evaluations, start=1):
        request = evaluation.request
        symbol_label = evaluation.normalized_symbol or request.symbol.upper()
        notional = (
            f"${evaluation.estimated_notional:,.2f}"
            if evaluation.estimated_notional is not None
            else "-"
        )
        fill = evaluation.paper_fill_estimate
        fill_status = fill.status.replace("_", " ") if fill else "-"
        fill_price = f"${fill.fill_price:,.2f}" if fill and fill.fill_price is not None else "-"
        fill_fee = f"${fill.estimated_fee:,.2f}" if fill and fill.estimated_fee is not None else "-"
        cash_after = f"${fill.cash_after:,.2f}" if fill and fill.cash_after is not None else "-"
        position_after = f"{fill.position_after:,.6f}" if fill and fill.position_after is not None else "-"
        exposure_after = (
            f"{fill.exposure_pct_after:.2f}%"
            if fill and fill.exposure_pct_after is not None
            else "-"
        )
        latest_reconciliations = broker_order_reconciliation_store.list_reconciliations(
            evaluation_id=evaluation.id,
            limit=1,
        )
        latest_reconciliation = latest_reconciliations[0] if latest_reconciliations else None
        broker_avg_fill = (
            f"${latest_reconciliation.broker_avg_fill_price:,.2f}"
            if latest_reconciliation and latest_reconciliation.broker_avg_fill_price is not None
            else "-"
        )
        broker_filled_notional = (
            f"${latest_reconciliation.broker_filled_notional:,.2f}"
            if latest_reconciliation and latest_reconciliation.broker_filled_notional is not None
            else "-"
        )
        broker_fee = (
            f"${latest_reconciliation.broker_fee:,.2f}"
            if latest_reconciliation and latest_reconciliation.broker_fee is not None
            else "-"
        )
        broker_position_qty = (
            f"{latest_reconciliation.broker_position_quantity:,.6f}"
            if latest_reconciliation and latest_reconciliation.broker_position_quantity is not None
            else "-"
        )
        broker_position_value = (
            f"${latest_reconciliation.broker_position_market_value:,.2f}"
            if latest_reconciliation and latest_reconciliation.broker_position_market_value is not None
            else "-"
        )
        broker_account_cash = (
            f"${latest_reconciliation.broker_account_cash:,.2f}"
            if latest_reconciliation and latest_reconciliation.broker_account_cash is not None
            else "-"
        )
        broker_account_equity = (
            f"${latest_reconciliation.broker_account_equity:,.2f}"
            if latest_reconciliation and latest_reconciliation.broker_account_equity is not None
            else "-"
        )
        paper_fill_delta_pct = (
            f"{latest_reconciliation.paper_fill_price_delta_pct:.2f}%"
            if latest_reconciliation and latest_reconciliation.paper_fill_price_delta_pct is not None
            else "-"
        )
        paper_fill_fee_delta = (
            f"${latest_reconciliation.paper_fill_fee_delta:,.2f}"
            if latest_reconciliation and latest_reconciliation.paper_fill_fee_delta is not None
            else "-"
        )
        lines.extend(
            [
                f"### {index}. {symbol_label}",
                "",
                f"- Evaluation id: {evaluation.id}",
                f"- Checked at: {evaluation.checked_at}",
                f"- Adapter id: {evaluation.adapter_id}",
                f"- Broker contract: {evaluation.broker_contract.id}",
                f"- Side: {request.side}",
                f"- Quantity: {request.quantity}",
                f"- Order type: {request.order_type}",
                f"- Limit price: {request.limit_price if request.limit_price is not None else '-'}",
                f"- Validation status: {evaluation.validation_status}",
                f"- Submission status: {evaluation.submission_status.replace('_', ' ')}",
                f"- Estimated notional: {notional}",
                f"- Broker order id: {evaluation.broker_order_id or '-'}",
                f"- External submission attempted: {evaluation.external_submission_attempted}",
                f"- Live submission supported: {evaluation.live_submission_supported}",
                f"- Reason: {evaluation.reason}",
                f"- Paper fill status: {fill_status}",
                f"- Paper fill price: {fill_price}",
                f"- Paper estimated fee: {fill_fee}",
                f"- Paper cash after: {cash_after}",
                f"- Paper position after: {position_after}",
                f"- Paper exposure after: {exposure_after}",
            ]
        )
        if latest_reconciliation:
            lines.extend(
                [
                    f"- Latest reconciliation id: {latest_reconciliation.id}",
                    f"- Latest reconciliation status: {latest_reconciliation.status.replace('_', ' ')}",
                    f"- Broker status: {latest_reconciliation.broker_status or '-'}",
                    f"- Broker filled quantity: {latest_reconciliation.broker_filled_quantity if latest_reconciliation.broker_filled_quantity is not None else '-'}",
                    f"- Broker avg fill price: {broker_avg_fill}",
                    f"- Broker filled notional: {broker_filled_notional}",
                    f"- Broker fee: {broker_fee}",
                    f"- Broker partial fill: {latest_reconciliation.broker_partial_fill if latest_reconciliation.broker_partial_fill is not None else '-'}",
                    f"- Broker fill activity count: {latest_reconciliation.broker_fill_activity_count}",
                    f"- Broker position quantity: {broker_position_qty}",
                    f"- Broker position market value: {broker_position_value}",
                    f"- Broker account cash: {broker_account_cash}",
                    f"- Broker account equity: {broker_account_equity}",
                    f"- Linked paper fill note id: {latest_reconciliation.linked_paper_fill_note_id or '-'}",
                    f"- Paper fill comparison status: {latest_reconciliation.paper_fill_comparison_status or '-'}",
                    f"- Paper fill price delta pct: {paper_fill_delta_pct}",
                    f"- Paper fill fee delta: {paper_fill_fee_delta}",
                ]
            )
        lines.append("")

    markdown = "\n".join(lines)
    return BrokerIntentEvaluationReport(
        generated_at=generated_at,
        title="US Paper Broker Intent Evaluation Report",
        filename=filename,
        evaluations=evaluations,
        summary=summary,
        markdown=markdown,
    )


def _paper_fill_order_note_analytics(
    *,
    notes: list[PaperFillOrderNote],
    limit: int,
    adapter_id: Optional[StockPaperBrokerAdapterId],
    symbol: Optional[str],
) -> PaperFillOrderNoteAnalytics:
    grouped: dict[tuple[StockPaperBrokerAdapterId, str], list[PaperFillOrderNote]] = {}
    for note in notes:
        grouped.setdefault((note.adapter_id, note.symbol.upper()), []).append(note)

    rows: list[PaperFillOrderNoteDriftRow] = []
    for (row_adapter_id, row_symbol), row_notes in grouped.items():
        matched_trade_count = sum(
            1 for note in row_notes if note.comparison_status == "matched_trade"
        )
        external_count = sum(1 for note in row_notes if note.external_submission_attempted)
        deltas = [
            note.price_delta_pct
            for note in row_notes
            if note.price_delta_pct is not None
        ]
        abs_deltas = [abs(delta) for delta in deltas]
        latest = row_notes[0]
        rows.append(
            PaperFillOrderNoteDriftRow(
                adapter_id=row_adapter_id,
                symbol=row_symbol,
                note_count=len(row_notes),
                matched_trade_count=matched_trade_count,
                no_trade_match_count=len(row_notes) - matched_trade_count,
                external_submission_attempted_count=external_count,
                avg_price_delta_pct=sum(deltas) / len(deltas) if deltas else None,
                avg_abs_price_delta_pct=sum(abs_deltas) / len(abs_deltas) if abs_deltas else None,
                worst_abs_price_delta_pct=max(abs_deltas) if abs_deltas else None,
                latest_price_delta_pct=latest.price_delta_pct,
                latest_created_at=latest.created_at,
                latest_session_id=latest.session_id,
                latest_evaluation_id=latest.evaluation_id,
                latest_comparison_status=latest.comparison_status,
                latest_note=latest.note,
            )
        )

    rows.sort(
        key=lambda row: (
            row.avg_abs_price_delta_pct if row.avg_abs_price_delta_pct is not None else -1,
            row.note_count,
            row.latest_created_at,
        ),
        reverse=True,
    )
    return PaperFillOrderNoteAnalytics(
        generated_at=datetime.now(timezone.utc).isoformat(),
        limit=limit,
        adapter_id=adapter_id,
        symbol=symbol,
        notes_considered=len(notes),
        matched_trade_count=sum(1 for note in notes if note.comparison_status == "matched_trade"),
        external_submission_attempted_count=sum(
            1 for note in notes if note.external_submission_attempted
        ),
        rows=rows,
    )


def _paper_fill_quality_gate(
    *,
    analytics: PaperFillOrderNoteAnalytics,
    min_notes: int,
    max_avg_abs_price_delta_pct: float,
    max_worst_abs_price_delta_pct: float,
    require_no_external_submission: bool,
) -> PaperFillOrderNoteQualityGate:
    gate_rows: list[PaperFillOrderNoteQualityGateRow] = []
    for row in analytics.rows:
        reasons: list[str] = []
        status: Literal["ready", "watch", "blocked"] = "ready"
        if row.note_count < min_notes:
            status = "watch"
            reasons.append(f"Needs at least {min_notes} linked paper fill notes.")
        if row.no_trade_match_count > 0:
            status = "watch" if status != "blocked" else status
            reasons.append("Some linked notes do not have a same-side simulated trade match.")
        if row.avg_abs_price_delta_pct is None:
            status = "watch" if status != "blocked" else status
            reasons.append("Average fill drift is unavailable until matched trades exist.")
        elif row.avg_abs_price_delta_pct > max_avg_abs_price_delta_pct:
            status = "blocked"
            reasons.append(
                f"Average absolute fill drift exceeds {max_avg_abs_price_delta_pct:.2f}%."
            )
        if row.worst_abs_price_delta_pct is None:
            status = "watch" if status != "blocked" else status
            reasons.append("Worst fill drift is unavailable until matched trades exist.")
        elif row.worst_abs_price_delta_pct > max_worst_abs_price_delta_pct:
            status = "blocked"
            reasons.append(
                f"Worst absolute fill drift exceeds {max_worst_abs_price_delta_pct:.2f}%."
            )
        if require_no_external_submission and row.external_submission_attempted_count > 0:
            status = "blocked"
            reasons.append("External broker submission was attempted in the sample window.")
        if not reasons:
            reasons.append("Paper fill drift is within the configured quality gate.")

        gate_rows.append(
            PaperFillOrderNoteQualityGateRow(
                adapter_id=row.adapter_id,
                symbol=row.symbol,
                status=status,
                reasons=reasons,
                note_count=row.note_count,
                matched_trade_count=row.matched_trade_count,
                no_trade_match_count=row.no_trade_match_count,
                external_submission_attempted_count=row.external_submission_attempted_count,
                avg_abs_price_delta_pct=row.avg_abs_price_delta_pct,
                worst_abs_price_delta_pct=row.worst_abs_price_delta_pct,
                latest_created_at=row.latest_created_at,
                latest_session_id=row.latest_session_id,
                latest_evaluation_id=row.latest_evaluation_id,
            )
        )

    if not gate_rows:
        status: Literal["ready", "watch", "blocked"] = "watch"
        reason = "No linked paper fill notes are available for the selected filters."
    elif any(row.status == "blocked" for row in gate_rows):
        status = "blocked"
        reason = "At least one symbol/adapter group breaches the paper fill quality gate."
    elif any(row.status == "watch" for row in gate_rows):
        status = "watch"
        reason = "More matched paper fill evidence is needed before this route is ready."
    else:
        status = "ready"
        reason = "All symbol/adapter groups pass the paper fill quality gate."

    return PaperFillOrderNoteQualityGate(
        generated_at=datetime.now(timezone.utc).isoformat(),
        status=status,
        reason=reason,
        limit=analytics.limit,
        min_notes=min_notes,
        max_avg_abs_price_delta_pct=max_avg_abs_price_delta_pct,
        max_worst_abs_price_delta_pct=max_worst_abs_price_delta_pct,
        require_no_external_submission=require_no_external_submission,
        adapter_id=analytics.adapter_id,
        symbol=analytics.symbol,
        analytics=analytics,
        rows=gate_rows,
    )


def _paper_fill_order_note_from_evaluation(
    *,
    evaluation: BrokerOrderIntentEvaluation,
    session: PaperTradingSession,
) -> Optional[PaperFillOrderNote]:
    fill = evaluation.paper_fill_estimate
    if (
        evaluation.validation_status != "accepted"
        or evaluation.submission_status != "paper_recorded"
        or fill is None
        or fill.status != "estimated_fill"
        or fill.fill_price is None
        or fill.estimated_notional is None
        or fill.estimated_fee is None
    ):
        return None

    symbol = (evaluation.normalized_symbol or evaluation.request.symbol).upper()
    matching_trade = next(
        (trade for trade in reversed(session.trades) if trade.side == evaluation.request.side),
        None,
    )

    simulated_fill_price: Optional[float] = None
    simulated_quantity: Optional[float] = None
    simulated_notional: Optional[float] = None
    simulated_trade_timestamp: Optional[str] = None
    price_delta: Optional[float] = None
    price_delta_pct: Optional[float] = None
    quantity_delta: Optional[float] = None
    notional_delta: Optional[float] = None
    comparison_status = "no_trade_match"

    if matching_trade is not None:
        simulated_trade_timestamp = matching_trade.timestamp
        simulated_fill_price = matching_trade.price
        simulated_quantity = matching_trade.quantity
        simulated_notional = matching_trade.notional
        price_delta = matching_trade.price - fill.fill_price
        price_delta_pct = price_delta / fill.fill_price * 100 if fill.fill_price else None
        quantity_delta = matching_trade.quantity - evaluation.request.quantity
        notional_delta = matching_trade.notional - fill.estimated_notional
        comparison_status = "matched_trade"

    note_text = (
        "Accepted paper fill estimate was attached to the paper session and compared "
        "with the latest same-side simulated trade."
        if matching_trade
        else "Accepted paper fill estimate was attached to the paper session; no same-side simulated trade was available yet."
    )

    return PaperFillOrderNote(
        id=str(uuid.uuid4()),
        created_at=datetime.now(timezone.utc).isoformat(),
        session_id=session.id,
        evaluation_id=evaluation.id,
        adapter_id=evaluation.adapter_id,
        symbol=symbol,
        side=evaluation.request.side,
        quantity=evaluation.request.quantity,
        order_type=evaluation.request.order_type,
        paper_fill_status="estimated_fill",
        intended_fill_price=fill.fill_price,
        intended_notional=fill.estimated_notional,
        intended_fee=fill.estimated_fee,
        simulated_trade_timestamp=simulated_trade_timestamp,
        simulated_fill_price=simulated_fill_price,
        simulated_quantity=simulated_quantity,
        simulated_notional=simulated_notional,
        price_delta=price_delta,
        price_delta_pct=price_delta_pct,
        quantity_delta=quantity_delta,
        notional_delta=notional_delta,
        comparison_status=comparison_status,
        external_submission_attempted=evaluation.external_submission_attempted,
        note=note_text,
    )


def _alert_review_queue(
    include_acknowledged: bool = False,
    severity: Optional[str] = None,
    source: Optional[str] = None,
    scenario: Optional[str] = None,
) -> AlertReviewResponse:
    checked_at = datetime.now(timezone.utc).isoformat()
    items: list[AlertReviewItem] = []

    for watch_item in portfolio_watchlist_store.list_items(limit=50):
        created_at = watch_item.last_run_at or watch_item.updated_at
        for alert in watch_item.last_alerts:
            items.append(
                AlertReviewItem(
                    id=f"portfolio-scan-{watch_item.id}-{alert.rule}",
                    source="portfolio_scan",
                    level=alert.level,
                    title=f"{watch_item.scenario_name} scan alert",
                    message=alert.message,
                    created_at=created_at,
                    scenario_id=watch_item.scenario_id,
                    scenario_name=watch_item.scenario_name,
                    watchlist_id=watch_item.id,
                    scan_id=watch_item.last_scan_id,
                    rule=alert.rule,
                    value=alert.value,
                    threshold=alert.threshold,
                )
            )
        if watch_item.last_error:
            items.append(
                AlertReviewItem(
                    id=f"portfolio-scan-error-{watch_item.id}",
                    source="portfolio_scan_error",
                    level="error",
                    title=f"{watch_item.scenario_name} scan failed",
                    message=watch_item.last_error,
                    created_at=created_at,
                    scenario_id=watch_item.scenario_id,
                    scenario_name=watch_item.scenario_name,
                    watchlist_id=watch_item.id,
                    scan_id=watch_item.last_scan_id,
                )
            )

    for watch_item in portfolio_paper_watchlist_store.list_items(limit=50):
        created_at = watch_item.last_run_at or watch_item.updated_at
        if watch_item.last_error:
            items.append(
                AlertReviewItem(
                    id=f"paper-watch-error-{watch_item.id}",
                    source="paper_watchlist_error",
                    level="error",
                    title=f"{watch_item.scenario_name} paper watch failed",
                    message=watch_item.last_error,
                    created_at=created_at,
                    scenario_id=watch_item.scenario_id,
                    scenario_name=watch_item.scenario_name,
                    watchlist_id=watch_item.id,
                )
            )
        for session_id in watch_item.last_session_ids[-8:]:
            session = session_store.get_paper_session(session_id)
            if session is None:
                continue
            if session.summary.status == "halted":
                items.append(
                    AlertReviewItem(
                        id=f"paper-session-halt-{watch_item.id}-{session.id}",
                        source="paper_session_halt",
                        level="halt",
                        title=f"{session.request.symbol} paper session halted",
                        message=session.summary.halted_reason or "Paper session halted.",
                        created_at=created_at,
                        scenario_id=watch_item.scenario_id,
                        scenario_name=watch_item.scenario_name,
                        watchlist_id=watch_item.id,
                        session_id=session.id,
                        symbol=session.request.symbol,
                        rule="session_status",
                    )
                )
            for event_index, event in enumerate(session.risk_events):
                if event.level == "info":
                    continue
                items.append(
                    AlertReviewItem(
                        id=f"paper-risk-{watch_item.id}-{session.id}-{event_index}",
                        source="paper_session_risk",
                        level=event.level,
                        title=f"{session.request.symbol} risk event",
                        message=event.message,
                        created_at=created_at,
                        scenario_id=watch_item.scenario_id,
                        scenario_name=watch_item.scenario_name,
                        watchlist_id=watch_item.id,
                        session_id=session.id,
                        symbol=session.request.symbol,
                        rule=event.rule,
                    )
                )

    items.extend(_broker_paper_submission_alerts())
    items.extend(_broker_reconciliation_alerts())
    items.extend(_paper_fill_drift_alerts())

    items = _annotate_alert_acknowledgements(
        items=items,
        include_acknowledged=include_acknowledged,
    )
    items = _filter_alert_review_items(
        items=items,
        severity=severity,
        source=source,
        scenario=scenario,
    )
    items.sort(key=lambda item: item.created_at, reverse=True)
    counts: dict[str, int] = {}
    for item in items:
        counts[item.level] = counts.get(item.level, 0) + 1

    return AlertReviewResponse(
        checked_at=checked_at,
        items=items[:50],
        counts=counts,
    )


def _filter_alert_review_items(
    *,
    items: list[AlertReviewItem],
    severity: Optional[str],
    source: Optional[str],
    scenario: Optional[str],
) -> list[AlertReviewItem]:
    valid_severities = {"info", "warning", "halt", "error"}
    valid_sources = {
        "portfolio_scan",
        "portfolio_scan_error",
        "paper_watchlist_error",
        "paper_session_risk",
        "paper_session_halt",
        "broker_paper_submission",
        "broker_reconciliation",
        "paper_fill_drift",
    }
    severity_filter = severity.strip().lower() if severity else None
    source_filter = source.strip() if source else None
    scenario_filter = scenario.strip().lower() if scenario else None

    if severity_filter and severity_filter not in valid_severities:
        raise HTTPException(status_code=400, detail="Unknown alert severity filter.")
    if source_filter and source_filter not in valid_sources:
        raise HTTPException(status_code=400, detail="Unknown alert source filter.")

    filtered = items
    if severity_filter:
        filtered = [item for item in filtered if item.level == severity_filter]
    if source_filter:
        filtered = [item for item in filtered if item.source == source_filter]
    if scenario_filter:
        filtered = [
            item
            for item in filtered
            if scenario_filter in (item.scenario_id or "").lower()
            or scenario_filter in (item.scenario_name or "").lower()
        ]
    return filtered


def _broker_paper_submission_alerts() -> list[AlertReviewItem]:
    items: list[AlertReviewItem] = []
    evaluations = broker_intent_evaluation_store.list_evaluations(limit=50)
    for evaluation in evaluations:
        if evaluation.adapter_id != "alpaca_us_equity_paper":
            continue
        if evaluation.submission_status not in {"blocked", "rejected"}:
            continue
        level: Literal["warning", "error"] = (
            "error" if evaluation.submission_status == "rejected" else "warning"
        )
        symbol = evaluation.normalized_symbol or evaluation.request.symbol.upper()
        items.append(
            AlertReviewItem(
                id=f"broker-paper-submission-{evaluation.id}",
                source="broker_paper_submission",
                level=level,
                title=f"{symbol} Alpaca paper submission {evaluation.submission_status}",
                message=evaluation.reason,
                created_at=evaluation.checked_at,
                evaluation_id=evaluation.id,
                adapter_id=evaluation.adapter_id,
                symbol=symbol,
                rule=f"submission_{evaluation.submission_status}",
            )
        )
    return items


def _broker_reconciliation_alerts() -> list[AlertReviewItem]:
    items: list[AlertReviewItem] = []
    reconciliations = broker_order_reconciliation_store.list_reconciliations(limit=50)
    for reconciliation in reconciliations:
        if reconciliation.status in {"matched", "unsupported"}:
            continue
        level: Literal["warning", "error"] = (
            "warning" if reconciliation.status == "blocked" else "error"
        )
        symbol = reconciliation.broker_symbol or "-"
        items.append(
            AlertReviewItem(
                id=f"broker-reconciliation-{reconciliation.id}",
                source="broker_reconciliation",
                level=level,
                title=f"Broker reconciliation {reconciliation.status.replace('_', ' ')}",
                message=reconciliation.reason,
                created_at=reconciliation.checked_at,
                evaluation_id=reconciliation.evaluation_id,
                reconciliation_id=reconciliation.id,
                adapter_id=reconciliation.adapter_id,
                symbol=symbol,
                rule=f"reconciliation_{reconciliation.status}",
            )
        )
    return items


def _paper_fill_drift_alerts() -> list[AlertReviewItem]:
    notes = paper_fill_order_note_store.list_notes(limit=PAPER_FILL_GATE_DEFAULT_LIMIT)
    if not notes:
        return []
    analytics = _paper_fill_order_note_analytics(
        notes=notes,
        limit=PAPER_FILL_GATE_DEFAULT_LIMIT,
        adapter_id=None,
        symbol=None,
    )
    quality_gate = _paper_fill_quality_gate(
        analytics=analytics,
        min_notes=PAPER_FILL_GATE_DEFAULT_MIN_NOTES,
        max_avg_abs_price_delta_pct=PAPER_FILL_GATE_DEFAULT_MAX_AVG_ABS_DELTA_PCT,
        max_worst_abs_price_delta_pct=PAPER_FILL_GATE_DEFAULT_MAX_WORST_ABS_DELTA_PCT,
        require_no_external_submission=PAPER_FILL_GATE_DEFAULT_REQUIRE_NO_EXTERNAL,
    )
    items: list[AlertReviewItem] = []
    for row in quality_gate.rows:
        if row.status == "ready":
            continue
        level: Literal["warning", "error"] = "error" if row.status == "blocked" else "warning"
        drift_value = row.worst_abs_price_delta_pct or row.avg_abs_price_delta_pct
        threshold = (
            quality_gate.max_worst_abs_price_delta_pct
            if row.worst_abs_price_delta_pct is not None
            else quality_gate.max_avg_abs_price_delta_pct
        )
        items.append(
            AlertReviewItem(
                id=f"paper-fill-drift-{row.adapter_id}-{row.symbol}-{row.latest_evaluation_id}",
                source="paper_fill_drift",
                level=level,
                title=f"{row.symbol} paper fill quality {row.status}",
                message=" ".join(row.reasons),
                created_at=row.latest_created_at,
                evaluation_id=row.latest_evaluation_id,
                adapter_id=row.adapter_id,
                session_id=row.latest_session_id,
                symbol=row.symbol,
                rule=f"paper_fill_quality_{row.status}",
                value=drift_value,
                threshold=threshold,
            )
        )
    return items


def _annotate_alert_acknowledgements(
    items: list[AlertReviewItem],
    include_acknowledged: bool,
) -> list[AlertReviewItem]:
    annotated: list[AlertReviewItem] = []
    for item in items:
        acknowledgement = alert_review_store.get_acknowledgement(item.id)
        if acknowledgement is None:
            annotated.append(item)
            continue
        acknowledged_item = item.model_copy(
            update={
                "acknowledgement_status": acknowledgement.status,
                "acknowledged_at": acknowledgement.acknowledged_at,
                "acknowledgement_note": acknowledgement.note,
            }
        )
        if include_acknowledged:
            annotated.append(acknowledged_item)
    return annotated


def _readiness_check(
    *,
    id: str,
    label: str,
    category: str = "system",
    status: str,
    message: str,
    weight: float = 1.0,
) -> LiveReadinessCheck:
    status_score = {"pass": 1.0, "warn": 0.5, "fail": 0.0}[status]
    return LiveReadinessCheck(
        id=id,
        label=label,
        category=category,
        status=status,
        message=message,
        weight=weight,
        score=round(status_score * weight, 4),
    )


def _readiness_breakdown(
    *,
    id: str,
    label: str,
    checks: list[LiveReadinessCheck],
) -> LiveReadinessBreakdown:
    total_weight = sum(check.weight for check in checks) or 1
    score = round(sum(check.score for check in checks) / total_weight * 100, 1)
    blocking_checks = [check.id for check in checks if check.status == "fail"]
    warning_checks = [check.id for check in checks if check.status == "warn"]
    if blocking_checks:
        status = "blocked"
        message = f"{len(blocking_checks)} blocking check(s) require action before arming."
    elif warning_checks:
        status = "watch"
        message = f"{len(warning_checks)} warning check(s) should be reviewed before arming."
    else:
        status = "ready"
        message = "All checks in this view are ready."
    return LiveReadinessBreakdown(
        id=id,
        label=label,
        status=status,
        score=score,
        checks=checks,
        blocking_checks=blocking_checks,
        warning_checks=warning_checks,
        message=message,
    )


def _readiness_breakdowns(
    checks: list[LiveReadinessCheck],
) -> list[LiveReadinessBreakdown]:
    system_checks = [check for check in checks if check.category == "system"]
    operator_checks = [check for check in checks if check.category == "operator"]
    return [
        _readiness_breakdown(
            id="system",
            label="System readiness",
            checks=system_checks,
        ),
        _readiness_breakdown(
            id="operator",
            label="Operator readiness",
            checks=operator_checks,
        ),
    ]


def _live_readiness(
    settings: Optional[ExecutionSettings] = None,
    simulated: bool = False,
) -> LiveReadinessResponse:
    checked_at = datetime.now(timezone.utc).isoformat()
    checks: list[LiveReadinessCheck] = []

    providers = get_market_data_provider_statuses()
    upbit_provider = next(
        (provider for provider in providers if provider.source == "upbit"),
        None,
    )
    if upbit_provider is None:
        checks.append(
            _readiness_check(
                id="upbit_public_data",
                label="Upbit public data",
                category="system",
                status="fail",
                message="Upbit public provider status is unavailable.",
                weight=1.2,
            )
        )
    elif upbit_provider.available:
        checks.append(
            _readiness_check(
                id="upbit_public_data",
                label="Upbit public data",
                category="system",
                status="pass",
                message=upbit_provider.note,
                weight=1.2,
            )
        )
    else:
        checks.append(
            _readiness_check(
                id="upbit_public_data",
                label="Upbit public data",
                category="system",
                status="warn",
                message=upbit_provider.last_error or upbit_provider.note,
                weight=1.2,
            )
        )

    settings = settings or get_execution_settings()
    checks.append(
        _readiness_check(
            id="execution_guard",
            label="Execution guard",
            category="system",
            status="pass" if settings.adapter_ready else "warn",
            message=(
                (
                    "Simulation assumes live routing flags, ACK, and Upbit credentials are configured; each order still requires confirmation."
                    if simulated
                    else "Live exchange routing is armed and still requires per-order confirmation."
                )
                if settings.adapter_ready
                else settings.reason
            ),
            weight=1.3,
        )
    )
    checks.append(
        _readiness_check(
            id="private_reads",
            label="Private reads",
            category="system",
            status="pass" if settings.private_reads_enabled else "warn",
            message=(
                (
                    "Simulation assumes Upbit private balances and order availability can be checked after credentials are configured."
                    if simulated
                    else "Upbit private balances and order availability can be checked."
                )
                if settings.private_reads_enabled
                else "UPBIT_ACCESS_KEY and UPBIT_SECRET_KEY are not configured; prechecks use local defaults."
            ),
            weight=1.0,
        )
    )

    active_alerts = _alert_review_queue(include_acknowledged=False).items
    blocking_alerts = [
        item for item in active_alerts if item.level in {"halt", "error"}
    ]
    warning_alerts = [item for item in active_alerts if item.level == "warning"]
    if blocking_alerts:
        alert_status = "fail"
        alert_message = (
            f"{len(blocking_alerts)} halt/error alert(s) need review before promotion."
        )
    elif warning_alerts:
        alert_status = "warn"
        alert_message = f"{len(warning_alerts)} warning alert(s) remain in the active review queue."
    else:
        alert_status = "pass"
        alert_message = "No active scan, watchlist, or paper-session alerts need review."
    checks.append(
        _readiness_check(
            id="active_alerts",
            label="Active alert queue",
            category="operator",
            status=alert_status,
            message=alert_message,
            weight=1.2,
        )
    )

    paper_sessions = session_store.list_paper_sessions(limit=20)
    live_sessions = session_store.list_live_sessions(limit=20)
    crypto_paper_sessions = [
        session
        for session in [*paper_sessions, *live_sessions]
        if session.request.symbol.startswith("KRW-")
        and session.summary.status in {"running", "completed"}
        and len(session.trades) > 0
    ]
    checks.append(
        _readiness_check(
            id="crypto_paper_sessions",
            label="Crypto paper evidence",
            category="operator",
            status="pass" if crypto_paper_sessions else "warn",
            message=(
                f"{len(crypto_paper_sessions)} recent KRW paper session(s) have simulated trades."
                if crypto_paper_sessions
                else "Run a KRW crypto paper session with trades before live approval."
            ),
            weight=1.0,
        )
    )

    dry_run_audits = [
        audit
        for audit in order_audit_store.list_records(limit=20)
        if audit.status == "dry_run"
    ]
    checks.append(
        _readiness_check(
            id="dry_run_audits",
            label="Dry-run audits",
            category="operator",
            status="pass" if dry_run_audits else "warn",
            message=(
                f"{len(dry_run_audits)} dry-run order intent(s) are available for review."
                if dry_run_audits
                else "Queue dry-run order intents from paper trades before live approval."
            ),
            weight=1.0,
        )
    )

    latest_dry_run = dry_run_audits[0] if dry_run_audits else None
    has_runbook_context = bool(
        latest_dry_run
        and latest_dry_run.response_payload
        and latest_dry_run.response_payload.get("dry_run")
    )
    checks.append(
        _readiness_check(
            id="approval_runbook",
            label="Approval runbook",
            category="operator",
            status="pass" if has_runbook_context else "warn",
            message=(
                "Latest dry-run audit can export a pre-approval runbook."
                if has_runbook_context
                else "Create a dry-run audit before exporting an approval runbook."
            ),
            weight=0.8,
        )
    )

    total_weight = sum(check.weight for check in checks) or 1
    score = round(sum(check.score for check in checks) / total_weight * 100, 1)
    has_failures = any(check.status == "fail" for check in checks)
    core_checks_ready = all(
        check.status == "pass"
        for check in checks
        if check.id
        in {
            "upbit_public_data",
            "execution_guard",
            "private_reads",
            "active_alerts",
        }
    )
    if has_failures or score < 50:
        status = "blocked"
    elif score >= 80 and core_checks_ready:
        status = "ready"
    else:
        status = "watch"

    return LiveReadinessResponse(
        checked_at=checked_at,
        status=status,
        score=score,
        checks=checks,
        breakdowns=_readiness_breakdowns(checks),
    )


def _cutover_item(
    *,
    id: str,
    label: str,
    status: str,
    message: str,
    evidence_id: Optional[str] = None,
) -> LiveCutoverChecklistItem:
    return LiveCutoverChecklistItem(
        id=id,
        label=label,
        status=status,
        message=message,
        evidence_id=evidence_id,
    )


def _latest_decision(
    *,
    decision_type: str,
    status: Optional[str] = None,
) -> Optional[OperatorDecisionRecord]:
    decisions = operator_decision_store.list_decisions(
        decision_type=decision_type,
        status=status,
        limit=1,
    )
    return decisions[0] if decisions else None


def _latest_relevant_operator_decisions(limit: int = 8) -> list[OperatorDecisionRecord]:
    decisions: list[OperatorDecisionRecord] = []
    seen: set[str] = set()
    for decision_type in (
        "live_cutover",
        "readiness_review",
        "dry_run_approval",
        "dry_run_promotion",
    ):
        for decision in operator_decision_store.list_decisions(
            decision_type=decision_type,
            limit=5,
        ):
            if decision.id in seen:
                continue
            seen.add(decision.id)
            decisions.append(decision)
    decisions.sort(key=lambda decision: decision.created_at, reverse=True)
    return decisions[:limit]


def _latest_valid_dry_run_approval() -> Optional[OperatorDecisionRecord]:
    for decision in operator_decision_store.list_decisions(
        decision_type="dry_run_approval",
        status="approved",
        limit=20,
    ):
        if decision.target_id and order_audit_store.get_record(decision.target_id):
            return decision
    return None


def _live_cutover_checklist(
    settings: Optional[ExecutionSettings] = None,
    assume_required_operator_decisions: bool = False,
    simulated: bool = False,
) -> LiveCutoverChecklistResponse:
    checked_at = datetime.now(timezone.utc).isoformat()
    settings = settings or get_execution_settings()
    readiness = _live_readiness(settings=settings, simulated=simulated)
    readiness_checks = {check.id: check for check in readiness.checks}

    readiness_review = _latest_decision(
        decision_type="readiness_review",
        status="approved",
    )
    latest_readiness_review = _latest_decision(decision_type="readiness_review")
    dry_run_approval = _latest_valid_dry_run_approval()
    latest_dry_run_review = _latest_decision(decision_type="dry_run_approval")
    live_cutover = _latest_decision(
        decision_type="live_cutover",
        status="approved",
    )
    latest_live_cutover = _latest_decision(decision_type="live_cutover")

    items: list[LiveCutoverChecklistItem] = []
    readiness_status = {
        "ready": "pass",
        "watch": "warn",
        "blocked": "fail",
    }[readiness.status]
    items.append(
        _cutover_item(
            id="system_readiness",
            label="System readiness score",
            status=readiness_status,
            message=f"Live readiness is {readiness.status} at {readiness.score:.1f}/100.",
            evidence_id=readiness.checked_at,
        )
    )

    private_reads = readiness_checks.get("private_reads")
    private_reads_ready = private_reads is not None and private_reads.status == "pass"
    items.append(
        _cutover_item(
            id="private_reads",
            label="Private account prechecks",
            status="pass" if private_reads_ready else "fail",
            message=(
                private_reads.message
                if private_reads is not None
                else "Private account readiness could not be evaluated."
            ),
        )
    )

    active_alerts = readiness_checks.get("active_alerts")
    items.append(
        _cutover_item(
            id="active_alerts",
            label="Active alert queue",
            status=active_alerts.status if active_alerts is not None else "fail",
            message=(
                active_alerts.message
                if active_alerts is not None
                else "Active alert queue could not be evaluated."
            ),
        )
    )

    evidence_check_ids = [
        "crypto_paper_sessions",
        "dry_run_audits",
        "approval_runbook",
    ]
    missing_evidence = [
        readiness_checks[check_id].label
        for check_id in evidence_check_ids
        if check_id in readiness_checks and readiness_checks[check_id].status != "pass"
    ]
    unavailable_evidence = [
        check_id for check_id in evidence_check_ids if check_id not in readiness_checks
    ]
    evidence_ready = not missing_evidence and not unavailable_evidence
    items.append(
        _cutover_item(
            id="dry_run_evidence",
            label="Paper and dry-run evidence",
            status="pass" if evidence_ready else "fail",
            message=(
                "KRW paper trades, dry-run audits, and approval runbook context are present."
                if evidence_ready
                else f"Missing cutover evidence: {', '.join([*missing_evidence, *unavailable_evidence])}."
            ),
        )
    )

    items.append(
        _cutover_item(
            id="readiness_review_decision",
            label="Readiness review decision",
            status="pass" if readiness_review or assume_required_operator_decisions else "fail",
            message=(
                f"Approved readiness review logged at {readiness_review.created_at}."
                if readiness_review
                else "Simulation assumes an approved readiness review decision is present."
                if assume_required_operator_decisions
                else (
                    f"Latest readiness review is {latest_readiness_review.status}; approved review is required."
                    if latest_readiness_review
                    else "No approved readiness review decision has been logged."
                )
            ),
            evidence_id=readiness_review.id if readiness_review else None,
        )
    )

    items.append(
        _cutover_item(
            id="dry_run_approval_decision",
            label="Dry-run approval decision",
            status="pass" if dry_run_approval or assume_required_operator_decisions else "fail",
            message=(
                f"Approved dry-run review is linked to audit {dry_run_approval.target_id}."
                if dry_run_approval
                else "Simulation assumes an approved dry-run review linked to an audit is present."
                if assume_required_operator_decisions
                else (
                    f"Latest dry-run review is {latest_dry_run_review.status}; approved review linked to an audit is required."
                    if latest_dry_run_review
                    else "No approved dry-run order review decision has been logged."
                )
            ),
            evidence_id=dry_run_approval.id if dry_run_approval else None,
        )
    )

    items.append(
        _cutover_item(
            id="live_cutover_decision",
            label="Live cutover decision",
            status="pass" if live_cutover or assume_required_operator_decisions else "fail",
            message=(
                f"Approved live cutover decision logged at {live_cutover.created_at}."
                if live_cutover
                else "Simulation assumes an approved live cutover decision is present."
                if assume_required_operator_decisions
                else (
                    f"Latest live cutover decision is {latest_live_cutover.status}; approved cutover is required."
                    if latest_live_cutover
                    else "No approved live cutover decision has been logged."
                )
            ),
            evidence_id=live_cutover.id if live_cutover else None,
        )
    )

    approvals_ready = bool(
        (readiness_review or assume_required_operator_decisions)
        and (dry_run_approval or assume_required_operator_decisions)
        and (live_cutover or assume_required_operator_decisions)
    )
    if settings.adapter_ready and not approvals_ready:
        adapter_status = "fail"
        adapter_message = "The Upbit adapter is armed before every required operator approval is logged."
    elif settings.adapter_ready:
        adapter_status = "pass"
        adapter_message = "The Upbit adapter is armed; per-order live confirmation still applies."
    elif private_reads_ready and approvals_ready:
        adapter_status = "warn"
        adapter_message = "Checklist approvals are present; live routing flags remain locked until the cutover window."
    else:
        adapter_status = "pass"
        adapter_message = "Live exchange routing remains locked while prerequisites are completed."
    items.append(
        _cutover_item(
            id="adapter_guard",
            label="Adapter guard state",
            status=adapter_status,
            message=adapter_message,
        )
    )

    items.append(
        _cutover_item(
            id="per_order_confirmation",
            label="Per-order confirmation",
            status="pass" if settings.live_confirmation_required else "fail",
            message=(
                "Every approval still requires live_confirmation=true at submission time."
                if settings.live_confirmation_required
                else "Per-order live confirmation is not enforced."
            ),
        )
    )

    if any(item.status == "fail" for item in items):
        status = "blocked"
    elif any(item.status == "warn" for item in items):
        status = "watch"
    else:
        status = "ready"

    return LiveCutoverChecklistResponse(
        checked_at=checked_at,
        status=status,
        items=items,
        readiness=readiness,
        latest_operator_decisions=_latest_relevant_operator_decisions(),
    )


def _run_due_portfolio_watchlist() -> PortfolioResearchSchedulerRun:
    checked_at = datetime.now(timezone.utc).isoformat()
    due_items = portfolio_watchlist_store.due_items(now=checked_at)
    scans: list[PortfolioResearchScan] = []
    alerts: list[PortfolioResearchAlert] = []
    errors: list[str] = []

    for item in due_items:
        scenario = portfolio_scenario_store.get_scenario(item.scenario_id)
        if scenario is None:
            message = f"Scenario {item.scenario_id} was not found."
            portfolio_watchlist_store.record_error(item=item, error=message, active=False)
            errors.append(message)
            continue

        try:
            previous_scan = (
                portfolio_scan_store.get_scan(item.last_scan_id)
                if item.last_scan_id
                else None
            )
            result = _run_portfolio_research_request(scenario.request)
            item_alerts = _portfolio_research_alerts(
                item=item,
                result=result,
                previous_scan=previous_scan,
            )
            scan = portfolio_scan_store.save_scan(scenario=scenario, result=result)
            portfolio_watchlist_store.record_scan(
                item=item,
                scan=scan,
                alerts=item_alerts,
            )
            scans.append(scan)
            alerts.extend(item_alerts)
        except Exception as exc:
            message = f"{item.scenario_name}: {exc}"
            portfolio_watchlist_store.record_error(item=item, error=message)
            errors.append(message)

    return PortfolioResearchSchedulerRun(
        checked_at=checked_at,
        due=len(due_items),
        scanned=scans,
        alerts=alerts,
        errors=errors,
    )


def _portfolio_research_alerts(
    item: PortfolioResearchWatchlistItem,
    result: PortfolioResearchResponse,
    previous_scan: Optional[PortfolioResearchScan] = None,
) -> list[PortfolioResearchAlert]:
    thresholds = item.alert_thresholds
    metrics = result.metrics
    alerts: list[PortfolioResearchAlert] = []

    if thresholds.max_drawdown_pct is not None:
        drawdown = abs(metrics.max_drawdown_pct)
        if drawdown >= thresholds.max_drawdown_pct:
            alerts.append(
                PortfolioResearchAlert(
                    rule="max_drawdown_pct",
                    message=(
                        f"{item.scenario_name} max drawdown is "
                        f"{drawdown:.2f}%, above {thresholds.max_drawdown_pct:.2f}%."
                    ),
                    value=round(drawdown, 4),
                    threshold=thresholds.max_drawdown_pct,
                )
            )

    if thresholds.min_total_return_pct is not None:
        if metrics.total_return_pct < thresholds.min_total_return_pct:
            alerts.append(
                PortfolioResearchAlert(
                    rule="min_total_return_pct",
                    message=(
                        f"{item.scenario_name} total return is "
                        f"{metrics.total_return_pct:.2f}%, below {thresholds.min_total_return_pct:.2f}%."
                    ),
                    value=metrics.total_return_pct,
                    threshold=thresholds.min_total_return_pct,
                )
            )

    if thresholds.min_average_edge_pct is not None:
        average_edge = (
            sum(allocation.strategy_edge_pct for allocation in result.allocations)
            / len(result.allocations)
            if result.allocations
            else 0.0
        )
        if average_edge < thresholds.min_average_edge_pct:
            alerts.append(
                PortfolioResearchAlert(
                    rule="min_average_edge_pct",
                    message=(
                        f"{item.scenario_name} average strategy edge is "
                        f"{average_edge:.2f}%, below {thresholds.min_average_edge_pct:.2f}%."
                    ),
                    value=round(average_edge, 4),
                    threshold=thresholds.min_average_edge_pct,
                )
            )

    if thresholds.max_return_drift_pct is not None and previous_scan is not None:
        previous_return = previous_scan.result.metrics.total_return_pct
        return_drift = abs(metrics.total_return_pct - previous_return)
        if return_drift >= thresholds.max_return_drift_pct:
            alerts.append(
                PortfolioResearchAlert(
                    rule="max_return_drift_pct",
                    message=(
                        f"{item.scenario_name} return drift is "
                        f"{return_drift:.2f}%, above {thresholds.max_return_drift_pct:.2f}%."
                    ),
                    value=round(return_drift, 4),
                    threshold=thresholds.max_return_drift_pct,
                )
            )

    return alerts


def _run_due_portfolio_paper_watchlist() -> PortfolioPaperSchedulerRun:
    checked_at = datetime.now(timezone.utc).isoformat()
    due_items = portfolio_paper_watchlist_store.due_items(now=checked_at)
    runs: list[PortfolioPaperWatchlistRun] = []
    errors: list[str] = []

    for item in due_items:
        run = _run_portfolio_paper_watchlist_item(item=item, checked_at=checked_at)
        runs.append(run)
        errors.extend(run.errors)

    return PortfolioPaperSchedulerRun(
        checked_at=checked_at,
        due=len(due_items),
        runs=runs,
        errors=errors,
    )


def _run_portfolio_paper_watchlist_item(
    item: PortfolioPaperWatchlistItem,
    checked_at: Optional[str] = None,
) -> PortfolioPaperWatchlistRun:
    run_checked_at = checked_at or datetime.now(timezone.utc).isoformat()
    scenario = portfolio_scenario_store.get_scenario(item.scenario_id)
    if scenario is None:
        message = f"Scenario {item.scenario_id} was not found."
        updated = portfolio_paper_watchlist_store.record_error(
            item=item,
            error=message,
            active=False,
        )
        return PortfolioPaperWatchlistRun(
            checked_at=run_checked_at,
            item=updated,
            sessions=[],
            errors=[message],
        )

    sessions, errors = _create_portfolio_paper_sessions(
        scenario=scenario,
        item=item,
    )
    if sessions:
        updated = portfolio_paper_watchlist_store.record_run(item=item, sessions=sessions)
        if errors:
            updated = portfolio_paper_watchlist_store.record_error(
                item=updated,
                error=" ".join(errors),
            )
    else:
        message = " ".join(errors) if errors else "No paper sessions were created."
        updated = portfolio_paper_watchlist_store.record_error(item=item, error=message)

    return PortfolioPaperWatchlistRun(
        checked_at=run_checked_at,
        item=updated,
        sessions=sessions,
        errors=errors,
    )


def _promote_portfolio_paper_watchlist_order_intents(
    item: PortfolioPaperWatchlistItem,
    request: PortfolioPaperPromotionRequest,
) -> PortfolioPaperPromotionResponse:
    checked_at = datetime.now(timezone.utc).isoformat()
    queued: list[StrategyOrderQueueResponse] = []
    paper_only_handoffs: list[PaperToLiveHandoff] = []
    eligible_sessions: list[PaperTradingSession] = []
    skipped_sessions: list[str] = []
    errors: list[str] = []
    paper_only_existing = 0

    if not item.last_session_ids:
        return PortfolioPaperPromotionResponse(
            checked_at=checked_at,
            item=item,
            errors=["Paper watchlist item has no generated sessions yet."],
        )

    promotion_context = _portfolio_paper_promotion_context(
        item=item,
        request=request,
        checked_at=checked_at,
    )
    recent_session_ids = list(reversed(item.last_session_ids))[: request.max_sessions]
    for session_id in recent_session_ids:
        session = session_store.get_paper_session(session_id)
        if session is None:
            skipped_sessions.append(f"{session_id}: stored paper session not found.")
            continue

        skip_reason = _paper_promotion_skip_reason(
            session=session,
            rules=request.rules,
        )
        if skip_reason:
            skipped_sessions.append(f"{session.request.symbol}: {skip_reason}")
            continue

        eligible_sessions.append(session)
        route = paper_to_live_route(session)
        if route.status == "paper_only_review":
            handoff = _paper_only_promotion_handoff(
                item=item,
                session=session,
                route=route,
                promotion_context=promotion_context,
                checked_at=checked_at,
            )
            if handoff.already_logged:
                paper_only_existing += 1
            paper_only_handoffs.append(handoff)
            continue
        if not route.eligible_for_order_audit:
            errors.append(f"{session.request.symbol}: {route.message}")
            continue
        try:
            queued.append(
                queue_strategy_order_intents(
                    session=session,
                    audit_store=order_audit_store,
                    source="paper_session",
                    max_intents=request.max_intents_per_session,
                    context=promotion_context,
                )
            )
        except ValueError as exc:
            errors.append(f"{session.request.symbol}: {exc}")

    return PortfolioPaperPromotionResponse(
        checked_at=checked_at,
        item=item,
        eligible_sessions=eligible_sessions,
        queued=queued,
        paper_only_handoffs=paper_only_handoffs,
        created=sum(response.created for response in queued),
        skipped_existing=sum(response.skipped_existing for response in queued) + paper_only_existing,
        skipped_sessions=skipped_sessions,
        errors=errors,
    )


def _portfolio_paper_promotion_context(
    item: PortfolioPaperWatchlistItem,
    request: PortfolioPaperPromotionRequest,
    checked_at: str,
) -> dict[str, object]:
    return {
        "source": "portfolio_paper_watchlist_promotion",
        "checked_at": checked_at,
        "watchlist_id": item.id,
        "scenario_id": item.scenario_id,
        "scenario_name": item.scenario_name,
        "promotion_rules": request.rules.model_dump(mode="json"),
        "max_sessions": request.max_sessions,
        "max_intents_per_session": request.max_intents_per_session,
        "last_session_ids": item.last_session_ids,
    }


def _paper_only_promotion_handoff(
    *,
    item: PortfolioPaperWatchlistItem,
    session: PaperTradingSession,
    route: PaperToLiveRoute,
    promotion_context: dict[str, object],
    checked_at: str,
) -> PaperToLiveHandoff:
    handoff_id = f"paper-only-{item.id}-{session.id}"
    existing = operator_decision_store.list_decisions(
        decision_type="dry_run_promotion",
        target_id=handoff_id,
        limit=1,
    )
    message = (
        f"{session.request.symbol} remains paper-only; captured for stock/ETF operator review "
        "without creating a live-order audit."
    )
    decision_id = existing[0].id if existing else None
    already_logged = bool(existing)
    if not existing:
        decision = operator_decision_store.save_decision(
            OperatorDecisionCreate(
                decision_type="dry_run_promotion",
                target_id=handoff_id,
                status="noted",
                note=message,
                context={
                    **promotion_context,
                    "handoff_id": handoff_id,
                    "route_status": route.status,
                    "adapter_id": route.adapter.id,
                    "adapter_label": route.adapter.label,
                    "asset_class": route.adapter.asset_class,
                    "execution_mode": route.adapter.execution_mode,
                    "live_order_supported": route.adapter.live_order_supported,
                    "dry_run_audit_supported": route.adapter.dry_run_audit_supported,
                    "session_id": session.id,
                    "symbol": session.request.symbol,
                    "source": session.request.source,
                    "strategy": session.request.strategy,
                    "total_return_pct": session.summary.total_return_pct,
                    "max_drawdown_pct": session.summary.max_drawdown_pct,
                    "orders": session.summary.orders,
                    "final_equity": session.summary.final_equity,
                },
            )
        )
        decision_id = decision.id

    return PaperToLiveHandoff(
        id=handoff_id,
        created_at=checked_at,
        session_id=session.id,
        symbol=session.request.symbol,
        source=session.request.source,
        scenario_id=item.scenario_id,
        scenario_name=item.scenario_name,
        watchlist_id=item.id,
        route=route,
        decision_id=decision_id,
        already_logged=already_logged,
        message=message,
    )


def _paper_promotion_skip_reason(
    session: PaperTradingSession,
    rules: PortfolioPaperPromotionRules,
) -> Optional[str]:
    if session.summary.total_return_pct < rules.min_total_return_pct:
        return (
            f"return {session.summary.total_return_pct:.2f}% is below "
            f"{rules.min_total_return_pct:.2f}%."
        )
    drawdown = abs(session.summary.max_drawdown_pct)
    if drawdown > rules.max_drawdown_pct:
        return f"drawdown {drawdown:.2f}% is above {rules.max_drawdown_pct:.2f}%."
    if session.summary.orders < rules.min_orders:
        return f"orders {session.summary.orders} is below {rules.min_orders}."
    if not session.trades:
        return "no simulated trades to promote."
    return None


def _create_portfolio_paper_sessions(
    scenario: PortfolioResearchScenario,
    item: PortfolioPaperWatchlistItem,
) -> tuple[list[PaperTradingSession], list[str]]:
    request = scenario.request
    weights = _portfolio_symbol_weights(request)
    sessions: list[PaperTradingSession] = []
    errors: list[str] = []

    for symbol in weights:
        allocated_cash = round(request.initial_cash * weights[symbol], 2)
        paper_request = PaperTradingRequest(
            symbol=symbol,
            timeframe=request.timeframe,
            source=request.source,
            strategy=request.strategy,
            initial_cash=max(allocated_cash, 0.01),
            fee_bps=request.fee_bps,
            slippage_bps=request.slippage_bps,
            candle_limit=request.candle_limit,
            params=request.params,
            risk_limits=item.risk_limits,
        )
        try:
            candles = get_candles(
                symbol=symbol,
                timeframe=paper_request.timeframe,
                source=paper_request.source,
                limit=paper_request.candle_limit,
            )
            session = run_paper_session(request=paper_request, candles=candles)
        except (MarketDataError, ValueError) as exc:
            errors.append(f"{symbol}: {exc}")
            continue

        _annotate_paper_session_warnings(
            session=session,
            candle_count=len(candles),
            scenario_name=scenario.name,
        )
        session_store.save_paper_session(session)
        sessions.append(session)

    return sessions, errors


def _portfolio_symbol_weights(request: PortfolioResearchRequest) -> dict[str, float]:
    symbols: list[str] = []
    seen = set()
    for symbol in request.symbols:
        normalized = symbol.strip().upper()
        if normalized and normalized not in seen:
            seen.add(normalized)
            symbols.append(normalized)

    if not symbols:
        return {}

    raw_weights = {
        symbol.strip().upper(): value
        for symbol, value in request.weights.items()
    }
    positive_weights = {symbol: max(float(raw_weights.get(symbol, 0)), 0.0) for symbol in symbols}
    total = sum(positive_weights.values())
    if total <= 0:
        equal_weight = 1 / len(symbols)
        return {symbol: equal_weight for symbol in symbols}
    return {symbol: positive_weights[symbol] / total for symbol in symbols}


def _annotate_paper_session_warnings(
    session: PaperTradingSession,
    candle_count: int,
    scenario_name: Optional[str] = None,
) -> None:
    request = session.request
    if request.source == "sample":
        session.warnings.append(
            "Paper session used deterministic sample candles. Switch source to upbit for public KRW market data."
        )
    if request.source == "sample_us":
        session.warnings.append(
            "Paper session used deterministic US stock/ETF sample candles."
        )
    if request.source == "alpha_vantage":
        session.warnings.append(
            "Paper session used Alpha Vantage compact daily stock/ETF candles."
        )
        if candle_count < request.candle_limit:
            session.warnings.append(
                f"Alpha Vantage compact daily data returned {candle_count} rows for this request."
            )
    if request.source == "upbit" and request.candle_limit > 200:
        session.warnings.append("Upbit public candle endpoint is capped to 200 rows per call.")
    if scenario_name:
        session.warnings.append(
            f"Generated from portfolio paper watchlist scenario: {scenario_name}."
        )


def _research_scheduler_loop() -> None:
    while not _scheduler_stop.is_set():
        try:
            _run_due_portfolio_watchlist()
            _run_due_portfolio_paper_watchlist()
        except Exception:
            pass
        _scheduler_stop.wait(_research_scheduler_poll_seconds())


def _research_scheduler_enabled() -> bool:
    configured = os.environ.get("QUANT_LAB_RESEARCH_SCHEDULER_ENABLED", "true").lower()
    return configured not in {"0", "false", "no", "off", "disabled"}


def _research_scheduler_poll_seconds() -> int:
    configured = os.environ.get("QUANT_LAB_RESEARCH_SCHEDULER_POLL_SECONDS", "60")
    try:
        return max(5, int(configured))
    except ValueError:
        return 60
