from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


Number = Union[int, float]
StockPaperBrokerAdapterId = Literal[
    "us_equity_paper",
    "alpaca_us_equity_paper_preview",
    "alpaca_us_equity_paper",
]
StrategyName = Literal["sma_crossover", "donchian_breakout", "rsi_mean_reversion"]


class Candle(BaseModel):
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class MarketTicker(BaseModel):
    symbol: str
    source: Literal["sample", "sample_us", "alpha_vantage", "upbit"]
    timestamp: str
    price: float
    change_pct: float
    volume_24h: Optional[float] = None
    quote_volume_24h: Optional[float] = None


class MarketDataProviderStatus(BaseModel):
    source: Literal["sample", "sample_us", "alpha_vantage", "upbit"]
    label: str
    status_checked_at: str
    configured: bool
    available: bool
    credential_name: Optional[str] = None
    base_url: Optional[str] = None
    cache_ttl_seconds: Optional[int] = None
    last_success_at: Optional[str] = None
    last_error_at: Optional[str] = None
    last_error: Optional[str] = None
    last_symbol: Optional[str] = None
    last_timeframe: Optional[str] = None
    last_rows: Optional[int] = None
    note: str


class MarketDataColumnarStatus(BaseModel):
    enabled: bool
    checked_at: str
    duckdb_path: str
    parquet_path: str
    rows: int = 0
    sources: List[str] = Field(default_factory=list)
    symbols: List[str] = Field(default_factory=list)
    timeframes: List[str] = Field(default_factory=list)
    last_fetched_at: Optional[str] = None
    last_exported_at: Optional[str] = None
    last_error: Optional[str] = None


class MarketDataColumnarExport(BaseModel):
    exported_at: str
    duckdb_path: str
    parquet_path: str
    rows: int
    source: Optional[str] = None
    symbol: Optional[str] = None
    timeframe: Optional[str] = None


class ExecutionStatus(BaseModel):
    exchange: Literal["upbit"]
    checked_at: str
    live_trading_enabled: bool
    adapter_ready: bool
    base_url: str
    reason: str


class ExecutionSettings(BaseModel):
    exchange: Literal["upbit"]
    checked_at: str
    base_url: str
    live_trading_enabled: bool
    live_ack_configured: bool
    live_ack_required_value: str
    live_confirmation_required: bool
    credential_configured: bool
    private_reads_enabled: bool
    adapter_ready: bool
    order_info_source: Literal["local_defaults", "upbit_orders_chance"]
    min_order_notional_krw: float
    approval_fee_bps: float
    approval_fee_rate: float
    max_approval_exposure_pct: float
    reason: str


class UpbitAccountBalance(BaseModel):
    currency: str
    balance: float
    locked: float
    avg_buy_price: Optional[float] = None
    unit_currency: Optional[str] = None


class UpbitOpenOrder(BaseModel):
    uuid: str
    market: str
    side: str
    ord_type: str
    state: str
    price: Optional[float] = None
    volume: Optional[float] = None
    remaining_volume: Optional[float] = None
    created_at: Optional[str] = None
    identifier: Optional[str] = None


class UpbitPrivateSnapshot(BaseModel):
    exchange: Literal["upbit"]
    checked_at: str
    credential_ready: bool
    base_url: str
    reason: str
    balances: List[UpbitAccountBalance] = Field(default_factory=list)
    open_orders: List[UpbitOpenOrder] = Field(default_factory=list)


class OrderIntentRequest(BaseModel):
    exchange: Literal["upbit"] = Field(default="upbit")
    market: str = Field(default="KRW-BTC")
    side: Literal["bid", "ask"]
    ord_type: Literal["limit", "price", "market", "best"] = Field(default="limit")
    volume: Optional[float] = Field(default=None, gt=0)
    price: Optional[float] = Field(default=None, gt=0)
    identifier: Optional[str] = None
    time_in_force: Optional[Literal["ioc", "fok", "post_only"]] = None
    live_confirmation: bool = Field(default=False)


class OrderAuditRecord(BaseModel):
    id: str
    created_at: str
    exchange: Literal["upbit"]
    market: str
    side: Literal["bid", "ask"]
    ord_type: Literal["limit", "price", "market", "best"]
    status: Literal["blocked", "submitted", "failed", "dry_run"]
    reason: str
    request_payload: Dict[str, Any]
    response_payload: Optional[Dict[str, Any]] = None


class OrderApprovalRequest(BaseModel):
    live_confirmation: bool = Field(default=False)


class OrderPrecheckItem(BaseModel):
    name: str
    status: Literal["pass", "warn", "fail"]
    message: str
    value: Optional[float] = None
    threshold: Optional[float] = None


class OrderPrecheckResult(BaseModel):
    record_id: str
    market: str
    side: Literal["bid", "ask"]
    checked_at: str
    status: Literal["pass", "warn", "fail"]
    order_info_source: Literal["local_defaults", "upbit_orders_chance"]
    order_info_checked_at: str
    order_info_age_seconds: float = 0.0
    estimated_notional: float
    min_order_notional: float
    max_order_notional: Optional[float] = None
    price_unit: Optional[float] = None
    fee_rate: float
    quote_currency: str
    base_currency: str
    credential_ready: bool
    available_quote_balance: Optional[float] = None
    available_base_balance: Optional[float] = None
    post_order_exposure_pct: Optional[float] = None
    max_post_order_exposure_pct: float
    checks: List[OrderPrecheckItem] = Field(default_factory=list)


class ExecutionRunbook(BaseModel):
    generated_at: str
    title: str
    record_id: str
    filename: str
    audit: OrderAuditRecord
    precheck: OrderPrecheckResult
    markdown: str


class StrategyOrderQueueRequest(BaseModel):
    max_intents: int = Field(default=5, ge=1, le=50)


class StrategyOrderQueueResponse(BaseModel):
    session_id: str
    source: Literal["paper_session", "live_paper_session"]
    created: int
    skipped_existing: int
    records: List[OrderAuditRecord] = Field(default_factory=list)


class Trade(BaseModel):
    timestamp: str
    side: Literal["buy", "sell"]
    price: float
    quantity: float
    notional: float
    fee: float
    cash_after: float
    equity_after: float


class EquityPoint(BaseModel):
    timestamp: str
    equity: float
    cash: float
    asset_quantity: float
    close: float
    target_exposure: float
    drawdown_pct: float


class BacktestMetrics(BaseModel):
    initial_equity: float
    final_equity: float
    total_return_pct: float
    buy_and_hold_final_equity: float = 0.0
    buy_and_hold_return_pct: float = 0.0
    buy_and_hold_max_drawdown_pct: float = 0.0
    strategy_edge_pct: float = 0.0
    cagr_pct: float
    max_drawdown_pct: float
    sharpe: float
    sortino: float
    exposure_pct: float
    trades: int


class BacktestRequest(BaseModel):
    symbol: str = Field(default="KRW-BTC")
    timeframe: str = Field(default="day")
    source: Literal["sample", "sample_us", "alpha_vantage", "upbit"] = Field(default="sample")
    strategy: StrategyName = Field(default="sma_crossover")
    initial_cash: float = Field(default=1_000_000, gt=0)
    fee_bps: float = Field(default=5, ge=0)
    slippage_bps: float = Field(default=2, ge=0)
    candle_limit: int = Field(default=180, ge=50, le=400)
    params: Dict[str, Number] = Field(default_factory=dict)


class BacktestResponse(BaseModel):
    id: Optional[str] = None
    created_at: Optional[str] = None
    request: BacktestRequest
    metrics: BacktestMetrics
    equity_curve: List[EquityPoint]
    trades: List[Trade]
    candles: List[Candle]
    warnings: List[str] = Field(default_factory=list)


class BacktestRunSummary(BaseModel):
    id: str
    created_at: str
    request: BacktestRequest
    metrics: BacktestMetrics
    warnings: List[str] = Field(default_factory=list)


class BacktestRun(BacktestResponse):
    id: str
    created_at: str


class BacktestSweepRequest(BacktestRequest):
    candidates: List[Dict[str, Number]] = Field(default_factory=list, max_length=16)


class BacktestSweepCandidate(BaseModel):
    rank: int
    score: float
    params: Dict[str, Number]
    metrics: BacktestMetrics
    trades: int
    warnings: List[str] = Field(default_factory=list)


class BacktestSweepResponse(BaseModel):
    generated_at: str
    request: BacktestSweepRequest
    candidates: List[BacktestSweepCandidate]
    best: Optional[BacktestSweepCandidate] = None
    warnings: List[str] = Field(default_factory=list)


class BacktestValidationRequest(BacktestRequest):
    train_fraction: float = Field(default=0.7, ge=0.5, le=0.9)


class BacktestValidationSegment(BaseModel):
    label: Literal["train", "test"]
    candle_count: int
    start_timestamp: str
    end_timestamp: str
    metrics: BacktestMetrics
    trades: int


class BacktestValidationResponse(BaseModel):
    generated_at: str
    request: BacktestValidationRequest
    total_candles: int
    train: BacktestValidationSegment
    test: BacktestValidationSegment
    edge_gap_pct: float
    return_gap_pct: float
    robustness_score: float
    verdict: Literal["pass", "watch", "fail"]
    reason: str
    warnings: List[str] = Field(default_factory=list)


class BacktestWalkForwardRequest(BacktestRequest):
    train_window: int = Field(default=90, ge=30, le=300)
    test_window: int = Field(default=30, ge=10, le=120)
    step_size: int = Field(default=30, ge=10, le=120)


class BacktestWalkForwardFold(BaseModel):
    index: int
    train: BacktestValidationSegment
    test: BacktestValidationSegment
    edge_gap_pct: float
    return_gap_pct: float
    robustness_score: float
    verdict: Literal["pass", "watch", "fail"]
    reason: str


class BacktestWalkForwardResponse(BaseModel):
    generated_at: str
    request: BacktestWalkForwardRequest
    total_candles: int
    folds: List[BacktestWalkForwardFold] = Field(default_factory=list)
    pass_count: int = 0
    watch_count: int = 0
    fail_count: int = 0
    average_test_return_pct: float
    average_test_edge_pct: float
    average_robustness_score: float
    verdict: Literal["pass", "watch", "fail"]
    reason: str
    warnings: List[str] = Field(default_factory=list)


class PortfolioResearchRequest(BaseModel):
    symbols: List[str] = Field(default_factory=lambda: ["SPY", "QQQ", "AAPL"], min_length=2, max_length=8)
    timeframe: str = Field(default="day")
    source: Literal["sample", "sample_us", "alpha_vantage", "upbit"] = Field(default="sample_us")
    strategy: StrategyName = Field(default="sma_crossover")
    initial_cash: float = Field(default=100_000, gt=0)
    fee_bps: float = Field(default=1, ge=0)
    slippage_bps: float = Field(default=1, ge=0)
    candle_limit: int = Field(default=180, ge=50, le=400)
    weights: Dict[str, float] = Field(default_factory=dict)
    rebalance_frequency: Literal["none", "monthly"] = Field(default="none")
    params: Dict[str, Number] = Field(default_factory=dict)


class PortfolioAllocationResult(BaseModel):
    symbol: str
    target_weight_pct: float
    final_weight_pct: float
    initial_cash: float
    final_equity: float
    total_return_pct: float
    strategy_edge_pct: float
    max_drawdown_pct: float
    sharpe: float
    trades: int


class PortfolioEquityPoint(BaseModel):
    timestamp: str
    equity: float
    drawdown_pct: float


class PortfolioResearchMetrics(BaseModel):
    initial_equity: float
    final_equity: float
    total_return_pct: float
    max_drawdown_pct: float
    average_return_pct: float
    rebalances: int
    best_symbol: str
    best_return_pct: float
    worst_symbol: str
    worst_return_pct: float
    trades: int


class PortfolioResearchResponse(BaseModel):
    request: PortfolioResearchRequest
    metrics: PortfolioResearchMetrics
    allocations: List[PortfolioAllocationResult]
    equity_curve: List[PortfolioEquityPoint]
    warnings: List[str] = Field(default_factory=list)


class PortfolioResearchPreset(BaseModel):
    id: str
    name: str
    description: str
    request: PortfolioResearchRequest


class PortfolioResearchScenarioCreate(BaseModel):
    name: str = Field(default="Saved portfolio scenario", min_length=1, max_length=80)
    request: PortfolioResearchRequest = Field(default_factory=PortfolioResearchRequest)


class PortfolioResearchScenario(BaseModel):
    id: str
    name: str
    created_at: str
    updated_at: str
    request: PortfolioResearchRequest


class PortfolioResearchScan(BaseModel):
    id: str
    scenario_id: str
    scenario_name: str
    created_at: str
    result: PortfolioResearchResponse


class PortfolioResearchAlertThresholds(BaseModel):
    max_drawdown_pct: Optional[float] = Field(default=None, ge=0, le=100)
    min_total_return_pct: Optional[float] = None
    min_average_edge_pct: Optional[float] = None
    max_return_drift_pct: Optional[float] = Field(default=None, ge=0)


class PortfolioResearchAlert(BaseModel):
    rule: Literal[
        "max_drawdown_pct",
        "min_total_return_pct",
        "min_average_edge_pct",
        "max_return_drift_pct",
    ]
    level: Literal["warning"] = "warning"
    message: str
    value: float
    threshold: float


class PortfolioResearchWatchlistCreate(BaseModel):
    scenario_id: str = Field(min_length=1)
    interval_minutes: int = Field(default=60, ge=1, le=1440)
    active: bool = True
    alert_thresholds: PortfolioResearchAlertThresholds = Field(
        default_factory=PortfolioResearchAlertThresholds
    )


class PortfolioResearchWatchlistItem(BaseModel):
    id: str
    scenario_id: str
    scenario_name: str
    created_at: str
    updated_at: str
    interval_minutes: int
    active: bool
    next_run_at: str
    alert_thresholds: PortfolioResearchAlertThresholds = Field(
        default_factory=PortfolioResearchAlertThresholds
    )
    last_run_at: Optional[str] = None
    last_scan_id: Optional[str] = None
    last_alerts: List[PortfolioResearchAlert] = Field(default_factory=list)
    last_error: Optional[str] = None


class PortfolioResearchSchedulerRun(BaseModel):
    checked_at: str
    due: int
    scanned: List[PortfolioResearchScan] = Field(default_factory=list)
    alerts: List[PortfolioResearchAlert] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class RiskLimits(BaseModel):
    max_position_pct: float = Field(default=60, ge=0, le=100)
    max_order_notional: Optional[float] = Field(default=500_000, gt=0)
    max_orders: int = Field(default=20, ge=0)
    max_session_loss_pct: float = Field(default=12, ge=0, le=100)
    kill_switch: bool = Field(default=False)


class RiskEvent(BaseModel):
    timestamp: str
    level: Literal["info", "warning", "halt"]
    rule: str
    message: str


class PaperTradingRequest(BacktestRequest):
    risk_limits: RiskLimits = Field(default_factory=RiskLimits)


class LivePaperTradingRequest(PaperTradingRequest):
    warmup_bars: int = Field(default=30, ge=2, le=300)


class PaperAdvanceRequest(BaseModel):
    steps: int = Field(default=1, ge=1, le=50)


class PaperTradingSummary(BaseModel):
    session_id: str
    status: Literal["running", "completed", "halted"]
    halted_reason: Optional[str] = None
    initial_equity: float
    final_equity: float
    total_return_pct: float
    max_drawdown_pct: float
    cash: float
    asset_quantity: float
    open_position_pct: float
    orders: int
    risk_events: int


class PaperTradingSession(BaseModel):
    id: str
    created_at: str
    request: PaperTradingRequest
    summary: PaperTradingSummary
    equity_curve: List[EquityPoint]
    trades: List[Trade]
    risk_events: List[RiskEvent]
    warnings: List[str] = Field(default_factory=list)


class LivePaperTradingSession(PaperTradingSession):
    request: LivePaperTradingRequest
    warmup_bars: int
    next_index: int
    total_candles: int
    mode: Literal["replay", "ticker"] = Field(default="replay")


class PortfolioPaperWatchlistCreate(BaseModel):
    scenario_id: str = Field(min_length=1)
    interval_minutes: int = Field(default=240, ge=1, le=1440)
    active: bool = True
    risk_limits: RiskLimits = Field(default_factory=RiskLimits)


class PortfolioPaperWatchlistItem(BaseModel):
    id: str
    scenario_id: str
    scenario_name: str
    created_at: str
    updated_at: str
    interval_minutes: int
    active: bool
    next_run_at: str
    risk_limits: RiskLimits = Field(default_factory=RiskLimits)
    last_run_at: Optional[str] = None
    last_session_ids: List[str] = Field(default_factory=list)
    last_error: Optional[str] = None


class PortfolioPaperWatchlistRun(BaseModel):
    checked_at: str
    item: PortfolioPaperWatchlistItem
    sessions: List[PaperTradingSession] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class PortfolioPaperSchedulerRun(BaseModel):
    checked_at: str
    due: int
    runs: List[PortfolioPaperWatchlistRun] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class PortfolioPaperPromotionRules(BaseModel):
    min_total_return_pct: float = Field(default=0)
    max_drawdown_pct: float = Field(default=15, ge=0, le=100)
    min_orders: int = Field(default=1, ge=0)


class PortfolioPaperPromotionRequest(BaseModel):
    max_sessions: int = Field(default=3, ge=1, le=8)
    max_intents_per_session: int = Field(default=3, ge=1, le=20)
    rules: PortfolioPaperPromotionRules = Field(default_factory=PortfolioPaperPromotionRules)


BotOperatingStyle = Literal[
    "trend_following",
    "mean_reversion",
    "breakout",
    "portfolio_rotation",
    "defensive_monitor",
    "custom",
]
BotExecutionMode = Literal["paper", "dry_run"]
BotConflictPolicy = Literal["allow", "block_same_symbol"]
BotRunStatus = Literal["completed", "halted", "blocked", "error"]


class BotProfileCreate(BaseModel):
    name: str = Field(default="Trend Scout", min_length=1, max_length=80)
    description: str = Field(
        default="Runs a paper strategy as an independently monitored bot.",
        max_length=240,
    )
    operating_style: BotOperatingStyle = Field(default="trend_following")
    request: PaperTradingRequest = Field(default_factory=PaperTradingRequest)
    execution_mode: BotExecutionMode = Field(default="paper")
    interval_minutes: int = Field(default=240, ge=1, le=1440)
    active: bool = True
    priority: int = Field(default=50, ge=1, le=100)
    max_intents_per_run: int = Field(default=3, ge=1, le=20)
    conflict_policy: BotConflictPolicy = Field(default="block_same_symbol")


class BotProfile(BaseModel):
    id: str
    name: str
    description: str
    operating_style: BotOperatingStyle
    request: PaperTradingRequest
    execution_mode: BotExecutionMode
    interval_minutes: int
    active: bool
    priority: int
    max_intents_per_run: int
    conflict_policy: BotConflictPolicy
    created_at: str
    updated_at: str
    next_run_at: str
    last_run_at: Optional[str] = None
    last_run_id: Optional[str] = None
    last_session_id: Optional[str] = None
    last_status: Optional[BotRunStatus] = None
    last_error: Optional[str] = None


class BotRun(BaseModel):
    id: str
    bot_id: str
    bot_name: str
    checked_at: str
    status: BotRunStatus
    operating_style: BotOperatingStyle
    execution_mode: BotExecutionMode
    request: PaperTradingRequest
    session: Optional[PaperTradingSession] = None
    queued: Optional[StrategyOrderQueueResponse] = None
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class BotFleetSummary(BaseModel):
    total_bots: int
    active_bots: int
    due_bots: int
    paper_bots: int
    dry_run_bots: int
    open_position_bots: int
    active_errors: int
    recent_dry_run_intents: int


class BotFleetStatus(BaseModel):
    checked_at: str
    summary: BotFleetSummary
    profiles: List[BotProfile] = Field(default_factory=list)
    recent_runs: List[BotRun] = Field(default_factory=list)


class BotFleetRun(BaseModel):
    checked_at: str
    due: int
    runs: List[BotRun] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class BrokerAdapterContract(BaseModel):
    id: str
    label: str
    provider_type: Literal["exchange", "paper_broker"]
    submission_mode: Literal["guarded_live", "paper_record_only", "external_paper"]
    live_order_supported: bool
    dry_run_supported: bool
    account_snapshot_supported: bool = False
    required_credentials: List[str] = Field(default_factory=list)
    supported_order_types: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class BrokerReadinessCheck(BaseModel):
    id: str
    label: str
    status: Literal["pass", "warn", "fail"]
    message: str


class BrokerReadinessItem(BaseModel):
    adapter_id: str
    label: str
    broker: str
    asset_class: Literal["crypto_spot", "stock_etf"]
    status: Literal["ready", "watch", "blocked"]
    live_submission_state: Literal["guarded_live", "paper_record_only", "external_paper", "blocked"]
    broker_contract: BrokerAdapterContract
    credential_boundary: str
    checks: List[BrokerReadinessCheck] = Field(default_factory=list)
    message: str


class BrokerReadinessResponse(BaseModel):
    checked_at: str
    items: List[BrokerReadinessItem] = Field(default_factory=list)


class BrokerOrderIntentRequest(BaseModel):
    adapter_id: StockPaperBrokerAdapterId = Field(default="us_equity_paper")
    symbol: str = Field(default="SPY", min_length=1, max_length=20)
    side: Literal["buy", "sell"] = Field(default="buy")
    quantity: float = Field(default=1, gt=0)
    order_type: Literal["market", "limit"] = Field(default="market")
    limit_price: Optional[float] = Field(default=None, gt=0)
    time_in_force: Literal["day", "gtc", "ioc", "fok"] = Field(default="day")
    client_order_id: Optional[str] = Field(default=None, max_length=120)
    live_confirmation: bool = Field(default=False)
    paper_submit_confirmation: bool = Field(default=False)
    reference_price: Optional[float] = Field(default=None, gt=0)
    cash_available: Optional[float] = Field(default=None, ge=0)
    current_position_quantity: float = Field(default=0, ge=0)
    portfolio_equity: Optional[float] = Field(default=None, gt=0)
    paper_fee_bps: float = Field(default=1, ge=0)
    paper_slippage_bps: float = Field(default=1, ge=0)
    paper_session_id: Optional[str] = Field(default=None, max_length=120)


class BrokerPaperFillEstimate(BaseModel):
    status: Literal[
        "estimated_fill",
        "not_fillable",
        "cash_shortfall",
        "position_shortfall",
    ]
    reason: str
    reference_price: float
    fill_price: Optional[float] = None
    quantity: float
    estimated_notional: Optional[float] = None
    estimated_fee: Optional[float] = None
    cash_after: Optional[float] = None
    position_after: Optional[float] = None
    exposure_pct_after: Optional[float] = None
    cash_sufficient: Optional[bool] = None
    position_sufficient: Optional[bool] = None
    fillable: bool
    fee_bps: float
    slippage_bps: float


class BrokerOrderIntentEvaluation(BaseModel):
    id: str
    checked_at: str
    adapter_id: StockPaperBrokerAdapterId
    broker_contract: BrokerAdapterContract
    request: BrokerOrderIntentRequest
    validation_status: Literal["accepted", "rejected"]
    submission_status: Literal["paper_recorded", "blocked", "rejected"]
    reason: str
    normalized_symbol: Optional[str] = None
    estimated_notional: Optional[float] = None
    broker_order_id: Optional[str] = None
    external_submission_attempted: bool = False
    live_submission_supported: bool = False
    paper_fill_estimate: Optional[BrokerPaperFillEstimate] = None


class BrokerOrderReconciliation(BaseModel):
    id: str
    checked_at: str
    evaluation_id: str
    adapter_id: StockPaperBrokerAdapterId
    local_submission_status: Literal["paper_recorded", "blocked", "rejected"]
    status: Literal["matched", "mismatch", "blocked", "not_found", "unsupported", "error"]
    reason: str
    broker_order_id: Optional[str] = None
    client_order_id: Optional[str] = None
    broker_status: Optional[str] = None
    broker_symbol: Optional[str] = None
    broker_side: Optional[str] = None
    broker_quantity: Optional[float] = None
    broker_filled_quantity: Optional[float] = None
    broker_avg_fill_price: Optional[float] = None
    broker_filled_notional: Optional[float] = None
    broker_fee: Optional[float] = None
    broker_partial_fill: Optional[bool] = None
    broker_fill_activity_count: int = 0
    broker_submitted_at: Optional[str] = None
    broker_filled_at: Optional[str] = None
    broker_position_quantity: Optional[float] = None
    broker_position_market_value: Optional[float] = None
    broker_position_cost_basis: Optional[float] = None
    broker_position_unrealized_pl: Optional[float] = None
    broker_position_snapshot: Dict[str, Any] = Field(default_factory=dict)
    broker_account_cash: Optional[float] = None
    broker_account_equity: Optional[float] = None
    broker_account_buying_power: Optional[float] = None
    broker_account_snapshot: Dict[str, Any] = Field(default_factory=dict)
    broker_fill_activities: List[Dict[str, Any]] = Field(default_factory=list)
    linked_paper_fill_note_id: Optional[str] = None
    paper_fill_comparison_status: Optional[
        Literal["matched", "drift", "partial_fill", "missing_broker_fill"]
    ] = None
    paper_fill_price_delta: Optional[float] = None
    paper_fill_price_delta_pct: Optional[float] = None
    paper_fill_notional_delta: Optional[float] = None
    paper_fill_fee_delta: Optional[float] = None
    external_lookup_attempted: bool = False
    broker_payload: Dict[str, Any] = Field(default_factory=dict)


class BrokerIntentEvaluationReport(BaseModel):
    generated_at: str
    title: str
    filename: str
    evaluations: List[BrokerOrderIntentEvaluation] = Field(default_factory=list)
    summary: Dict[str, int] = Field(default_factory=dict)
    markdown: str


class PaperFillOrderNote(BaseModel):
    id: str
    created_at: str
    session_id: str
    evaluation_id: str
    adapter_id: StockPaperBrokerAdapterId
    symbol: str
    side: Literal["buy", "sell"]
    quantity: float
    order_type: Literal["market", "limit"]
    paper_fill_status: Literal["estimated_fill"]
    intended_fill_price: float
    intended_notional: float
    intended_fee: float
    simulated_trade_timestamp: Optional[str] = None
    simulated_fill_price: Optional[float] = None
    simulated_quantity: Optional[float] = None
    simulated_notional: Optional[float] = None
    price_delta: Optional[float] = None
    price_delta_pct: Optional[float] = None
    quantity_delta: Optional[float] = None
    notional_delta: Optional[float] = None
    comparison_status: Literal["matched_trade", "no_trade_match"]
    external_submission_attempted: bool = False
    note: str


class PaperFillOrderNoteDriftRow(BaseModel):
    adapter_id: StockPaperBrokerAdapterId
    symbol: str
    note_count: int
    matched_trade_count: int
    no_trade_match_count: int
    external_submission_attempted_count: int
    avg_price_delta_pct: Optional[float] = None
    avg_abs_price_delta_pct: Optional[float] = None
    worst_abs_price_delta_pct: Optional[float] = None
    latest_price_delta_pct: Optional[float] = None
    latest_created_at: str
    latest_session_id: str
    latest_evaluation_id: str
    latest_comparison_status: Literal["matched_trade", "no_trade_match"]
    latest_note: str


class PaperFillOrderNoteAnalytics(BaseModel):
    generated_at: str
    limit: int
    adapter_id: Optional[StockPaperBrokerAdapterId] = None
    symbol: Optional[str] = None
    notes_considered: int
    matched_trade_count: int
    external_submission_attempted_count: int
    rows: List[PaperFillOrderNoteDriftRow] = Field(default_factory=list)


PaperFillQualityGateStatus = Literal["ready", "watch", "blocked"]


class PaperFillOrderNoteQualityGateRow(BaseModel):
    adapter_id: StockPaperBrokerAdapterId
    symbol: str
    status: PaperFillQualityGateStatus
    reasons: List[str] = Field(default_factory=list)
    note_count: int
    matched_trade_count: int
    no_trade_match_count: int
    external_submission_attempted_count: int
    avg_abs_price_delta_pct: Optional[float] = None
    worst_abs_price_delta_pct: Optional[float] = None
    latest_created_at: str
    latest_session_id: str
    latest_evaluation_id: str


class PaperFillOrderNoteQualityGate(BaseModel):
    generated_at: str
    status: PaperFillQualityGateStatus
    reason: str
    limit: int
    min_notes: int
    max_avg_abs_price_delta_pct: float
    max_worst_abs_price_delta_pct: float
    require_no_external_submission: bool
    adapter_id: Optional[StockPaperBrokerAdapterId] = None
    symbol: Optional[str] = None
    analytics: PaperFillOrderNoteAnalytics
    rows: List[PaperFillOrderNoteQualityGateRow] = Field(default_factory=list)


class StockEtfBrokerExpansionCandidate(BaseModel):
    decision_id: str
    target_id: Optional[str] = None
    created_at: str
    decision_status: Literal["approved", "rejected", "needs_work", "noted"]
    symbol: str
    session_id: Optional[str] = None
    scenario_name: Optional[str] = None
    source: Optional[str] = None
    adapter_id: Optional[str] = None
    adapter_label: Optional[str] = None
    quality_gate_status: PaperFillQualityGateStatus
    quality_gate_reason: str
    quality_gate_checked_at: Optional[str] = None
    note_count: int = 0
    matched_trade_count: int = 0
    avg_abs_price_delta_pct: Optional[float] = None
    worst_abs_price_delta_pct: Optional[float] = None
    approved_for_broker_expansion: bool = False
    message: str


class StockEtfBrokerExpansionReadiness(BaseModel):
    generated_at: str
    status: Literal["ready", "watch", "blocked"]
    reason: str
    counts: Dict[str, int] = Field(default_factory=dict)
    candidates: List[StockEtfBrokerExpansionCandidate] = Field(default_factory=list)


class StockEtfBrokerExpansionReport(BaseModel):
    generated_at: str
    title: str
    filename: str
    readiness: StockEtfBrokerExpansionReadiness
    markdown: str


class StockEtfBrokerExpansionOrderPayload(BaseModel):
    adapter_id: StockPaperBrokerAdapterId
    symbol: str
    side: Literal["buy", "sell"]
    quantity: float
    order_type: Literal["market", "limit"]
    time_in_force: str = "day"
    expected_fill_price: float
    estimated_notional: float
    evaluation_id: str
    paper_session_id: str
    external_submission_attempted: bool = False
    payload: Dict[str, Any] = Field(default_factory=dict)


class StockEtfBrokerExpansionPackage(BaseModel):
    generated_at: str
    title: str
    filename: str
    candidate: StockEtfBrokerExpansionCandidate
    quality_gate: PaperFillOrderNoteQualityGate
    broker_evaluations: List[BrokerOrderIntentEvaluation] = Field(default_factory=list)
    order_notes: List[PaperFillOrderNote] = Field(default_factory=list)
    order_payloads: List[StockEtfBrokerExpansionOrderPayload] = Field(default_factory=list)
    markdown: str


class StockEtfBrokerExpansionPreflightCheck(BaseModel):
    id: str
    label: str
    status: Literal["pass", "warn", "fail"]
    message: str
    evidence_id: Optional[str] = None


class StockEtfBrokerExpansionPreflight(BaseModel):
    generated_at: str
    title: str
    filename: str
    status: Literal["pass", "warn", "fail"]
    reason: str
    package: StockEtfBrokerExpansionPackage
    checks: List[StockEtfBrokerExpansionPreflightCheck] = Field(default_factory=list)
    markdown: str


class StockEtfBrokerExpansionRehearsalOrder(BaseModel):
    id: str
    evaluation_id: str
    adapter_id: StockPaperBrokerAdapterId
    symbol: str
    side: Literal["buy", "sell"]
    quantity: float
    order_type: Literal["market", "limit"]
    status: Literal["accepted", "rejected"]
    reason: str
    expected_fill_price: float
    estimated_notional: float
    paper_session_id: str
    external_submission_attempted: bool = False
    payload: Dict[str, Any] = Field(default_factory=dict)


class StockEtfBrokerExpansionRehearsal(BaseModel):
    generated_at: str
    title: str
    filename: str
    status: Literal["pass", "warn", "fail"]
    reason: str
    preflight: StockEtfBrokerExpansionPreflight
    accepted_orders: int
    rejected_orders: int
    orders: List[StockEtfBrokerExpansionRehearsalOrder] = Field(default_factory=list)
    markdown: str


class PaperToLiveAdapterProfile(BaseModel):
    id: Literal[
        "upbit_crypto_spot",
        "us_equity_paper",
        "alpaca_us_equity_paper_preview",
        "alpaca_us_equity_paper",
    ]
    label: str
    broker: str
    asset_class: Literal["crypto_spot", "stock_etf"]
    execution_mode: Literal["guarded_live", "paper_only"]
    live_order_supported: bool
    dry_run_audit_supported: bool
    supported_sources: List[str] = Field(default_factory=list)
    symbol_hint: str
    broker_contract: BrokerAdapterContract
    reason: str


class PaperToLiveRoute(BaseModel):
    session_id: str
    symbol: str
    source: Literal["sample", "sample_us", "alpha_vantage", "upbit"]
    adapter: PaperToLiveAdapterProfile
    status: Literal["dry_run_ready", "paper_only_review", "unsupported"]
    eligible_for_order_audit: bool
    message: str


class PaperToLiveHandoff(BaseModel):
    id: str
    created_at: str
    session_id: str
    symbol: str
    source: Literal["sample", "sample_us", "alpha_vantage", "upbit"]
    scenario_id: Optional[str] = None
    scenario_name: Optional[str] = None
    watchlist_id: Optional[str] = None
    route: PaperToLiveRoute
    decision_id: Optional[str] = None
    already_logged: bool = False
    message: str


class PortfolioPaperPromotionResponse(BaseModel):
    checked_at: str
    item: PortfolioPaperWatchlistItem
    eligible_sessions: List[PaperTradingSession] = Field(default_factory=list)
    queued: List[StrategyOrderQueueResponse] = Field(default_factory=list)
    paper_only_handoffs: List[PaperToLiveHandoff] = Field(default_factory=list)
    created: int = 0
    skipped_existing: int = 0
    skipped_sessions: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class AlertReviewItem(BaseModel):
    id: str
    source: Literal[
        "portfolio_scan",
        "portfolio_scan_error",
        "paper_watchlist_error",
        "paper_session_risk",
        "paper_session_halt",
        "broker_paper_submission",
        "broker_reconciliation",
        "paper_fill_drift",
    ]
    level: Literal["info", "warning", "halt", "error"]
    title: str
    message: str
    created_at: str
    scenario_id: Optional[str] = None
    scenario_name: Optional[str] = None
    watchlist_id: Optional[str] = None
    scan_id: Optional[str] = None
    session_id: Optional[str] = None
    evaluation_id: Optional[str] = None
    reconciliation_id: Optional[str] = None
    adapter_id: Optional[str] = None
    symbol: Optional[str] = None
    rule: Optional[str] = None
    value: Optional[float] = None
    threshold: Optional[float] = None
    acknowledgement_status: Optional[Literal["acknowledged", "dismissed"]] = None
    acknowledged_at: Optional[str] = None
    acknowledgement_note: Optional[str] = None


class AlertReviewResponse(BaseModel):
    checked_at: str
    items: List[AlertReviewItem] = Field(default_factory=list)
    counts: Dict[str, int] = Field(default_factory=dict)


class AlertReviewAcknowledgeRequest(BaseModel):
    status: Literal["acknowledged", "dismissed"] = Field(default="acknowledged")
    note: Optional[str] = Field(default=None, max_length=240)


class AlertReviewAcknowledgement(BaseModel):
    alert_id: str
    status: Literal["acknowledged", "dismissed"]
    acknowledged_at: str
    note: Optional[str] = None


class LiveReadinessCheck(BaseModel):
    id: str
    label: str
    category: Literal["system", "operator"] = Field(default="system")
    status: Literal["pass", "warn", "fail"]
    message: str
    weight: float = Field(default=1.0, gt=0)
    score: float = Field(default=0)


class LiveReadinessBreakdown(BaseModel):
    id: Literal["system", "operator"]
    label: str
    status: Literal["ready", "watch", "blocked"]
    score: float
    checks: List[LiveReadinessCheck] = Field(default_factory=list)
    blocking_checks: List[str] = Field(default_factory=list)
    warning_checks: List[str] = Field(default_factory=list)
    message: str


class LiveReadinessResponse(BaseModel):
    checked_at: str
    status: Literal["ready", "watch", "blocked"]
    score: float
    checks: List[LiveReadinessCheck] = Field(default_factory=list)
    breakdowns: List[LiveReadinessBreakdown] = Field(default_factory=list)


class LiveCutoverChecklistItem(BaseModel):
    id: str
    label: str
    status: Literal["pass", "warn", "fail"]
    message: str
    evidence_id: Optional[str] = None


class OperatorDecisionCreate(BaseModel):
    decision_type: Literal[
        "readiness_review",
        "dry_run_promotion",
        "dry_run_approval",
        "alert_review",
        "live_cutover",
    ] = Field(default="readiness_review")
    target_id: Optional[str] = Field(default=None, max_length=160)
    status: Literal["approved", "rejected", "needs_work", "noted"] = Field(default="noted")
    note: Optional[str] = Field(default=None, max_length=500)
    context: Dict[str, Any] = Field(default_factory=dict)


class OperatorDecisionRecord(BaseModel):
    id: str
    created_at: str
    decision_type: Literal[
        "readiness_review",
        "dry_run_promotion",
        "dry_run_approval",
        "alert_review",
        "live_cutover",
    ]
    target_id: Optional[str] = None
    status: Literal["approved", "rejected", "needs_work", "noted"]
    note: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)


class LiveCutoverChecklistResponse(BaseModel):
    checked_at: str
    status: Literal["ready", "watch", "blocked"]
    items: List[LiveCutoverChecklistItem] = Field(default_factory=list)
    readiness: LiveReadinessResponse
    latest_operator_decisions: List[OperatorDecisionRecord] = Field(default_factory=list)


class LiveCutoverRunbook(BaseModel):
    generated_at: str
    title: str
    filename: str
    checklist: LiveCutoverChecklistResponse
    settings: ExecutionSettings
    markdown: str


class LiveArmingSimulationRequest(BaseModel):
    live_trading_enabled: bool = True
    live_ack_configured: bool = True
    credential_configured: bool = True
    assume_required_operator_decisions: bool = False


class LiveArmingSimulationChange(BaseModel):
    id: str
    label: str
    current_status: Literal["pass", "warn", "fail"]
    simulated_status: Literal["pass", "warn", "fail"]
    current_message: str
    simulated_message: str
    changed: bool


class LiveArmingSimulationResponse(BaseModel):
    generated_at: str
    no_order_submission: bool = True
    assumptions: LiveArmingSimulationRequest
    current: LiveCutoverChecklistResponse
    simulated: LiveCutoverChecklistResponse
    changes: List[LiveArmingSimulationChange] = Field(default_factory=list)
    current_blockers: List[LiveCutoverChecklistItem] = Field(default_factory=list)
    simulated_blockers: List[LiveCutoverChecklistItem] = Field(default_factory=list)
    summary: str


class PostCutoverMonitorItem(BaseModel):
    id: str
    label: str
    status: Literal["pass", "warn", "fail"]
    message: str
    evidence_id: Optional[str] = None


class PostCutoverOrderMonitor(BaseModel):
    checked_at: str
    status: Literal["idle", "watch", "attention", "blocked"]
    settings: ExecutionSettings
    private_snapshot: Optional[UpbitPrivateSnapshot] = None
    private_snapshot_error: Optional[str] = None
    open_orders: List[UpbitOpenOrder] = Field(default_factory=list)
    recent_approval_attempts: List[OrderAuditRecord] = Field(default_factory=list)
    latest_audit: Optional[OrderAuditRecord] = None
    counts: Dict[str, int] = Field(default_factory=dict)
    items: List[PostCutoverMonitorItem] = Field(default_factory=list)


class PostCutoverCloseoutReport(BaseModel):
    generated_at: str
    title: str
    filename: str
    monitor: PostCutoverOrderMonitor
    operator_decisions: List[OperatorDecisionRecord] = Field(default_factory=list)
    markdown: str


class StrategyHealthMilestone(BaseModel):
    id: str
    label: str
    status: Literal["pass", "warn", "fail"]
    message: str
    evidence_id: Optional[str] = None


class StrategyHealthTrace(BaseModel):
    id: str
    status: Literal["healthy", "watch", "attention", "blocked"]
    market: str
    side: Literal["bid", "ask"]
    scenario_id: Optional[str] = None
    scenario_name: Optional[str] = None
    watchlist_id: Optional[str] = None
    source_session_id: Optional[str] = None
    source_trade_timestamp: Optional[str] = None
    simulated_notional: Optional[float] = None
    promotion_rules: Dict[str, Any] = Field(default_factory=dict)
    dry_run_audit: OrderAuditRecord
    approval_decisions: List[OperatorDecisionRecord] = Field(default_factory=list)
    approval_attempts: List[OrderAuditRecord] = Field(default_factory=list)
    latest_approval_attempt: Optional[OrderAuditRecord] = None
    closeout_status: Optional[str] = None
    milestones: List[StrategyHealthMilestone] = Field(default_factory=list)


class StrategyHealthTraceResponse(BaseModel):
    checked_at: str
    traces: List[StrategyHealthTrace] = Field(default_factory=list)
    counts: Dict[str, int] = Field(default_factory=dict)


class StrategyHealthHandoffReport(BaseModel):
    generated_at: str
    title: str
    filename: str
    traces: StrategyHealthTraceResponse
    closeout_report: PostCutoverCloseoutReport
    markdown: str


class CryptoLiveBetaDrillReport(BaseModel):
    generated_at: str
    title: str
    filename: str
    symbol: str
    paper_sessions: List[PaperTradingSession] = Field(default_factory=list)
    dry_run_audits: List[OrderAuditRecord] = Field(default_factory=list)
    prechecks: Dict[str, OrderPrecheckResult] = Field(default_factory=dict)
    runbooks: List[ExecutionRunbook] = Field(default_factory=list)
    readiness: LiveReadinessResponse
    cutover_simulation: LiveArmingSimulationResponse
    closeout_report: PostCutoverCloseoutReport
    strategy_health: StrategyHealthTraceResponse
    markdown: str


class OperatorDecisionReport(BaseModel):
    generated_at: str
    title: str
    filename: str
    decisions: List[OperatorDecisionRecord] = Field(default_factory=list)
    markdown: str


class MarketDefaults(BaseModel):
    symbols: List[str]
    timeframes: List[str]
    strategies: List[str]
    default_request: BacktestRequest


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str
    note: Optional[str] = None


class OpsRunbookLink(BaseModel):
    id: str
    title: str
    path: str
    api_path: str
    description: str


class OpsSchedulerStatus(BaseModel):
    enabled: bool
    thread_alive: bool
    poll_seconds: int
    stop_requested: bool


class OpsLiveLockStatus(BaseModel):
    live_trading_enabled: bool
    live_ack_configured: bool
    credential_configured: bool
    adapter_ready: bool
    live_locked: bool
    reason: str


class OpsSelfCheckResponse(BaseModel):
    checked_at: str
    service: str
    version: str
    status: Literal["ok"]
    database_path: str
    duckdb_path: str
    parquet_path: str
    columnar_cache_enabled: bool
    artifact_paths: Dict[str, str]
    scheduler: OpsSchedulerStatus
    live_lock: OpsLiveLockStatus
    runbooks: List[OpsRunbookLink] = Field(default_factory=list)
