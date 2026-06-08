import React from 'react';
import ReactDOM from 'react-dom/client';
import { createAvatar } from '@dicebear/core';
import { bottts, identicon, pixelArt, pixelArtNeutral } from '@dicebear/collection';
import {
  Activity,
  AlertTriangle,
  Database,
  Download,
  FileText,
  History,
  KeyRound,
  Moon,
  Pause,
  Play,
  Plus,
  Radio,
  RefreshCcw,
  Save,
  Settings,
  ShieldCheck,
  Sun,
  Trash2,
  TrendingUp,
  X,
} from 'lucide-react';
import './styles.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
const THEME_STORAGE_KEY = 'quant-lab-theme';

type Strategy = 'sma_crossover' | 'donchian_breakout' | 'rsi_mean_reversion';
type Source = 'sample' | 'sample_us' | 'alpha_vantage' | 'upbit';
type DisplayCurrency = 'KRW' | 'USD';
type ThemeMode = 'light' | 'dark';
type PortfolioRebalanceFrequency = 'none' | 'monthly';
type HistorySortKey = 'recent' | 'edge' | 'return' | 'sharpe' | 'drawdown';
type HistorySourceFilter = Source | 'all';
type HistoryStrategyFilter = Strategy | 'all';
type ChecklistState = 'ready' | 'warn' | 'missing';
type AlertSeverityFilter = 'all' | 'info' | 'warning' | 'halt' | 'error';
type OperatorDecisionStatus = 'approved' | 'rejected' | 'needs_work' | 'noted';
type OperatorDecisionType =
  | 'readiness_review'
  | 'dry_run_promotion'
  | 'dry_run_approval'
  | 'alert_review'
  | 'live_cutover';
type OperatorDecisionTypeFilter = OperatorDecisionType | 'all';
type OperatorDecisionStatusFilter = OperatorDecisionStatus | 'all';
type OperatorRouteStatusFilter = 'all' | 'paper_only_review' | 'dry_run_ready' | 'unsupported';
type AlertSourceFilter =
  | 'all'
  | 'portfolio_scan'
  | 'portfolio_scan_error'
  | 'paper_watchlist_error'
  | 'paper_session_risk'
  | 'paper_session_halt'
  | 'broker_paper_submission'
  | 'broker_reconciliation'
  | 'paper_fill_drift';

type AlertReviewFilters = {
  severity: AlertSeverityFilter;
  source: AlertSourceFilter;
  scenario: string;
};

type OperatorJournalFilters = {
  decisionType: OperatorDecisionTypeFilter;
  status: OperatorDecisionStatusFilter;
  routeStatus: OperatorRouteStatusFilter;
  targetId: string;
};

type BacktestRequest = {
  symbol: string;
  timeframe: string;
  source: Source;
  strategy: Strategy;
  initial_cash: number;
  fee_bps: number;
  slippage_bps: number;
  candle_limit: number;
  params: Record<string, number>;
};

type BacktestMetrics = {
  initial_equity: number;
  final_equity: number;
  total_return_pct: number;
  buy_and_hold_final_equity?: number;
  buy_and_hold_return_pct?: number;
  buy_and_hold_max_drawdown_pct?: number;
  strategy_edge_pct?: number;
  cagr_pct: number;
  max_drawdown_pct: number;
  sharpe: number;
  sortino: number;
  exposure_pct: number;
  trades: number;
};

type EquityPoint = {
  timestamp: string;
  equity: number;
  cash: number;
  asset_quantity: number;
  close: number;
  target_exposure: number;
  drawdown_pct: number;
};

type Trade = {
  timestamp: string;
  side: 'buy' | 'sell';
  price: number;
  quantity: number;
  notional: number;
  fee: number;
  cash_after: number;
  equity_after: number;
};

type Candle = {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

type BacktestResponse = {
  id?: string;
  created_at?: string;
  request: BacktestRequest;
  metrics: BacktestMetrics;
  equity_curve: EquityPoint[];
  trades: Trade[];
  candles?: Candle[];
  warnings: string[];
};

type BacktestRunSummary = {
  id: string;
  created_at: string;
  request: BacktestRequest;
  metrics: BacktestMetrics;
  warnings: string[];
};

type BacktestSweepCandidate = {
  rank: number;
  score: number;
  params: Record<string, number>;
  metrics: BacktestMetrics;
  trades: number;
  warnings: string[];
};

type BacktestSweepResponse = {
  generated_at: string;
  request: BacktestRequest & { candidates: Record<string, number>[] };
  candidates: BacktestSweepCandidate[];
  best?: BacktestSweepCandidate | null;
  warnings: string[];
};

type BacktestValidationSegment = {
  label: 'train' | 'test';
  candle_count: number;
  start_timestamp: string;
  end_timestamp: string;
  metrics: BacktestMetrics;
  trades: number;
};

type BacktestValidationResponse = {
  generated_at: string;
  request: BacktestRequest & { train_fraction: number };
  total_candles: number;
  train: BacktestValidationSegment;
  test: BacktestValidationSegment;
  edge_gap_pct: number;
  return_gap_pct: number;
  robustness_score: number;
  verdict: 'pass' | 'watch' | 'fail';
  reason: string;
  warnings: string[];
};

type BacktestWalkForwardFold = {
  index: number;
  train: BacktestValidationSegment;
  test: BacktestValidationSegment;
  edge_gap_pct: number;
  return_gap_pct: number;
  robustness_score: number;
  verdict: 'pass' | 'watch' | 'fail';
  reason: string;
};

type BacktestWalkForwardResponse = {
  generated_at: string;
  request: BacktestRequest & {
    train_window: number;
    test_window: number;
    step_size: number;
  };
  total_candles: number;
  folds: BacktestWalkForwardFold[];
  pass_count: number;
  watch_count: number;
  fail_count: number;
  average_test_return_pct: number;
  average_test_edge_pct: number;
  average_robustness_score: number;
  verdict: 'pass' | 'watch' | 'fail';
  reason: string;
  warnings: string[];
};

type PortfolioResearchRequest = {
  symbols: string[];
  timeframe: string;
  source: Source;
  strategy: Strategy;
  initial_cash: number;
  fee_bps: number;
  slippage_bps: number;
  candle_limit: number;
  weights: Record<string, number>;
  rebalance_frequency: PortfolioRebalanceFrequency;
  params: Record<string, number>;
};

type PortfolioAllocationResult = {
  symbol: string;
  target_weight_pct: number;
  final_weight_pct: number;
  initial_cash: number;
  final_equity: number;
  total_return_pct: number;
  strategy_edge_pct: number;
  max_drawdown_pct: number;
  sharpe: number;
  trades: number;
};

type PortfolioEquityPoint = {
  timestamp: string;
  equity: number;
  drawdown_pct: number;
};

type PortfolioResearchMetrics = {
  initial_equity: number;
  final_equity: number;
  total_return_pct: number;
  max_drawdown_pct: number;
  average_return_pct: number;
  rebalances: number;
  best_symbol: string;
  best_return_pct: number;
  worst_symbol: string;
  worst_return_pct: number;
  trades: number;
};

type PortfolioResearchResponse = {
  request: PortfolioResearchRequest;
  metrics: PortfolioResearchMetrics;
  allocations: PortfolioAllocationResult[];
  equity_curve: PortfolioEquityPoint[];
  warnings: string[];
};

type PortfolioResearchPreset = {
  id: string;
  name: string;
  description: string;
  request: PortfolioResearchRequest;
};

type PortfolioResearchScenario = {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  request: PortfolioResearchRequest;
};

type PortfolioResearchScan = {
  id: string;
  scenario_id: string;
  scenario_name: string;
  created_at: string;
  result: PortfolioResearchResponse;
};

type PortfolioResearchWatchlistItem = {
  id: string;
  scenario_id: string;
  scenario_name: string;
  created_at: string;
  updated_at: string;
  interval_minutes: number;
  active: boolean;
  next_run_at: string;
  alert_thresholds: PortfolioResearchAlertThresholds;
  last_run_at?: string | null;
  last_scan_id?: string | null;
  last_alerts: PortfolioResearchAlert[];
  last_error?: string | null;
};

type PortfolioResearchAlertThresholds = {
  max_drawdown_pct?: number | null;
  min_total_return_pct?: number | null;
  min_average_edge_pct?: number | null;
  max_return_drift_pct?: number | null;
};

type PortfolioResearchAlert = {
  rule: 'max_drawdown_pct' | 'min_total_return_pct' | 'min_average_edge_pct' | 'max_return_drift_pct';
  level: 'warning';
  message: string;
  value: number;
  threshold: number;
};

type PortfolioResearchSchedulerRun = {
  checked_at: string;
  due: number;
  scanned: PortfolioResearchScan[];
  alerts: PortfolioResearchAlert[];
  errors: string[];
};

type PortfolioPaperWatchlistItem = {
  id: string;
  scenario_id: string;
  scenario_name: string;
  created_at: string;
  updated_at: string;
  interval_minutes: number;
  active: boolean;
  next_run_at: string;
  risk_limits: RiskLimits;
  last_run_at?: string | null;
  last_session_ids: string[];
  last_error?: string | null;
};

type PortfolioPaperWatchlistRun = {
  checked_at: string;
  item: PortfolioPaperWatchlistItem;
  sessions: PaperTradingSession[];
  errors: string[];
};

type PortfolioPaperSchedulerRun = {
  checked_at: string;
  due: number;
  runs: PortfolioPaperWatchlistRun[];
  errors: string[];
};

type PaperToLiveAdapterProfile = {
  id:
    | 'upbit_crypto_spot'
    | 'us_equity_paper'
    | 'alpaca_us_equity_paper_preview'
    | 'alpaca_us_equity_paper';
  label: string;
  broker: string;
  asset_class: 'crypto_spot' | 'stock_etf';
  execution_mode: 'guarded_live' | 'paper_only';
  live_order_supported: boolean;
  dry_run_audit_supported: boolean;
  supported_sources: string[];
  symbol_hint: string;
  broker_contract: {
    id: string;
    label: string;
    provider_type: 'exchange' | 'paper_broker';
    submission_mode: 'guarded_live' | 'paper_record_only' | 'external_paper';
    live_order_supported: boolean;
    dry_run_supported: boolean;
    account_snapshot_supported: boolean;
    required_credentials: string[];
    supported_order_types: string[];
    notes: string[];
  };
  reason: string;
};

type BrokerReadinessCheck = {
  id: string;
  label: string;
  status: 'pass' | 'warn' | 'fail';
  message: string;
};

type BrokerReadinessItem = {
  adapter_id: string;
  label: string;
  broker: string;
  asset_class: 'crypto_spot' | 'stock_etf';
  status: 'ready' | 'watch' | 'blocked';
  live_submission_state: 'guarded_live' | 'paper_record_only' | 'external_paper' | 'blocked';
  broker_contract: PaperToLiveAdapterProfile['broker_contract'];
  credential_boundary: string;
  checks: BrokerReadinessCheck[];
  message: string;
};

type BrokerReadinessResponse = {
  checked_at: string;
  items: BrokerReadinessItem[];
};

type BrokerIntentSide = 'buy' | 'sell';
type BrokerIntentOrderType = 'market' | 'limit';
type BrokerIntentAdapterId =
  | 'us_equity_paper'
  | 'alpaca_us_equity_paper_preview'
  | 'alpaca_us_equity_paper';

type BrokerPaperFillEstimate = {
  status: 'estimated_fill' | 'not_fillable' | 'cash_shortfall' | 'position_shortfall';
  reason: string;
  reference_price: number;
  fill_price?: number | null;
  quantity: number;
  estimated_notional?: number | null;
  estimated_fee?: number | null;
  cash_after?: number | null;
  position_after?: number | null;
  exposure_pct_after?: number | null;
  cash_sufficient?: boolean | null;
  position_sufficient?: boolean | null;
  fillable: boolean;
  fee_bps: number;
  slippage_bps: number;
};

type BrokerIntentEvaluation = {
  id: string;
  checked_at: string;
  adapter_id: BrokerIntentAdapterId;
  broker_contract: PaperToLiveAdapterProfile['broker_contract'];
  request: {
    adapter_id: BrokerIntentAdapterId;
    symbol: string;
    side: BrokerIntentSide;
    quantity: number;
    order_type: BrokerIntentOrderType;
    limit_price?: number | null;
    time_in_force: 'day' | 'gtc' | 'ioc' | 'fok';
    client_order_id?: string | null;
    live_confirmation: boolean;
    paper_submit_confirmation: boolean;
    reference_price?: number | null;
    cash_available?: number | null;
    current_position_quantity: number;
    portfolio_equity?: number | null;
    paper_fee_bps: number;
    paper_slippage_bps: number;
    paper_session_id?: string | null;
  };
  validation_status: 'accepted' | 'rejected';
  submission_status: 'paper_recorded' | 'blocked' | 'rejected';
  reason: string;
  normalized_symbol?: string | null;
  estimated_notional?: number | null;
  broker_order_id?: string | null;
  external_submission_attempted: boolean;
  live_submission_supported: boolean;
  paper_fill_estimate?: BrokerPaperFillEstimate | null;
};

type BrokerOrderReconciliation = {
  id: string;
  checked_at: string;
  evaluation_id: string;
  adapter_id: BrokerIntentAdapterId;
  local_submission_status: 'paper_recorded' | 'blocked' | 'rejected';
  status: 'matched' | 'mismatch' | 'blocked' | 'not_found' | 'unsupported' | 'error';
  reason: string;
  broker_order_id?: string | null;
  client_order_id?: string | null;
  broker_status?: string | null;
  broker_symbol?: string | null;
  broker_side?: string | null;
  broker_quantity?: number | null;
  broker_filled_quantity?: number | null;
  broker_avg_fill_price?: number | null;
  broker_filled_notional?: number | null;
  broker_fee?: number | null;
  broker_partial_fill?: boolean | null;
  broker_fill_activity_count: number;
  broker_submitted_at?: string | null;
  broker_filled_at?: string | null;
  broker_position_quantity?: number | null;
  broker_position_market_value?: number | null;
  broker_position_cost_basis?: number | null;
  broker_position_unrealized_pl?: number | null;
  broker_position_snapshot: Record<string, unknown>;
  broker_account_cash?: number | null;
  broker_account_equity?: number | null;
  broker_account_buying_power?: number | null;
  broker_account_snapshot: Record<string, unknown>;
  broker_fill_activities: Record<string, unknown>[];
  linked_paper_fill_note_id?: string | null;
  paper_fill_comparison_status?:
    | 'matched'
    | 'drift'
    | 'partial_fill'
    | 'missing_broker_fill'
    | null;
  paper_fill_price_delta?: number | null;
  paper_fill_price_delta_pct?: number | null;
  paper_fill_notional_delta?: number | null;
  paper_fill_fee_delta?: number | null;
  external_lookup_attempted: boolean;
  broker_payload: Record<string, unknown>;
};

type PaperFillOrderNote = {
  id: string;
  created_at: string;
  session_id: string;
  evaluation_id: string;
  adapter_id: BrokerIntentAdapterId;
  symbol: string;
  side: 'buy' | 'sell';
  quantity: number;
  order_type: BrokerIntentOrderType;
  paper_fill_status: 'estimated_fill';
  intended_fill_price: number;
  intended_notional: number;
  intended_fee: number;
  simulated_trade_timestamp?: string | null;
  simulated_fill_price?: number | null;
  simulated_quantity?: number | null;
  simulated_notional?: number | null;
  price_delta?: number | null;
  price_delta_pct?: number | null;
  quantity_delta?: number | null;
  notional_delta?: number | null;
  comparison_status: 'matched_trade' | 'no_trade_match';
  external_submission_attempted: boolean;
  note: string;
};

type PaperFillOrderNoteDriftRow = {
  adapter_id: BrokerIntentAdapterId;
  symbol: string;
  note_count: number;
  matched_trade_count: number;
  no_trade_match_count: number;
  external_submission_attempted_count: number;
  avg_price_delta_pct?: number | null;
  avg_abs_price_delta_pct?: number | null;
  worst_abs_price_delta_pct?: number | null;
  latest_price_delta_pct?: number | null;
  latest_created_at: string;
  latest_session_id: string;
  latest_evaluation_id: string;
  latest_comparison_status: 'matched_trade' | 'no_trade_match';
  latest_note: string;
};

type PaperFillOrderNoteAnalytics = {
  generated_at: string;
  limit: number;
  adapter_id?: BrokerIntentAdapterId | null;
  symbol?: string | null;
  notes_considered: number;
  matched_trade_count: number;
  external_submission_attempted_count: number;
  rows: PaperFillOrderNoteDriftRow[];
};

type PaperFillQualityGateStatus = 'ready' | 'watch' | 'blocked';

type PaperFillOrderNoteQualityGateRow = {
  adapter_id: BrokerIntentAdapterId;
  symbol: string;
  status: PaperFillQualityGateStatus;
  reasons: string[];
  note_count: number;
  matched_trade_count: number;
  no_trade_match_count: number;
  external_submission_attempted_count: number;
  avg_abs_price_delta_pct?: number | null;
  worst_abs_price_delta_pct?: number | null;
  latest_created_at: string;
  latest_session_id: string;
  latest_evaluation_id: string;
};

type PaperFillOrderNoteQualityGate = {
  generated_at: string;
  status: PaperFillQualityGateStatus;
  reason: string;
  limit: number;
  min_notes: number;
  max_avg_abs_price_delta_pct: number;
  max_worst_abs_price_delta_pct: number;
  require_no_external_submission: boolean;
  adapter_id?: BrokerIntentAdapterId | null;
  symbol?: string | null;
  analytics: PaperFillOrderNoteAnalytics;
  rows: PaperFillOrderNoteQualityGateRow[];
};

type StockEtfBrokerExpansionCandidate = {
  decision_id: string;
  target_id?: string | null;
  created_at: string;
  decision_status: OperatorDecisionStatus;
  symbol: string;
  session_id?: string | null;
  scenario_name?: string | null;
  source?: string | null;
  adapter_id?: string | null;
  adapter_label?: string | null;
  quality_gate_status: PaperFillQualityGateStatus;
  quality_gate_reason: string;
  quality_gate_checked_at?: string | null;
  note_count: number;
  matched_trade_count: number;
  avg_abs_price_delta_pct?: number | null;
  worst_abs_price_delta_pct?: number | null;
  approved_for_broker_expansion: boolean;
  message: string;
};

type StockEtfBrokerExpansionReadiness = {
  generated_at: string;
  status: 'ready' | 'watch' | 'blocked';
  reason: string;
  counts: Record<string, number>;
  candidates: StockEtfBrokerExpansionCandidate[];
};

type StockEtfBrokerExpansionReport = {
  generated_at: string;
  title: string;
  filename: string;
  readiness: StockEtfBrokerExpansionReadiness;
  markdown: string;
};

type StockEtfBrokerExpansionOrderPayload = {
  adapter_id: BrokerIntentAdapterId;
  symbol: string;
  side: 'buy' | 'sell';
  quantity: number;
  order_type: BrokerIntentOrderType;
  time_in_force: string;
  expected_fill_price: number;
  estimated_notional: number;
  evaluation_id: string;
  paper_session_id: string;
  external_submission_attempted: boolean;
  payload: Record<string, unknown>;
};

type StockEtfBrokerExpansionPackage = {
  generated_at: string;
  title: string;
  filename: string;
  candidate: StockEtfBrokerExpansionCandidate;
  quality_gate: PaperFillOrderNoteQualityGate;
  broker_evaluations: BrokerIntentEvaluation[];
  order_notes: PaperFillOrderNote[];
  order_payloads: StockEtfBrokerExpansionOrderPayload[];
  markdown: string;
};

type StockEtfBrokerExpansionPreflightCheck = {
  id: string;
  label: string;
  status: 'pass' | 'warn' | 'fail';
  message: string;
  evidence_id?: string | null;
};

type StockEtfBrokerExpansionPreflight = {
  generated_at: string;
  title: string;
  filename: string;
  status: 'pass' | 'warn' | 'fail';
  reason: string;
  package: StockEtfBrokerExpansionPackage;
  checks: StockEtfBrokerExpansionPreflightCheck[];
  markdown: string;
};

type StockEtfBrokerExpansionRehearsalOrder = {
  id: string;
  evaluation_id: string;
  adapter_id: BrokerIntentAdapterId;
  symbol: string;
  side: 'buy' | 'sell';
  quantity: number;
  order_type: BrokerIntentOrderType;
  status: 'accepted' | 'rejected';
  reason: string;
  expected_fill_price: number;
  estimated_notional: number;
  paper_session_id: string;
  external_submission_attempted: boolean;
  payload: Record<string, unknown>;
};

type StockEtfBrokerExpansionRehearsal = {
  generated_at: string;
  title: string;
  filename: string;
  status: 'pass' | 'warn' | 'fail';
  reason: string;
  preflight: StockEtfBrokerExpansionPreflight;
  accepted_orders: number;
  rejected_orders: number;
  orders: StockEtfBrokerExpansionRehearsalOrder[];
  markdown: string;
};

type BrokerIntentEvaluationReport = {
  generated_at: string;
  title: string;
  filename: string;
  evaluations: BrokerIntentEvaluation[];
  summary: Record<string, number>;
  markdown: string;
};

type PaperToLiveRoute = {
  session_id: string;
  symbol: string;
  source: Source;
  adapter: PaperToLiveAdapterProfile;
  status: 'dry_run_ready' | 'paper_only_review' | 'unsupported';
  eligible_for_order_audit: boolean;
  message: string;
};

type PaperToLiveHandoff = {
  id: string;
  created_at: string;
  session_id: string;
  symbol: string;
  source: Source;
  scenario_id?: string | null;
  scenario_name?: string | null;
  watchlist_id?: string | null;
  route: PaperToLiveRoute;
  decision_id?: string | null;
  already_logged: boolean;
  message: string;
};

type PortfolioPaperPromotionResponse = {
  checked_at: string;
  item: PortfolioPaperWatchlistItem;
  eligible_sessions: PaperTradingSession[];
  queued: StrategyOrderQueueResponse[];
  paper_only_handoffs: PaperToLiveHandoff[];
  created: number;
  skipped_existing: number;
  skipped_sessions: string[];
  errors: string[];
};

type AlertReviewItem = {
  id: string;
  source:
    | 'portfolio_scan'
    | 'portfolio_scan_error'
    | 'paper_watchlist_error'
    | 'paper_session_risk'
    | 'paper_session_halt'
    | 'broker_paper_submission'
    | 'broker_reconciliation'
    | 'paper_fill_drift';
  level: 'info' | 'warning' | 'halt' | 'error';
  title: string;
  message: string;
  created_at: string;
  scenario_id?: string | null;
  scenario_name?: string | null;
  watchlist_id?: string | null;
  scan_id?: string | null;
  session_id?: string | null;
  evaluation_id?: string | null;
  reconciliation_id?: string | null;
  adapter_id?: string | null;
  symbol?: string | null;
  rule?: string | null;
  value?: number | null;
  threshold?: number | null;
  acknowledgement_status?: 'acknowledged' | 'dismissed' | null;
  acknowledged_at?: string | null;
  acknowledgement_note?: string | null;
};

type AlertReviewResponse = {
  checked_at: string;
  items: AlertReviewItem[];
  counts: Record<string, number>;
};

type AlertReviewAcknowledgement = {
  alert_id: string;
  status: 'acknowledged' | 'dismissed';
  acknowledged_at: string;
  note?: string | null;
};

type LiveReadinessCheck = {
  id: string;
  label: string;
  category: 'system' | 'operator';
  status: 'pass' | 'warn' | 'fail';
  message: string;
  weight: number;
  score: number;
};

type LiveReadinessBreakdown = {
  id: 'system' | 'operator';
  label: string;
  status: 'ready' | 'watch' | 'blocked';
  score: number;
  checks: LiveReadinessCheck[];
  blocking_checks: string[];
  warning_checks: string[];
  message: string;
};

type LiveReadinessResponse = {
  checked_at: string;
  status: 'ready' | 'watch' | 'blocked';
  score: number;
  checks: LiveReadinessCheck[];
  breakdowns: LiveReadinessBreakdown[];
};

type LiveCutoverChecklistItem = {
  id: string;
  label: string;
  status: 'pass' | 'warn' | 'fail';
  message: string;
  evidence_id?: string | null;
};

type LiveCutoverChecklistResponse = {
  checked_at: string;
  status: 'ready' | 'watch' | 'blocked';
  items: LiveCutoverChecklistItem[];
  readiness: LiveReadinessResponse;
  latest_operator_decisions: OperatorDecisionRecord[];
};

type OperatorDecisionRecord = {
  id: string;
  created_at: string;
  decision_type: OperatorDecisionType;
  target_id?: string | null;
  status: OperatorDecisionStatus;
  note?: string | null;
  context: Record<string, unknown>;
};

type OperatorDecisionReport = {
  generated_at: string;
  title: string;
  filename: string;
  decisions: OperatorDecisionRecord[];
  markdown: string;
};

type MarketTicker = {
  symbol: string;
  source: Source;
  timestamp: string;
  price: number;
  change_pct: number;
  volume_24h?: number | null;
  quote_volume_24h?: number | null;
};

type MarketDataProviderStatus = {
  source: Source;
  label: string;
  status_checked_at: string;
  configured: boolean;
  available: boolean;
  credential_name?: string | null;
  base_url?: string | null;
  cache_ttl_seconds?: number | null;
  last_success_at?: string | null;
  last_error_at?: string | null;
  last_error?: string | null;
  last_symbol?: string | null;
  last_timeframe?: string | null;
  last_rows?: number | null;
  note: string;
};

type MarketDataColumnarStatus = {
  enabled: boolean;
  checked_at: string;
  duckdb_path: string;
  parquet_path: string;
  rows: number;
  sources: string[];
  symbols: string[];
  timeframes: string[];
  last_fetched_at?: string | null;
  last_exported_at?: string | null;
  last_error?: string | null;
};

type MarketDataColumnarExport = {
  exported_at: string;
  duckdb_path: string;
  parquet_path: string;
  rows: number;
  source?: string | null;
  symbol?: string | null;
  timeframe?: string | null;
};

type ExecutionStatus = {
  exchange: 'upbit';
  checked_at: string;
  live_trading_enabled: boolean;
  adapter_ready: boolean;
  base_url: string;
  reason: string;
};

type ExecutionSettings = {
  exchange: 'upbit';
  checked_at: string;
  base_url: string;
  live_trading_enabled: boolean;
  live_ack_configured: boolean;
  live_ack_required_value: string;
  live_confirmation_required: boolean;
  credential_configured: boolean;
  private_reads_enabled: boolean;
  adapter_ready: boolean;
  order_info_source: 'local_defaults' | 'upbit_orders_chance';
  min_order_notional_krw: number;
  approval_fee_bps: number;
  approval_fee_rate: number;
  max_approval_exposure_pct: number;
  reason: string;
};

type OpsRunbookLink = {
  id: string;
  title: string;
  path: string;
  api_path: string;
  description: string;
};

type OpsSelfCheckResponse = {
  checked_at: string;
  service: string;
  version: string;
  status: 'ok';
  database_path: string;
  duckdb_path: string;
  parquet_path: string;
  columnar_cache_enabled: boolean;
  artifact_paths: Record<string, string>;
  scheduler: {
    enabled: boolean;
    thread_alive: boolean;
    poll_seconds: number;
    stop_requested: boolean;
  };
  live_lock: {
    live_trading_enabled: boolean;
    live_ack_configured: boolean;
    credential_configured: boolean;
    adapter_ready: boolean;
    live_locked: boolean;
    reason: string;
  };
  runbooks: OpsRunbookLink[];
};

type OrderAuditRecord = {
  id: string;
  created_at: string;
  exchange: 'upbit';
  market: string;
  side: 'bid' | 'ask';
  ord_type: 'limit' | 'price' | 'market' | 'best';
  status: 'blocked' | 'submitted' | 'failed' | 'dry_run';
  reason: string;
  request_payload: Record<string, unknown>;
  response_payload?: Record<string, unknown> | null;
};

type PromotionContext = {
  source?: string;
  checked_at?: string;
  watchlist_id?: string;
  scenario_id?: string;
  scenario_name?: string;
  promotion_rules?: {
    min_total_return_pct?: number;
    max_drawdown_pct?: number;
    min_orders?: number;
  };
  max_sessions?: number;
  max_intents_per_session?: number;
};

type StrategyOrderQueueResponse = {
  session_id: string;
  source: 'paper_session' | 'live_paper_session';
  created: number;
  skipped_existing: number;
  records: OrderAuditRecord[];
};

type OrderPrecheckItem = {
  name: string;
  status: 'pass' | 'warn' | 'fail';
  message: string;
  value?: number | null;
  threshold?: number | null;
};

type OrderPrecheckResult = {
  record_id: string;
  market: string;
  side: 'bid' | 'ask';
  checked_at: string;
  status: 'pass' | 'warn' | 'fail';
  order_info_source: 'local_defaults' | 'upbit_orders_chance';
  order_info_checked_at: string;
  order_info_age_seconds: number;
  estimated_notional: number;
  min_order_notional: number;
  max_order_notional?: number | null;
  price_unit?: number | null;
  fee_rate: number;
  quote_currency: string;
  base_currency: string;
  credential_ready: boolean;
  available_quote_balance?: number | null;
  available_base_balance?: number | null;
  post_order_exposure_pct?: number | null;
  max_post_order_exposure_pct: number;
  checks: OrderPrecheckItem[];
};

type ExecutionRunbook = {
  generated_at: string;
  title: string;
  record_id: string;
  filename: string;
  audit: OrderAuditRecord;
  precheck: OrderPrecheckResult;
  markdown: string;
};

type LiveCutoverRunbook = {
  generated_at: string;
  title: string;
  filename: string;
  checklist: LiveCutoverChecklistResponse;
  settings: ExecutionSettings;
  markdown: string;
};

type LiveArmingSimulationRequest = {
  live_trading_enabled: boolean;
  live_ack_configured: boolean;
  credential_configured: boolean;
  assume_required_operator_decisions: boolean;
};

type LiveArmingSimulationChange = {
  id: string;
  label: string;
  current_status: 'pass' | 'warn' | 'fail';
  simulated_status: 'pass' | 'warn' | 'fail';
  current_message: string;
  simulated_message: string;
  changed: boolean;
};

type LiveArmingSimulationResponse = {
  generated_at: string;
  no_order_submission: boolean;
  assumptions: LiveArmingSimulationRequest;
  current: LiveCutoverChecklistResponse;
  simulated: LiveCutoverChecklistResponse;
  changes: LiveArmingSimulationChange[];
  current_blockers: LiveCutoverChecklistItem[];
  simulated_blockers: LiveCutoverChecklistItem[];
  summary: string;
};

type UpbitAccountBalance = {
  currency: string;
  balance: number;
  locked: number;
  avg_buy_price?: number | null;
  unit_currency?: string | null;
};

type UpbitOpenOrder = {
  uuid: string;
  market: string;
  side: string;
  ord_type: string;
  state: string;
  price?: number | null;
  volume?: number | null;
  remaining_volume?: number | null;
  created_at?: string | null;
  identifier?: string | null;
};

type UpbitPrivateSnapshot = {
  exchange: 'upbit';
  checked_at: string;
  credential_ready: boolean;
  base_url: string;
  reason: string;
  balances: UpbitAccountBalance[];
  open_orders: UpbitOpenOrder[];
};

type PostCutoverMonitorItem = {
  id: string;
  label: string;
  status: 'pass' | 'warn' | 'fail';
  message: string;
  evidence_id?: string | null;
};

type PostCutoverOrderMonitor = {
  checked_at: string;
  status: 'idle' | 'watch' | 'attention' | 'blocked';
  settings: ExecutionSettings;
  private_snapshot?: UpbitPrivateSnapshot | null;
  private_snapshot_error?: string | null;
  open_orders: UpbitOpenOrder[];
  recent_approval_attempts: OrderAuditRecord[];
  latest_audit?: OrderAuditRecord | null;
  counts: Record<string, number>;
  items: PostCutoverMonitorItem[];
};

type PostCutoverCloseoutReport = {
  generated_at: string;
  title: string;
  filename: string;
  monitor: PostCutoverOrderMonitor;
  operator_decisions: OperatorDecisionRecord[];
  markdown: string;
};

type StrategyHealthMilestone = {
  id: string;
  label: string;
  status: 'pass' | 'warn' | 'fail';
  message: string;
  evidence_id?: string | null;
};

type StrategyHealthTrace = {
  id: string;
  status: 'healthy' | 'watch' | 'attention' | 'blocked';
  market: string;
  side: 'bid' | 'ask';
  scenario_id?: string | null;
  scenario_name?: string | null;
  watchlist_id?: string | null;
  source_session_id?: string | null;
  source_trade_timestamp?: string | null;
  simulated_notional?: number | null;
  promotion_rules: Record<string, unknown>;
  dry_run_audit: OrderAuditRecord;
  approval_decisions: OperatorDecisionRecord[];
  approval_attempts: OrderAuditRecord[];
  latest_approval_attempt?: OrderAuditRecord | null;
  closeout_status?: string | null;
  milestones: StrategyHealthMilestone[];
};

type StrategyHealthTraceResponse = {
  checked_at: string;
  traces: StrategyHealthTrace[];
  counts: Record<string, number>;
};

type StrategyHealthHandoffReport = {
  generated_at: string;
  title: string;
  filename: string;
  traces: StrategyHealthTraceResponse;
  closeout_report: PostCutoverCloseoutReport;
  markdown: string;
};

type CryptoLiveBetaDrillReport = {
  generated_at: string;
  title: string;
  filename: string;
  symbol: string;
  paper_sessions: PaperTradingSession[];
  dry_run_audits: OrderAuditRecord[];
  prechecks: Record<string, OrderPrecheckResult>;
  runbooks: ExecutionRunbook[];
  readiness: LiveReadinessResponse;
  cutover_simulation: LiveArmingSimulationResponse;
  closeout_report: PostCutoverCloseoutReport;
  strategy_health: StrategyHealthTraceResponse;
  markdown: string;
};

type RiskLimits = {
  max_position_pct: number;
  max_order_notional: number;
  max_orders: number;
  max_session_loss_pct: number;
  kill_switch: boolean;
};

type RiskEvent = {
  timestamp: string;
  level: 'info' | 'warning' | 'halt';
  rule: string;
  message: string;
};

type PaperTradingSummary = {
  session_id: string;
  status: 'running' | 'completed' | 'halted';
  halted_reason?: string | null;
  initial_equity: number;
  final_equity: number;
  total_return_pct: number;
  max_drawdown_pct: number;
  cash: number;
  asset_quantity: number;
  open_position_pct: number;
  orders: number;
  risk_events: number;
};

type PaperTradingSession = {
  id: string;
  created_at: string;
  request: BacktestRequest & { risk_limits: RiskLimits };
  summary: PaperTradingSummary;
  equity_curve: EquityPoint[];
  trades: Trade[];
  risk_events: RiskEvent[];
  warnings: string[];
};

type LivePaperTradingSession = PaperTradingSession & {
  warmup_bars: number;
  next_index: number;
  total_candles: number;
  mode?: 'replay' | 'ticker';
};

type BotOperatingStyle =
  | 'trend_following'
  | 'mean_reversion'
  | 'breakout'
  | 'portfolio_rotation'
  | 'defensive_monitor'
  | 'custom';
type BotExecutionMode = 'paper' | 'dry_run';
type BotConflictPolicy = 'allow' | 'block_same_symbol';
type BotRunStatus = 'completed' | 'halted' | 'blocked' | 'error';
type BotAvatarStyle = 'pixel_art' | 'pixel_art_neutral' | 'bottts' | 'identicon';
type BotVisualStatus = BotRunStatus | 'idle' | 'paused' | 'running';
type BotDetailTab = 'overview' | 'backtest';
type BotFleetStatusFilter = 'all' | 'active' | 'paused' | 'running' | 'completed' | 'attention';
type BotFleetSortKey = 'priority' | 'return' | 'capital' | 'schedule' | 'name';

type BotAvatar = {
  seed: string;
  style: BotAvatarStyle;
  accent_color: string;
};

type BotProfile = {
  id: string;
  name: string;
  description: string;
  operating_style: BotOperatingStyle;
  request: BacktestRequest & { risk_limits: RiskLimits };
  execution_mode: BotExecutionMode;
  interval_minutes: number;
  active: boolean;
  priority: number;
  max_intents_per_run: number;
  conflict_policy: BotConflictPolicy;
  avatar: BotAvatar;
  created_at: string;
  updated_at: string;
  next_run_at: string;
  last_run_at?: string | null;
  last_run_id?: string | null;
  last_session_id?: string | null;
  last_status?: BotRunStatus | null;
  last_error?: string | null;
};

type BotProfileCreate = {
  name: string;
  description: string;
  operating_style: BotOperatingStyle;
  request: BacktestRequest & { risk_limits: RiskLimits };
  execution_mode: BotExecutionMode;
  interval_minutes: number;
  active: boolean;
  priority: number;
  max_intents_per_run: number;
  conflict_policy: BotConflictPolicy;
  avatar?: BotAvatar;
};

type BotPreset = BotProfileCreate & {
  id: string;
  persona: string;
  summary: string;
};

type BotRun = {
  id: string;
  bot_id: string;
  bot_name: string;
  checked_at: string;
  status: BotRunStatus;
  operating_style: BotOperatingStyle;
  execution_mode: BotExecutionMode;
  request: BacktestRequest & { risk_limits: RiskLimits };
  session?: PaperTradingSession | null;
  queued?: StrategyOrderQueueResponse | null;
  warnings: string[];
  errors: string[];
};

type BotFleetSummary = {
  total_bots: number;
  active_bots: number;
  due_bots: number;
  paper_bots: number;
  dry_run_bots: number;
  open_position_bots: number;
  active_errors: number;
  recent_dry_run_intents: number;
};

type BotFleetStatus = {
  checked_at: string;
  summary: BotFleetSummary;
  profiles: BotProfile[];
  recent_runs: BotRun[];
};

type BotFleetRun = {
  checked_at: string;
  due: number;
  runs: BotRun[];
  errors: string[];
};

const defaultRequest: BacktestRequest = {
  symbol: 'KRW-BTC',
  timeframe: 'day',
  source: 'sample',
  strategy: 'sma_crossover',
  initial_cash: 1_000_000,
  fee_bps: 5,
  slippage_bps: 2,
  candle_limit: 180,
  params: defaultParamsForStrategy('sma_crossover'),
};

const defaultRiskLimits: RiskLimits = {
  max_position_pct: 60,
  max_order_notional: 500_000,
  max_orders: 20,
  max_session_loss_pct: 12,
  kill_switch: false,
};

const botPresets: BotPreset[] = [
  {
    id: 'trend-watchdog',
    name: '추세 추종 감시자',
    persona: '강한 흐름을 따라가되 과열과 손실 제한을 함께 감시합니다.',
    summary: '코인 돌파 흐름을 드라이런 주문 intent까지 연결하는 기본 모멘텀 봇입니다.',
    description: 'KRW crypto 돌파 흐름을 추적하고 리스크 한도 안에서 dry-run intent를 남깁니다.',
    operating_style: 'breakout',
    execution_mode: 'dry_run',
    interval_minutes: 120,
    active: true,
    priority: 80,
    max_intents_per_run: 2,
    conflict_policy: 'allow',
    avatar: { seed: 'trend-watchdog-breakout-v1', style: 'bottts', accent_color: '#d59a25' },
    request: {
      symbol: 'KRW-BTC',
      timeframe: 'day',
      source: 'sample',
      strategy: 'donchian_breakout',
      initial_cash: 1_000_000,
      fee_bps: 5,
      slippage_bps: 2,
      candle_limit: 180,
      params: { lookback: 20, exit_lookback: 10 },
      risk_limits: { ...defaultRiskLimits, max_position_pct: 50 },
    },
  },
  {
    id: 'pullback-catcher',
    name: '되돌림 포착가',
    persona: '과매도 구간에서 반등 가능성을 기다리는 역추세형 운용자입니다.',
    summary: 'ETF/대형주 paper 세션에서 RSI 되돌림 신호를 조심스럽게 확인합니다.',
    description: 'US ETF mean reversion을 paper-only로 실행해 과매도 반등 후보를 관찰합니다.',
    operating_style: 'mean_reversion',
    execution_mode: 'paper',
    interval_minutes: 240,
    active: true,
    priority: 60,
    max_intents_per_run: 3,
    conflict_policy: 'allow',
    avatar: { seed: 'pullback-catcher-v1', style: 'pixel_art_neutral', accent_color: '#5d84be' },
    request: {
      symbol: 'SPY',
      timeframe: 'day',
      source: 'sample_us',
      strategy: 'rsi_mean_reversion',
      initial_cash: 100_000,
      fee_bps: 1,
      slippage_bps: 1,
      candle_limit: 180,
      params: { rsi_window: 14, buy_below: 35, sell_above: 58 },
      risk_limits: { ...defaultRiskLimits, max_position_pct: 40, max_order_notional: 25_000 },
    },
  },
  {
    id: 'core-crossover',
    name: '코어 크로스오버',
    persona: '복잡한 신호보다 기준선과 꾸준함을 선호하는 보수형 봇입니다.',
    summary: 'SMA 교차 신호로 BTC paper sleeve를 안정적으로 관찰합니다.',
    description: 'Baseline SMA crossover로 장기 기준선 이탈과 회복을 확인합니다.',
    operating_style: 'trend_following',
    execution_mode: 'paper',
    interval_minutes: 360,
    active: true,
    priority: 50,
    max_intents_per_run: 3,
    conflict_policy: 'allow',
    avatar: { seed: 'core-crossover-v1', style: 'pixel_art', accent_color: '#2f9b73' },
    request: {
      symbol: 'KRW-BTC',
      timeframe: 'day',
      source: 'sample',
      strategy: 'sma_crossover',
      initial_cash: 1_000_000,
      fee_bps: 5,
      slippage_bps: 2,
      candle_limit: 180,
      params: { fast_window: 10, slow_window: 30 },
      risk_limits: defaultRiskLimits,
    },
  },
  {
    id: 'volatility-breakout',
    name: '변동성 돌파 사냥꾼',
    persona: '짧은 기회만 선별하고 포지션 크기를 낮게 유지하는 공격형 실험 봇입니다.',
    summary: 'SOL처럼 변동성이 큰 자산에서 더 빠른 돌파/청산 구간을 테스트합니다.',
    description: '고변동 crypto 돌파 신호를 작은 주문 한도로 실험합니다.',
    operating_style: 'breakout',
    execution_mode: 'dry_run',
    interval_minutes: 90,
    active: true,
    priority: 70,
    max_intents_per_run: 2,
    conflict_policy: 'allow',
    avatar: { seed: 'volatility-breakout-v1', style: 'bottts', accent_color: '#d14d35' },
    request: {
      symbol: 'KRW-SOL',
      timeframe: 'day',
      source: 'sample',
      strategy: 'donchian_breakout',
      initial_cash: 1_000_000,
      fee_bps: 5,
      slippage_bps: 3,
      candle_limit: 180,
      params: { lookback: 14, exit_lookback: 7 },
      risk_limits: { ...defaultRiskLimits, max_position_pct: 35, max_order_notional: 300_000 },
    },
  },
  {
    id: 'margin-manager',
    name: '안전마진 관리자',
    persona: '수익보다 손실 제한, 낮은 노출, 운영 안정성을 먼저 보는 방어형 봇입니다.',
    summary: 'US ETF paper-only로 낮은 포지션 비중과 엄격한 손실 중단선을 적용합니다.',
    description: '낮은 노출의 SMA paper session으로 리스크 감시 중심 운영을 수행합니다.',
    operating_style: 'defensive_monitor',
    execution_mode: 'paper',
    interval_minutes: 480,
    active: true,
    priority: 45,
    max_intents_per_run: 1,
    conflict_policy: 'block_same_symbol',
    avatar: { seed: 'margin-manager-v1', style: 'identicon', accent_color: '#64748b' },
    request: {
      symbol: 'SPY',
      timeframe: 'day',
      source: 'sample_us',
      strategy: 'sma_crossover',
      initial_cash: 100_000,
      fee_bps: 1,
      slippage_bps: 1,
      candle_limit: 180,
      params: { fast_window: 20, slow_window: 60 },
      risk_limits: {
        ...defaultRiskLimits,
        max_position_pct: 25,
        max_order_notional: 15_000,
        max_orders: 10,
        max_session_loss_pct: 8,
      },
    },
  },
  {
    id: 'tenbagger-scout',
    name: '텐배거 탐색가',
    persona: '긴 호흡의 성장 후보를 찾되 아직은 paper로만 검증하는 성장형 봇입니다.',
    summary: 'QQQ/NVDA류 성장 자산의 추세 신호를 paper 환경에서 관찰합니다.',
    description: '성장형 US equity 후보를 paper-only 추세 전략으로 추적합니다.',
    operating_style: 'portfolio_rotation',
    execution_mode: 'paper',
    interval_minutes: 360,
    active: true,
    priority: 55,
    max_intents_per_run: 2,
    conflict_policy: 'allow',
    avatar: { seed: 'tenbagger-scout-v1', style: 'pixel_art', accent_color: '#6d76d9' },
    request: {
      symbol: 'NVDA',
      timeframe: 'day',
      source: 'sample_us',
      strategy: 'donchian_breakout',
      initial_cash: 100_000,
      fee_bps: 1,
      slippage_bps: 2,
      candle_limit: 180,
      params: { lookback: 30, exit_lookback: 15 },
      risk_limits: { ...defaultRiskLimits, max_position_pct: 45, max_order_notional: 20_000 },
    },
  },
  {
    id: 'big-short-watch',
    name: '빅쇼트 감시자',
    persona: '공매도를 실행하지 않고 과열, 하락 전환, 리스크 확대 신호만 감시합니다.',
    summary: '방어형 paper 봇으로 급락 리스크를 먼저 발견하는 운영 보조 역할입니다.',
    description: 'Short 주문 없이 paper session에서 하락 리스크와 손실 중단 기준을 감시합니다.',
    operating_style: 'defensive_monitor',
    execution_mode: 'paper',
    interval_minutes: 180,
    active: true,
    priority: 65,
    max_intents_per_run: 1,
    conflict_policy: 'block_same_symbol',
    avatar: { seed: 'big-short-watch-v1', style: 'identicon', accent_color: '#a73621' },
    request: {
      symbol: 'QQQ',
      timeframe: 'day',
      source: 'sample_us',
      strategy: 'rsi_mean_reversion',
      initial_cash: 100_000,
      fee_bps: 1,
      slippage_bps: 1,
      candle_limit: 180,
      params: { rsi_window: 14, buy_below: 30, sell_above: 62 },
      risk_limits: {
        ...defaultRiskLimits,
        max_position_pct: 20,
        max_order_notional: 10_000,
        max_orders: 8,
        max_session_loss_pct: 6,
      },
    },
  },
];

const defaultAlertThresholds: PortfolioResearchAlertThresholds = {
  max_drawdown_pct: 12,
  min_total_return_pct: 0,
  min_average_edge_pct: 0,
  max_return_drift_pct: 5,
};

const defaultAlertFilters: AlertReviewFilters = {
  severity: 'all',
  source: 'all',
  scenario: '',
};

const defaultOperatorJournalFilters: OperatorJournalFilters = {
  decisionType: 'all',
  status: 'all',
  routeStatus: 'all',
  targetId: '',
};

const sourceOptions: { value: Source; label: string }[] = [
  { value: 'sample', label: 'Sample crypto' },
  { value: 'upbit', label: 'Upbit public' },
  { value: 'sample_us', label: 'Sample US stocks/ETFs' },
  { value: 'alpha_vantage', label: 'Alpha Vantage daily' },
];

const symbolsBySource: Record<Source, string[]> = {
  sample: ['KRW-BTC', 'KRW-ETH', 'KRW-SOL'],
  upbit: ['KRW-BTC', 'KRW-ETH', 'KRW-SOL'],
  sample_us: ['SPY', 'QQQ', 'AAPL', 'MSFT', 'NVDA', 'TSLA'],
  alpha_vantage: ['SPY', 'QQQ', 'AAPL', 'MSFT', 'NVDA', 'TSLA'],
};

function botProfileFromPreset(preset: BotPreset): BotProfileCreate {
  return {
    name: preset.name,
    description: preset.description,
    operating_style: preset.operating_style,
    execution_mode: preset.execution_mode,
    interval_minutes: preset.interval_minutes,
    active: preset.active,
    priority: preset.priority,
    max_intents_per_run: preset.max_intents_per_run,
    conflict_policy: preset.conflict_policy,
    avatar: preset.avatar ? { ...preset.avatar } : undefined,
    request: {
      ...preset.request,
      params: { ...preset.request.params },
      risk_limits: { ...preset.request.risk_limits },
    },
  };
}

function backtestRequestFromBot(profile: BotProfile): BacktestRequest {
  return {
    symbol: profile.request.symbol,
    timeframe: profile.request.timeframe,
    source: profile.request.source,
    strategy: profile.request.strategy,
    initial_cash: profile.request.initial_cash,
    fee_bps: profile.request.fee_bps,
    slippage_bps: profile.request.slippage_bps,
    candle_limit: profile.request.candle_limit,
    params: { ...profile.request.params },
  };
}

function App() {
  const [theme, setTheme] = React.useState<ThemeMode>(() => initialThemeMode());
  const [request, setRequest] = React.useState<BacktestRequest>(defaultRequest);
  const [riskLimits, setRiskLimits] = React.useState<RiskLimits>(defaultRiskLimits);
  const [result, setResult] = React.useState<BacktestResponse | null>(null);
  const [sweepResult, setSweepResult] = React.useState<BacktestSweepResponse | null>(null);
  const [validationResult, setValidationResult] = React.useState<BacktestValidationResponse | null>(null);
  const [walkForwardResult, setWalkForwardResult] = React.useState<BacktestWalkForwardResponse | null>(null);
  const [backtestRuns, setBacktestRuns] = React.useState<BacktestRunSummary[]>([]);
  const [portfolioSymbols, setPortfolioSymbols] = React.useState<string[]>(
    symbolsBySource.sample.slice(0, 3),
  );
  const [portfolioWeights, setPortfolioWeights] = React.useState<Record<string, number>>(
    equalWeights(symbolsBySource.sample.slice(0, 3)),
  );
  const [portfolioRebalance, setPortfolioRebalance] =
    React.useState<PortfolioRebalanceFrequency>('none');
  const [portfolioResult, setPortfolioResult] = React.useState<PortfolioResearchResponse | null>(null);
  const [portfolioPresets, setPortfolioPresets] = React.useState<PortfolioResearchPreset[]>([]);
  const [portfolioScenarios, setPortfolioScenarios] = React.useState<PortfolioResearchScenario[]>([]);
  const [portfolioScans, setPortfolioScans] = React.useState<PortfolioResearchScan[]>([]);
  const [portfolioWatchlist, setPortfolioWatchlist] = React.useState<PortfolioResearchWatchlistItem[]>([]);
  const [portfolioPaperWatchlist, setPortfolioPaperWatchlist] = React.useState<PortfolioPaperWatchlistItem[]>([]);
  const [botFleet, setBotFleet] = React.useState<BotFleetStatus | null>(null);
  const [botFleetLastRun, setBotFleetLastRun] = React.useState<BotFleetRun | null>(null);
  const [portfolioScenarioName, setPortfolioScenarioName] = React.useState('Core ETF monthly');
  const [portfolioWatchInterval, setPortfolioWatchInterval] = React.useState(60);
  const [portfolioAlertThresholds, setPortfolioAlertThresholds] =
    React.useState<PortfolioResearchAlertThresholds>(defaultAlertThresholds);
  const [selectedCompareIds, setSelectedCompareIds] = React.useState<string[]>([]);
  const [comparisonDetails, setComparisonDetails] = React.useState<Record<string, BacktestResponse>>({});
  const [comparisonLoadingIds, setComparisonLoadingIds] = React.useState<string[]>([]);
  const [marketTicker, setMarketTicker] = React.useState<MarketTicker | null>(null);
  const [providerStatuses, setProviderStatuses] = React.useState<MarketDataProviderStatus[]>([]);
  const [columnarStatus, setColumnarStatus] = React.useState<MarketDataColumnarStatus | null>(null);
  const [columnarExport, setColumnarExport] = React.useState<MarketDataColumnarExport | null>(null);
  const [executionStatus, setExecutionStatus] = React.useState<ExecutionStatus | null>(null);
  const [executionSettings, setExecutionSettings] = React.useState<ExecutionSettings | null>(null);
  const [opsSelfCheck, setOpsSelfCheck] = React.useState<OpsSelfCheckResponse | null>(null);
  const [paperLiveAdapters, setPaperLiveAdapters] = React.useState<PaperToLiveAdapterProfile[]>([]);
  const [brokerReadiness, setBrokerReadiness] = React.useState<BrokerReadinessResponse | null>(null);
  const [brokerIntentAdapterId, setBrokerIntentAdapterId] =
    React.useState<BrokerIntentAdapterId>('us_equity_paper');
  const [brokerIntentSymbol, setBrokerIntentSymbol] = React.useState('SPY');
  const [brokerIntentSide, setBrokerIntentSide] = React.useState<BrokerIntentSide>('buy');
  const [brokerIntentQuantity, setBrokerIntentQuantity] = React.useState(1);
  const [brokerIntentOrderType, setBrokerIntentOrderType] =
    React.useState<BrokerIntentOrderType>('limit');
  const [brokerIntentLimitPrice, setBrokerIntentLimitPrice] = React.useState(500);
  const [brokerIntentReferencePrice, setBrokerIntentReferencePrice] = React.useState(499);
  const [brokerIntentCashAvailable, setBrokerIntentCashAvailable] = React.useState(10_000);
  const [brokerIntentCurrentPosition, setBrokerIntentCurrentPosition] = React.useState(0);
  const [brokerIntentPortfolioEquity, setBrokerIntentPortfolioEquity] = React.useState(10_000);
  const [brokerIntentFeeBps, setBrokerIntentFeeBps] = React.useState(1);
  const [brokerIntentSlippageBps, setBrokerIntentSlippageBps] = React.useState(1);
  const [brokerIntentLiveConfirmation, setBrokerIntentLiveConfirmation] = React.useState(false);
  const [brokerIntentPaperSubmitConfirmation, setBrokerIntentPaperSubmitConfirmation] =
    React.useState(false);
  const [brokerIntentEvaluation, setBrokerIntentEvaluation] =
    React.useState<BrokerIntentEvaluation | null>(null);
  const [brokerIntentReconciliation, setBrokerIntentReconciliation] =
    React.useState<BrokerOrderReconciliation | null>(null);
  const [brokerIntentHistory, setBrokerIntentHistory] = React.useState<BrokerIntentEvaluation[]>([]);
  const [paperFillDriftAnalytics, setPaperFillDriftAnalytics] =
    React.useState<PaperFillOrderNoteAnalytics | null>(null);
  const [paperFillQualityGate, setPaperFillQualityGate] =
    React.useState<PaperFillOrderNoteQualityGate | null>(null);
  const [privateSnapshot, setPrivateSnapshot] = React.useState<UpbitPrivateSnapshot | null>(null);
  const [orderAudits, setOrderAudits] = React.useState<OrderAuditRecord[]>([]);
  const [postCutoverMonitor, setPostCutoverMonitor] =
    React.useState<PostCutoverOrderMonitor | null>(null);
  const [strategyHealth, setStrategyHealth] = React.useState<StrategyHealthTraceResponse | null>(null);
  const [alertReview, setAlertReview] = React.useState<AlertReviewResponse | null>(null);
  const [liveReadiness, setLiveReadiness] = React.useState<LiveReadinessResponse | null>(null);
  const [cutoverChecklist, setCutoverChecklist] =
    React.useState<LiveCutoverChecklistResponse | null>(null);
  const [armingSimulation, setArmingSimulation] =
    React.useState<LiveArmingSimulationResponse | null>(null);
  const [operatorDecisions, setOperatorDecisions] = React.useState<OperatorDecisionRecord[]>([]);
  const [operatorJournal, setOperatorJournal] = React.useState<OperatorDecisionRecord[]>([]);
  const [stockPaperHandoffs, setStockPaperHandoffs] = React.useState<OperatorDecisionRecord[]>([]);
  const [stockBrokerExpansionReadiness, setStockBrokerExpansionReadiness] =
    React.useState<StockEtfBrokerExpansionReadiness | null>(null);
  const [alertFilters, setAlertFilters] = React.useState<AlertReviewFilters>(defaultAlertFilters);
  const [operatorJournalFilters, setOperatorJournalFilters] =
    React.useState<OperatorJournalFilters>(defaultOperatorJournalFilters);
  const [operatorDecisionStatus, setOperatorDecisionStatus] =
    React.useState<OperatorDecisionStatus>('noted');
  const [operatorDecisionNote, setOperatorDecisionNote] = React.useState('');
  const [cutoverDecisionStatus, setCutoverDecisionStatus] =
    React.useState<OperatorDecisionStatus>('needs_work');
  const [cutoverDecisionNote, setCutoverDecisionNote] = React.useState('');
  const [armingSimulationAssumeDecisions, setArmingSimulationAssumeDecisions] =
    React.useState(false);
  const [orderPrechecks, setOrderPrechecks] = React.useState<Record<string, OrderPrecheckResult>>({});
  const [executionRefreshing, setExecutionRefreshing] = React.useState(false);
  const [brokerIntentLoading, setBrokerIntentLoading] = React.useState(false);
  const [brokerIntentHistoryLoading, setBrokerIntentHistoryLoading] = React.useState(false);
  const [brokerIntentReportExporting, setBrokerIntentReportExporting] = React.useState(false);
  const [brokerIntentReconcilingId, setBrokerIntentReconcilingId] = React.useState<string | null>(null);
  const [paperFillDriftLoading, setPaperFillDriftLoading] = React.useState(false);
  const [readinessLoading, setReadinessLoading] = React.useState(false);
  const [cutoverLoading, setCutoverLoading] = React.useState(false);
  const [postCutoverMonitorLoading, setPostCutoverMonitorLoading] = React.useState(false);
  const [strategyHealthLoading, setStrategyHealthLoading] = React.useState(false);
  const [operatorDecisionLoading, setOperatorDecisionLoading] = React.useState(false);
  const [cutoverDecisionLoading, setCutoverDecisionLoading] = React.useState(false);
  const [armingSimulationLoading, setArmingSimulationLoading] = React.useState(false);
  const [operatorJournalLoading, setOperatorJournalLoading] = React.useState(false);
  const [operatorJournalExporting, setOperatorJournalExporting] = React.useState(false);
  const [stockHandoffLoading, setStockHandoffLoading] = React.useState(false);
  const [stockHandoffExporting, setStockHandoffExporting] = React.useState(false);
  const [stockBrokerExpansionLoading, setStockBrokerExpansionLoading] = React.useState(false);
  const [stockBrokerExpansionExporting, setStockBrokerExpansionExporting] = React.useState(false);
  const [stockBrokerExpansionPackageExportingId, setStockBrokerExpansionPackageExportingId] =
    React.useState<string | null>(null);
  const [stockBrokerExpansionPreflightExportingId, setStockBrokerExpansionPreflightExportingId] =
    React.useState<string | null>(null);
  const [stockBrokerExpansionRehearsalExportingId, setStockBrokerExpansionRehearsalExportingId] =
    React.useState<string | null>(null);
  const [stockHandoffReviewingId, setStockHandoffReviewingId] = React.useState<string | null>(null);
  const [stockHandoffExpandedKey, setStockHandoffExpandedKey] = React.useState<string | null>(null);
  const [stockHandoffSessions, setStockHandoffSessions] =
    React.useState<Record<string, PaperTradingSession>>({});
  const [stockHandoffBrokerEvaluations, setStockHandoffBrokerEvaluations] =
    React.useState<Record<string, BrokerIntentEvaluation[]>>({});
  const [stockHandoffOrderNotes, setStockHandoffOrderNotes] =
    React.useState<Record<string, PaperFillOrderNote[]>>({});
  const [stockHandoffQualityGates, setStockHandoffQualityGates] =
    React.useState<Record<string, PaperFillOrderNoteQualityGate>>({});
  const [stockHandoffDetailLoadingKey, setStockHandoffDetailLoadingKey] =
    React.useState<string | null>(null);
  const [executionUpdatedAt, setExecutionUpdatedAt] = React.useState<string | null>(null);
  const [paperSession, setPaperSession] = React.useState<PaperTradingSession | null>(null);
  const [liveSession, setLiveSession] = React.useState<LivePaperTradingSession | null>(null);
  const [liveSessions, setLiveSessions] = React.useState<LivePaperTradingSession[]>([]);
  const [autoReplay, setAutoReplay] = React.useState(false);
  const [autoTick, setAutoTick] = React.useState(false);
  const [autoReplayMs, setAutoReplayMs] = React.useState(1200);
  const [loading, setLoading] = React.useState(false);
  const [sweepLoading, setSweepLoading] = React.useState(false);
  const [validationLoading, setValidationLoading] = React.useState(false);
  const [walkForwardLoading, setWalkForwardLoading] = React.useState(false);
  const [paperLoading, setPaperLoading] = React.useState(false);
  const [portfolioLoading, setPortfolioLoading] = React.useState(false);
  const [liveLoading, setLiveLoading] = React.useState(false);
  const [advanceLoading, setAdvanceLoading] = React.useState(false);
  const [tickLoading, setTickLoading] = React.useState(false);
  const [orderQueueLoading, setOrderQueueLoading] = React.useState(false);
  const [columnarLoading, setColumnarLoading] = React.useState(false);
  const [portfolioScenarioLoading, setPortfolioScenarioLoading] = React.useState(false);
  const [portfolioScanLoadingId, setPortfolioScanLoadingId] = React.useState<string | null>(null);
  const [portfolioWatchlistLoading, setPortfolioWatchlistLoading] = React.useState(false);
  const [portfolioPaperWatchlistLoading, setPortfolioPaperWatchlistLoading] = React.useState(false);
  const [botFleetLoading, setBotFleetLoading] = React.useState(false);
  const [botFleetRunningId, setBotFleetRunningId] = React.useState<string | null>(null);
  const [orderQueueMessage, setOrderQueueMessage] = React.useState<string | null>(null);
  const [portfolioScenarioMessage, setPortfolioScenarioMessage] = React.useState<string | null>(null);
  const [approvalLoadingId, setApprovalLoadingId] = React.useState<string | null>(null);
  const [runbookLoadingId, setRunbookLoadingId] = React.useState<string | null>(null);
  const [cutoverRunbookExporting, setCutoverRunbookExporting] = React.useState(false);
  const [closeoutReportExporting, setCloseoutReportExporting] = React.useState(false);
  const [strategyHealthReportExporting, setStrategyHealthReportExporting] = React.useState(false);
  const [cryptoDrillReportExporting, setCryptoDrillReportExporting] = React.useState(false);
  const [approvalMessage, setApprovalMessage] = React.useState<string | null>(null);
  const [loadingRunId, setLoadingRunId] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [sweepError, setSweepError] = React.useState<string | null>(null);
  const [validationError, setValidationError] = React.useState<string | null>(null);
  const [walkForwardError, setWalkForwardError] = React.useState<string | null>(null);
  const [executionError, setExecutionError] = React.useState<string | null>(null);
  const [brokerIntentError, setBrokerIntentError] = React.useState<string | null>(null);
  const [paperFillDriftError, setPaperFillDriftError] = React.useState<string | null>(null);
  const [postCutoverMonitorError, setPostCutoverMonitorError] = React.useState<string | null>(null);
  const [strategyHealthError, setStrategyHealthError] = React.useState<string | null>(null);
  const [historyError, setHistoryError] = React.useState<string | null>(null);
  const [comparisonError, setComparisonError] = React.useState<string | null>(null);
  const [tickerError, setTickerError] = React.useState<string | null>(null);
  const [providerStatusError, setProviderStatusError] = React.useState<string | null>(null);
  const [columnarError, setColumnarError] = React.useState<string | null>(null);
  const [alertReviewError, setAlertReviewError] = React.useState<string | null>(null);
  const [readinessError, setReadinessError] = React.useState<string | null>(null);
  const [cutoverError, setCutoverError] = React.useState<string | null>(null);
  const [operatorDecisionError, setOperatorDecisionError] = React.useState<string | null>(null);
  const [operatorJournalError, setOperatorJournalError] = React.useState<string | null>(null);
  const [stockHandoffError, setStockHandoffError] = React.useState<string | null>(null);
  const [stockBrokerExpansionError, setStockBrokerExpansionError] = React.useState<string | null>(null);
  const [stockHandoffDetailError, setStockHandoffDetailError] = React.useState<string | null>(null);
  const [operatorDecisionMessage, setOperatorDecisionMessage] = React.useState<string | null>(null);
  const [cutoverDecisionMessage, setCutoverDecisionMessage] = React.useState<string | null>(null);
  const [stockHandoffMessage, setStockHandoffMessage] = React.useState<string | null>(null);
  const [portfolioScenarioError, setPortfolioScenarioError] = React.useState<string | null>(null);
  const [botFleetError, setBotFleetError] = React.useState<string | null>(null);
  const [botFleetMessage, setBotFleetMessage] = React.useState<string | null>(null);
  const [paperError, setPaperError] = React.useState<string | null>(null);
  const [portfolioError, setPortfolioError] = React.useState<string | null>(null);
  const [liveError, setLiveError] = React.useState<string | null>(null);
  const advanceInFlight = React.useRef(false);
  const tickInFlight = React.useRef(false);
  const comparisonFetches = React.useRef<Set<string>>(new Set());

  React.useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  const refreshProviderStatuses = React.useCallback(async () => {
    setProviderStatusError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/markets/providers/status`);
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      const payload = (await response.json()) as MarketDataProviderStatus[];
      setProviderStatuses(payload);
    } catch (err) {
      setProviderStatusError(
        err instanceof Error ? err.message : 'Could not load data provider status',
      );
    }
  }, []);

  const refreshColumnarStatus = React.useCallback(async () => {
    setColumnarError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/markets/cache/columnar/status`);
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      setColumnarStatus((await response.json()) as MarketDataColumnarStatus);
    } catch (err) {
      setColumnarError(err instanceof Error ? err.message : 'Could not load columnar cache status');
    }
  }, []);

  const refreshMarketDataState = React.useCallback(() => {
    void refreshProviderStatuses();
    void refreshColumnarStatus();
  }, [refreshColumnarStatus, refreshProviderStatuses]);

  const exportColumnarCache = React.useCallback(async () => {
    setColumnarLoading(true);
    setColumnarError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/markets/cache/columnar/export`, {
        method: 'POST',
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      setColumnarExport((await response.json()) as MarketDataColumnarExport);
      await refreshColumnarStatus();
    } catch (err) {
      setColumnarError(err instanceof Error ? err.message : 'Could not export columnar cache');
    } finally {
      setColumnarLoading(false);
    }
  }, [refreshColumnarStatus]);

  const refreshPortfolioLibrary = React.useCallback(async () => {
    setPortfolioScenarioError(null);
    try {
      const [
        presetsResponse,
        scenariosResponse,
        scansResponse,
        watchlistResponse,
        paperWatchlistResponse,
      ] = await Promise.all([
        fetch(`${API_BASE_URL}/api/research/portfolio/presets`),
        fetch(`${API_BASE_URL}/api/research/portfolio/scenarios`),
        fetch(`${API_BASE_URL}/api/research/portfolio/scans`),
        fetch(`${API_BASE_URL}/api/research/portfolio/watchlist`),
        fetch(`${API_BASE_URL}/api/paper/watchlist`),
      ]);
      if (!presetsResponse.ok) {
        const payload = await presetsResponse.json().catch(() => null);
        throw new Error(payload?.detail ?? `Preset request failed with ${presetsResponse.status}`);
      }
      if (!scenariosResponse.ok) {
        const payload = await scenariosResponse.json().catch(() => null);
        throw new Error(payload?.detail ?? `Scenario request failed with ${scenariosResponse.status}`);
      }
      if (!scansResponse.ok) {
        const payload = await scansResponse.json().catch(() => null);
        throw new Error(payload?.detail ?? `Scan request failed with ${scansResponse.status}`);
      }
      if (!watchlistResponse.ok) {
        const payload = await watchlistResponse.json().catch(() => null);
        throw new Error(payload?.detail ?? `Watchlist request failed with ${watchlistResponse.status}`);
      }
      if (!paperWatchlistResponse.ok) {
        const payload = await paperWatchlistResponse.json().catch(() => null);
        throw new Error(payload?.detail ?? `Paper watchlist request failed with ${paperWatchlistResponse.status}`);
      }
      setPortfolioPresets((await presetsResponse.json()) as PortfolioResearchPreset[]);
      setPortfolioScenarios((await scenariosResponse.json()) as PortfolioResearchScenario[]);
      setPortfolioScans((await scansResponse.json()) as PortfolioResearchScan[]);
      setPortfolioWatchlist((await watchlistResponse.json()) as PortfolioResearchWatchlistItem[]);
      setPortfolioPaperWatchlist((await paperWatchlistResponse.json()) as PortfolioPaperWatchlistItem[]);
    } catch (err) {
      setPortfolioScenarioError(
        err instanceof Error ? err.message : 'Could not load portfolio scenarios',
      );
    }
  }, []);

  const refreshBotFleet = React.useCallback(async () => {
    setBotFleetError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/bots/fleet`);
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Bot fleet request failed with ${response.status}`);
      }
      setBotFleet((await response.json()) as BotFleetStatus);
    } catch (err) {
      setBotFleetError(err instanceof Error ? err.message : 'Could not load bot fleet');
    }
  }, []);

  const createBotProfile = React.useCallback(async (profile: BotProfileCreate) => {
    setBotFleetLoading(true);
    setBotFleetError(null);
    setBotFleetMessage(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/bots/profiles`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(profile),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Bot profile create failed with ${response.status}`);
      }
      const created = (await response.json()) as BotProfile;
      setBotFleetMessage(`${created.name} 봇을 추가했습니다.`);
      await refreshBotFleet();
      return created;
    } catch (err) {
      setBotFleetError(err instanceof Error ? err.message : '봇을 추가하지 못했습니다.');
      throw err;
    } finally {
      setBotFleetLoading(false);
    }
  }, [refreshBotFleet]);

  const runDueBotFleet = React.useCallback(async () => {
    setBotFleetLoading(true);
    setBotFleetError(null);
    setBotFleetMessage(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/bots/run-due`, { method: 'POST' });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Bot fleet run failed with ${response.status}`);
      }
      const payload = (await response.json()) as BotFleetRun;
      setBotFleetLastRun(payload);
      const latestSession = payload.runs.find((run) => run.session)?.session ?? null;
      if (latestSession) {
        setPaperSession(latestSession);
        setLiveSession(null);
      }
      setBotFleetMessage(`실행 대상 봇 ${payload.runs.length}개를 실행했습니다. 이슈 ${payload.errors.length}개.`);
      await refreshBotFleet();
    } catch (err) {
      setBotFleetError(err instanceof Error ? err.message : '실행 대상 봇을 실행하지 못했습니다.');
    } finally {
      setBotFleetLoading(false);
    }
  }, [refreshBotFleet]);

  const runBotProfile = React.useCallback(async (botId: string) => {
    setBotFleetRunningId(botId);
    setBotFleetError(null);
    setBotFleetMessage(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/bots/profiles/${encodeURIComponent(botId)}/run`, {
        method: 'POST',
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Bot run failed with ${response.status}`);
      }
      const run = (await response.json()) as BotRun;
      setBotFleetLastRun({
        checked_at: run.checked_at,
        due: 1,
        runs: [run],
        errors: run.errors,
      });
      if (run.session) {
        setPaperSession(run.session);
        setLiveSession(null);
      }
      setBotFleetMessage(`${run.bot_name} 봇 실행이 ${botRunStatusLabel(run.status)} 상태로 끝났습니다.`);
      await refreshBotFleet();
    } catch (err) {
      setBotFleetError(err instanceof Error ? err.message : '봇을 실행하지 못했습니다.');
    } finally {
      setBotFleetRunningId(null);
    }
  }, [refreshBotFleet]);

  const pauseBotProfile = React.useCallback(async (botId: string) => {
    setBotFleetRunningId(botId);
    setBotFleetError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/bots/profiles/${encodeURIComponent(botId)}/pause`, {
        method: 'POST',
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Bot pause failed with ${response.status}`);
      }
      setBotFleetMessage('봇을 일시정지했습니다.');
      await refreshBotFleet();
    } catch (err) {
      setBotFleetError(err instanceof Error ? err.message : '봇을 일시정지하지 못했습니다.');
    } finally {
      setBotFleetRunningId(null);
    }
  }, [refreshBotFleet]);

  const resumeBotProfile = React.useCallback(async (botId: string) => {
    setBotFleetRunningId(botId);
    setBotFleetError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/bots/profiles/${encodeURIComponent(botId)}/resume`, {
        method: 'POST',
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Bot resume failed with ${response.status}`);
      }
      setBotFleetMessage('봇을 재개했습니다.');
      await refreshBotFleet();
    } catch (err) {
      setBotFleetError(err instanceof Error ? err.message : '봇을 재개하지 못했습니다.');
    } finally {
      setBotFleetRunningId(null);
    }
  }, [refreshBotFleet]);

  const deleteBotProfile = React.useCallback(async (botId: string) => {
    setBotFleetRunningId(botId);
    setBotFleetError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/bots/profiles/${encodeURIComponent(botId)}`, {
        method: 'DELETE',
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Bot delete failed with ${response.status}`);
      }
      setBotFleetMessage('봇을 삭제했습니다.');
      await refreshBotFleet();
    } catch (err) {
      setBotFleetError(err instanceof Error ? err.message : '봇을 삭제하지 못했습니다.');
    } finally {
      setBotFleetRunningId(null);
    }
  }, [refreshBotFleet]);

  const refreshLiveReadiness = React.useCallback(async () => {
    setReadinessLoading(true);
    setReadinessError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/readiness/live`);
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Readiness check failed with ${response.status}`);
      }
      setLiveReadiness((await response.json()) as LiveReadinessResponse);
    } catch (err) {
      setReadinessError(err instanceof Error ? err.message : 'Could not load live readiness');
    } finally {
      setReadinessLoading(false);
    }
  }, []);

  const refreshCutoverChecklist = React.useCallback(async () => {
    setCutoverLoading(true);
    setCutoverError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/execution/cutover-checklist`);
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Cutover checklist failed with ${response.status}`);
      }
      setCutoverChecklist((await response.json()) as LiveCutoverChecklistResponse);
    } catch (err) {
      setCutoverError(err instanceof Error ? err.message : 'Could not load cutover checklist');
    } finally {
      setCutoverLoading(false);
    }
  }, []);

  const refreshPostCutoverMonitor = React.useCallback(async () => {
    setPostCutoverMonitorLoading(true);
    setPostCutoverMonitorError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/execution/post-cutover-monitor`);
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Post-cutover monitor failed with ${response.status}`);
      }
      setPostCutoverMonitor((await response.json()) as PostCutoverOrderMonitor);
    } catch (err) {
      setPostCutoverMonitorError(
        err instanceof Error ? err.message : 'Could not load post-cutover monitor',
      );
    } finally {
      setPostCutoverMonitorLoading(false);
    }
  }, []);

  const refreshStrategyHealth = React.useCallback(async () => {
    setStrategyHealthLoading(true);
    setStrategyHealthError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/research/strategy-health/traces?limit=12`);
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Strategy health trace failed with ${response.status}`);
      }
      setStrategyHealth((await response.json()) as StrategyHealthTraceResponse);
    } catch (err) {
      setStrategyHealthError(
        err instanceof Error ? err.message : 'Could not load strategy health trace',
      );
    } finally {
      setStrategyHealthLoading(false);
    }
  }, []);

  const refreshOperatorDecisions = React.useCallback(async () => {
    setOperatorDecisionError(null);
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/operator/decisions?decision_type=readiness_review&limit=5`,
      );
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Operator decisions failed with ${response.status}`);
      }
      setOperatorDecisions((await response.json()) as OperatorDecisionRecord[]);
    } catch (err) {
      setOperatorDecisionError(
        err instanceof Error ? err.message : 'Could not load operator decisions',
      );
    }
  }, []);

  const refreshOperatorJournal = React.useCallback(async () => {
    setOperatorJournalLoading(true);
    setOperatorJournalError(null);
    try {
      const params = new URLSearchParams();
      params.set('limit', '20');
      if (operatorJournalFilters.decisionType !== 'all') {
        params.set('decision_type', operatorJournalFilters.decisionType);
      }
      if (operatorJournalFilters.status !== 'all') {
        params.set('status', operatorJournalFilters.status);
      }
      if (operatorJournalFilters.routeStatus !== 'all') {
        params.set('route_status', operatorJournalFilters.routeStatus);
      }
      if (operatorJournalFilters.targetId.trim()) {
        params.set('target_id', operatorJournalFilters.targetId.trim());
      }
      const response = await fetch(`${API_BASE_URL}/api/operator/decisions?${params.toString()}`);
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Operations journal failed with ${response.status}`);
      }
      setOperatorJournal((await response.json()) as OperatorDecisionRecord[]);
    } catch (err) {
      setOperatorJournalError(
        err instanceof Error ? err.message : 'Could not load operations journal',
      );
    } finally {
      setOperatorJournalLoading(false);
    }
  }, [operatorJournalFilters]);

  const operatorJournalSearchParams = React.useCallback((limit: number) => {
    const params = new URLSearchParams();
    params.set('limit', String(limit));
    if (operatorJournalFilters.decisionType !== 'all') {
      params.set('decision_type', operatorJournalFilters.decisionType);
    }
    if (operatorJournalFilters.status !== 'all') {
      params.set('status', operatorJournalFilters.status);
    }
    if (operatorJournalFilters.routeStatus !== 'all') {
      params.set('route_status', operatorJournalFilters.routeStatus);
    }
    if (operatorJournalFilters.targetId.trim()) {
      params.set('target_id', operatorJournalFilters.targetId.trim());
    }
    return params;
  }, [operatorJournalFilters]);

  const stockHandoffSearchParams = React.useCallback((limit: number) => {
    const params = new URLSearchParams();
    params.set('limit', String(limit));
    params.set('decision_type', 'dry_run_promotion');
    params.set('route_status', 'paper_only_review');
    return params;
  }, []);

  const refreshStockPaperHandoffs = React.useCallback(async () => {
    setStockHandoffLoading(true);
    setStockHandoffError(null);
    try {
      const params = stockHandoffSearchParams(8);
      const response = await fetch(`${API_BASE_URL}/api/operator/decisions?${params.toString()}`);
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Stock/ETF handoffs failed with ${response.status}`);
      }
      const handoffs = (await response.json()) as OperatorDecisionRecord[];
      setStockPaperHandoffs(handoffs);
      const gateEntries = await Promise.all(
        handoffs.map(async (handoff) => {
          const symbol = decisionContextText(handoff, 'symbol');
          if (!symbol) return null;
          const gateParams = new URLSearchParams();
          gateParams.set('symbol', symbol);
          gateParams.set('limit', '200');
          const gateResponse = await fetch(
            `${API_BASE_URL}/api/paper/order-notes/quality-gate?${gateParams.toString()}`,
          );
          if (!gateResponse.ok) return null;
          return [
            handoffDecisionKey(handoff),
            (await gateResponse.json()) as PaperFillOrderNoteQualityGate,
          ] as const;
        }),
      );
      setStockHandoffQualityGates((current) => ({
        ...current,
        ...Object.fromEntries(
          gateEntries.filter(
            (entry): entry is [string, PaperFillOrderNoteQualityGate] => Boolean(entry),
          ),
        ),
      }));
    } catch (err) {
      setStockHandoffError(
        err instanceof Error ? err.message : 'Could not load stock/ETF paper handoffs',
      );
    } finally {
      setStockHandoffLoading(false);
    }
  }, [stockHandoffSearchParams]);

  const refreshStockBrokerExpansionReadiness = React.useCallback(async () => {
    setStockBrokerExpansionLoading(true);
    setStockBrokerExpansionError(null);
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/paper/stock-etf/broker-expansion-readiness?limit=20`,
      );
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Broker expansion readiness failed with ${response.status}`);
      }
      setStockBrokerExpansionReadiness((await response.json()) as StockEtfBrokerExpansionReadiness);
    } catch (err) {
      setStockBrokerExpansionError(
        err instanceof Error ? err.message : 'Could not load stock/ETF broker expansion readiness',
      );
    } finally {
      setStockBrokerExpansionLoading(false);
    }
  }, []);

  const refreshAlertReview = React.useCallback(async () => {
    setAlertReviewError(null);
    try {
      const params = new URLSearchParams();
      if (alertFilters.severity !== 'all') {
        params.set('severity', alertFilters.severity);
      }
      if (alertFilters.source !== 'all') {
        params.set('source', alertFilters.source);
      }
      if (alertFilters.scenario.trim()) {
        params.set('scenario', alertFilters.scenario.trim());
      }
      const query = params.toString();
      const response = await fetch(
        `${API_BASE_URL}/api/alerts/review${query ? `?${query}` : ''}`,
      );
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Alert review failed with ${response.status}`);
      }
      setAlertReview((await response.json()) as AlertReviewResponse);
      await refreshLiveReadiness();
    } catch (err) {
      setAlertReviewError(err instanceof Error ? err.message : 'Could not load alert review queue');
    }
  }, [alertFilters, refreshLiveReadiness]);

  const acknowledgeAlertReviewItem = React.useCallback(async (
    alertId: string,
    status: 'acknowledged' | 'dismissed',
  ) => {
    setAlertReviewError(null);
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/alerts/review/${encodeURIComponent(alertId)}/acknowledge`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status }),
        },
      );
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Alert acknowledgement failed with ${response.status}`);
      }
      await response.json() as AlertReviewAcknowledgement;
      await refreshAlertReview();
    } catch (err) {
      setAlertReviewError(
        err instanceof Error ? err.message : 'Could not acknowledge alert review item',
      );
    }
  }, [refreshAlertReview]);

  const refreshTicker = React.useCallback(async () => {
    setTickerError(null);
    const params = new URLSearchParams({
      symbol: request.symbol,
      source: request.source,
    });

    try {
      const response = await fetch(`${API_BASE_URL}/api/markets/ticker?${params.toString()}`);
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      const payload = (await response.json()) as MarketTicker;
      setMarketTicker(payload);
    } catch (err) {
      setMarketTicker(null);
      setTickerError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      await refreshProviderStatuses();
      await refreshColumnarStatus();
    }
  }, [refreshColumnarStatus, refreshProviderStatuses, request.source, request.symbol]);

  const refreshLiveSessions = React.useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/paper/live-sessions`);
      if (!response.ok) return;
      const payload = (await response.json()) as LivePaperTradingSession[];
      setLiveSessions(payload.slice().reverse());
    } catch {
      setLiveSessions([]);
    }
  }, []);

  const refreshBacktestRuns = React.useCallback(async () => {
    setHistoryError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/backtests/runs`);
      if (!response.ok) return;
      const payload = (await response.json()) as BacktestRunSummary[];
      setBacktestRuns(payload);
    } catch (err) {
      setHistoryError(err instanceof Error ? err.message : 'Could not load backtest history');
    }
  }, []);

  const refreshExecutionState = React.useCallback(async () => {
    setExecutionRefreshing(true);
    setExecutionError(null);
    try {
      const [
        statusResponse,
        settingsResponse,
        opsSelfCheckResponse,
        adaptersResponse,
        brokerReadinessResponse,
        snapshotResponse,
        auditResponse,
        monitorResponse,
        strategyHealthResponse,
      ] = await Promise.all([
        fetch(`${API_BASE_URL}/api/execution/status`),
        fetch(`${API_BASE_URL}/api/execution/settings`),
        fetch(`${API_BASE_URL}/api/ops/self-check`),
        fetch(`${API_BASE_URL}/api/execution/paper-live-adapters`),
        fetch(`${API_BASE_URL}/api/execution/broker-readiness`),
        fetch(`${API_BASE_URL}/api/execution/private-snapshot`),
        fetch(`${API_BASE_URL}/api/execution/order-audits`),
        fetch(`${API_BASE_URL}/api/execution/post-cutover-monitor`),
        fetch(`${API_BASE_URL}/api/research/strategy-health/traces?limit=12`),
      ]);
      const partialErrors: string[] = [];
      if (!statusResponse.ok) {
        const payload = await statusResponse.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${statusResponse.status}`);
      }
      const statusPayload = (await statusResponse.json()) as ExecutionStatus;
      setExecutionStatus(statusPayload);
      if (settingsResponse.ok) {
        const settingsPayload = (await settingsResponse.json()) as ExecutionSettings;
        setExecutionSettings(settingsPayload);
      } else {
        const payload = await settingsResponse.json().catch(() => null);
        setExecutionSettings(null);
        partialErrors.push(
          payload?.detail ?? `Execution settings failed with ${settingsResponse.status}`,
        );
      }
      if (opsSelfCheckResponse.ok) {
        setOpsSelfCheck((await opsSelfCheckResponse.json()) as OpsSelfCheckResponse);
      } else {
        const payload = await opsSelfCheckResponse.json().catch(() => null);
        setOpsSelfCheck(null);
        partialErrors.push(
          payload?.detail ?? `Ops self-check failed with ${opsSelfCheckResponse.status}`,
        );
      }
      if (adaptersResponse.ok) {
        setPaperLiveAdapters((await adaptersResponse.json()) as PaperToLiveAdapterProfile[]);
      } else {
        const payload = await adaptersResponse.json().catch(() => null);
        setPaperLiveAdapters([]);
        partialErrors.push(
          payload?.detail ?? `Paper-live adapters failed with ${adaptersResponse.status}`,
        );
      }
      if (brokerReadinessResponse.ok) {
        setBrokerReadiness((await brokerReadinessResponse.json()) as BrokerReadinessResponse);
      } else {
        const payload = await brokerReadinessResponse.json().catch(() => null);
        setBrokerReadiness(null);
        partialErrors.push(
          payload?.detail ?? `Broker readiness failed with ${brokerReadinessResponse.status}`,
        );
      }
      if (snapshotResponse.ok) {
        const snapshotPayload = (await snapshotResponse.json()) as UpbitPrivateSnapshot;
        setPrivateSnapshot(snapshotPayload);
      } else {
        const payload = await snapshotResponse.json().catch(() => null);
        setPrivateSnapshot(null);
        partialErrors.push(
          payload?.detail ?? `Private snapshot failed with ${snapshotResponse.status}`,
        );
      }
      if (auditResponse.ok) {
        const auditPayload = (await auditResponse.json()) as OrderAuditRecord[];
        setOrderAudits(auditPayload);
        const dryRuns = auditPayload.filter((audit) => audit.status === 'dry_run').slice(0, 5);
        const precheckEntries = await Promise.all(
          dryRuns.map(async (audit) => {
            const response = await fetch(
              `${API_BASE_URL}/api/execution/order-audits/${audit.id}/precheck`,
            );
            if (!response.ok) return null;
            return [audit.id, (await response.json()) as OrderPrecheckResult] as const;
          }),
        );
        setOrderPrechecks(
          Object.fromEntries(precheckEntries.filter((entry): entry is [string, OrderPrecheckResult] => Boolean(entry))),
        );
      } else {
        partialErrors.push(`Order audit refresh failed with ${auditResponse.status}`);
        setOrderPrechecks({});
      }
      if (monitorResponse.ok) {
        setPostCutoverMonitor((await monitorResponse.json()) as PostCutoverOrderMonitor);
      } else {
        const payload = await monitorResponse.json().catch(() => null);
        setPostCutoverMonitor(null);
        partialErrors.push(
          payload?.detail ?? `Post-cutover monitor failed with ${monitorResponse.status}`,
        );
      }
      if (strategyHealthResponse.ok) {
        setStrategyHealth((await strategyHealthResponse.json()) as StrategyHealthTraceResponse);
      } else {
        const payload = await strategyHealthResponse.json().catch(() => null);
        setStrategyHealth(null);
        partialErrors.push(
          payload?.detail ?? `Strategy health trace failed with ${strategyHealthResponse.status}`,
        );
      }
      setExecutionUpdatedAt(new Date().toISOString());
      if (partialErrors.length > 0) {
        setExecutionError(partialErrors.join(' '));
      }
      await refreshLiveReadiness();
      await refreshCutoverChecklist();
    } catch (err) {
      setExecutionError(err instanceof Error ? err.message : 'Could not load execution status');
    } finally {
      setExecutionRefreshing(false);
    }
  }, [refreshCutoverChecklist, refreshLiveReadiness]);

  const refreshBrokerIntentHistory = React.useCallback(async () => {
    setBrokerIntentHistoryLoading(true);
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/execution/broker-intents/evaluations?adapter_id=${brokerIntentAdapterId}&limit=6`,
      );
      if (!response.ok) {
        const errorPayload = await response.json().catch(() => null);
        throw new Error(errorPayload?.detail ?? `Request failed with ${response.status}`);
      }
      setBrokerIntentHistory((await response.json()) as BrokerIntentEvaluation[]);
    } catch (err) {
      setBrokerIntentError(
        err instanceof Error ? err.message : 'Could not load broker intent history',
      );
    } finally {
      setBrokerIntentHistoryLoading(false);
    }
  }, [brokerIntentAdapterId]);

  const changeBrokerIntentAdapter = React.useCallback((value: BrokerIntentAdapterId) => {
    setBrokerIntentAdapterId(value);
    setBrokerIntentPaperSubmitConfirmation(false);
    setBrokerIntentEvaluation(null);
    setBrokerIntentReconciliation(null);
    setBrokerIntentError(null);
  }, []);

  const refreshPaperFillDriftAnalytics = React.useCallback(async () => {
    setPaperFillDriftLoading(true);
    setPaperFillDriftError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/paper/order-notes/quality-gate?limit=200`);
      if (!response.ok) {
        const errorPayload = await response.json().catch(() => null);
        throw new Error(errorPayload?.detail ?? `Request failed with ${response.status}`);
      }
      const gate = (await response.json()) as PaperFillOrderNoteQualityGate;
      setPaperFillQualityGate(gate);
      setPaperFillDriftAnalytics(gate.analytics);
    } catch (err) {
      setPaperFillDriftError(
        err instanceof Error ? err.message : 'Could not load paper fill drift analytics',
      );
    } finally {
      setPaperFillDriftLoading(false);
    }
  }, []);

  const evaluateBrokerIntent = React.useCallback(async () => {
    setBrokerIntentLoading(true);
    setBrokerIntentError(null);
    try {
      const linkedPaperSessionId =
        paperSession &&
        isUsdSource(paperSession.request.source) &&
        paperSession.request.symbol.toUpperCase() === (brokerIntentSymbol.trim().toUpperCase() || 'SPY')
          ? paperSession.id
          : null;
      const payload = {
        adapter_id: brokerIntentAdapterId,
        symbol: brokerIntentSymbol.trim().toUpperCase() || 'SPY',
        side: brokerIntentSide,
        quantity: brokerIntentQuantity,
        order_type: brokerIntentOrderType,
        limit_price: brokerIntentOrderType === 'limit' ? brokerIntentLimitPrice : null,
        time_in_force: 'day',
        reference_price: brokerIntentReferencePrice,
        cash_available: brokerIntentCashAvailable,
        current_position_quantity: brokerIntentCurrentPosition,
        portfolio_equity: brokerIntentPortfolioEquity,
        paper_fee_bps: brokerIntentFeeBps,
        paper_slippage_bps: brokerIntentSlippageBps,
        paper_session_id: linkedPaperSessionId,
        client_order_id: `dashboard-${Date.now()}`,
        live_confirmation: brokerIntentLiveConfirmation,
        paper_submit_confirmation: brokerIntentPaperSubmitConfirmation,
      };
      const response = await fetch(`${API_BASE_URL}/api/execution/broker-intents/evaluate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const errorPayload = await response.json().catch(() => null);
        throw new Error(errorPayload?.detail ?? `Request failed with ${response.status}`);
      }
      const evaluation = (await response.json()) as BrokerIntentEvaluation;
      setBrokerIntentEvaluation(evaluation);
      setBrokerIntentReconciliation(null);
      setBrokerIntentHistory((current) => [
        evaluation,
        ...current.filter((item) => item.id !== evaluation.id),
      ].slice(0, 6));
      if (linkedPaperSessionId) {
        void refreshPaperFillDriftAnalytics();
        void refreshStockPaperHandoffs();
        void refreshStockBrokerExpansionReadiness();
      }
    } catch (err) {
      setBrokerIntentError(
        err instanceof Error ? err.message : 'Could not evaluate broker intent',
      );
    } finally {
      setBrokerIntentLoading(false);
    }
  }, [
    brokerIntentAdapterId,
    brokerIntentCashAvailable,
    brokerIntentCurrentPosition,
    brokerIntentFeeBps,
    brokerIntentLimitPrice,
    brokerIntentLiveConfirmation,
    brokerIntentOrderType,
    brokerIntentPaperSubmitConfirmation,
    brokerIntentPortfolioEquity,
    brokerIntentQuantity,
    brokerIntentReferencePrice,
    brokerIntentSide,
    brokerIntentSlippageBps,
    brokerIntentSymbol,
    paperSession,
    refreshPaperFillDriftAnalytics,
    refreshStockBrokerExpansionReadiness,
    refreshStockPaperHandoffs,
  ]);

  const reconcileBrokerIntentEvaluation = React.useCallback(async (evaluationId: string) => {
    setBrokerIntentReconcilingId(evaluationId);
    setBrokerIntentError(null);
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/execution/broker-intents/evaluations/${encodeURIComponent(
          evaluationId,
        )}/reconcile`,
      );
      if (!response.ok) {
        const errorPayload = await response.json().catch(() => null);
        throw new Error(errorPayload?.detail ?? `Request failed with ${response.status}`);
      }
      setBrokerIntentReconciliation((await response.json()) as BrokerOrderReconciliation);
    } catch (err) {
      setBrokerIntentError(
        err instanceof Error ? err.message : 'Could not reconcile broker intent evaluation',
      );
    } finally {
      setBrokerIntentReconcilingId(null);
    }
  }, []);

  const runBacktest = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/backtests/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      const payload = (await response.json()) as BacktestResponse;
      setResult(payload);
      if (payload.id) {
        setComparisonDetails((current) => ({ ...current, [payload.id!]: payload }));
        setSelectedCompareIds((current) => [
          payload.id!,
          ...current.filter((id) => id !== payload.id),
        ].slice(0, 3));
      }
      await refreshBacktestRuns();
      await refreshProviderStatuses();
      await refreshColumnarStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [refreshBacktestRuns, refreshColumnarStatus, refreshProviderStatuses, request]);

  const runBotBacktest = React.useCallback(async (profile: BotProfile) => {
    const botRequest = backtestRequestFromBot(profile);
    const response = await fetch(`${API_BASE_URL}/api/backtests/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(botRequest),
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new Error(payload?.detail ?? `Bot backtest failed with ${response.status}`);
    }
    const payload = (await response.json()) as BacktestResponse;
    setRequest(botRequest);
    setResult(payload);
    if (payload.id) {
      setComparisonDetails((current) => ({ ...current, [payload.id!]: payload }));
      setSelectedCompareIds((current) => [
        payload.id!,
        ...current.filter((id) => id !== payload.id),
      ].slice(0, 3));
    }
    await refreshBacktestRuns();
    await refreshProviderStatuses();
    await refreshColumnarStatus();
    return payload;
  }, [refreshBacktestRuns, refreshColumnarStatus, refreshProviderStatuses]);

  const runBacktestSweep = React.useCallback(async () => {
    setSweepLoading(true);
    setSweepError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/backtests/sweep`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Sweep failed with ${response.status}`);
      }
      setSweepResult((await response.json()) as BacktestSweepResponse);
      await refreshProviderStatuses();
      await refreshColumnarStatus();
    } catch (err) {
      setSweepError(err instanceof Error ? err.message : 'Could not run parameter sweep');
    } finally {
      setSweepLoading(false);
    }
  }, [refreshColumnarStatus, refreshProviderStatuses, request]);

  const validateBacktestSplit = React.useCallback(async () => {
    setValidationLoading(true);
    setValidationError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/backtests/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...request, train_fraction: 0.7 }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Validation failed with ${response.status}`);
      }
      setValidationResult((await response.json()) as BacktestValidationResponse);
      await refreshProviderStatuses();
      await refreshColumnarStatus();
    } catch (err) {
      setValidationError(err instanceof Error ? err.message : 'Could not validate train/test split');
    } finally {
      setValidationLoading(false);
    }
  }, [refreshColumnarStatus, refreshProviderStatuses, request]);

  const runWalkForwardValidation = React.useCallback(async () => {
    setWalkForwardLoading(true);
    setWalkForwardError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/backtests/walk-forward`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...request,
          train_window: Math.min(90, Math.max(30, request.candle_limit - 60)),
          test_window: 30,
          step_size: 30,
        }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Walk-forward failed with ${response.status}`);
      }
      setWalkForwardResult((await response.json()) as BacktestWalkForwardResponse);
      await refreshProviderStatuses();
      await refreshColumnarStatus();
    } catch (err) {
      setWalkForwardError(err instanceof Error ? err.message : 'Could not run walk-forward validation');
    } finally {
      setWalkForwardLoading(false);
    }
  }, [refreshColumnarStatus, refreshProviderStatuses, request]);

  const loadBacktestRun = React.useCallback(async (runId: string) => {
    setLoadingRunId(runId);
    setHistoryError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/backtests/runs/${runId}`);
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      const payload = (await response.json()) as BacktestResponse;
      setResult(payload);
      if (payload.id) {
        setComparisonDetails((current) => ({ ...current, [payload.id!]: payload }));
      }
      setRequest(payload.request);
    } catch (err) {
      setHistoryError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoadingRunId(null);
    }
  }, []);

  const runPaperSession = React.useCallback(async () => {
    setPaperLoading(true);
    setPaperError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/paper/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...request, risk_limits: riskLimits }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      const payload = (await response.json()) as PaperTradingSession;
      setAutoReplay(false);
      setAutoTick(false);
      setLiveSession(null);
      setPaperSession(payload);
      if (isUsdSource(payload.request.source)) {
        setBrokerIntentSymbol(payload.request.symbol.toUpperCase());
        const latestTrade = payload.trades[payload.trades.length - 1];
        const latestEquityPoint = payload.equity_curve[payload.equity_curve.length - 1];
        setBrokerIntentReferencePrice(latestTrade?.price ?? latestEquityPoint?.close ?? brokerIntentReferencePrice);
      }
      setOrderQueueMessage(null);
      await refreshProviderStatuses();
      await refreshColumnarStatus();
      await refreshLiveReadiness();
    } catch (err) {
      setPaperError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setPaperLoading(false);
    }
  }, [brokerIntentReferencePrice, refreshColumnarStatus, refreshLiveReadiness, refreshProviderStatuses, request, riskLimits]);

  const currentPortfolioRequest = React.useCallback((): PortfolioResearchRequest => ({
    symbols: portfolioSymbols,
    timeframe: request.timeframe,
    source: request.source,
    strategy: request.strategy,
    initial_cash: request.initial_cash,
    fee_bps: request.fee_bps,
    slippage_bps: request.slippage_bps,
    candle_limit: request.candle_limit,
    weights: Object.fromEntries(
      portfolioSymbols.map((symbol) => [symbol, portfolioWeights[symbol] ?? 0]),
    ),
    rebalance_frequency: portfolioRebalance,
    params: request.params,
  }), [portfolioRebalance, portfolioSymbols, portfolioWeights, request]);

  const applyPortfolioRequest = React.useCallback((
    nextRequest: PortfolioResearchRequest,
    label?: string,
  ) => {
    const symbols = nextRequest.symbols.map((symbol) => symbol.toUpperCase()).slice(0, 8);
    setRequest({
      symbol: nextRequest.symbols[0] ?? defaultSymbolForSource(nextRequest.source),
      timeframe: nextRequest.timeframe,
      source: nextRequest.source,
      strategy: nextRequest.strategy,
      initial_cash: nextRequest.initial_cash,
      fee_bps: nextRequest.fee_bps,
      slippage_bps: nextRequest.slippage_bps,
      candle_limit: nextRequest.candle_limit,
      params: nextRequest.params,
    });
    setRiskLimits((current) => ({
      ...current,
      max_order_notional: isUsdSource(nextRequest.source) ? 25_000 : 500_000,
    }));
    setPortfolioSymbols(symbols);
    setPortfolioWeights(
      Object.keys(nextRequest.weights).length > 0
        ? nextRequest.weights
        : equalWeights(symbols),
    );
    setPortfolioRebalance(nextRequest.rebalance_frequency);
    setPortfolioResult(null);
    setPortfolioError(null);
    setSweepResult(null);
    setSweepError(null);
    setValidationResult(null);
    setValidationError(null);
    setWalkForwardResult(null);
    setWalkForwardError(null);
    setPaperSession(null);
    setLiveSession(null);
    setAutoReplay(false);
    setAutoTick(false);
    setOrderQueueMessage(null);
    if (label) {
      setPortfolioScenarioName(label);
      setPortfolioScenarioMessage(`Loaded ${label}.`);
    }
  }, []);

  const savePortfolioScenario = React.useCallback(async () => {
    setPortfolioScenarioLoading(true);
    setPortfolioScenarioError(null);
    setPortfolioScenarioMessage(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/research/portfolio/scenarios`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: portfolioScenarioName.trim() || 'Saved portfolio scenario',
          request: currentPortfolioRequest(),
        }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      const saved = (await response.json()) as PortfolioResearchScenario;
      setPortfolioScenarioName(saved.name);
      setPortfolioScenarioMessage(`Saved ${saved.name}.`);
      await refreshPortfolioLibrary();
    } catch (err) {
      setPortfolioScenarioError(
        err instanceof Error ? err.message : 'Could not save portfolio scenario',
      );
    } finally {
      setPortfolioScenarioLoading(false);
    }
  }, [currentPortfolioRequest, portfolioScenarioName, refreshPortfolioLibrary]);

  const deletePortfolioScenario = React.useCallback(async (scenarioId: string) => {
    const scenario = portfolioScenarios.find((item) => item.id === scenarioId);
    setPortfolioScenarioLoading(true);
    setPortfolioScenarioError(null);
    setPortfolioScenarioMessage(null);
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/research/portfolio/scenarios/${scenarioId}`,
        { method: 'DELETE' },
      );
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      setPortfolioScenarioMessage(
        scenario ? `Deleted ${scenario.name}.` : 'Deleted scenario.',
      );
      await refreshPortfolioLibrary();
    } catch (err) {
      setPortfolioScenarioError(
        err instanceof Error ? err.message : 'Could not delete portfolio scenario',
      );
    } finally {
      setPortfolioScenarioLoading(false);
    }
  }, [portfolioScenarios, refreshPortfolioLibrary]);

  const openPortfolioScan = React.useCallback((scan: PortfolioResearchScan) => {
    applyPortfolioRequest(scan.result.request, scan.scenario_name);
    setPortfolioResult(scan.result);
    setPortfolioScenarioMessage(
      `Opened ${scan.scenario_name} scan from ${shortDateTime(scan.created_at)}.`,
    );
  }, [applyPortfolioRequest]);

  const scanPortfolioScenario = React.useCallback(async (scenarioId: string) => {
    const scenario = portfolioScenarios.find((item) => item.id === scenarioId);
    setPortfolioScanLoadingId(scenarioId);
    setPortfolioScenarioError(null);
    setPortfolioScenarioMessage(null);
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/research/portfolio/scenarios/${scenarioId}/scan`,
        { method: 'POST' },
      );
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      const scan = (await response.json()) as PortfolioResearchScan;
      setPortfolioResult(scan.result);
      setPortfolioScenarioMessage(
        `Scanned ${scenario?.name ?? scan.scenario_name}: ${percent(scan.result.metrics.total_return_pct)} return.`,
      );
      await refreshPortfolioLibrary();
      await refreshAlertReview();
      await refreshProviderStatuses();
      await refreshColumnarStatus();
    } catch (err) {
      setPortfolioScenarioError(
        err instanceof Error ? err.message : 'Could not scan portfolio scenario',
      );
    } finally {
      setPortfolioScanLoadingId(null);
    }
  }, [portfolioScenarios, refreshAlertReview, refreshColumnarStatus, refreshPortfolioLibrary, refreshProviderStatuses]);

  const updatePortfolioAlertThreshold = React.useCallback((
    key: keyof PortfolioResearchAlertThresholds,
    value: number,
  ) => {
    setPortfolioAlertThresholds((current) => ({
      ...current,
      [key]: Number.isFinite(value) ? value : null,
    }));
  }, []);

  const addPortfolioWatchlistItem = React.useCallback(async (scenarioId: string) => {
    const scenario = portfolioScenarios.find((item) => item.id === scenarioId);
    setPortfolioWatchlistLoading(true);
    setPortfolioScenarioError(null);
    setPortfolioScenarioMessage(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/research/portfolio/watchlist`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scenario_id: scenarioId,
          interval_minutes: portfolioWatchInterval,
          active: true,
          alert_thresholds: portfolioAlertThresholds,
        }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      const item = (await response.json()) as PortfolioResearchWatchlistItem;
      setPortfolioScenarioMessage(
        `Watching ${scenario?.name ?? item.scenario_name} every ${item.interval_minutes} min.`,
      );
      await refreshPortfolioLibrary();
      await refreshAlertReview();
    } catch (err) {
      setPortfolioScenarioError(
        err instanceof Error ? err.message : 'Could not update portfolio watchlist',
      );
    } finally {
      setPortfolioWatchlistLoading(false);
    }
  }, [portfolioAlertThresholds, portfolioScenarios, portfolioWatchInterval, refreshAlertReview, refreshPortfolioLibrary]);

  const runDuePortfolioWatchlist = React.useCallback(async () => {
    setPortfolioWatchlistLoading(true);
    setPortfolioScenarioError(null);
    setPortfolioScenarioMessage(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/research/portfolio/watchlist/run-due`, {
        method: 'POST',
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      const run = (await response.json()) as PortfolioResearchSchedulerRun;
      if (run.scanned.length > 0) {
        setPortfolioResult(run.scanned[0].result);
      }
      setPortfolioScenarioMessage(
        `Checked ${run.due} due watch items; scanned ${run.scanned.length}; alerts ${run.alerts.length}.`,
      );
      if (run.errors.length > 0) {
        setPortfolioScenarioError(run.errors.join(' '));
      }
      await refreshPortfolioLibrary();
      await refreshAlertReview();
      await refreshProviderStatuses();
      await refreshColumnarStatus();
    } catch (err) {
      setPortfolioScenarioError(
        err instanceof Error ? err.message : 'Could not run due portfolio scans',
      );
    } finally {
      setPortfolioWatchlistLoading(false);
    }
  }, [refreshAlertReview, refreshColumnarStatus, refreshPortfolioLibrary, refreshProviderStatuses]);

  const deletePortfolioWatchlistItem = React.useCallback(async (itemId: string) => {
    setPortfolioWatchlistLoading(true);
    setPortfolioScenarioError(null);
    setPortfolioScenarioMessage(null);
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/research/portfolio/watchlist/${itemId}`,
        { method: 'DELETE' },
      );
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      setPortfolioScenarioMessage('Removed watchlist item.');
      await refreshPortfolioLibrary();
      await refreshAlertReview();
    } catch (err) {
      setPortfolioScenarioError(
        err instanceof Error ? err.message : 'Could not remove portfolio watchlist item',
      );
    } finally {
      setPortfolioWatchlistLoading(false);
    }
  }, [refreshAlertReview, refreshPortfolioLibrary]);

  const addPortfolioPaperWatchlistItem = React.useCallback(async (scenarioId: string) => {
    const scenario = portfolioScenarios.find((item) => item.id === scenarioId);
    setPortfolioPaperWatchlistLoading(true);
    setPortfolioScenarioError(null);
    setPortfolioScenarioMessage(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/paper/watchlist`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scenario_id: scenarioId,
          interval_minutes: portfolioWatchInterval,
          active: true,
          risk_limits: riskLimits,
        }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      const item = (await response.json()) as PortfolioPaperWatchlistItem;
      setPortfolioScenarioMessage(
        `Paper watching ${scenario?.name ?? item.scenario_name} every ${item.interval_minutes} min.`,
      );
      await refreshPortfolioLibrary();
      await refreshAlertReview();
    } catch (err) {
      setPortfolioScenarioError(
        err instanceof Error ? err.message : 'Could not update paper watchlist',
      );
    } finally {
      setPortfolioPaperWatchlistLoading(false);
    }
  }, [portfolioScenarios, portfolioWatchInterval, refreshAlertReview, refreshPortfolioLibrary, riskLimits]);

  const runPortfolioPaperWatchlistItem = React.useCallback(async (itemId: string) => {
    setPortfolioPaperWatchlistLoading(true);
    setPortfolioScenarioError(null);
    setPortfolioScenarioMessage(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/paper/watchlist/${itemId}/run`, {
        method: 'POST',
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      const run = (await response.json()) as PortfolioPaperWatchlistRun;
      if (run.sessions.length > 0) {
        setAutoReplay(false);
        setAutoTick(false);
        setLiveSession(null);
        setPaperSession(run.sessions[0]);
      }
      setPortfolioScenarioMessage(
        `Created ${run.sessions.length} paper sessions from ${run.item.scenario_name}.`,
      );
      if (run.errors.length > 0) {
        setPortfolioScenarioError(run.errors.join(' '));
      }
      await refreshPortfolioLibrary();
      await refreshAlertReview();
      await refreshProviderStatuses();
      await refreshColumnarStatus();
    } catch (err) {
      setPortfolioScenarioError(
        err instanceof Error ? err.message : 'Could not run paper watchlist item',
      );
    } finally {
      setPortfolioPaperWatchlistLoading(false);
    }
  }, [refreshAlertReview, refreshColumnarStatus, refreshPortfolioLibrary, refreshProviderStatuses]);

  const runDuePortfolioPaperWatchlist = React.useCallback(async () => {
    setPortfolioPaperWatchlistLoading(true);
    setPortfolioScenarioError(null);
    setPortfolioScenarioMessage(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/paper/watchlist/run-due`, {
        method: 'POST',
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      const run = (await response.json()) as PortfolioPaperSchedulerRun;
      const firstSession = run.runs.flatMap((item) => item.sessions)[0];
      if (firstSession) {
        setAutoReplay(false);
        setAutoTick(false);
        setLiveSession(null);
        setPaperSession(firstSession);
      }
      const created = run.runs.reduce((sum, item) => sum + item.sessions.length, 0);
      setPortfolioScenarioMessage(
        `Checked ${run.due} due paper watch items; created ${created} sessions.`,
      );
      if (run.errors.length > 0) {
        setPortfolioScenarioError(run.errors.join(' '));
      }
      await refreshPortfolioLibrary();
      await refreshAlertReview();
      await refreshProviderStatuses();
      await refreshColumnarStatus();
    } catch (err) {
      setPortfolioScenarioError(
        err instanceof Error ? err.message : 'Could not run due paper watchlist',
      );
    } finally {
      setPortfolioPaperWatchlistLoading(false);
    }
  }, [refreshAlertReview, refreshColumnarStatus, refreshPortfolioLibrary, refreshProviderStatuses]);

  const deletePortfolioPaperWatchlistItem = React.useCallback(async (itemId: string) => {
    setPortfolioPaperWatchlistLoading(true);
    setPortfolioScenarioError(null);
    setPortfolioScenarioMessage(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/paper/watchlist/${itemId}`, {
        method: 'DELETE',
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      setPortfolioScenarioMessage('Removed paper watchlist item.');
      await refreshPortfolioLibrary();
      await refreshAlertReview();
    } catch (err) {
      setPortfolioScenarioError(
        err instanceof Error ? err.message : 'Could not remove paper watchlist item',
      );
    } finally {
      setPortfolioPaperWatchlistLoading(false);
    }
  }, [refreshAlertReview, refreshPortfolioLibrary]);

  const promotePortfolioPaperWatchlistItem = React.useCallback(async (itemId: string) => {
    setPortfolioPaperWatchlistLoading(true);
    setPortfolioScenarioError(null);
    setPortfolioScenarioMessage(null);
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/paper/watchlist/${itemId}/promote-order-intents`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            max_sessions: 3,
            max_intents_per_session: 3,
            rules: {
              min_total_return_pct: 0,
              max_drawdown_pct: 15,
              min_orders: 1,
            },
          }),
        },
      );
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      const promoted = (await response.json()) as PortfolioPaperPromotionResponse;
      if (promoted.eligible_sessions.length > 0) {
        setAutoReplay(false);
        setAutoTick(false);
        setLiveSession(null);
        setPaperSession(promoted.eligible_sessions[0]);
      }
      const paperOnlyCount = promoted.paper_only_handoffs.length;
      setPortfolioScenarioMessage(
        `Promoted ${promoted.created} dry-run intents and ${paperOnlyCount} paper-only handoffs from ${promoted.item.scenario_name}; ${promoted.skipped_existing} already logged.`,
      );
      const details = [...promoted.errors, ...promoted.skipped_sessions];
      if (details.length > 0) {
        setPortfolioScenarioError(details.join(' '));
      }
      await refreshExecutionState();
      await refreshPortfolioLibrary();
      await refreshAlertReview();
      await refreshStockPaperHandoffs();
    } catch (err) {
      setPortfolioScenarioError(
        err instanceof Error ? err.message : 'Could not promote paper watchlist item',
      );
    } finally {
      setPortfolioPaperWatchlistLoading(false);
    }
  }, [refreshAlertReview, refreshExecutionState, refreshPortfolioLibrary, refreshStockPaperHandoffs]);

  const logPaperWatchlistDecision = React.useCallback(async (item: PortfolioPaperWatchlistItem) => {
    setOperatorDecisionLoading(true);
    setOperatorDecisionError(null);
    setPortfolioScenarioError(null);
    setPortfolioScenarioMessage(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/operator/decisions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          decision_type: 'dry_run_promotion',
          target_id: item.id,
          status: item.last_error ? 'needs_work' : 'noted',
          note: item.last_error
            ? `${item.scenario_name} promotion review needs work: ${item.last_error}`
            : `${item.scenario_name} paper promotion review noted.`,
          context: {
            watchlist_id: item.id,
            scenario_id: item.scenario_id,
            scenario_name: item.scenario_name,
            active: item.active,
            interval_minutes: item.interval_minutes,
            last_run_at: item.last_run_at ?? null,
            last_session_ids: item.last_session_ids,
            last_error: item.last_error ?? null,
            readiness_status: liveReadiness?.status ?? null,
            readiness_score: liveReadiness?.score ?? null,
          },
        }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      const decision = (await response.json()) as OperatorDecisionRecord;
      setPortfolioScenarioMessage(
        `Logged ${decision.status.replaceAll('_', ' ')} promotion review for ${item.scenario_name}.`,
      );
      await refreshOperatorDecisions();
      await refreshOperatorJournal();
      await refreshStockPaperHandoffs();
    } catch (err) {
      setPortfolioScenarioError(
        err instanceof Error ? err.message : 'Could not log promotion review decision',
      );
    } finally {
      setOperatorDecisionLoading(false);
    }
  }, [liveReadiness, refreshOperatorDecisions, refreshOperatorJournal, refreshStockPaperHandoffs]);

  const runPortfolioResearch = React.useCallback(async () => {
    if (portfolioSymbols.length < 2) {
      setPortfolioError('Select at least two symbols for portfolio research.');
      return;
    }

    setPortfolioLoading(true);
    setPortfolioError(null);
    try {
      const payload = currentPortfolioRequest();
      const response = await fetch(`${API_BASE_URL}/api/research/portfolio`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail ?? `Request failed with ${response.status}`);
      }
      setPortfolioResult((await response.json()) as PortfolioResearchResponse);
      await refreshProviderStatuses();
      await refreshColumnarStatus();
    } catch (err) {
      setPortfolioError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setPortfolioLoading(false);
    }
  }, [currentPortfolioRequest, portfolioSymbols.length, refreshColumnarStatus, refreshProviderStatuses]);

  const startLiveReplay = React.useCallback(async () => {
    setLiveLoading(true);
    setLiveError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/paper/live-sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...request,
          warmup_bars: defaultWarmupBars(request),
          risk_limits: riskLimits,
        }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      const payload = (await response.json()) as LivePaperTradingSession;
      setAutoTick(false);
      setPaperSession(null);
      setLiveSession(payload);
      setOrderQueueMessage(null);
      await refreshLiveSessions();
      await refreshProviderStatuses();
      await refreshColumnarStatus();
      await refreshLiveReadiness();
      await refreshCutoverChecklist();
    } catch (err) {
      setLiveError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLiveLoading(false);
    }
  }, [refreshColumnarStatus, refreshCutoverChecklist, refreshLiveReadiness, refreshLiveSessions, refreshProviderStatuses, request, riskLimits]);

  const startTickerPaper = React.useCallback(async () => {
    setLiveLoading(true);
    setLiveError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/paper/ticker-sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...request,
          warmup_bars: defaultWarmupBars(request),
          risk_limits: riskLimits,
        }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      const payload = (await response.json()) as LivePaperTradingSession;
      setAutoReplay(false);
      setPaperSession(null);
      setLiveSession(payload);
      setOrderQueueMessage(null);
      await refreshLiveSessions();
      await refreshProviderStatuses();
      await refreshColumnarStatus();
      await refreshLiveReadiness();
      await refreshCutoverChecklist();
    } catch (err) {
      setLiveError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLiveLoading(false);
    }
  }, [refreshColumnarStatus, refreshCutoverChecklist, refreshLiveReadiness, refreshLiveSessions, refreshProviderStatuses, request, riskLimits]);

  const advanceLiveReplay = React.useCallback(async (steps = 5) => {
    if (
      !liveSession ||
      liveSession.summary.status !== 'running' ||
      liveSession.mode === 'ticker' ||
      advanceInFlight.current
    ) {
      return;
    }
    advanceInFlight.current = true;
    setAdvanceLoading(true);
    setLiveError(null);
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/paper/live-sessions/${liveSession.id}/advance`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ steps }),
        },
      );
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      const payload = (await response.json()) as LivePaperTradingSession;
      setLiveSession(payload);
      await refreshLiveSessions();
      await refreshLiveReadiness();
      await refreshCutoverChecklist();
    } catch (err) {
      setLiveError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      advanceInFlight.current = false;
      setAdvanceLoading(false);
    }
  }, [liveSession, refreshCutoverChecklist, refreshLiveReadiness, refreshLiveSessions]);

  const advanceTickerPaper = React.useCallback(async () => {
    if (
      !liveSession ||
      liveSession.summary.status !== 'running' ||
      liveSession.mode !== 'ticker' ||
      tickInFlight.current
    ) {
      return;
    }
    tickInFlight.current = true;
    setTickLoading(true);
    setLiveError(null);
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/paper/live-sessions/${liveSession.id}/tick`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        },
      );
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      const payload = (await response.json()) as LivePaperTradingSession;
      setLiveSession(payload);
      await refreshTicker();
      await refreshLiveSessions();
      await refreshLiveReadiness();
      await refreshCutoverChecklist();
    } catch (err) {
      setLiveError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      tickInFlight.current = false;
      setTickLoading(false);
    }
  }, [liveSession, refreshCutoverChecklist, refreshLiveReadiness, refreshLiveSessions, refreshTicker]);

  const queueDryRunOrderIntents = React.useCallback(async () => {
    const activeSession = liveSession ?? paperSession;
    if (!activeSession) return;

    const endpoint = isLiveSession(activeSession)
      ? `${API_BASE_URL}/api/paper/live-sessions/${activeSession.id}/order-intents`
      : `${API_BASE_URL}/api/paper/sessions/${activeSession.id}/order-intents`;

    setOrderQueueLoading(true);
    setPaperError(null);
    setOrderQueueMessage(null);
    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ max_intents: 5 }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      const payload = (await response.json()) as StrategyOrderQueueResponse;
      if (payload.created > 0) {
        setOrderQueueMessage(
          `Queued ${payload.created} dry-run intents; ${payload.skipped_existing} already audited.`,
        );
        setApprovalMessage(null);
      } else {
        setOrderQueueMessage('No new dry-run intents; latest trades are already audited.');
      }
      await refreshExecutionState();
    } catch (err) {
      setPaperError(err instanceof Error ? err.message : 'Could not queue dry-run intents');
    } finally {
      setOrderQueueLoading(false);
    }
  }, [liveSession, paperSession, refreshExecutionState]);

  const approveDryRunOrder = React.useCallback(async (audit: OrderAuditRecord) => {
    const price = payloadNumber(audit.request_payload.price);
    const volume = payloadNumber(audit.request_payload.volume);
    const confirmed = window.confirm(
      `Approve ${audit.side.toUpperCase()} ${audit.market} ${quantity(volume)} @ ${money(price)}?\n\nThe backend live guard must still be armed before any exchange order can be submitted.`,
    );
    if (!confirmed) return;

    setApprovalLoadingId(audit.id);
    setExecutionError(null);
    setApprovalMessage(null);
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/execution/order-audits/${audit.id}/approve`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ live_confirmation: true }),
        },
      );
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      const payload = (await response.json()) as OrderAuditRecord;
      setApprovalMessage(
        payload.status === 'submitted'
          ? `Submitted approved order for ${payload.market}.`
          : `Approval recorded as ${payload.status}: ${payload.reason}`,
      );
      await refreshExecutionState();
    } catch (err) {
      setExecutionError(err instanceof Error ? err.message : 'Could not approve dry-run order');
    } finally {
      setApprovalLoadingId(null);
    }
  }, [refreshExecutionState]);

  const logDryRunApprovalDecision = React.useCallback(async (
    audit: OrderAuditRecord,
    decisionStatus: OperatorDecisionStatus,
  ) => {
    const precheck = orderPrechecks[audit.id];
    const promotion = promotionContext(audit.response_payload);
    setOperatorDecisionLoading(true);
    setOperatorDecisionError(null);
    setApprovalMessage(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/operator/decisions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          decision_type: 'dry_run_approval',
          target_id: audit.id,
          status: decisionStatus,
          note: `${audit.market} ${audit.side} dry-run review marked ${decisionStatus.replaceAll('_', ' ')}.`,
          context: {
            audit_id: audit.id,
            market: audit.market,
            side: audit.side,
            ord_type: audit.ord_type,
            audit_status: audit.status,
            precheck_status: precheck?.status ?? 'pending',
            estimated_notional: precheck?.estimated_notional ?? null,
            readiness_status: liveReadiness?.status ?? null,
            readiness_score: liveReadiness?.score ?? null,
            promotion_context: promotion,
          },
        }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      const decision = (await response.json()) as OperatorDecisionRecord;
      setApprovalMessage(
        `Logged ${decision.status.replaceAll('_', ' ')} review for ${audit.market}.`,
      );
      await refreshOperatorDecisions();
      await refreshOperatorJournal();
      await refreshCutoverChecklist();
    } catch (err) {
      setOperatorDecisionError(
        err instanceof Error ? err.message : 'Could not log dry-run review decision',
      );
    } finally {
      setOperatorDecisionLoading(false);
    }
  }, [
    liveReadiness,
    orderPrechecks,
    refreshCutoverChecklist,
    refreshOperatorDecisions,
    refreshOperatorJournal,
  ]);

  const exportDryRunRunbook = React.useCallback(async (audit: OrderAuditRecord) => {
    setRunbookLoadingId(audit.id);
    setExecutionError(null);
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/execution/order-audits/${audit.id}/runbook`,
      );
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      const runbook = (await response.json()) as ExecutionRunbook;
      const blob = new Blob([runbook.markdown], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = runbook.filename;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setApprovalMessage(`Exported ${runbook.filename}.`);
    } catch (err) {
      setExecutionError(err instanceof Error ? err.message : 'Could not export approval runbook');
    } finally {
      setRunbookLoadingId(null);
    }
  }, []);

  const exportDryRunRunbookById = React.useCallback(async (recordId: string) => {
    setRunbookLoadingId(recordId);
    setOperatorJournalError(null);
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/execution/order-audits/${recordId}/runbook`,
      );
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      const runbook = (await response.json()) as ExecutionRunbook;
      const blob = new Blob([runbook.markdown], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = runbook.filename;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setOperatorJournalError(
        err instanceof Error ? err.message : 'Could not export linked approval runbook',
      );
    } finally {
      setRunbookLoadingId(null);
    }
  }, []);

  const exportCutoverRunbook = React.useCallback(async () => {
    setCutoverRunbookExporting(true);
    setCutoverError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/execution/cutover-checklist/runbook`);
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      const runbook = (await response.json()) as LiveCutoverRunbook;
      const blob = new Blob([runbook.markdown], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = runbook.filename;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setCutoverDecisionMessage(`Exported ${runbook.filename}.`);
    } catch (err) {
      setCutoverError(err instanceof Error ? err.message : 'Could not export cutover runbook');
    } finally {
      setCutoverRunbookExporting(false);
    }
  }, []);

  const simulateArming = React.useCallback(async () => {
    setArmingSimulationLoading(true);
    setCutoverError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/execution/cutover-checklist/simulate-arming`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          live_trading_enabled: true,
          live_ack_configured: true,
          credential_configured: true,
          assume_required_operator_decisions: armingSimulationAssumeDecisions,
        } satisfies LiveArmingSimulationRequest),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      setArmingSimulation((await response.json()) as LiveArmingSimulationResponse);
    } catch (err) {
      setCutoverError(err instanceof Error ? err.message : 'Could not simulate live arming');
    } finally {
      setArmingSimulationLoading(false);
    }
  }, [armingSimulationAssumeDecisions]);

  const exportPostCutoverCloseoutReport = React.useCallback(async () => {
    setCloseoutReportExporting(true);
    setPostCutoverMonitorError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/execution/post-cutover-monitor/closeout-report`);
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      const report = (await response.json()) as PostCutoverCloseoutReport;
      const blob = new Blob([report.markdown], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = report.filename;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setPostCutoverMonitorError(
        err instanceof Error ? err.message : 'Could not export live-window closeout report',
      );
    } finally {
      setCloseoutReportExporting(false);
    }
  }, []);

  const exportStrategyHealthHandoffReport = React.useCallback(async () => {
    setStrategyHealthReportExporting(true);
    setStrategyHealthError(null);
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/research/strategy-health/handoff-report?limit=20`,
      );
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      const report = (await response.json()) as StrategyHealthHandoffReport;
      const blob = new Blob([report.markdown], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = report.filename;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setStrategyHealthError(
        err instanceof Error ? err.message : 'Could not export strategy health handoff report',
      );
    } finally {
      setStrategyHealthReportExporting(false);
    }
  }, []);

  const exportCryptoLiveBetaDrillReport = React.useCallback(async () => {
    setCryptoDrillReportExporting(true);
    setStrategyHealthError(null);
    const drillSymbol = request.symbol.startsWith('KRW-') ? request.symbol : 'KRW-BTC';
    try {
      const params = new URLSearchParams({ symbol: drillSymbol, limit: '5' });
      const response = await fetch(
        `${API_BASE_URL}/api/research/crypto-live-beta-drill/report?${params.toString()}`,
      );
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      const report = (await response.json()) as CryptoLiveBetaDrillReport;
      const blob = new Blob([report.markdown], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = report.filename;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setStrategyHealthError(
        err instanceof Error ? err.message : 'Could not export crypto live beta drill report',
      );
    } finally {
      setCryptoDrillReportExporting(false);
    }
  }, [request.symbol]);

  const exportBrokerIntentEvaluationReport = React.useCallback(async () => {
    setBrokerIntentReportExporting(true);
    setBrokerIntentError(null);
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/execution/broker-intents/evaluations/report?adapter_id=${brokerIntentAdapterId}&limit=50`,
      );
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      const report = (await response.json()) as BrokerIntentEvaluationReport;
      const blob = new Blob([report.markdown], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = report.filename;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setBrokerIntentError(
        err instanceof Error ? err.message : 'Could not export broker intent report',
      );
    } finally {
      setBrokerIntentReportExporting(false);
    }
  }, [brokerIntentAdapterId]);

  const exportOperatorJournalReport = React.useCallback(async () => {
    setOperatorJournalExporting(true);
    setOperatorJournalError(null);
    try {
      const params = operatorJournalSearchParams(100);
      const response = await fetch(
        `${API_BASE_URL}/api/operator/decisions/report?${params.toString()}`,
      );
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      const report = (await response.json()) as OperatorDecisionReport;
      const blob = new Blob([report.markdown], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = report.filename;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setOperatorJournalError(
        err instanceof Error ? err.message : 'Could not export operations journal report',
      );
    } finally {
      setOperatorJournalExporting(false);
    }
  }, [operatorJournalSearchParams]);

  const exportStockPaperHandoffReport = React.useCallback(async () => {
    setStockHandoffExporting(true);
    setStockHandoffError(null);
    try {
      const params = stockHandoffSearchParams(100);
      const response = await fetch(
        `${API_BASE_URL}/api/operator/decisions/report?${params.toString()}`,
      );
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      const report = (await response.json()) as OperatorDecisionReport;
      const blob = new Blob([report.markdown], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = report.filename.replace('operations-journal', 'stock-etf-handoffs');
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setStockHandoffError(
        err instanceof Error ? err.message : 'Could not export stock/ETF handoff report',
      );
    } finally {
      setStockHandoffExporting(false);
    }
  }, [stockHandoffSearchParams]);

  const exportStockBrokerExpansionReport = React.useCallback(async () => {
    setStockBrokerExpansionExporting(true);
    setStockBrokerExpansionError(null);
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/paper/stock-etf/broker-expansion-readiness/report?limit=100`,
      );
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      const report = (await response.json()) as StockEtfBrokerExpansionReport;
      const blob = new Blob([report.markdown], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = report.filename;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setStockBrokerExpansionError(
        err instanceof Error ? err.message : 'Could not export stock/ETF broker expansion report',
      );
    } finally {
      setStockBrokerExpansionExporting(false);
    }
  }, []);

  const exportStockBrokerExpansionPackage = React.useCallback(async (decisionId: string) => {
    setStockBrokerExpansionPackageExportingId(decisionId);
    setStockBrokerExpansionError(null);
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/paper/stock-etf/broker-expansion-readiness/package/${encodeURIComponent(decisionId)}`,
      );
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      const expansionPackage = (await response.json()) as StockEtfBrokerExpansionPackage;
      const blob = new Blob([expansionPackage.markdown], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = expansionPackage.filename;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setStockBrokerExpansionError(
        err instanceof Error ? err.message : 'Could not export stock/ETF broker expansion package',
      );
    } finally {
      setStockBrokerExpansionPackageExportingId(null);
    }
  }, []);

  const exportStockBrokerExpansionPreflight = React.useCallback(async (decisionId: string) => {
    setStockBrokerExpansionPreflightExportingId(decisionId);
    setStockBrokerExpansionError(null);
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/paper/stock-etf/broker-expansion-readiness/package/${encodeURIComponent(decisionId)}/preflight`,
      );
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      const preflight = (await response.json()) as StockEtfBrokerExpansionPreflight;
      const blob = new Blob([preflight.markdown], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = preflight.filename;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setStockBrokerExpansionError(
        err instanceof Error ? err.message : 'Could not export stock/ETF broker expansion preflight',
      );
    } finally {
      setStockBrokerExpansionPreflightExportingId(null);
    }
  }, []);

  const exportStockBrokerExpansionRehearsal = React.useCallback(async (decisionId: string) => {
    setStockBrokerExpansionRehearsalExportingId(decisionId);
    setStockBrokerExpansionError(null);
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/paper/stock-etf/broker-expansion-readiness/package/${encodeURIComponent(decisionId)}/rehearsal`,
      );
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      const rehearsal = (await response.json()) as StockEtfBrokerExpansionRehearsal;
      const blob = new Blob([rehearsal.markdown], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = rehearsal.filename;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setStockBrokerExpansionError(
        err instanceof Error ? err.message : 'Could not export stock/ETF broker expansion rehearsal',
      );
    } finally {
      setStockBrokerExpansionRehearsalExportingId(null);
    }
  }, []);

  const logStockPaperHandoffDecision = React.useCallback(async (
    handoff: OperatorDecisionRecord,
    status: OperatorDecisionStatus,
  ) => {
    const targetId = decisionContextText(handoff, 'handoff_id') ?? handoff.target_id ?? handoff.id;
    const symbol = decisionContextText(handoff, 'symbol') ?? 'Stock/ETF';
    const routeStatus = decisionContextText(handoff, 'route_status') ?? 'paper_only_review';
    setStockHandoffReviewingId(handoff.id);
    setStockHandoffError(null);
    setStockHandoffMessage(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/operator/decisions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          decision_type: 'dry_run_promotion',
          target_id: targetId,
          status,
          note: `${symbol} paper-only handoff ${status.replaceAll('_', ' ')}; no live-order audit created.`,
          context: {
            ...handoff.context,
            route_status: routeStatus,
            review_source: 'stock_etf_handoff_panel',
            reviewed_decision_id: handoff.id,
            previous_status: handoff.status,
            reviewed_at: new Date().toISOString(),
          },
        }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      const decision = (await response.json()) as OperatorDecisionRecord;
      setStockHandoffMessage(
        `Marked ${symbol} handoff as ${decision.status.replaceAll('_', ' ')}.`,
      );
      await refreshStockPaperHandoffs();
      await refreshStockBrokerExpansionReadiness();
      await refreshOperatorJournal();
    } catch (err) {
      setStockHandoffError(
        err instanceof Error ? err.message : 'Could not log stock/ETF handoff decision',
      );
    } finally {
      setStockHandoffReviewingId(null);
    }
  }, [refreshOperatorJournal, refreshStockBrokerExpansionReadiness, refreshStockPaperHandoffs]);

  const toggleStockPaperHandoffDetails = React.useCallback(async (handoff: OperatorDecisionRecord) => {
    const handoffKey = handoffDecisionKey(handoff);
    if (stockHandoffExpandedKey === handoffKey) {
      setStockHandoffExpandedKey(null);
      setStockHandoffDetailError(null);
      return;
    }

    setStockHandoffExpandedKey(handoffKey);
    setStockHandoffDetailError(null);
    const sessionId = decisionContextText(handoff, 'session_id');
    if (!sessionId) {
      setStockHandoffDetailError('This handoff does not include a linked paper session ID.');
      return;
    }
    const symbol = decisionContextText(handoff, 'symbol');
    const needsSession = !stockHandoffSessions[sessionId];
    const needsBrokerEvaluations = Boolean(symbol) && !stockHandoffBrokerEvaluations[handoffKey];
    const needsOrderNotes = !stockHandoffOrderNotes[handoffKey];
    const needsQualityGate = Boolean(symbol) && !stockHandoffQualityGates[handoffKey];
    if (!needsSession && !needsBrokerEvaluations && !needsOrderNotes && !needsQualityGate) return;

    setStockHandoffDetailLoadingKey(handoffKey);
    try {
      if (needsSession) {
        const response = await fetch(`${API_BASE_URL}/api/paper/sessions/${encodeURIComponent(sessionId)}`);
        if (!response.ok) {
          const payload = await response.json().catch(() => null);
          throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
        }
        const session = (await response.json()) as PaperTradingSession;
        setStockHandoffSessions((current) => ({
          ...current,
          [session.id]: session,
        }));
      }
      if (needsBrokerEvaluations && symbol) {
        const params = new URLSearchParams();
        params.set('symbol', symbol);
        params.set('limit', '3');
        const response = await fetch(
          `${API_BASE_URL}/api/execution/broker-intents/evaluations?${params.toString()}`,
        );
        if (!response.ok) {
          const payload = await response.json().catch(() => null);
          throw new Error(payload?.detail ?? `Broker evaluations failed with ${response.status}`);
        }
        const evaluations = (await response.json()) as BrokerIntentEvaluation[];
        setStockHandoffBrokerEvaluations((current) => ({
          ...current,
          [handoffKey]: evaluations,
        }));
      }
      if (needsOrderNotes) {
        const response = await fetch(
          `${API_BASE_URL}/api/paper/sessions/${encodeURIComponent(sessionId)}/order-notes?limit=5`,
        );
        if (!response.ok) {
          const payload = await response.json().catch(() => null);
          throw new Error(payload?.detail ?? `Order notes failed with ${response.status}`);
        }
        const notes = (await response.json()) as PaperFillOrderNote[];
        setStockHandoffOrderNotes((current) => ({
          ...current,
          [handoffKey]: notes,
        }));
      }
      if (needsQualityGate && symbol) {
        const params = new URLSearchParams();
        params.set('symbol', symbol);
        params.set('limit', '200');
        const response = await fetch(
          `${API_BASE_URL}/api/paper/order-notes/quality-gate?${params.toString()}`,
        );
        if (!response.ok) {
          const payload = await response.json().catch(() => null);
          throw new Error(payload?.detail ?? `Quality gate failed with ${response.status}`);
        }
        const gate = (await response.json()) as PaperFillOrderNoteQualityGate;
        setStockHandoffQualityGates((current) => ({
          ...current,
          [handoffKey]: gate,
        }));
      }
    } catch (err) {
      setStockHandoffDetailError(
        err instanceof Error ? err.message : 'Could not load linked paper session details',
      );
    } finally {
      setStockHandoffDetailLoadingKey(null);
    }
  }, [
    stockHandoffBrokerEvaluations,
    stockHandoffExpandedKey,
    stockHandoffOrderNotes,
    stockHandoffQualityGates,
    stockHandoffSessions,
  ]);

  const saveReadinessDecision = React.useCallback(async () => {
    if (!liveReadiness) return;
    setOperatorDecisionLoading(true);
    setOperatorDecisionError(null);
    setOperatorDecisionMessage(null);
    try {
      const warningChecks = liveReadiness.checks
        .filter((check) => check.status === 'warn')
        .map((check) => check.id);
      const failedChecks = liveReadiness.checks
        .filter((check) => check.status === 'fail')
        .map((check) => check.id);
      const response = await fetch(`${API_BASE_URL}/api/operator/decisions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          decision_type: 'readiness_review',
          target_id: liveReadiness.checked_at,
          status: operatorDecisionStatus,
          note: operatorDecisionNote.trim() || null,
          context: {
            readiness_status: liveReadiness.status,
            readiness_score: liveReadiness.score,
            readiness_breakdowns: liveReadiness.breakdowns.map((breakdown) => ({
              id: breakdown.id,
              status: breakdown.status,
              score: breakdown.score,
              blocking_checks: breakdown.blocking_checks,
              warning_checks: breakdown.warning_checks,
            })),
            warning_checks: warningChecks,
            failed_checks: failedChecks,
            checked_at: liveReadiness.checked_at,
          },
        }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      const decision = (await response.json()) as OperatorDecisionRecord;
      setOperatorDecisionMessage(`Logged ${decision.status.replaceAll('_', ' ')} decision.`);
      setOperatorDecisionNote('');
      await refreshOperatorDecisions();
      await refreshOperatorJournal();
      await refreshCutoverChecklist();
    } catch (err) {
      setOperatorDecisionError(
        err instanceof Error ? err.message : 'Could not save readiness decision',
      );
    } finally {
      setOperatorDecisionLoading(false);
    }
  }, [
    liveReadiness,
    operatorDecisionNote,
    operatorDecisionStatus,
    refreshCutoverChecklist,
    refreshOperatorDecisions,
    refreshOperatorJournal,
  ]);

  const saveCutoverDecision = React.useCallback(async () => {
    if (!cutoverChecklist) return;
    setCutoverDecisionLoading(true);
    setCutoverError(null);
    setCutoverDecisionMessage(null);
    try {
      const blockingItems = cutoverChecklist.items
        .filter((item) => item.status === 'fail')
        .map((item) => item.id);
      const warningItems = cutoverChecklist.items
        .filter((item) => item.status === 'warn')
        .map((item) => item.id);
      const response = await fetch(`${API_BASE_URL}/api/operator/decisions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          decision_type: 'live_cutover',
          target_id: cutoverChecklist.checked_at,
          status: cutoverDecisionStatus,
          note: cutoverDecisionNote.trim() || null,
          context: {
            checklist_status: cutoverChecklist.status,
            checked_at: cutoverChecklist.checked_at,
            readiness_status: cutoverChecklist.readiness.status,
            readiness_score: cutoverChecklist.readiness.score,
            blocking_items: blockingItems,
            warning_items: warningItems,
          },
        }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
      }
      const decision = (await response.json()) as OperatorDecisionRecord;
      setCutoverDecisionMessage(
        `Logged ${decision.status.replaceAll('_', ' ')} live cutover decision.`,
      );
      setCutoverDecisionNote('');
      await refreshCutoverChecklist();
      await refreshOperatorDecisions();
      await refreshOperatorJournal();
    } catch (err) {
      setCutoverError(err instanceof Error ? err.message : 'Could not save cutover decision');
    } finally {
      setCutoverDecisionLoading(false);
    }
  }, [
    cutoverChecklist,
    cutoverDecisionNote,
    cutoverDecisionStatus,
    refreshCutoverChecklist,
    refreshOperatorDecisions,
    refreshOperatorJournal,
  ]);

  React.useEffect(() => {
    void runBacktest();
  }, []);

  React.useEffect(() => {
    void refreshTicker();

    const timer = window.setInterval(() => {
      void refreshTicker();
    }, 10000);

    return () => window.clearInterval(timer);
  }, [refreshTicker]);

  React.useEffect(() => {
    void refreshLiveSessions();
  }, [refreshLiveSessions]);

  React.useEffect(() => {
    refreshMarketDataState();
  }, [refreshMarketDataState]);

  React.useEffect(() => {
    void refreshPortfolioLibrary();
  }, [refreshPortfolioLibrary]);

  React.useEffect(() => {
    void refreshBotFleet();
  }, [refreshBotFleet]);

  React.useEffect(() => {
    void refreshAlertReview();
  }, [refreshAlertReview]);

  React.useEffect(() => {
    void refreshBacktestRuns();
  }, [refreshBacktestRuns]);

  React.useEffect(() => {
    void refreshExecutionState();
  }, [refreshExecutionState]);

  React.useEffect(() => {
    void refreshBrokerIntentHistory();
  }, [refreshBrokerIntentHistory]);

  React.useEffect(() => {
    void refreshPaperFillDriftAnalytics();
  }, [refreshPaperFillDriftAnalytics]);

  React.useEffect(() => {
    void refreshLiveReadiness();
  }, [refreshLiveReadiness]);

  React.useEffect(() => {
    void refreshCutoverChecklist();
  }, [refreshCutoverChecklist]);

  React.useEffect(() => {
    void refreshOperatorDecisions();
  }, [refreshOperatorDecisions]);

  React.useEffect(() => {
    void refreshOperatorJournal();
  }, [refreshOperatorJournal]);

  React.useEffect(() => {
    void refreshStockPaperHandoffs();
  }, [refreshStockPaperHandoffs]);

  React.useEffect(() => {
    void refreshStockBrokerExpansionReadiness();
  }, [refreshStockBrokerExpansionReadiness]);

  React.useEffect(() => {
    setSelectedCompareIds((current) =>
      current.filter((id) => backtestRuns.some((run) => run.id === id)),
    );
  }, [backtestRuns]);

  React.useEffect(() => {
    if (selectedCompareIds.length === 0) {
      comparisonFetches.current.clear();
      setComparisonDetails({});
      setComparisonLoadingIds([]);
      setComparisonError(null);
      return;
    }

    setComparisonDetails((current) => {
      const nextEntries = Object.entries(current).filter(([id]) => selectedCompareIds.includes(id));
      if (nextEntries.length === Object.keys(current).length) return current;
      return Object.fromEntries(nextEntries);
    });

    const missingIds = selectedCompareIds.filter(
      (id) => !comparisonDetails[id] && !comparisonFetches.current.has(id),
    );
    if (missingIds.length === 0) return;

    let cancelled = false;
    missingIds.forEach((id) => comparisonFetches.current.add(id));
    setComparisonError(null);
    setComparisonLoadingIds((current) => Array.from(new Set([...current, ...missingIds])));

    void Promise.all(
      missingIds.map(async (runId) => {
        const response = await fetch(`${API_BASE_URL}/api/backtests/runs/${runId}`);
        if (!response.ok) {
          const payload = await response.json().catch(() => null);
          throw new Error(payload?.detail ?? `Run ${runId} failed with ${response.status}`);
        }
        return (await response.json()) as BacktestResponse;
      }),
    )
      .then((payloads) => {
        if (cancelled) return;
        setComparisonDetails((current) => {
          const next = { ...current };
          payloads.forEach((payload) => {
            if (payload.id && selectedCompareIds.includes(payload.id)) {
              next[payload.id] = payload;
            }
          });
          return next;
        });
      })
      .catch((err) => {
        if (!cancelled) {
          setComparisonError(err instanceof Error ? err.message : 'Could not load comparison curves');
        }
      })
      .finally(() => {
        missingIds.forEach((id) => comparisonFetches.current.delete(id));
        if (!cancelled) {
          setComparisonLoadingIds((current) =>
            current.filter((id) => !missingIds.includes(id)),
          );
        }
      });

    return () => {
      cancelled = true;
    };
  }, [comparisonDetails, selectedCompareIds]);

  React.useEffect(() => {
    if (liveSession?.summary.status && liveSession.summary.status !== 'running') {
      setAutoReplay(false);
      setAutoTick(false);
    }
  }, [liveSession?.summary.status]);

  React.useEffect(() => {
    if (
      !autoReplay ||
      !liveSession ||
      liveSession.summary.status !== 'running' ||
      liveSession.mode === 'ticker'
    ) {
      return;
    }

    const timer = window.setInterval(() => {
      void advanceLiveReplay(1);
    }, autoReplayMs);

    return () => window.clearInterval(timer);
  }, [advanceLiveReplay, autoReplay, autoReplayMs, liveSession]);

  React.useEffect(() => {
    if (
      !autoTick ||
      !liveSession ||
      liveSession.summary.status !== 'running' ||
      liveSession.mode !== 'ticker'
    ) {
      return;
    }

    const timer = window.setInterval(() => {
      void advanceTickerPaper();
    }, autoReplayMs);

    return () => window.clearInterval(timer);
  }, [advanceTickerPaper, autoReplayMs, autoTick, liveSession]);

  const updateParam = (key: string, value: number) => {
    setSweepResult(null);
    setSweepError(null);
    setValidationResult(null);
    setValidationError(null);
    setWalkForwardResult(null);
    setWalkForwardError(null);
    setRequest((current) => ({
      ...current,
      params: {
        ...current.params,
        [key]: value,
      },
    }));
  };

  const switchStrategy = (strategy: Strategy) => {
    setSweepResult(null);
    setSweepError(null);
    setValidationResult(null);
    setValidationError(null);
    setWalkForwardResult(null);
    setWalkForwardError(null);
    setRequest((current) => ({
      ...current,
      strategy,
      params: defaultParamsForStrategy(strategy),
    }));
  };

  const updateRiskLimit = (key: keyof RiskLimits, value: number | boolean) => {
    setRiskLimits((current) => ({ ...current, [key]: value }));
  };

  const changeSource = (source: Source) => {
    const usdSource = isUsdSource(source);
    setRequest((current) => ({
      ...current,
      source,
      symbol: defaultSymbolForSource(source),
      timeframe: 'day',
      initial_cash: usdSource ? 100_000 : 1_000_000,
      fee_bps: usdSource ? 1 : 5,
      slippage_bps: usdSource ? 1 : 2,
    }));
    setRiskLimits((current) => ({
      ...current,
      max_order_notional: usdSource ? 25_000 : 500_000,
    }));
    setPaperSession(null);
    setLiveSession(null);
    setAutoReplay(false);
    setAutoTick(false);
    setOrderQueueMessage(null);
    const nextPortfolioSymbols = symbolsBySource[source].slice(0, 3);
    setPortfolioSymbols(nextPortfolioSymbols);
    setPortfolioWeights(equalWeights(nextPortfolioSymbols));
    setPortfolioResult(null);
    setPortfolioError(null);
    setSweepResult(null);
    setSweepError(null);
    setValidationResult(null);
    setValidationError(null);
    setWalkForwardResult(null);
    setWalkForwardError(null);
  };

  const togglePortfolioSymbol = (symbol: string) => {
    setPortfolioSymbols((current) => {
      const next = current.includes(symbol)
        ? current.filter((item) => item !== symbol)
        : [...current, symbol].slice(0, 8);
      setPortfolioWeights(equalWeights(next));
      return next;
    });
    setPortfolioError(null);
  };

  const updatePortfolioWeight = (symbol: string, value: number) => {
    setPortfolioWeights((current) => ({
      ...current,
      [symbol]: clamp(value, 1, 100),
    }));
    setPortfolioError(null);
  };

  const toggleCompareRun = React.useCallback((runId: string) => {
    setSelectedCompareIds((current) => {
      if (current.includes(runId)) {
        return current.filter((id) => id !== runId);
      }
      return [runId, ...current].slice(0, 3);
    });
  }, []);

  const changeMarketSymbol = React.useCallback((symbol: string) => {
    setRequest((current) => ({
      ...current,
      symbol,
    }));
    setMarketTicker(null);
    setTickerError(null);
  }, []);

  const comparisonRuns = selectedCompareIds
    .map((id) => backtestRuns.find((run) => run.id === id))
    .filter((run): run is BacktestRunSummary => Boolean(run));
  const currentCurrency = currencyForSource(result?.request.source ?? request.source);
  const currentSymbols = symbolsBySource[request.source];

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Quant Lab</p>
          <h1>퀀트 봇 운영 워크스페이스</h1>
        </div>
        <div className="topbar-actions">
          <button
            className="theme-toggle"
            onClick={() => setTheme((current) => (current === 'dark' ? 'light' : 'dark'))}
            title={theme === 'dark' ? '라이트 테마로 전환' : '다크 테마로 전환'}
            type="button"
          >
            {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
            {theme === 'dark' ? '라이트' : '다크'}
          </button>
          <div className="status-pill" title="실거래 주문은 별도 승인 게이트 전까지 잠겨 있습니다.">
            <ShieldCheck size={16} />
            {executionStatus?.adapter_ready ? '실거래 준비됨' : '실거래 잠금'}
          </div>
        </div>
      </header>

      <section className="workspace-grid">
        <section className="results-stack">
          <MarketTickerPanel
            ticker={marketTicker}
            error={tickerError}
            providers={providerStatuses}
            columnarStatus={columnarStatus}
            source={request.source}
            symbol={request.symbol}
            symbols={currentSymbols}
            onRefresh={refreshTicker}
            onSourceChange={changeSource}
            onSymbolChange={changeMarketSymbol}
          />
          <BotFleetPanel
            fleet={botFleet}
            lastRun={botFleetLastRun}
            loading={botFleetLoading}
            runningId={botFleetRunningId}
            message={botFleetMessage}
            error={botFleetError}
            backtestRuns={backtestRuns}
            onRefresh={refreshBotFleet}
            onCreateBot={createBotProfile}
            onRunDue={runDueBotFleet}
            onRunBot={runBotProfile}
            onPauseBot={pauseBotProfile}
            onResumeBot={resumeBotProfile}
            onDeleteBot={deleteBotProfile}
            onRunBacktest={runBotBacktest}
          />
          <DataProvidersPanel
            providers={providerStatuses}
            columnarStatus={columnarStatus}
            columnarExport={columnarExport}
            columnarLoading={columnarLoading}
            error={providerStatusError}
            columnarError={columnarError}
            onRefresh={refreshMarketDataState}
            onExportColumnar={exportColumnarCache}
          />
          <ExecutionPanel
            status={executionStatus}
            snapshot={privateSnapshot}
            audits={orderAudits}
            refreshing={executionRefreshing}
            updatedAt={executionUpdatedAt}
            onRefresh={refreshExecutionState}
          />
          <ExecutionSettingsPanel settings={executionSettings} />
          <PaperLiveAdapterPanel
            adapters={paperLiveAdapters}
            request={request}
            paperWatchlist={portfolioPaperWatchlist}
          />
          <BrokerReadinessPanel readiness={brokerReadiness} />
          <BrokerIntentSandboxPanel
            adapters={paperLiveAdapters.filter((adapter) => adapter.asset_class === 'stock_etf')}
            adapterId={brokerIntentAdapterId}
            linkedPaperSession={
              paperSession && isUsdSource(paperSession.request.source)
                ? paperSession
                : null
            }
            symbol={brokerIntentSymbol}
            side={brokerIntentSide}
            quantity={brokerIntentQuantity}
            orderType={brokerIntentOrderType}
            limitPrice={brokerIntentLimitPrice}
            referencePrice={brokerIntentReferencePrice}
            cashAvailable={brokerIntentCashAvailable}
            currentPosition={brokerIntentCurrentPosition}
            portfolioEquity={brokerIntentPortfolioEquity}
            feeBps={brokerIntentFeeBps}
            slippageBps={brokerIntentSlippageBps}
            liveConfirmation={brokerIntentLiveConfirmation}
            paperSubmitConfirmation={brokerIntentPaperSubmitConfirmation}
            loading={brokerIntentLoading}
            historyLoading={brokerIntentHistoryLoading}
            reportExporting={brokerIntentReportExporting}
            reconcilingId={brokerIntentReconcilingId}
            evaluation={brokerIntentEvaluation}
            reconciliation={brokerIntentReconciliation}
            history={brokerIntentHistory}
            error={brokerIntentError}
            onAdapterIdChange={changeBrokerIntentAdapter}
            onSymbolChange={setBrokerIntentSymbol}
            onSideChange={setBrokerIntentSide}
            onQuantityChange={setBrokerIntentQuantity}
            onOrderTypeChange={setBrokerIntentOrderType}
            onLimitPriceChange={setBrokerIntentLimitPrice}
            onReferencePriceChange={setBrokerIntentReferencePrice}
            onCashAvailableChange={setBrokerIntentCashAvailable}
            onCurrentPositionChange={setBrokerIntentCurrentPosition}
            onPortfolioEquityChange={setBrokerIntentPortfolioEquity}
            onFeeBpsChange={setBrokerIntentFeeBps}
            onSlippageBpsChange={setBrokerIntentSlippageBps}
            onLiveConfirmationChange={setBrokerIntentLiveConfirmation}
            onPaperSubmitConfirmationChange={setBrokerIntentPaperSubmitConfirmation}
            onEvaluate={evaluateBrokerIntent}
            onReconcile={reconcileBrokerIntentEvaluation}
            onRefreshHistory={refreshBrokerIntentHistory}
            onExportReport={exportBrokerIntentEvaluationReport}
          />
          <PaperFillDriftPanel
            analytics={paperFillDriftAnalytics}
            qualityGate={paperFillQualityGate}
            loading={paperFillDriftLoading}
            error={paperFillDriftError}
            onRefresh={refreshPaperFillDriftAnalytics}
          />
          <StockEtfBrokerExpansionPanel
            readiness={stockBrokerExpansionReadiness}
            loading={stockBrokerExpansionLoading}
            exporting={stockBrokerExpansionExporting}
            packageExportingId={stockBrokerExpansionPackageExportingId}
            preflightExportingId={stockBrokerExpansionPreflightExportingId}
            rehearsalExportingId={stockBrokerExpansionRehearsalExportingId}
            error={stockBrokerExpansionError}
            onRefresh={refreshStockBrokerExpansionReadiness}
            onExport={exportStockBrokerExpansionReport}
            onExportPackage={exportStockBrokerExpansionPackage}
            onExportPreflight={exportStockBrokerExpansionPreflight}
            onExportRehearsal={exportStockBrokerExpansionRehearsal}
          />
          <StockEtfHandoffPanel
            handoffs={stockPaperHandoffs}
            loading={stockHandoffLoading}
            exporting={stockHandoffExporting}
            reviewingId={stockHandoffReviewingId}
            expandedKey={stockHandoffExpandedKey}
            detailLoadingKey={stockHandoffDetailLoadingKey}
            sessionsById={stockHandoffSessions}
            brokerEvaluationsByKey={stockHandoffBrokerEvaluations}
            orderNotesByKey={stockHandoffOrderNotes}
            qualityGatesByKey={stockHandoffQualityGates}
            error={stockHandoffError}
            detailError={stockHandoffDetailError}
            message={stockHandoffMessage}
            onRefresh={refreshStockPaperHandoffs}
            onExport={exportStockPaperHandoffReport}
            onLogDecision={logStockPaperHandoffDecision}
            onToggleDetails={toggleStockPaperHandoffDetails}
          />
          <LiveReadinessPanel
            readiness={liveReadiness}
            decisions={operatorDecisions}
            decisionStatus={operatorDecisionStatus}
            decisionNote={operatorDecisionNote}
            decisionLoading={operatorDecisionLoading}
            decisionMessage={operatorDecisionMessage}
            loading={readinessLoading}
            error={readinessError ?? operatorDecisionError}
            onRefresh={refreshLiveReadiness}
            onDecisionStatusChange={setOperatorDecisionStatus}
            onDecisionNoteChange={setOperatorDecisionNote}
            onSaveDecision={saveReadinessDecision}
          />
          <CutoverChecklistPanel
            checklist={cutoverChecklist}
            decisionStatus={cutoverDecisionStatus}
            decisionNote={cutoverDecisionNote}
            decisionLoading={cutoverDecisionLoading}
            decisionMessage={cutoverDecisionMessage}
            runbookExporting={cutoverRunbookExporting}
            simulation={armingSimulation}
            simulationLoading={armingSimulationLoading}
            assumeSimulationDecisions={armingSimulationAssumeDecisions}
            loading={cutoverLoading}
            error={cutoverError}
            onRefresh={refreshCutoverChecklist}
            onExportRunbook={exportCutoverRunbook}
            onSimulateArming={simulateArming}
            onAssumeSimulationDecisionsChange={setArmingSimulationAssumeDecisions}
            onDecisionStatusChange={setCutoverDecisionStatus}
            onDecisionNoteChange={setCutoverDecisionNote}
            onSaveDecision={saveCutoverDecision}
          />
          <PostCutoverMonitorPanel
            monitor={postCutoverMonitor}
            loading={postCutoverMonitorLoading}
            exporting={closeoutReportExporting}
            error={postCutoverMonitorError}
            onRefresh={refreshPostCutoverMonitor}
            onExportCloseout={exportPostCutoverCloseoutReport}
          />
          <StrategyHealthTracePanel
            trace={strategyHealth}
            loading={strategyHealthLoading}
            exporting={strategyHealthReportExporting}
            drillExporting={cryptoDrillReportExporting}
            error={strategyHealthError}
            onRefresh={refreshStrategyHealth}
            onExport={exportStrategyHealthHandoffReport}
            onExportDrill={exportCryptoLiveBetaDrillReport}
          />
          <EnvironmentChecklistPanel
            settings={executionSettings}
            selfCheck={opsSelfCheck}
            providers={providerStatuses}
          />
          <AlertReviewPanel
            review={alertReview}
            filters={alertFilters}
            error={alertReviewError}
            onRefresh={refreshAlertReview}
            onFiltersChange={setAlertFilters}
            onAcknowledge={acknowledgeAlertReviewItem}
          />
          <OperationsJournalPanel
            decisions={operatorJournal}
            filters={operatorJournalFilters}
            loading={operatorJournalLoading}
            exporting={operatorJournalExporting}
            runbookLoadingId={runbookLoadingId}
            error={operatorJournalError}
            onRefresh={refreshOperatorJournal}
            onExport={exportOperatorJournalReport}
            onExportRunbook={exportDryRunRunbookById}
            onFiltersChange={setOperatorJournalFilters}
          />
          <OrderReviewPanel
            status={executionStatus}
            audits={orderAudits}
            prechecks={orderPrechecks}
            approvingId={approvalLoadingId}
            runbookLoadingId={runbookLoadingId}
            decisionLoading={operatorDecisionLoading}
            message={approvalMessage}
            onApprove={approveDryRunOrder}
            onExportRunbook={exportDryRunRunbook}
            onLogDecision={logDryRunApprovalDecision}
          />
          <Metrics metrics={result?.metrics} currency={currentCurrency} />
          <PortfolioResearchPanel
            result={portfolioResult}
            presets={portfolioPresets}
            scenarios={portfolioScenarios}
            scans={portfolioScans}
            watchlist={portfolioWatchlist}
            paperWatchlist={portfolioPaperWatchlist}
            symbols={currentSymbols}
            selectedSymbols={portfolioSymbols}
            weights={portfolioWeights}
            rebalanceFrequency={portfolioRebalance}
            loading={portfolioLoading}
            scenarioLoading={portfolioScenarioLoading}
            scanLoadingId={portfolioScanLoadingId}
            watchlistLoading={portfolioWatchlistLoading}
            paperWatchlistLoading={portfolioPaperWatchlistLoading}
            scenarioName={portfolioScenarioName}
            watchIntervalMinutes={portfolioWatchInterval}
            alertThresholds={portfolioAlertThresholds}
            scenarioMessage={portfolioScenarioMessage}
            scenarioError={portfolioScenarioError}
            currency={currentCurrency}
            onApplyPreset={(preset) => applyPortfolioRequest(preset.request, preset.name)}
            onApplyScenario={(scenario) => applyPortfolioRequest(scenario.request, scenario.name)}
            onOpenScan={openPortfolioScan}
            onScanScenario={scanPortfolioScenario}
            onAddWatchlist={addPortfolioWatchlistItem}
            onRunDueWatchlist={runDuePortfolioWatchlist}
            onDeleteWatchlist={deletePortfolioWatchlistItem}
            onAddPaperWatchlist={addPortfolioPaperWatchlistItem}
            onRunPaperWatchlist={runPortfolioPaperWatchlistItem}
            onRunDuePaperWatchlist={runDuePortfolioPaperWatchlist}
            onDeletePaperWatchlist={deletePortfolioPaperWatchlistItem}
            onPromotePaperWatchlist={promotePortfolioPaperWatchlistItem}
            onLogPaperWatchlistDecision={logPaperWatchlistDecision}
            onToggleSymbol={togglePortfolioSymbol}
            onWeightChange={updatePortfolioWeight}
            onRebalanceChange={setPortfolioRebalance}
            onScenarioNameChange={setPortfolioScenarioName}
            onWatchIntervalChange={(value) => setPortfolioWatchInterval(clamp(value, 1, 1440))}
            onAlertThresholdChange={updatePortfolioAlertThreshold}
            onSaveScenario={savePortfolioScenario}
            onDeleteScenario={deletePortfolioScenario}
            onRun={runPortfolioResearch}
          />
          <BacktestHistoryPanel
            runs={backtestRuns}
            activeRunId={result?.id ?? null}
            selectedCompareIds={selectedCompareIds}
            loadingRunId={loadingRunId}
            onLoad={loadBacktestRun}
            onToggleCompare={toggleCompareRun}
          />
          <BacktestComparisonPanel
            runs={comparisonRuns}
            detailsById={comparisonDetails}
            loadingIds={comparisonLoadingIds}
            error={comparisonError}
          />
          <PaperPanel
            session={liveSession ?? paperSession}
            sessions={liveSessions}
            currency={currencyForSource((liveSession ?? paperSession)?.request.source ?? request.source)}
            queueLoading={orderQueueLoading}
            queueMessage={orderQueueMessage}
            onQueueOrderIntents={queueDryRunOrderIntents}
          />
          <section className="panel chart-panel">
            <div className="panel-title">
              <TrendingUp size={18} />
              <h2>Equity curve</h2>
            </div>
            <EquityChart
              points={result?.equity_curve ?? []}
              currency={currentCurrency}
              request={result?.request}
              metrics={result?.metrics}
            />
          </section>
          <TradesTable trades={result?.trades ?? []} currency={currentCurrency} />
        </section>
      </section>
    </main>
  );
}

function MarketTickerPanel({
  ticker,
  error,
  providers,
  columnarStatus,
  source,
  symbol,
  symbols,
  onRefresh,
  onSourceChange,
  onSymbolChange,
}: {
  ticker: MarketTicker | null;
  error: string | null;
  providers: MarketDataProviderStatus[];
  columnarStatus: MarketDataColumnarStatus | null;
  source: Source;
  symbol: string;
  symbols: string[];
  onRefresh: () => void;
  onSourceChange: (source: Source) => void;
  onSymbolChange: (symbol: string) => void;
}) {
  const activeTicker = ticker?.source === source && ticker.symbol === symbol ? ticker : null;
  const changeClass = activeTicker
    ? activeTicker.change_pct < 0
      ? 'ticker-negative'
      : 'ticker-positive'
    : 'ticker-neutral';
  const provider = providers.find((item) => item.source === source) ?? null;
  const providerState = provider?.available ? 'ready' : provider?.configured ? 'blocked' : 'missing';
  const providerLabel = provider
    ? provider.available
      ? '데이터 정상'
      : provider.configured
        ? '확인 필요'
        : '설정 필요'
    : '대기 중';
  const marketSourceLabel = sourceLabelKo(source);
  const volumeLabel = activeTicker?.quote_volume_24h ? '거래대금' : '거래량';
  const volumeDisplay = tickerVolumeDisplay(activeTicker);

  return (
    <section className="panel ticker-panel">
      <div className="panel-title">
        <Activity size={18} />
        <h2>마켓 데이터</h2>
        <button className="icon-button" onClick={onRefresh} title="마켓 데이터 새로고침" type="button">
          <RefreshCcw size={15} />
        </button>
      </div>
      <div className="ticker-status-row">
        <span className="ticker-source">{marketSourceLabel}</span>
        <span className={`market-data-state market-data-${providerState}`}>{providerLabel}</span>
        <span className={`market-data-state market-data-${columnarStatus?.enabled ? 'ready' : 'missing'}`}>
          캐시 {columnarStatus?.enabled ? `${columnarStatus.rows.toLocaleString()}행` : '꺼짐'}
        </span>
      </div>
      <div className="ticker-control-row">
        <label className="ticker-field">
          <span>데이터 소스</span>
          <select value={source} onChange={(event) => onSourceChange(event.target.value as Source)}>
            {sourceOptions.map((option) => (
              <option value={option.value} key={option.value}>
                {sourceLabelKo(option.value)}
              </option>
            ))}
          </select>
        </label>
        <label className="ticker-field">
          <span>종목</span>
          <select value={symbol} onChange={(event) => onSymbolChange(event.target.value)}>
            {symbols.map((item) => (
              <option value={item} key={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
        <button className="secondary-button ticker-refresh-button" onClick={onRefresh} type="button">
          <RefreshCcw size={15} />
          시세 확인
        </button>
      </div>
      <div className="ticker-grid">
        <div>
          <span>종목</span>
          <strong>{activeTicker?.symbol ?? symbol}</strong>
        </div>
        <div>
          <span>현재가</span>
          <strong>{money(activeTicker?.price, currencyForSource(source))}</strong>
        </div>
        <div>
          <span>24H 변동</span>
          <strong className={changeClass}>{percent(activeTicker?.change_pct)}</strong>
        </div>
        <div>
          <span>갱신 시각</span>
          <strong>{activeTicker ? shortDateTime(activeTicker.timestamp) : '-'}</strong>
        </div>
        <div>
          <span>{volumeLabel}</span>
          <strong>{volumeDisplay}</strong>
        </div>
        <div>
          <span>최근 수집</span>
          <strong>{provider?.last_success_at ? shortDateTime(provider.last_success_at) : '-'}</strong>
        </div>
      </div>
      {error ? <p className="error-message">{error}</p> : null}
    </section>
  );
}

type DiceBearStyle = Parameters<typeof createAvatar>[0];

const BOT_AVATAR_COLLECTION: Record<BotAvatarStyle, DiceBearStyle> = {
  pixel_art: pixelArt as DiceBearStyle,
  pixel_art_neutral: pixelArtNeutral as DiceBearStyle,
  bottts: bottts as DiceBearStyle,
  identicon: identicon as DiceBearStyle,
};

const BOT_AVATAR_FALLBACK: Record<BotOperatingStyle, BotAvatar> = {
  trend_following: { seed: 'trend-following', style: 'pixel_art', accent_color: '#2f9b73' },
  mean_reversion: { seed: 'mean-reversion', style: 'pixel_art_neutral', accent_color: '#5d84be' },
  breakout: { seed: 'breakout', style: 'bottts', accent_color: '#d59a25' },
  portfolio_rotation: { seed: 'portfolio-rotation', style: 'identicon', accent_color: '#6d76d9' },
  defensive_monitor: { seed: 'defensive-monitor', style: 'identicon', accent_color: '#64748b' },
  custom: { seed: 'custom-bot', style: 'pixel_art', accent_color: '#8b5cf6' },
};

function BotProfileAvatar({ profile, status }: { profile: BotProfile; status: BotVisualStatus }) {
  const accentColor = normalizeBotAvatarColor(
    profile.avatar?.accent_color ?? BOT_AVATAR_FALLBACK[profile.operating_style].accent_color,
  );
  const imageUri = React.useMemo(() => botAvatarDataUri(profile), [profile]);

  return (
    <div
      className={`bot-avatar-frame ${botAvatarStatusClass(status)}`}
      style={{ '--bot-avatar-accent': accentColor } as React.CSSProperties}
      title={`${profile.name} avatar`}
    >
      <img className="bot-avatar-image" src={imageUri} alt={`${profile.name} avatar`} />
    </div>
  );
}

function botAvatarDataUri(profile: BotProfile) {
  const fallback = BOT_AVATAR_FALLBACK[profile.operating_style];
  const avatar = profile.avatar ?? fallback;
  const style = BOT_AVATAR_COLLECTION[avatar.style] ? avatar.style : fallback.style;
  const seed = avatar.seed?.trim() || `${profile.operating_style}:${profile.name}:${profile.id}`;
  const accent = normalizeBotAvatarColor(avatar.accent_color || fallback.accent_color).replace('#', '');

  return createAvatar(BOT_AVATAR_COLLECTION[style], {
    seed,
    backgroundColor: [accent],
    backgroundType: ['solid'],
    radius: 8,
    size: 64,
  }).toDataUri();
}

function normalizeBotAvatarColor(color: string) {
  return /^#[0-9a-f]{6}$/i.test(color) ? color : '#2f9b73';
}

function BotFleetPanel({
  fleet,
  lastRun,
  loading,
  runningId,
  message,
  error,
  backtestRuns,
  onRefresh,
  onCreateBot,
  onRunDue,
  onRunBot,
  onPauseBot,
  onResumeBot,
  onDeleteBot,
  onRunBacktest,
}: {
  fleet: BotFleetStatus | null;
  lastRun: BotFleetRun | null;
  loading: boolean;
  runningId: string | null;
  message: string | null;
  error: string | null;
  backtestRuns: BacktestRunSummary[];
  onRefresh: () => void;
  onCreateBot: (profile: BotProfileCreate) => Promise<BotProfile>;
  onRunDue: () => void;
  onRunBot: (botId: string) => void | Promise<void>;
  onPauseBot: (botId: string) => void;
  onResumeBot: (botId: string) => void;
  onDeleteBot: (botId: string) => void;
  onRunBacktest: (profile: BotProfile) => Promise<BacktestResponse>;
}) {
  const profiles = fleet?.profiles ?? [];
  const summary = fleet?.summary;
  const latestRunByBot = new Map((fleet?.recent_runs ?? []).map((run) => [run.bot_id, run]));
  const [setupOpen, setSetupOpen] = React.useState(false);
  const [selectedPresetId, setSelectedPresetId] = React.useState(botPresets[0].id);
  const [draft, setDraft] = React.useState<BotProfileCreate>(() => botProfileFromPreset(botPresets[0]));
  const [saving, setSaving] = React.useState(false);
  const [deleteTarget, setDeleteTarget] = React.useState<BotProfile | null>(null);
  const [selectedProfileId, setSelectedProfileId] = React.useState<string | null>(null);
  const [detailOpen, setDetailOpen] = React.useState(false);
  const [detailTab, setDetailTab] = React.useState<BotDetailTab>('overview');
  const [statusFilter, setStatusFilter] = React.useState<BotFleetStatusFilter>('all');
  const [sortKey, setSortKey] = React.useState<BotFleetSortKey>('priority');
  const [backtestResultsByBot, setBacktestResultsByBot] = React.useState<Record<string, BacktestResponse>>({});
  const [backtestLoadingId, setBacktestLoadingId] = React.useState<string | null>(null);
  const [backtestError, setBacktestError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (selectedProfileId && !profiles.some((profile) => profile.id === selectedProfileId)) {
      setSelectedProfileId(null);
      setDetailOpen(false);
    }
  }, [profiles, selectedProfileId]);

  const openDetail = React.useCallback((profile: BotProfile, nextTab: BotDetailTab = 'overview') => {
    setSelectedProfileId(profile.id);
    setDetailTab(nextTab);
    setBacktestError(null);
    setDetailOpen(true);
  }, []);

  const applyPreset = React.useCallback((preset: BotPreset) => {
    setSelectedPresetId(preset.id);
    setDraft(botProfileFromPreset(preset));
  }, []);

  const openSetup = React.useCallback(() => {
    applyPreset(botPresets[0]);
    setSetupOpen(true);
  }, [applyPreset]);

  const updateDraftRequest = React.useCallback((updates: Partial<BacktestRequest & { risk_limits: RiskLimits }>) => {
    setDraft((current) => ({
      ...current,
      request: {
        ...current.request,
        ...updates,
      },
    }));
  }, []);

  const changeDraftSource = React.useCallback((source: Source) => {
    const usdSource = isUsdSource(source);
    updateDraftRequest({
      source,
      symbol: defaultSymbolForSource(source),
      initial_cash: usdSource ? 100_000 : 1_000_000,
      fee_bps: usdSource ? 1 : 5,
      slippage_bps: usdSource ? 1 : 2,
      risk_limits: {
        ...draft.request.risk_limits,
        max_order_notional: usdSource ? 25_000 : 500_000,
      },
    });
  }, [draft.request.risk_limits, updateDraftRequest]);

  const switchDraftStrategy = React.useCallback((strategy: Strategy) => {
    updateDraftRequest({
      strategy,
      params: defaultParamsForStrategy(strategy),
    });
  }, [updateDraftRequest]);

  const updateDraftParam = React.useCallback((key: string, value: number) => {
    updateDraftRequest({
      params: {
        ...draft.request.params,
        [key]: value,
      },
    });
  }, [draft.request.params, updateDraftRequest]);

  const updateDraftRisk = React.useCallback((key: keyof RiskLimits, value: number | boolean) => {
    updateDraftRequest({
      risk_limits: {
        ...draft.request.risk_limits,
        [key]: value,
      },
    });
  }, [draft.request.risk_limits, updateDraftRequest]);

  const submitDraft = React.useCallback(async (runAfterSave: boolean) => {
    setSaving(true);
    try {
      const created = await onCreateBot(draft);
      setSelectedProfileId(created.id);
      setDetailTab('overview');
      setSetupOpen(false);
      if (runAfterSave) {
        await onRunBot(created.id);
      }
    } finally {
      setSaving(false);
    }
  }, [draft, onCreateBot, onRunBot]);

  const deleteTargetRun = deleteTarget ? latestRunByBot.get(deleteTarget.id) : undefined;
  const deleteTargetHasPosition = (deleteTargetRun?.session?.summary.open_position_pct ?? 0) > 0;
  const selectedProfile = selectedProfileId
    ? profiles.find((profile) => profile.id === selectedProfileId) ?? null
    : null;
  const selectedLatestRun = selectedProfile ? latestRunByBot.get(selectedProfile.id) : undefined;
  const selectedBacktestResult = selectedProfile ? backtestResultsByBot[selectedProfile.id] : undefined;

  const runSelectedBacktest = React.useCallback(async () => {
    if (!selectedProfile) return;
    setBacktestLoadingId(selectedProfile.id);
    setBacktestError(null);
    try {
      const payload = await onRunBacktest(selectedProfile);
      setBacktestResultsByBot((current) => ({ ...current, [selectedProfile.id]: payload }));
      setDetailTab('backtest');
    } catch (err) {
      setBacktestError(err instanceof Error ? err.message : '봇 백테스트를 실행하지 못했습니다.');
    } finally {
      setBacktestLoadingId(null);
    }
  }, [onRunBacktest, selectedProfile]);

  const botRows = profiles.map((profile) => {
    const latest = latestRunByBot.get(profile.id);
    const status = latest?.status ?? profile.last_status ?? 'idle';
    const visualStatus: BotVisualStatus = runningId === profile.id ? 'running' : profile.active ? status : 'paused';
    const currency = currencyForSource(profile.request.source);
    const capital = latest?.session?.summary.final_equity ?? profile.request.initial_cash;
    const returnPct = latest?.session?.summary.total_return_pct;
    return {
      profile,
      latest,
      visualStatus,
      currency,
      capital,
      returnPct,
    };
  });
  const visibleBotRows = botRows
    .filter(({ profile, visualStatus }) => {
      if (statusFilter === 'all') return true;
      if (statusFilter === 'active') return profile.active;
      if (statusFilter === 'paused') return !profile.active;
      if (statusFilter === 'running') return visualStatus === 'running';
      if (statusFilter === 'completed') return visualStatus === 'completed';
      return profile.last_error || ['halted', 'blocked', 'error'].includes(visualStatus);
    })
    .sort((left, right) => {
      if (sortKey === 'return') {
        return (right.returnPct ?? Number.NEGATIVE_INFINITY) - (left.returnPct ?? Number.NEGATIVE_INFINITY);
      }
      if (sortKey === 'capital') {
        return right.capital - left.capital;
      }
      if (sortKey === 'schedule') {
        return new Date(left.profile.next_run_at).getTime() - new Date(right.profile.next_run_at).getTime();
      }
      if (sortKey === 'name') {
        return left.profile.name.localeCompare(right.profile.name);
      }
      return right.profile.priority - left.profile.priority || left.profile.name.localeCompare(right.profile.name);
    });
  const activeFilterLabel = botFleetStatusFilterLabel(statusFilter);

  return (
    <section className="panel bot-fleet-panel">
      <div className="panel-title">
        <Radio size={18} />
        <h2>봇 운영</h2>
        <button className="icon-button" onClick={onRefresh} title="봇 목록 새로고침">
          <RefreshCcw size={15} />
        </button>
      </div>

      <div className="bot-fleet-summary">
        <div>
          <span>활성 봇</span>
          <strong>{summary?.active_bots ?? 0}/{summary?.total_bots ?? 0}</strong>
        </div>
        <div>
          <span>실행 대기</span>
          <strong>{summary?.due_bots ?? 0}</strong>
        </div>
        <div>
          <span>열린 포지션</span>
          <strong>{summary?.open_position_bots ?? 0}</strong>
        </div>
        <div>
          <span>드라이런 주문</span>
          <strong>{summary?.recent_dry_run_intents ?? 0}</strong>
        </div>
      </div>

      <div className="bot-fleet-actions">
        <button className="secondary-button compact-action" onClick={openSetup} disabled={loading || saving}>
          <Plus size={15} />
          봇 추가
        </button>
        <button className="run-button compact-action" onClick={onRunDue} disabled={loading || profiles.length === 0}>
          <Play size={15} />
          실행 대상 실행
        </button>
      </div>

      <div className="bot-fleet-toolbar">
        <div className="segmented-filter" role="tablist" aria-label="봇 상태 필터">
          {(['all', 'active', 'running', 'paused', 'completed', 'attention'] as BotFleetStatusFilter[]).map((filter) => (
            <button
              className={statusFilter === filter ? 'active' : ''}
              key={filter}
              onClick={() => setStatusFilter(filter)}
              role="tab"
              aria-selected={statusFilter === filter}
              type="button"
            >
              {botFleetStatusFilterLabel(filter)}
            </button>
          ))}
          <label className="compact-select">
            <span>정렬</span>
            <select value={sortKey} onChange={(event) => setSortKey(event.target.value as BotFleetSortKey)}>
              <option value="priority">우선순위</option>
              <option value="return">수익률</option>
              <option value="capital">운용자본</option>
              <option value="schedule">다음 실행</option>
              <option value="name">이름</option>
            </select>
          </label>
        </div>
        <span className="bot-fleet-count">{visibleBotRows.length}/{profiles.length}개</span>
      </div>

      <div className="bot-fleet-grid">
        {profiles.length > 0 ? (
          <div className="bot-fleet-header">
            <span>봇 정보</span>
            <span>전략</span>
            <span>모드</span>
            <span>운용자본</span>
            <span>수익률</span>
            <span>스케줄</span>
            <span>상태</span>
          </div>
        ) : null}
        {visibleBotRows.length > 0 ? (
          visibleBotRows.map(({ profile, visualStatus, currency, capital, returnPct }) => {
            return (
              <div
                className={`bot-fleet-row${detailOpen && selectedProfileId === profile.id ? ' bot-fleet-row-selected' : ''}`}
                key={profile.id}
              >
                <div className="bot-fleet-row-grid">
                  <div className="bot-fleet-main">
                    <BotProfileAvatar profile={profile} status={visualStatus} />
                    <div className="bot-fleet-title">
                      <strong>{profile.name}</strong>
                      <span>{botStyleLabel(profile.operating_style)} · {profile.request.symbol}</span>
                    </div>
                  </div>
                  <span>{strategyLabelKo(profile.request.strategy)}</span>
                  <span className="value-exposure">{botExecutionLabel(profile.execution_mode)}</span>
                  <span className="value-capital">{money(capital, currency)}</span>
                  <span className={valueToneClass(returnPct)}>{percent(returnPct)}</span>
                  <span className={profile.active ? 'value-neutral' : 'value-paused'}>
                    {profile.active ? `다음 ${shortDateTime(profile.next_run_at)}` : '일시정지'}
                  </span>
                  <span className={botStatusClass(visualStatus)}>{botVisualStatusLabel(visualStatus)}</span>
                </div>
                {profile.last_error ? <p className="warning-message">{profile.last_error}</p> : null}
                <div className="bot-fleet-row-actions">
                  <button
                    className="secondary-button compact-action"
                    onClick={() => openDetail(profile)}
                    disabled={runningId === profile.id}
                  >
                    <FileText size={14} />
                    상세
                  </button>
                  <button
                    className="secondary-button compact-action"
                    onClick={() => onRunBot(profile.id)}
                    disabled={runningId === profile.id}
                  >
                    <Play size={14} />
                    실행
                  </button>
                  {profile.active ? (
                    <button
                      className="secondary-button compact-action"
                      onClick={() => onPauseBot(profile.id)}
                      disabled={runningId === profile.id}
                    >
                      <Pause size={14} />
                      일시정지
                    </button>
                  ) : (
                    <button
                      className="secondary-button compact-action"
                      onClick={() => onResumeBot(profile.id)}
                      disabled={runningId === profile.id}
                    >
                      <Play size={14} />
                      재개
                    </button>
                  )}
                  <button
                    className="icon-button danger-icon"
                    onClick={() => setDeleteTarget(profile)}
                    disabled={runningId === profile.id}
                    title={`${profile.name} 삭제`}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            );
          })
        ) : profiles.length > 0 ? (
          <div className="readiness-empty">{activeFilterLabel} 조건에 맞는 봇이 없습니다.</div>
        ) : (
          <div className="readiness-empty">아직 봇이 없습니다. 봇 추가로 전략 프리셋을 선택하세요.</div>
        )}
      </div>

      {lastRun ? (
        <div className="bot-run-strip">
          <span>마지막 실행</span>
          <strong>{lastRun.runs.length}개 봇</strong>
          <span>{shortDateTime(lastRun.checked_at)}</span>
        </div>
      ) : null}
      {message ? <p className="success-message">{message}</p> : null}
      {error ? <p className="error-message">{error}</p> : null}

      {detailOpen && selectedProfile ? (
        <div className="modal-backdrop" role="presentation">
          <div className="bot-detail-modal" role="dialog" aria-modal="true" aria-labelledby="bot-detail-title">
            <div className="modal-title">
              <div>
                <span>봇 상세</span>
                <h3 id="bot-detail-title">{selectedProfile.name}</h3>
              </div>
              <button
                className="icon-button"
                onClick={() => setDetailOpen(false)}
                title="닫기"
                type="button"
              >
                <X size={16} />
              </button>
            </div>
            <BotFleetDetailPanel
              profile={selectedProfile}
              latestRun={selectedLatestRun}
              tab={detailTab}
              backtestRuns={backtestRuns}
              backtestResult={selectedBacktestResult}
              backtestLoading={backtestLoadingId === selectedProfile.id}
              backtestError={backtestError}
              onTabChange={setDetailTab}
              onRunBacktest={() => void runSelectedBacktest()}
            />
          </div>
        </div>
      ) : null}

      {setupOpen ? (
        <div className="modal-backdrop" role="presentation">
          <div className="setup-modal" role="dialog" aria-modal="true" aria-labelledby="bot-setup-title">
            <div className="modal-title">
              <div>
                <span>봇 설정</span>
                <h3 id="bot-setup-title">봇 실행 설정</h3>
              </div>
              <button className="icon-button" onClick={() => setSetupOpen(false)} title="닫기">
                <X size={16} />
              </button>
            </div>

            <div className="preset-grid">
              {botPresets.map((preset) => (
                <button
                  className={`preset-card ${selectedPresetId === preset.id ? 'preset-card-active' : ''}`}
                  key={preset.id}
                  onClick={() => applyPreset(preset)}
                  type="button"
                >
                  <strong>{preset.name}</strong>
                  <span>{preset.persona}</span>
                </button>
              ))}
            </div>

            <div className="setup-form-grid">
              <label>
                봇 이름
                <input
                  value={draft.name}
                  onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))}
                />
              </label>
              <label>
                운영 성격
                <select
                  value={draft.operating_style}
                  onChange={(event) =>
                    setDraft((current) => ({ ...current, operating_style: event.target.value as BotOperatingStyle }))
                  }
                >
                  {(['trend_following', 'mean_reversion', 'breakout', 'portfolio_rotation', 'defensive_monitor', 'custom'] as BotOperatingStyle[]).map((style) => (
                    <option value={style} key={style}>{botStyleLabel(style)}</option>
                  ))}
                </select>
              </label>
              <label className="setup-form-wide">
                봇 설명
                <textarea
                  value={draft.description}
                  onChange={(event) => setDraft((current) => ({ ...current, description: event.target.value }))}
                />
              </label>
            </div>

            <div className="setup-form-grid">
              <label>
                데이터 소스
                <select
                  value={draft.request.source}
                  onChange={(event) => changeDraftSource(event.target.value as Source)}
                >
                  {sourceOptions.map((option) => (
                    <option value={option.value} key={option.value}>{sourceLabelKo(option.value)}</option>
                  ))}
                </select>
              </label>
              <label>
                종목
                <select
                  value={draft.request.symbol}
                  onChange={(event) => updateDraftRequest({ symbol: event.target.value })}
                >
                  {symbolsBySource[draft.request.source].map((symbol) => (
                    <option value={symbol} key={symbol}>{symbol}</option>
                  ))}
                </select>
              </label>
              <label>
                전략
                <select
                  value={draft.request.strategy}
                  onChange={(event) => switchDraftStrategy(event.target.value as Strategy)}
                >
                  <option value="sma_crossover">{strategyLabelKo('sma_crossover')}</option>
                  <option value="donchian_breakout">{strategyLabelKo('donchian_breakout')}</option>
                  <option value="rsi_mean_reversion">{strategyLabelKo('rsi_mean_reversion')}</option>
                </select>
              </label>
              <label>
                실행 모드
                <select
                  value={draft.execution_mode}
                  onChange={(event) =>
                    setDraft((current) => ({ ...current, execution_mode: event.target.value as BotExecutionMode }))
                  }
                >
                  <option value="paper">{botExecutionLabel('paper')}</option>
                  <option value="dry_run">{botExecutionLabel('dry_run')}</option>
                </select>
              </label>
            </div>

            <div className="setup-form-grid">
              <label>
                초기 자본
                <input
                  type="number"
                  min="10000"
                  step="10000"
                  value={draft.request.initial_cash}
                  onChange={(event) => updateDraftRequest({ initial_cash: Number(event.target.value) })}
                />
              </label>
              <label>
                실행 주기(분)
                <input
                  type="number"
                  min="1"
                  max="1440"
                  value={draft.interval_minutes}
                  onChange={(event) =>
                    setDraft((current) => ({ ...current, interval_minutes: Number(event.target.value) }))
                  }
                />
              </label>
              <label>
                캔들 수
                <input
                  type="number"
                  min="50"
                  max="400"
                  value={draft.request.candle_limit}
                  onChange={(event) => updateDraftRequest({ candle_limit: Number(event.target.value) })}
                />
              </label>
              <label>
                우선순위
                <input
                  type="number"
                  min="1"
                  max="100"
                  value={draft.priority}
                  onChange={(event) =>
                    setDraft((current) => ({ ...current, priority: Number(event.target.value) }))
                  }
                />
              </label>
            </div>

            <div className="setup-form-grid">
              {draft.request.strategy === 'sma_crossover' ? (
                <>
                  <label>
                    빠른 SMA
                    <input
                      type="number"
                      min="2"
                      value={draft.request.params.fast_window}
                      onChange={(event) => updateDraftParam('fast_window', Number(event.target.value))}
                    />
                  </label>
                  <label>
                    느린 SMA
                    <input
                      type="number"
                      min="3"
                      value={draft.request.params.slow_window}
                      onChange={(event) => updateDraftParam('slow_window', Number(event.target.value))}
                    />
                  </label>
                </>
              ) : draft.request.strategy === 'donchian_breakout' ? (
                <>
                  <label>
                    돌파 기준
                    <input
                      type="number"
                      min="3"
                      value={draft.request.params.lookback}
                      onChange={(event) => updateDraftParam('lookback', Number(event.target.value))}
                    />
                  </label>
                  <label>
                    청산 기준
                    <input
                      type="number"
                      min="3"
                      value={draft.request.params.exit_lookback}
                      onChange={(event) => updateDraftParam('exit_lookback', Number(event.target.value))}
                    />
                  </label>
                </>
              ) : (
                <>
                  <label>
                    RSI 기간
                    <input
                      type="number"
                      min="2"
                      value={draft.request.params.rsi_window}
                      onChange={(event) => updateDraftParam('rsi_window', Number(event.target.value))}
                    />
                  </label>
                  <label>
                    매수 기준
                    <input
                      type="number"
                      min="1"
                      max="98"
                      value={draft.request.params.buy_below}
                      onChange={(event) => updateDraftParam('buy_below', Number(event.target.value))}
                    />
                  </label>
                  <label>
                    매도 기준
                    <input
                      type="number"
                      min="2"
                      max="99"
                      value={draft.request.params.sell_above}
                      onChange={(event) => updateDraftParam('sell_above', Number(event.target.value))}
                    />
                  </label>
                </>
              )}
            </div>

            <div className="setup-form-grid">
              <label>
                최대 포지션 %
                <input
                  type="number"
                  min="0"
                  max="100"
                  value={draft.request.risk_limits.max_position_pct}
                  onChange={(event) => updateDraftRisk('max_position_pct', Number(event.target.value))}
                />
              </label>
              <label>
                주문당 최대 금액
                <input
                  type="number"
                  min="1000"
                  step="10000"
                  value={draft.request.risk_limits.max_order_notional}
                  onChange={(event) => updateDraftRisk('max_order_notional', Number(event.target.value))}
                />
              </label>
              <label>
                최대 진입 수
                <input
                  type="number"
                  min="0"
                  value={draft.request.risk_limits.max_orders}
                  onChange={(event) => updateDraftRisk('max_orders', Number(event.target.value))}
                />
              </label>
              <label>
                손실 중단 %
                <input
                  type="number"
                  min="0"
                  max="100"
                  value={draft.request.risk_limits.max_session_loss_pct}
                  onChange={(event) => updateDraftRisk('max_session_loss_pct', Number(event.target.value))}
                />
              </label>
            </div>

            <div className="setup-inline-options">
              <label className="toggle-row">
                <input
                  type="checkbox"
                  checked={draft.active}
                  onChange={(event) => setDraft((current) => ({ ...current, active: event.target.checked }))}
                />
                저장 후 활성화
              </label>
              <label className="toggle-row">
                <input
                  type="checkbox"
                  checked={draft.request.risk_limits.kill_switch}
                  onChange={(event) => updateDraftRisk('kill_switch', event.target.checked)}
                />
                킬 스위치
              </label>
              <label>
                충돌 정책
                <select
                  value={draft.conflict_policy}
                  onChange={(event) =>
                    setDraft((current) => ({ ...current, conflict_policy: event.target.value as BotConflictPolicy }))
                  }
                >
                  <option value="allow">{botConflictPolicyLabel('allow')}</option>
                  <option value="block_same_symbol">{botConflictPolicyLabel('block_same_symbol')}</option>
                </select>
              </label>
            </div>

            <div className="modal-actions">
              <button className="secondary-button compact-action" onClick={() => setSetupOpen(false)} type="button">
                취소
              </button>
              <button className="secondary-button compact-action" onClick={() => void submitDraft(false)} disabled={loading || saving}>
                <Save size={15} />
                {saving ? '저장 중' : '저장'}
              </button>
              <button className="run-button compact-action" onClick={() => void submitDraft(true)} disabled={loading || saving}>
                <Play size={15} />
                저장 후 실행
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {deleteTarget ? (
        <div className="modal-backdrop" role="presentation">
          <div className="confirm-modal" role="dialog" aria-modal="true" aria-labelledby="bot-delete-title">
            <div className="modal-title">
              <div>
                <span>삭제 확인</span>
                <h3 id="bot-delete-title">{deleteTarget.name} 봇을 삭제할까요?</h3>
              </div>
              <button className="icon-button" onClick={() => setDeleteTarget(null)} title="닫기">
                <X size={16} />
              </button>
            </div>
            <p>
              봇 프로필은 삭제되지만 이미 저장된 실행 기록은 유지됩니다.
              {deleteTarget.active ? ' 활성 봇이므로 예약 실행도 중단됩니다.' : ''}
              {deleteTargetHasPosition ? ' 최근 paper position이 열려 있어 삭제 전 확인이 필요합니다.' : ''}
            </p>
            <div className="modal-actions">
              <button className="secondary-button compact-action" onClick={() => setDeleteTarget(null)}>
                취소
              </button>
              <button
                className="stop-button compact-action"
                onClick={() => {
                  const botId = deleteTarget.id;
                  setDeleteTarget(null);
                  onDeleteBot(botId);
                }}
                disabled={runningId === deleteTarget.id}
              >
                <Trash2 size={15} />
                삭제
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function BotFleetDetailPanel({
  profile,
  latestRun,
  tab,
  backtestRuns,
  backtestResult,
  backtestLoading,
  backtestError,
  onTabChange,
  onRunBacktest,
}: {
  profile: BotProfile;
  latestRun?: BotRun;
  tab: BotDetailTab;
  backtestRuns: BacktestRunSummary[];
  backtestResult?: BacktestResponse;
  backtestLoading: boolean;
  backtestError: string | null;
  onTabChange: (tab: BotDetailTab) => void;
  onRunBacktest: () => void;
}) {
  const currency = currencyForSource(profile.request.source);
  const matchingRuns = backtestRuns
    .filter((run) => botBacktestRunMatchesProfile(run, profile))
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 4);
  const latestBacktestSummary = matchingRuns[0];
  const displayedMetrics = backtestResult?.metrics ?? latestBacktestSummary?.metrics;
  const displayedWarnings = backtestResult?.warnings ?? latestBacktestSummary?.warnings ?? [];
  const latestSession = latestRun?.session;
  const backtestRequest = backtestRequestFromBot(profile);
  const metricItems = [
    { label: '최종 자본', value: money(displayedMetrics?.final_equity, currency) },
    { label: '수익률', value: percent(displayedMetrics?.total_return_pct), tone: displayedMetrics?.total_return_pct },
    { label: '전략 우위', value: percent(displayedMetrics?.strategy_edge_pct), tone: displayedMetrics?.strategy_edge_pct },
    { label: '최대 낙폭', value: percent(displayedMetrics?.max_drawdown_pct) },
    { label: '샤프', value: number(displayedMetrics?.sharpe) },
    { label: '거래 수', value: displayedMetrics?.trades.toString() ?? '-' },
  ];

  return (
    <div className="bot-detail-panel">
      <div className="bot-detail-header">
        <BotProfileAvatar profile={profile} status={profile.active ? latestRun?.status ?? 'idle' : 'paused'} />
        <div>
          <span>봇 상세</span>
          <strong>{profile.name}</strong>
          <p>{profile.description}</p>
        </div>
        <span className={botStatusClass(profile.active ? latestRun?.status ?? 'idle' : 'paused')}>
          {botVisualStatusLabel(profile.active ? latestRun?.status ?? 'idle' : 'paused')}
        </span>
      </div>

      <div className="bot-detail-tabs" role="tablist" aria-label={`${profile.name} 상세 탭`}>
        <button
          className={`bot-detail-tab${tab === 'overview' ? ' bot-detail-tab-active' : ''}`}
          onClick={() => onTabChange('overview')}
          role="tab"
          type="button"
        >
          개요
        </button>
        <button
          className={`bot-detail-tab${tab === 'backtest' ? ' bot-detail-tab-active' : ''}`}
          onClick={() => onTabChange('backtest')}
          role="tab"
          type="button"
        >
          백테스트
        </button>
      </div>

      {tab === 'overview' ? (
        <div className="bot-detail-grid">
          <div>
            <span>전략</span>
            <strong>{strategyLabelKo(profile.request.strategy)}</strong>
            <p>{botStyleLabel(profile.operating_style)} · {sourceLabelKo(profile.request.source)}</p>
          </div>
          <div>
            <span>운영 모드</span>
            <strong>{botExecutionLabel(profile.execution_mode)}</strong>
            <p>{profile.active ? `다음 ${shortDateTime(profile.next_run_at)}` : '일시정지'}</p>
          </div>
          <div>
            <span>자본 / 종목</span>
            <strong>{money(profile.request.initial_cash, currency)}</strong>
            <p>{profile.request.symbol} · {profile.request.timeframe}</p>
          </div>
          <div>
            <span>리스크</span>
            <strong>{percent(profile.request.risk_limits.max_position_pct)}</strong>
            <p>주문 {money(profile.request.risk_limits.max_order_notional, currency)} · 손실 중단 {percent(profile.request.risk_limits.max_session_loss_pct)}</p>
          </div>
          <div>
            <span>최근 실행</span>
            <strong>{latestRun ? botRunStatusLabel(latestRun.status) : '-'}</strong>
            <p>{latestRun ? shortDateTime(latestRun.checked_at) : '아직 실행 기록 없음'}</p>
          </div>
          <div>
            <span>최근 수익률</span>
            <strong className={valueToneClass(latestSession?.summary.total_return_pct)}>
              {percent(latestSession?.summary.total_return_pct)}
            </strong>
            <p>포지션 {percent(latestSession?.summary.open_position_pct)} · 주문 {latestSession?.summary.orders ?? 0}</p>
          </div>
        </div>
      ) : (
        <div className="bot-backtest-panel">
          <div className="bot-backtest-actions">
            <div>
              <strong>{backtestRequest.symbol} · {strategyLabelKo(backtestRequest.strategy)}</strong>
              <span>
                {sourceLabelKo(backtestRequest.source)} · {backtestRequest.candle_limit}캔들 · 수수료 {number(backtestRequest.fee_bps)}bps
              </span>
            </div>
            <button
              className="run-button compact-action"
              disabled={backtestLoading}
              onClick={onRunBacktest}
              type="button"
            >
              <TrendingUp size={15} />
              {backtestLoading ? '실행 중' : '백테스트 실행'}
            </button>
          </div>

          {displayedMetrics ? (
            <div className="bot-backtest-metrics">
              {metricItems.map((item) => (
                <div className="metric-card" key={item.label}>
                  <span>{item.label}</span>
                  <strong className={item.tone !== undefined ? valueToneClass(item.tone) : undefined}>
                    {item.value}
                  </strong>
                </div>
              ))}
            </div>
          ) : (
            <div className="bot-detail-empty">아직 이 봇의 백테스트 결과가 없습니다.</div>
          )}

          {backtestResult ? (
            <div className="bot-backtest-chart">
              <EquityChart
                points={backtestResult.equity_curve}
                currency={currency}
                request={backtestResult.request}
                metrics={backtestResult.metrics}
              />
            </div>
          ) : null}

          {displayedWarnings.map((warning, index) => (
            <p className="warning-message" key={`${warning}-${index}`}>{warning}</p>
          ))}

          <div className="bot-backtest-history">
            <div className="bot-backtest-history-title">
              <strong>최근 백테스트</strong>
              <span>{matchingRuns.length}개</span>
            </div>
            {matchingRuns.length > 0 ? (
              matchingRuns.map((run) => (
                <div className="bot-backtest-run-row" key={run.id}>
                  <div>
                    <strong>{shortDateTime(run.created_at)}</strong>
                    <span>{run.request.symbol} · {strategyLabelKo(run.request.strategy)}</span>
                  </div>
                  <span className={valueToneClass(run.metrics.total_return_pct)}>{percent(run.metrics.total_return_pct)}</span>
                  <span>{percent(run.metrics.max_drawdown_pct)} MDD</span>
                  <span>{number(run.metrics.sharpe)} Sharpe</span>
                </div>
              ))
            ) : (
              <div className="bot-detail-empty">저장된 동일 전략 백테스트가 없습니다.</div>
            )}
          </div>

          {backtestError ? <p className="error-message">{backtestError}</p> : null}
        </div>
      )}
    </div>
  );
}

function botBacktestRunMatchesProfile(run: BacktestRunSummary, profile: BotProfile) {
  return (
    run.request.symbol === profile.request.symbol &&
    run.request.source === profile.request.source &&
    run.request.strategy === profile.request.strategy &&
    run.request.timeframe === profile.request.timeframe
  );
}

function botStyleLabel(style: BotOperatingStyle) {
  const labels: Record<BotOperatingStyle, string> = {
    trend_following: '추세 추종',
    mean_reversion: '되돌림',
    breakout: '돌파',
    portfolio_rotation: '포트폴리오 로테이션',
    defensive_monitor: '방어 감시',
    custom: '사용자 정의',
  };
  return labels[style];
}

function strategyLabelKo(strategy: Strategy) {
  const labels: Record<Strategy, string> = {
    sma_crossover: 'SMA 크로스오버',
    donchian_breakout: '돈치안 돌파',
    rsi_mean_reversion: 'RSI 되돌림',
  };
  return labels[strategy];
}

function sourceLabelKo(source: Source) {
  const labels: Record<Source, string> = {
    sample: '샘플 코인',
    upbit: '업비트 공개 시세',
    sample_us: '샘플 미국 주식/ETF',
    alpha_vantage: 'Alpha Vantage 일봉',
  };
  return labels[source];
}

function botExecutionLabel(mode: BotExecutionMode) {
  return mode === 'paper' ? '페이퍼' : '드라이런';
}

function botConflictPolicyLabel(policy: BotConflictPolicy) {
  return policy === 'allow' ? '같은 종목 허용' : '같은 종목 차단';
}

function botVisualStatusLabel(status: BotVisualStatus) {
  const labels: Record<BotVisualStatus, string> = {
    completed: '완료',
    halted: '중단',
    blocked: '차단',
    error: '오류',
    idle: '대기',
    paused: '일시정지',
    running: '실행 중',
  };
  return labels[status];
}

function botFleetStatusFilterLabel(filter: BotFleetStatusFilter) {
  const labels: Record<BotFleetStatusFilter, string> = {
    all: '전체',
    active: '활성',
    paused: '일시정지',
    running: '실행 중',
    completed: '완료',
    attention: '주의',
  };
  return labels[filter];
}

function botRunStatusLabel(status: BotRunStatus) {
  return botVisualStatusLabel(status);
}

function botStatusClass(status: BotVisualStatus) {
  if (status === 'completed') return 'session-status status-completed';
  if (status === 'running') return 'session-status status-running';
  if (status === 'paused') return 'session-status status-paused';
  if (status === 'halted' || status === 'blocked' || status === 'error') return 'session-status status-halted';
  return 'session-status status-idle';
}

function valueToneClass(value?: number | null) {
  if (value === undefined || value === null || Number.isNaN(value)) return 'value-neutral';
  if (value > 0) return 'value-profit';
  if (value < 0) return 'value-loss';
  return 'value-neutral';
}

function botAvatarStatusClass(status: BotVisualStatus) {
  if (status === 'completed') return 'bot-avatar-completed';
  if (status === 'running') return 'bot-avatar-running';
  if (status === 'paused') return 'bot-avatar-paused';
  if (status === 'halted' || status === 'blocked' || status === 'error') return 'bot-avatar-halted';
  return 'bot-avatar-idle';
}

function DataProvidersPanel({
  providers,
  columnarStatus,
  columnarExport,
  columnarLoading,
  error,
  columnarError,
  onRefresh,
  onExportColumnar,
}: {
  providers: MarketDataProviderStatus[];
  columnarStatus: MarketDataColumnarStatus | null;
  columnarExport: MarketDataColumnarExport | null;
  columnarLoading: boolean;
  error: string | null;
  columnarError: string | null;
  onRefresh: () => void;
  onExportColumnar: () => void;
}) {
  const ordered = providers.length > 0
    ? providers
    : sourceOptions.map((option) => ({
        source: option.value,
        label: option.label,
        configured: false,
        available: false,
        note: 'Loading provider status.',
      }) as MarketDataProviderStatus);

  return (
    <section className="panel providers-panel">
      <div className="panel-title">
        <Database size={18} />
        <h2>Data providers</h2>
        <button
          className="icon-button"
          onClick={onRefresh}
          title="Refresh market data provider status"
        >
          <RefreshCcw size={15} />
        </button>
      </div>
      <div className="providers-list">
        {ordered.map((provider) => {
          const state = provider.available ? 'ready' : provider.configured ? 'blocked' : 'missing';
          return (
            <div className="provider-row" key={provider.source}>
              <div className="provider-head">
                <strong>{provider.label}</strong>
                <span className={`provider-state provider-${state}`}>{state}</span>
              </div>
              <div className="provider-meta">
                <span>{provider.source}</span>
                <span>{provider.credential_name ? provider.credential_name : 'no key required'}</span>
                <span>ttl {provider.cache_ttl_seconds ?? '-'}s</span>
                <span>{provider.last_rows ? `${provider.last_rows} rows` : 'no rows yet'}</span>
              </div>
              <p>{provider.last_error ?? provider.note}</p>
              <div className="provider-last">
                <span>
                  last ok {provider.last_success_at ? shortDateTime(provider.last_success_at) : '-'}
                </span>
                <span>status {shortTime(provider.status_checked_at)}</span>
                <span>
                  last try {provider.last_symbol ?? '-'} · {provider.last_timeframe ?? '-'}
                </span>
              </div>
            </div>
          );
        })}
      </div>
      <div className="columnar-cache">
        <div className="columnar-head">
          <div>
            <strong>Columnar candle cache</strong>
            <span
              className={`provider-state provider-${columnarStatus?.enabled ? 'ready' : 'missing'}`}
            >
              {columnarStatus?.enabled ? 'ready' : 'missing'}
            </span>
          </div>
          <button
            className="icon-button"
            disabled={columnarLoading || !columnarStatus?.enabled}
            onClick={onExportColumnar}
            title="Export candle cache to Parquet"
          >
            <Download size={15} />
          </button>
        </div>
        <div className="provider-meta">
          <span>{columnarStatus ? `${columnarStatus.rows} rows` : 'checking'}</span>
          <span>{columnarStatus?.sources.length ? columnarStatus.sources.join(', ') : 'no sources'}</span>
          <span>{columnarStatus?.timeframes.length ? columnarStatus.timeframes.join(', ') : 'no frames'}</span>
        </div>
        <p className="columnar-path">
          DuckDB {compactPath(columnarStatus?.duckdb_path)} · Parquet {compactPath(columnarStatus?.parquet_path)}
        </p>
        <div className="provider-last">
          <span>
            fetched {columnarStatus?.last_fetched_at ? shortDateTime(columnarStatus.last_fetched_at) : '-'}
          </span>
          <span>
            exported {columnarExport ? shortDateTime(columnarExport.exported_at) : shortDateTime(columnarStatus?.last_exported_at)}
          </span>
          <span>{columnarLoading ? 'exporting' : 'idle'}</span>
        </div>
        {columnarStatus?.last_error ? (
          <p className="warning-message">{columnarStatus.last_error}</p>
        ) : null}
        {columnarError ? <p className="error-message">{columnarError}</p> : null}
      </div>
      {error ? <p className="error-message">{error}</p> : null}
    </section>
  );
}

function ExecutionPanel({
  status,
  snapshot,
  audits,
  refreshing,
  updatedAt,
  onRefresh,
}: {
  status: ExecutionStatus | null;
  snapshot: UpbitPrivateSnapshot | null;
  audits: OrderAuditRecord[];
  refreshing: boolean;
  updatedAt: string | null;
  onRefresh: () => void;
}) {
  const latestAudits = audits.slice(0, 3);
  const topBalances = snapshot?.balances
    .filter((balance) => balance.balance > 0 || balance.locked > 0)
    .slice(0, 4) ?? [];
  const stateLabel = status?.adapter_ready ? 'armed' : 'locked';
  const checkedAt = snapshot?.checked_at ?? status?.checked_at ?? updatedAt;

  return (
    <section className="panel execution-panel">
      <div className="panel-title">
        <ShieldCheck size={18} />
        <h2>Execution guard</h2>
        <button
          className="icon-button"
          onClick={onRefresh}
          disabled={refreshing}
          title="Refresh account and order guard state"
        >
          <RefreshCcw size={15} />
        </button>
        <span className={`execution-state execution-${stateLabel}`}>{stateLabel}</span>
      </div>
      <div className="execution-grid">
        <div>
          <span>Exchange</span>
          <strong>{status?.exchange ?? 'upbit'}</strong>
        </div>
        <div>
          <span>Live flag</span>
          <strong>{status?.live_trading_enabled ? 'on' : 'off'}</strong>
        </div>
        <div>
          <span>Adapter</span>
          <strong>{status?.adapter_ready ? 'ready' : 'blocked'}</strong>
        </div>
        <div>
          <span>Base URL</span>
          <strong>{status?.base_url ?? '-'}</strong>
        </div>
      </div>
      <p className="execution-reason">{status?.reason ?? 'Loading execution status.'}</p>
      <div className="private-summary">
        <div>
          <span>Private reads</span>
          <strong>{snapshot?.credential_ready ? 'ready' : 'disabled'}</strong>
        </div>
        <div>
          <span>Balances</span>
          <strong>{snapshot?.balances.length ?? 0}</strong>
        </div>
        <div>
          <span>Open orders</span>
          <strong>{snapshot?.open_orders.length ?? 0}</strong>
        </div>
      </div>
      <p className="execution-refresh-meta">
        {refreshing ? 'Refreshing private account state...' : `Last check ${checkedAt ? shortDateTime(checkedAt) : '-'}`}
      </p>
      <p className="execution-reason">{snapshot?.reason ?? 'Loading private account snapshot.'}</p>
      {topBalances.length > 0 ? (
        <div className="balance-list">
          {topBalances.map((balance) => (
            <div className="balance-row" key={balance.currency}>
              <strong>{balance.currency}</strong>
              <span>{number(balance.balance)}</span>
              <span>locked {number(balance.locked)}</span>
            </div>
          ))}
        </div>
      ) : null}
      <div className="audit-list">
        {latestAudits.map((audit) => (
          <div className="audit-row" key={audit.id}>
            <div>
              <strong>{audit.market}</strong>
              <span>{audit.side}</span>
              <span>{audit.ord_type}</span>
            </div>
            <div>
              <span className={`audit-status audit-${audit.status}`}>{audit.status}</span>
              <span>{shortTime(audit.created_at)}</span>
            </div>
          </div>
        ))}
        {latestAudits.length === 0 ? (
          <div className="audit-empty">No live order intents have been recorded.</div>
        ) : null}
      </div>
    </section>
  );
}

function ExecutionSettingsPanel({
  settings,
}: {
  settings: ExecutionSettings | null;
}) {
  const stateLabel = settings?.adapter_ready ? 'armed' : 'locked';
  const sourceLabel = settings?.order_info_source
    ? settings.order_info_source.replaceAll('_', ' ')
    : '-';

  return (
    <section className="panel execution-settings-panel">
      <div className="panel-title">
        <Settings size={18} />
        <h2>Execution settings</h2>
        <span className={`execution-state execution-${stateLabel}`}>{stateLabel}</span>
      </div>
      <div className="settings-grid">
        <div>
          <span>Credentials</span>
          <strong>{settings?.credential_configured ? 'configured' : 'missing'}</strong>
        </div>
        <div>
          <span>Live ACK</span>
          <strong>{settings?.live_ack_configured ? 'set' : 'missing'}</strong>
        </div>
        <div>
          <span>Private reads</span>
          <strong>{settings?.private_reads_enabled ? 'ready' : 'disabled'}</strong>
        </div>
        <div>
          <span>Order info</span>
          <strong>{sourceLabel}</strong>
        </div>
        <div>
          <span>Min order</span>
          <strong>{money(settings?.min_order_notional_krw)}</strong>
        </div>
        <div>
          <span>Approval fee</span>
          <strong>{feeRate(settings?.approval_fee_rate)}</strong>
        </div>
        <div>
          <span>Max exposure</span>
          <strong>{percent(settings?.max_approval_exposure_pct)}</strong>
        </div>
        <div>
          <span>Confirmation</span>
          <strong>{settings?.live_confirmation_required ? 'required' : 'off'}</strong>
        </div>
      </div>
      <p className="settings-note">
        ACK value: {settings?.live_ack_required_value ?? 'REAL_ORDERS_OK'} · Base URL:{' '}
        {settings?.base_url ?? '-'} · Checked:{' '}
        {settings?.checked_at ? shortDateTime(settings.checked_at) : '-'}
      </p>
      <p className="execution-reason">
        {settings?.reason ?? 'Loading execution settings.'}
      </p>
    </section>
  );
}

function PaperLiveAdapterPanel({
  adapters,
  request,
  paperWatchlist,
}: {
  adapters: PaperToLiveAdapterProfile[];
  request: BacktestRequest;
  paperWatchlist: PortfolioPaperWatchlistItem[];
}) {
  const currentAdapterId = request.symbol.startsWith('KRW-')
    ? 'upbit_crypto_spot'
    : isUsdSource(request.source)
      ? 'us_equity_paper'
      : null;
  const currentAdapter = adapters.find((adapter) => adapter.id === currentAdapterId);
  const currentState = currentAdapter?.execution_mode === 'guarded_live'
    ? 'dry-run audit'
    : currentAdapter?.execution_mode === 'paper_only'
      ? 'paper-only'
      : 'unrouted';
  const stockPaperOnlyCount = paperWatchlist.filter((item) => {
    const scenario = item.scenario_name.toLowerCase();
    return scenario.includes('etf') || scenario.includes('stock') || scenario.includes('equity');
  }).length;

  return (
    <section className="panel adapter-route-panel">
      <div className="panel-title">
        <Radio size={18} />
        <h2>Paper-live routing</h2>
        <span className={`execution-state execution-${currentAdapter?.live_order_supported ? 'armed' : 'locked'}`}>
          {currentState}
        </span>
      </div>
      <div className="adapter-route-current">
        <div>
          <span>Current symbol</span>
          <strong>{request.symbol}</strong>
          <p>{currentAdapter?.reason ?? 'No paper-to-live route is configured for this source.'}</p>
        </div>
        <div>
          <span>Source</span>
          <strong>{request.source}</strong>
          <p>{stockPaperOnlyCount} stock/ETF paper watch item(s) can be handed off without live-order routing.</p>
        </div>
      </div>
      <div className="adapter-route-grid">
        {adapters.map((adapter) => (
          <div
            className={`adapter-route-card adapter-route-${adapter.execution_mode}`}
            key={adapter.id}
          >
            <div>
              <strong>{adapter.label}</strong>
              <span>{adapter.execution_mode.replaceAll('_', ' ')}</span>
            </div>
            <p>{adapter.reason}</p>
            <div className="adapter-route-meta">
              <span>{adapter.asset_class.replaceAll('_', ' ')}</span>
              <span>{adapter.symbol_hint}</span>
              <span>{adapter.supported_sources.join(', ')}</span>
              <span>{adapter.broker_contract.label}</span>
              <span>{adapter.broker_contract.submission_mode.replaceAll('_', ' ')}</span>
            </div>
          </div>
        ))}
        {adapters.length === 0 ? (
          <div className="readiness-empty">Paper-live adapter routes have not loaded yet.</div>
        ) : null}
      </div>
    </section>
  );
}

function BrokerReadinessPanel({
  readiness,
}: {
  readiness: BrokerReadinessResponse | null;
}) {
  const items = readiness?.items ?? [];

  return (
    <section className="panel broker-readiness-panel">
      <div className="panel-title">
        <ShieldCheck size={18} />
        <h2>Broker readiness</h2>
        <span className="broker-readiness-count">
          {readiness?.checked_at ? shortDateTime(readiness.checked_at) : 'checking'}
        </span>
      </div>
      <div className="broker-readiness-grid">
        {items.map((item) => (
          <div className={`broker-readiness-card broker-readiness-${item.status}`} key={item.adapter_id}>
            <div className="broker-readiness-head">
              <div>
                <strong>{item.label}</strong>
                <span>{item.broker_contract.label}</span>
              </div>
              <span className={`broker-state broker-state-${item.status}`}>
                {item.status}
              </span>
            </div>
            <p>{item.message}</p>
            <div className="broker-readiness-meta">
              <span>{item.asset_class.replaceAll('_', ' ')}</span>
              <span>{item.live_submission_state.replaceAll('_', ' ')}</span>
              <span>{item.broker_contract.provider_type.replaceAll('_', ' ')}</span>
            </div>
            <div className="broker-credential-boundary">
              <KeyRound size={14} />
              <span>{item.credential_boundary}</span>
            </div>
            <div className="broker-check-list">
              {item.checks.map((check) => (
                <div className={`broker-check broker-check-${check.status}`} key={check.id}>
                  <span>{check.label}</span>
                  <strong>{check.status}</strong>
                  <p>{check.message}</p>
                </div>
              ))}
            </div>
          </div>
        ))}
        {items.length === 0 ? (
          <div className="readiness-empty">Broker readiness has not loaded yet.</div>
        ) : null}
      </div>
    </section>
  );
}

function BrokerIntentSandboxPanel({
  adapters,
  adapterId,
  linkedPaperSession,
  symbol,
  side,
  quantity,
  orderType,
  limitPrice,
  referencePrice,
  cashAvailable,
  currentPosition,
  portfolioEquity,
  feeBps,
  slippageBps,
  liveConfirmation,
  paperSubmitConfirmation,
  loading,
  historyLoading,
  reportExporting,
  reconcilingId,
  evaluation,
  reconciliation,
  history,
  error,
  onAdapterIdChange,
  onSymbolChange,
  onSideChange,
  onQuantityChange,
  onOrderTypeChange,
  onLimitPriceChange,
  onReferencePriceChange,
  onCashAvailableChange,
  onCurrentPositionChange,
  onPortfolioEquityChange,
  onFeeBpsChange,
  onSlippageBpsChange,
  onLiveConfirmationChange,
  onPaperSubmitConfirmationChange,
  onEvaluate,
  onReconcile,
  onRefreshHistory,
  onExportReport,
}: {
  adapters: PaperToLiveAdapterProfile[];
  adapterId: BrokerIntentAdapterId;
  linkedPaperSession: PaperTradingSession | null;
  symbol: string;
  side: BrokerIntentSide;
  quantity: number;
  orderType: BrokerIntentOrderType;
  limitPrice: number;
  referencePrice: number;
  cashAvailable: number;
  currentPosition: number;
  portfolioEquity: number;
  feeBps: number;
  slippageBps: number;
  liveConfirmation: boolean;
  paperSubmitConfirmation: boolean;
  loading: boolean;
  historyLoading: boolean;
  reportExporting: boolean;
  reconcilingId: string | null;
  evaluation: BrokerIntentEvaluation | null;
  reconciliation: BrokerOrderReconciliation | null;
  history: BrokerIntentEvaluation[];
  error: string | null;
  onAdapterIdChange: (value: BrokerIntentAdapterId) => void;
  onSymbolChange: (value: string) => void;
  onSideChange: (value: BrokerIntentSide) => void;
  onQuantityChange: (value: number) => void;
  onOrderTypeChange: (value: BrokerIntentOrderType) => void;
  onLimitPriceChange: (value: number) => void;
  onReferencePriceChange: (value: number) => void;
  onCashAvailableChange: (value: number) => void;
  onCurrentPositionChange: (value: number) => void;
  onPortfolioEquityChange: (value: number) => void;
  onFeeBpsChange: (value: number) => void;
  onSlippageBpsChange: (value: number) => void;
  onLiveConfirmationChange: (value: boolean) => void;
  onPaperSubmitConfirmationChange: (value: boolean) => void;
  onEvaluate: () => void;
  onReconcile: (evaluationId: string) => void;
  onRefreshHistory: () => void;
  onExportReport: () => void;
}) {
  const fillEstimate = evaluation?.paper_fill_estimate;
  const adapterOptions = adapters.filter(
    (adapter): adapter is PaperToLiveAdapterProfile & { id: BrokerIntentAdapterId } =>
      adapter.id === 'us_equity_paper' ||
      adapter.id === 'alpaca_us_equity_paper_preview' ||
      adapter.id === 'alpaca_us_equity_paper',
  );
  const selectedAdapter = adapterOptions.find((adapter) => adapter.id === adapterId);
  const linkedSessionMatches =
    linkedPaperSession?.request.symbol.toUpperCase() === symbol.trim().toUpperCase();

  return (
    <section className="panel broker-intent-panel">
      <div className="panel-title">
        <Settings size={18} />
        <h2>US paper broker sandbox</h2>
        <span className={`broker-intent-state broker-intent-${evaluation?.submission_status ?? 'idle'}`}>
          {evaluation?.submission_status.replaceAll('_', ' ') ?? 'idle'}
        </span>
      </div>
      <div className="broker-intent-form">
        <label className="broker-intent-adapter-select">
          Adapter
          <select
            value={adapterId}
            onChange={(event) => onAdapterIdChange(event.target.value as BrokerIntentAdapterId)}
            title="Paper broker adapter contract to evaluate"
          >
            {(adapterOptions.length > 0
              ? adapterOptions
              : [
                  {
                    id: 'us_equity_paper' as BrokerIntentAdapterId,
                    label: 'US stock/ETF paper handoff',
                  },
                ]).map((adapter) => (
              <option value={adapter.id} key={adapter.id}>
                {adapter.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Symbol
          <input
            value={symbol}
            onChange={(event) => onSymbolChange(event.target.value.toUpperCase())}
            title="US stock/ETF symbol"
          />
        </label>
        <label>
          Side
          <select
            value={side}
            onChange={(event) => onSideChange(event.target.value as BrokerIntentSide)}
            title="Broker intent side"
          >
            <option value="buy">Buy</option>
            <option value="sell">Sell</option>
          </select>
        </label>
        <label>
          Quantity
          <input
            min={0.000001}
            step={0.000001}
            type="number"
            value={quantity}
            onChange={(event) => onQuantityChange(Number(event.target.value))}
            title="Broker intent quantity"
          />
        </label>
        <label>
          Order type
          <select
            value={orderType}
            onChange={(event) => onOrderTypeChange(event.target.value as BrokerIntentOrderType)}
            title="Broker intent order type"
          >
            <option value="market">Market</option>
            <option value="limit">Limit</option>
          </select>
        </label>
        <label>
          Limit price
          <input
            disabled={orderType !== 'limit'}
            min={0.01}
            step={0.01}
            type="number"
            value={limitPrice}
            onChange={(event) => onLimitPriceChange(Number(event.target.value))}
            title="Limit price used for paper broker notional estimation"
          />
        </label>
        <label>
          Ref price
          <input
            min={0.01}
            step={0.01}
            type="number"
            value={referencePrice}
            onChange={(event) => onReferencePriceChange(Number(event.target.value))}
            title="Reference price used for paper fill estimation"
          />
        </label>
        <label>
          Cash
          <input
            min={0}
            step={100}
            type="number"
            value={cashAvailable}
            onChange={(event) => onCashAvailableChange(Number(event.target.value))}
            title="Cash available for the paper fill estimate"
          />
        </label>
        <label>
          Position
          <input
            min={0}
            step={0.000001}
            type="number"
            value={currentPosition}
            onChange={(event) => onCurrentPositionChange(Number(event.target.value))}
            title="Current paper position quantity before this estimate"
          />
        </label>
        <label>
          Equity
          <input
            min={0.01}
            step={100}
            type="number"
            value={portfolioEquity}
            onChange={(event) => onPortfolioEquityChange(Number(event.target.value))}
            title="Portfolio equity used for exposure estimation"
          />
        </label>
        <label>
          Fee bps
          <input
            min={0}
            step={0.1}
            type="number"
            value={feeBps}
            onChange={(event) => onFeeBpsChange(Number(event.target.value))}
            title="Paper fill fee in basis points"
          />
        </label>
        <label>
          Slip bps
          <input
            min={0}
            step={0.1}
            type="number"
            value={slippageBps}
            onChange={(event) => onSlippageBpsChange(Number(event.target.value))}
            title="Paper fill slippage in basis points"
          />
        </label>
        <label className="toggle-row broker-intent-toggle">
          <input
            checked={liveConfirmation}
            onChange={(event) => onLiveConfirmationChange(event.target.checked)}
            type="checkbox"
          />
          Live confirm
        </label>
        <label className="toggle-row broker-intent-toggle">
          <input
            checked={paperSubmitConfirmation}
            onChange={(event) => onPaperSubmitConfirmationChange(event.target.checked)}
            type="checkbox"
          />
          Paper submit
        </label>
        <button
          className="tertiary-button compact-action"
          disabled={loading}
          onClick={onEvaluate}
          title="Evaluate this broker-neutral intent against the selected paper broker"
          type="button"
        >
          {loading ? 'Evaluating...' : 'Evaluate'}
        </button>
      </div>
      {selectedAdapter ? (
        <div className="broker-intent-adapter-note">
          <span>{selectedAdapter.broker_contract.id}</span>
          <p>{selectedAdapter.reason}</p>
          {linkedPaperSession ? (
            <p>
              Paper session link: {linkedSessionMatches ? linkedPaperSession.id : 'symbol mismatch'}
            </p>
          ) : null}
        </div>
      ) : null}
      {evaluation ? (
        <div className="broker-intent-result">
          <div>
            <span>Adapter</span>
            <strong>{evaluation.adapter_id.replaceAll('_', ' ')}</strong>
            <p>{evaluation.broker_contract.id}</p>
          </div>
          <div>
            <span>Validation</span>
            <strong>{evaluation.validation_status}</strong>
            <p>{evaluation.normalized_symbol ?? '-'}</p>
          </div>
          <div>
            <span>Submission</span>
            <strong>{evaluation.submission_status.replaceAll('_', ' ')}</strong>
            <p>{evaluation.reason}</p>
          </div>
          <div>
            <span>Notional</span>
            <strong>{money(evaluation.estimated_notional ?? undefined, 'USD')}</strong>
            <p>external: {evaluation.external_submission_attempted ? 'yes' : 'no'}</p>
          </div>
          <div>
            <span>Paper fill</span>
            <strong>{fillEstimate?.status.replaceAll('_', ' ') ?? '-'}</strong>
            <p>
              {fillEstimate?.fill_price ? money(fillEstimate.fill_price, 'USD') : '-'} / cash{' '}
              {money(fillEstimate?.cash_after ?? undefined, 'USD')}
            </p>
          </div>
        </div>
      ) : null}
      {reconciliation ? (
        <div className="broker-intent-result broker-reconciliation-result">
          <div>
            <span>Reconciliation</span>
            <strong>{reconciliation.status.replaceAll('_', ' ')}</strong>
            <p>{reconciliation.reason}</p>
          </div>
          <div>
            <span>Broker status</span>
            <strong>{reconciliation.broker_status?.replaceAll('_', ' ') ?? '-'}</strong>
            <p>{reconciliation.broker_order_id ?? reconciliation.client_order_id ?? '-'}</p>
          </div>
          <div>
            <span>Broker order</span>
            <strong>{reconciliation.broker_symbol ?? '-'}</strong>
            <p>
              {reconciliation.broker_side ?? '-'}{' '}
              {reconciliation.broker_quantity ?? '-'} / filled{' '}
              {reconciliation.broker_filled_quantity ?? 0}
            </p>
          </div>
          <div>
            <span>Fill evidence</span>
            <strong>
              {reconciliation.broker_partial_fill ? 'partial fill' : 'fill check'}
            </strong>
            <p>
              {money(reconciliation.broker_avg_fill_price ?? undefined, 'USD')} /{' '}
              {money(reconciliation.broker_filled_notional ?? undefined, 'USD')}
            </p>
          </div>
          <div>
            <span>Fees</span>
            <strong>{money(reconciliation.broker_fee ?? undefined, 'USD')}</strong>
            <p>{reconciliation.broker_fill_activity_count} fill activities</p>
          </div>
          <div>
            <span>Position</span>
            <strong>{reconciliation.broker_position_quantity ?? '-'}</strong>
            <p>
              {money(reconciliation.broker_position_market_value ?? undefined, 'USD')} / P&L{' '}
              {money(reconciliation.broker_position_unrealized_pl ?? undefined, 'USD')}
            </p>
          </div>
          <div>
            <span>Account</span>
            <strong>{money(reconciliation.broker_account_cash ?? undefined, 'USD')}</strong>
            <p>
              equity {money(reconciliation.broker_account_equity ?? undefined, 'USD')} / buying{' '}
              {money(reconciliation.broker_account_buying_power ?? undefined, 'USD')}
            </p>
          </div>
          <div>
            <span>Paper compare</span>
            <strong>{reconciliation.paper_fill_comparison_status?.replaceAll('_', ' ') ?? '-'}</strong>
            <p>
              {percent(reconciliation.paper_fill_price_delta_pct ?? undefined)} / fee{' '}
              {money(reconciliation.paper_fill_fee_delta ?? undefined, 'USD')}
            </p>
          </div>
          <div>
            <span>Lookup</span>
            <strong>{reconciliation.external_lookup_attempted ? 'external paper' : 'local block'}</strong>
            <p>{shortDateTime(reconciliation.checked_at)}</p>
          </div>
        </div>
      ) : null}
      <div className="broker-intent-history">
        <div className="broker-intent-history-title">
          <div>
            <span>Recent evaluations</span>
            <strong>{history.length} saved</strong>
          </div>
          <div className="broker-intent-history-actions">
            <button
              className="icon-button"
              disabled={historyLoading}
              onClick={onRefreshHistory}
              title="Reload recent paper broker evaluations"
              type="button"
            >
              <RefreshCcw size={15} />
            </button>
            <button
              className="icon-button"
              disabled={reportExporting}
              onClick={onExportReport}
              title="Export broker intent evaluation report"
              type="button"
            >
              <Download size={15} />
            </button>
          </div>
        </div>
        {history.length > 0 ? (
          <div className="broker-intent-history-list">
            {history.map((item) => (
              <div className="broker-intent-history-row" key={item.id}>
                <div>
                  <strong>{item.normalized_symbol ?? item.request.symbol.toUpperCase()}</strong>
                  <span>
                    {item.request.side} {item.request.quantity} {item.request.order_type}
                  </span>
                </div>
                <span>{item.adapter_id.replaceAll('_', ' ')}</span>
                <span className={`broker-intent-state broker-intent-${item.submission_status}`}>
                  {item.submission_status.replaceAll('_', ' ')}
                </span>
                <span>{item.paper_fill_estimate?.status.replaceAll('_', ' ') ?? '-'}</span>
                <span>{shortDateTime(item.checked_at)}</span>
                <span>{money(item.estimated_notional ?? undefined, 'USD')}</span>
                <button
                  className="icon-button"
                  disabled={reconcilingId === item.id}
                  onClick={() => onReconcile(item.id)}
                  title="Reconcile this saved evaluation with broker paper order status"
                  type="button"
                >
                  <RefreshCcw size={14} />
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div className="broker-intent-history-empty">
            No broker intent evaluations have been saved yet.
          </div>
        )}
      </div>
      {error ? <p className="error-message">{error}</p> : null}
    </section>
  );
}

function PaperFillDriftPanel({
  analytics,
  qualityGate,
  loading,
  error,
  onRefresh,
}: {
  analytics: PaperFillOrderNoteAnalytics | null;
  qualityGate: PaperFillOrderNoteQualityGate | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}) {
  const rows = analytics?.rows ?? [];
  const gateRows = new Map(
    (qualityGate?.rows ?? []).map((row) => [`${row.adapter_id}-${row.symbol}`, row]),
  );
  return (
    <section className="panel paper-drift-panel">
      <div className="panel-title">
        <Activity size={18} />
        <h2>Paper fill drift</h2>
        <div className="paper-drift-title-actions">
          <span className={`paper-gate-status paper-gate-${qualityGate?.status ?? 'watch'}`}>
            {qualityGate?.status ?? 'watch'}
          </span>
          <button
            className="icon-button"
            disabled={loading}
            onClick={onRefresh}
            title="Reload paper fill drift"
            type="button"
          >
            <RefreshCcw size={15} />
          </button>
        </div>
      </div>
      <div className="paper-drift-summary">
        <div>
          <span>Notes</span>
          <strong>{analytics?.notes_considered ?? 0}</strong>
          <p>{analytics ? `${analytics.matched_trade_count} matched` : 'No sample'}</p>
        </div>
        <div>
          <span>Groups</span>
          <strong>{rows.length}</strong>
          <p>{analytics ? `latest ${shortDateTime(analytics.generated_at)}` : '-'}</p>
        </div>
        <div>
          <span>External</span>
          <strong>{analytics?.external_submission_attempted_count ?? 0}</strong>
          <p>paper boundary</p>
        </div>
        <div>
          <span>Gate</span>
          <strong>{qualityGate?.status ?? 'watch'}</strong>
          <p>
            min {qualityGate?.min_notes ?? 3} / avg{' '}
            {percent(qualityGate?.max_avg_abs_price_delta_pct ?? undefined)}
          </p>
        </div>
      </div>
      {qualityGate ? (
        <div className={`paper-drift-gate-note paper-gate-note-${qualityGate.status}`}>
          <strong>{qualityGate.reason}</strong>
          <span>
            worst limit {percent(qualityGate.max_worst_abs_price_delta_pct)} · external{' '}
            {qualityGate.require_no_external_submission ? 'blocked' : 'allowed'}
          </span>
        </div>
      ) : null}
      {rows.length > 0 ? (
        <div className="paper-drift-list">
          {rows.map((row) => {
            const gateRow = gateRows.get(`${row.adapter_id}-${row.symbol}`);
            return (
              <div className="paper-drift-row" key={`${row.adapter_id}-${row.symbol}`}>
                <div>
                  <strong>{row.symbol}</strong>
                  <span>{row.adapter_id.replaceAll('_', ' ')}</span>
                </div>
                <span className={`paper-gate-status paper-gate-${gateRow?.status ?? 'watch'}`}>
                  {gateRow?.status ?? 'watch'}
                </span>
                <span>{row.note_count} notes</span>
                <span>
                  {row.matched_trade_count}/{row.note_count} matched
                </span>
                <span>avg |Δ| {percent(row.avg_abs_price_delta_pct ?? undefined)}</span>
                <span>worst |Δ| {percent(row.worst_abs_price_delta_pct ?? undefined)}</span>
                <span>latest {percent(row.latest_price_delta_pct ?? undefined)}</span>
                <span>{shortDateTime(row.latest_created_at)}</span>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="paper-drift-empty">
          {loading ? 'Loading paper fill drift...' : 'No linked paper fill notes yet.'}
        </div>
      )}
      {error ? <p className="error-message">{error}</p> : null}
    </section>
  );
}

function StockEtfBrokerExpansionPanel({
  readiness,
  loading,
  exporting,
  packageExportingId,
  preflightExportingId,
  rehearsalExportingId,
  error,
  onRefresh,
  onExport,
  onExportPackage,
  onExportPreflight,
  onExportRehearsal,
}: {
  readiness: StockEtfBrokerExpansionReadiness | null;
  loading: boolean;
  exporting: boolean;
  packageExportingId: string | null;
  preflightExportingId: string | null;
  rehearsalExportingId: string | null;
  error: string | null;
  onRefresh: () => void;
  onExport: () => void;
  onExportPackage: (decisionId: string) => void;
  onExportPreflight: (decisionId: string) => void;
  onExportRehearsal: (decisionId: string) => void;
}) {
  const candidates = readiness?.candidates ?? [];
  const readyCandidates = candidates.filter((candidate) => candidate.approved_for_broker_expansion);
  return (
    <section className="panel stock-expansion-panel">
      <div className="panel-title">
        <ShieldCheck size={18} />
        <h2>Stock/ETF broker expansion</h2>
        <div className="stock-expansion-actions">
          <span className={`paper-gate-status paper-gate-${readiness?.status ?? 'watch'}`}>
            {readiness?.status ?? 'watch'}
          </span>
          <button
            className="icon-button"
            disabled={loading}
            onClick={onRefresh}
            title="Reload stock/ETF broker expansion readiness"
            type="button"
          >
            <RefreshCcw size={15} />
          </button>
          <button
            className="icon-button"
            disabled={exporting || !readiness}
            onClick={onExport}
            title="Export stock/ETF broker expansion readiness report"
            type="button"
          >
            <Download size={15} />
          </button>
        </div>
      </div>
      <div className="stock-expansion-summary">
        <div>
          <span>Ready</span>
          <strong>{readiness?.counts.approved_ready ?? 0}</strong>
          <p>{readiness?.reason ?? 'Waiting for paper-only handoff evidence.'}</p>
        </div>
        <div>
          <span>Candidates</span>
          <strong>{readiness?.counts.candidates ?? 0}</strong>
          <p>{readiness?.generated_at ? shortDateTime(readiness.generated_at) : '-'}</p>
        </div>
        <div>
          <span>Watch</span>
          <strong>{readiness?.counts.watch ?? 0}</strong>
          <p>{readiness?.counts.blocked ?? 0} blocked</p>
        </div>
      </div>
      {candidates.length > 0 ? (
        <div className="stock-expansion-list">
          {candidates.slice(0, 5).map((candidate) => (
            <div className="stock-expansion-row" key={candidate.decision_id}>
              <div>
                <strong>{candidate.symbol}</strong>
                <span>{candidate.adapter_label ?? candidate.adapter_id ?? 'paper adapter'}</span>
              </div>
              <span className={`paper-gate-status paper-gate-${candidate.quality_gate_status}`}>
                {candidate.quality_gate_status}
              </span>
              <span>{candidate.decision_status.replaceAll('_', ' ')}</span>
              <span>{candidate.note_count} notes</span>
              <span>avg |Δ| {percent(candidate.avg_abs_price_delta_pct ?? undefined)}</span>
              <div className="stock-expansion-row-actions">
                <button
                  className="stock-expansion-package-button"
                  disabled={
                    !candidate.approved_for_broker_expansion ||
                    packageExportingId === candidate.decision_id
                  }
                  onClick={() => onExportPackage(candidate.decision_id)}
                  title={
                    candidate.approved_for_broker_expansion
                      ? `Export ${candidate.symbol} broker expansion package`
                      : 'Package requires an approved-ready handoff'
                  }
                  type="button"
                >
                  {packageExportingId === candidate.decision_id ? 'Exporting' : 'Package'}
                </button>
                <button
                  className="stock-expansion-package-button"
                  disabled={
                    !candidate.approved_for_broker_expansion ||
                    preflightExportingId === candidate.decision_id
                  }
                  onClick={() => onExportPreflight(candidate.decision_id)}
                  title={
                    candidate.approved_for_broker_expansion
                      ? `Export ${candidate.symbol} broker expansion preflight`
                      : 'Preflight requires an approved-ready handoff'
                  }
                  type="button"
                >
                  {preflightExportingId === candidate.decision_id ? 'Checking' : 'Preflight'}
                </button>
                <button
                  className="stock-expansion-package-button"
                  disabled={
                    !candidate.approved_for_broker_expansion ||
                    rehearsalExportingId === candidate.decision_id
                  }
                  onClick={() => onExportRehearsal(candidate.decision_id)}
                  title={
                    candidate.approved_for_broker_expansion
                      ? `Export ${candidate.symbol} local paper broker rehearsal`
                      : 'Rehearsal requires an approved-ready handoff'
                  }
                  type="button"
                >
                  {rehearsalExportingId === candidate.decision_id ? 'Replaying' : 'Rehearsal'}
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="stock-expansion-empty">
          {loading ? 'Loading broker expansion readiness...' : 'No stock/ETF expansion candidates yet.'}
        </div>
      )}
      {readyCandidates.length > 0 ? (
        <div className="stock-expansion-note">
          {readyCandidates.length} approved stock/ETF handoff(s) have ready paper-fill evidence.
        </div>
      ) : null}
      {error ? <p className="error-message">{error}</p> : null}
    </section>
  );
}

function StockEtfHandoffPanel({
  handoffs,
  loading,
  exporting,
  reviewingId,
  expandedKey,
  detailLoadingKey,
  sessionsById,
  brokerEvaluationsByKey,
  orderNotesByKey,
  qualityGatesByKey,
  error,
  detailError,
  message,
  onRefresh,
  onExport,
  onLogDecision,
  onToggleDetails,
}: {
  handoffs: OperatorDecisionRecord[];
  loading: boolean;
  exporting: boolean;
  reviewingId: string | null;
  expandedKey: string | null;
  detailLoadingKey: string | null;
  sessionsById: Record<string, PaperTradingSession>;
  brokerEvaluationsByKey: Record<string, BrokerIntentEvaluation[]>;
  orderNotesByKey: Record<string, PaperFillOrderNote[]>;
  qualityGatesByKey: Record<string, PaperFillOrderNoteQualityGate>;
  error: string | null;
  detailError: string | null;
  message: string | null;
  onRefresh: () => void;
  onExport: () => void;
  onLogDecision: (handoff: OperatorDecisionRecord, status: OperatorDecisionStatus) => void;
  onToggleDetails: (handoff: OperatorDecisionRecord) => void;
}) {
  const latestHandoffs = latestDecisionPerHandoff(handoffs);
  const statusOptions: { value: OperatorDecisionStatus; label: string }[] = [
    { value: 'noted', label: 'Noted' },
    { value: 'needs_work', label: 'Needs work' },
    { value: 'approved', label: 'Approve paper' },
    { value: 'rejected', label: 'Reject' },
  ];
  const symbols = Array.from(new Set(
    latestHandoffs
      .map((handoff) => decisionContextText(handoff, 'symbol'))
      .filter((symbol): symbol is string => Boolean(symbol)),
  ));
  const needsWork = latestHandoffs.filter((handoff) =>
    handoff.status === 'needs_work' || handoff.status === 'rejected',
  ).length;
  const latestAt = latestHandoffs[0]?.created_at;
  const symbolPreview = symbols.slice(0, 4).join(', ') || '-';

  return (
    <section className="panel stock-handoff-panel">
      <div className="panel-title">
        <History size={18} />
        <h2>Stock/ETF handoffs</h2>
        <button
          className="icon-button"
          onClick={onRefresh}
          disabled={loading}
          title="Refresh stock/ETF handoffs"
          type="button"
        >
          <RefreshCcw size={15} />
        </button>
        <button
          className="icon-button"
          onClick={onExport}
          disabled={exporting}
          title="Export stock/ETF handoff report"
          type="button"
        >
          <Download size={15} />
        </button>
        <span className="stock-handoff-count">
          {loading ? 'loading' : `${latestHandoffs.length} handoffs`}
        </span>
      </div>
      <div className="stock-handoff-grid">
        <div className="stock-handoff-card">
          <span>Recent</span>
          <strong>{latestHandoffs.length}</strong>
          <p>paper-only route</p>
        </div>
        <div className="stock-handoff-card">
          <span>Symbols</span>
          <strong>{symbols.length}</strong>
          <p>{symbolPreview}</p>
        </div>
        <div className="stock-handoff-card">
          <span>Needs work</span>
          <strong>{needsWork}</strong>
          <p>{latestAt ? shortDateTime(latestAt) : '-'}</p>
        </div>
      </div>
      <div className="stock-handoff-list">
        {latestHandoffs.map((handoff) => {
          const handoffKey = handoffDecisionKey(handoff);
          const sessionId = decisionContextText(handoff, 'session_id');
          const symbol = decisionContextText(handoff, 'symbol') ?? '-';
          const scenario = decisionContextText(handoff, 'scenario_name') ?? 'Portfolio paper session';
          const source = decisionContextText(handoff, 'source') ?? '-';
          const adapterLabel = decisionContextText(handoff, 'adapter_label') ?? 'paper-only route';
          const routeStatus = decisionContextText(handoff, 'route_status');
          const totalReturn = decisionContextNumber(handoff, 'total_return_pct');
          const maxDrawdown = decisionContextNumber(handoff, 'max_drawdown_pct');
          const orders = decisionContextNumber(handoff, 'orders');
          const orderLabel = orders === undefined ? '-' : new Intl.NumberFormat('en-US').format(orders);
          const isExpanded = expandedKey === handoffKey;
          const detailSession = sessionId ? sessionsById[sessionId] : undefined;
          const brokerEvaluations = brokerEvaluationsByKey[handoffKey] ?? [];
          const orderNotes = orderNotesByKey[handoffKey] ?? [];
          const qualityGate = qualityGatesByKey[handoffKey];
          const isDetailLoading = detailLoadingKey === handoffKey;

          return (
            <React.Fragment key={handoffKey}>
              <div className="stock-handoff-row">
                <div>
                  <strong>{symbol}</strong>
                  <p>{scenario}</p>
                  <div className="stock-handoff-meta">
                    <span>{source}</span>
                    <span>{adapterLabel}</span>
                    {sessionId ? <span>{sessionId}</span> : null}
                    {routeStatus ? (
                      <span className={`stock-handoff-route stock-handoff-route-${routeStatus}`}>
                        {routeStatus.replaceAll('_', ' ')}
                      </span>
                    ) : null}
                    <span className={`paper-gate-status paper-gate-${qualityGate?.status ?? 'watch'}`}>
                      gate {qualityGate?.status ?? 'watch'}
                    </span>
                  </div>
                </div>
                <div className="stock-handoff-stats">
                  <span className={`journal-state journal-${handoff.status}`}>
                    {handoff.status.replaceAll('_', ' ')}
                  </span>
                  <span className="stock-handoff-stat">{percent(totalReturn)} return</span>
                  <span className="stock-handoff-stat">{percent(maxDrawdown)} DD</span>
                  <span className="stock-handoff-stat">{orderLabel} orders</span>
                  <span className="stock-handoff-stat">{shortDateTime(handoff.created_at)}</span>
                  <div className="stock-handoff-actions">
                    <button
                      className="stock-handoff-action"
                      disabled={isDetailLoading}
                      onClick={() => onToggleDetails(handoff)}
                      title={`${isExpanded ? 'Hide' : 'Show'} linked paper session trades and promotion rules`}
                      type="button"
                    >
                      {isExpanded ? 'Hide detail' : 'Detail'}
                    </button>
                    {statusOptions.map((option) => {
                      const approvalLocked =
                        option.value === 'approved' && qualityGate?.status !== 'ready';
                      return (
                        <button
                          className={`stock-handoff-action stock-handoff-action-${option.value}`}
                          disabled={
                            reviewingId === handoff.id ||
                            handoff.status === option.value ||
                            approvalLocked
                          }
                          key={option.value}
                          onClick={() => onLogDecision(handoff, option.value)}
                          title={
                            approvalLocked
                              ? `Quality gate is ${qualityGate?.status ?? 'loading'}`
                              : `Mark ${symbol} handoff as ${option.label}`
                          }
                          type="button"
                        >
                          {reviewingId === handoff.id && handoff.status !== option.value
                            ? 'Saving'
                            : option.label}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
              {isExpanded ? (
                <StockEtfHandoffDetail
                  handoff={handoff}
                  session={detailSession}
                  brokerEvaluations={brokerEvaluations}
                  orderNotes={orderNotes}
                  qualityGate={qualityGate}
                  loading={isDetailLoading}
                  error={detailError}
                />
              ) : null}
            </React.Fragment>
          );
        })}
        {latestHandoffs.length === 0 ? (
          <div className="stock-handoff-empty">No stock/ETF paper-only handoffs yet.</div>
        ) : null}
      </div>
      {message ? <p className="success-message">{message}</p> : null}
      {error ? <p className="error-message">{error}</p> : null}
    </section>
  );
}

function StockEtfHandoffDetail({
  handoff,
  session,
  brokerEvaluations,
  orderNotes,
  qualityGate,
  loading,
  error,
}: {
  handoff: OperatorDecisionRecord;
  session?: PaperTradingSession;
  brokerEvaluations: BrokerIntentEvaluation[];
  orderNotes: PaperFillOrderNote[];
  qualityGate?: PaperFillOrderNoteQualityGate;
  loading: boolean;
  error: string | null;
}) {
  const promotionRules = decisionContextObject(handoff, 'promotion_rules');
  const currency = session ? currencyForSource(session.request.source) : 'USD';
  const trades = session?.trades.slice(-6) ?? [];

  return (
    <div className="stock-handoff-detail">
      {loading ? <div className="stock-handoff-detail-empty">Loading linked paper session.</div> : null}
      {!loading && error ? <p className="error-message">{error}</p> : null}
      {!loading && !error ? (
        <>
          <div className="stock-handoff-detail-grid">
            <div>
              <span>Paper session</span>
              <strong>{session?.id ?? decisionContextText(handoff, 'session_id') ?? '-'}</strong>
              <p>{session ? `${session.request.strategy.replaceAll('_', ' ')} · ${session.request.timeframe}` : 'Session data not loaded.'}</p>
            </div>
            <div>
              <span>Final equity</span>
              <strong>{money(session?.summary.final_equity, currency)}</strong>
              <p>{percent(session?.summary.total_return_pct)} return</p>
            </div>
            <div>
              <span>Risk</span>
              <strong>{percent(session?.summary.max_drawdown_pct)} DD</strong>
              <p>{session?.risk_events.length ?? 0} risk events</p>
            </div>
          </div>
          <div className="stock-handoff-rule-grid">
            <div>
              <span>Min return</span>
              <strong>{percent(payloadNumber(promotionRules?.min_total_return_pct))}</strong>
            </div>
            <div>
              <span>Max drawdown</span>
              <strong>{percent(payloadNumber(promotionRules?.max_drawdown_pct))}</strong>
            </div>
            <div>
              <span>Min orders</span>
              <strong>{payloadNumber(promotionRules?.min_orders) ?? '-'}</strong>
            </div>
          </div>
          <div className="stock-handoff-quality-gate">
            <div className="stock-handoff-quality-gate-head">
              <div>
                <span>Paper fill quality gate</span>
                <strong>{qualityGate?.status ?? 'watch'}</strong>
                <p>{qualityGate?.reason ?? 'Quality gate evidence is still loading.'}</p>
              </div>
              <span className={`paper-gate-status paper-gate-${qualityGate?.status ?? 'watch'}`}>
                {qualityGate?.status ?? 'watch'}
              </span>
            </div>
            <div className="stock-handoff-quality-gate-grid">
              <div>
                <span>Min notes</span>
                <strong>{qualityGate?.min_notes ?? 3}</strong>
              </div>
              <div>
                <span>Avg limit</span>
                <strong>{percent(qualityGate?.max_avg_abs_price_delta_pct ?? undefined)}</strong>
              </div>
              <div>
                <span>Worst limit</span>
                <strong>{percent(qualityGate?.max_worst_abs_price_delta_pct ?? undefined)}</strong>
              </div>
            </div>
            {(qualityGate?.rows ?? []).map((row) => (
              <div className="stock-handoff-quality-gate-row" key={`${row.adapter_id}-${row.symbol}`}>
                <div>
                  <strong>{row.symbol}</strong>
                  <span>{row.adapter_id.replaceAll('_', ' ')}</span>
                </div>
                <span className={`paper-gate-status paper-gate-${row.status}`}>{row.status}</span>
                <span>{row.note_count} notes</span>
                <span>{row.matched_trade_count} matched</span>
                <span>avg |Δ| {percent(row.avg_abs_price_delta_pct ?? undefined)}</span>
                <span>worst |Δ| {percent(row.worst_abs_price_delta_pct ?? undefined)}</span>
              </div>
            ))}
          </div>
          <div className="stock-handoff-trades">
            {trades.map((trade, index) => (
              <div className="stock-handoff-trade-row" key={`${trade.timestamp}-${trade.side}-${index}`}>
                <span>{new Date(trade.timestamp).toISOString().slice(0, 10)}</span>
                <strong className={`side side-${trade.side}`}>{trade.side}</strong>
                <span>{money(trade.price, currency)}</span>
                <span>{quantity(trade.quantity)}</span>
                <span>{money(trade.notional, currency)}</span>
              </div>
            ))}
            {trades.length === 0 ? (
              <div className="stock-handoff-detail-empty">No linked paper trades available.</div>
            ) : null}
          </div>
          <div className="stock-handoff-broker-evals">
            {brokerEvaluations.map((evaluation) => {
              const fill = evaluation.paper_fill_estimate;
              return (
                <div className="stock-handoff-broker-row" key={evaluation.id}>
                  <div>
                    <strong>{evaluation.normalized_symbol ?? evaluation.request.symbol.toUpperCase()}</strong>
                    <span>{shortDateTime(evaluation.checked_at)}</span>
                  </div>
                  <span className={`broker-intent-state broker-intent-${evaluation.submission_status}`}>
                    {evaluation.submission_status.replaceAll('_', ' ')}
                  </span>
                  <span>{fill?.status.replaceAll('_', ' ') ?? '-'}</span>
                  <span>{fill?.fill_price ? money(fill.fill_price, 'USD') : '-'}</span>
                  <span>{fill?.cash_after !== undefined && fill?.cash_after !== null ? money(fill.cash_after, 'USD') : '-'}</span>
                  <span>external: {evaluation.external_submission_attempted ? 'yes' : 'no'}</span>
                </div>
              );
            })}
            {brokerEvaluations.length === 0 ? (
              <div className="stock-handoff-detail-empty">No broker intent evaluations for this symbol.</div>
            ) : null}
          </div>
          <div className="stock-handoff-order-notes">
            {orderNotes.map((note) => (
              <div className="stock-handoff-order-note-row" key={note.id}>
                <div>
                  <strong>{note.symbol}</strong>
                  <span>{note.adapter_id.replaceAll('_', ' ')}</span>
                </div>
                <span>{note.side} {quantity(note.quantity)}</span>
                <span>{money(note.intended_fill_price, 'USD')}</span>
                <span>
                  sim {note.simulated_fill_price !== undefined && note.simulated_fill_price !== null
                    ? money(note.simulated_fill_price, 'USD')
                    : '-'}
                </span>
                <span>
                  Δ {note.price_delta_pct !== undefined && note.price_delta_pct !== null
                    ? percent(note.price_delta_pct)
                    : '-'}
                </span>
                <span>{note.comparison_status.replaceAll('_', ' ')}</span>
              </div>
            ))}
            {orderNotes.length === 0 ? (
              <div className="stock-handoff-detail-empty">No linked paper fill order notes yet.</div>
            ) : null}
          </div>
        </>
      ) : null}
    </div>
  );
}

function LiveReadinessPanel({
  readiness,
  decisions,
  decisionStatus,
  decisionNote,
  decisionLoading,
  decisionMessage,
  loading,
  error,
  onRefresh,
  onDecisionStatusChange,
  onDecisionNoteChange,
  onSaveDecision,
}: {
  readiness: LiveReadinessResponse | null;
  decisions: OperatorDecisionRecord[];
  decisionStatus: OperatorDecisionStatus;
  decisionNote: string;
  decisionLoading: boolean;
  decisionMessage: string | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
  onDecisionStatusChange: (status: OperatorDecisionStatus) => void;
  onDecisionNoteChange: (note: string) => void;
  onSaveDecision: () => void;
}) {
  const status = readiness?.status ?? 'watch';
  const score = readiness ? Math.round(readiness.score) : 0;
  const checks = readiness?.checks ?? [];
  const breakdowns = readiness?.breakdowns ?? [];
  const statusOptions: { value: OperatorDecisionStatus; label: string }[] = [
    { value: 'noted', label: 'Noted' },
    { value: 'needs_work', label: 'Needs work' },
    { value: 'approved', label: 'Approved' },
    { value: 'rejected', label: 'Rejected' },
  ];

  return (
    <section className="panel readiness-panel">
      <div className="panel-title">
        <Activity size={18} />
        <h2>Live readiness</h2>
        <button
          className="icon-button"
          onClick={onRefresh}
          disabled={loading}
          title="Refresh live readiness score"
          type="button"
        >
          <RefreshCcw size={15} />
        </button>
        <span className={`readiness-state readiness-${status}`}>{status}</span>
      </div>
      <div className="readiness-score-grid">
        <div className="readiness-score-card">
          <span>Score</span>
          <strong>{loading && !readiness ? '-' : score}</strong>
          <p>{readiness?.checked_at ? `Checked ${shortDateTime(readiness.checked_at)}` : 'Checking readiness state.'}</p>
        </div>
        <div className="readiness-score-card">
          <span>Blocking checks</span>
          <strong>{checks.filter((check) => check.status === 'fail').length}</strong>
          <p>{checks.filter((check) => check.status === 'warn').length} warnings remain</p>
        </div>
      </div>
      <div className="readiness-breakdown-grid">
        {breakdowns.map((breakdown) => (
          <div
            className={`readiness-breakdown-card readiness-breakdown-${breakdown.status}`}
            key={breakdown.id}
          >
            <div>
              <span>{breakdown.label}</span>
              <strong>{Math.round(breakdown.score)}</strong>
            </div>
            <p>{breakdown.message}</p>
            <small>
              {breakdown.blocking_checks.length} blockers · {breakdown.warning_checks.length} warnings
            </small>
          </div>
        ))}
        {breakdowns.length === 0 ? (
          <div className="readiness-empty">Readiness views have not loaded yet.</div>
        ) : null}
      </div>
      <div className="readiness-list">
        {checks.map((check) => (
          <div className={`readiness-row readiness-row-${check.status}`} key={check.id}>
            <div>
              <strong>
                {check.label}
                <span className={`readiness-category readiness-category-${check.category}`}>
                  {check.category}
                </span>
              </strong>
              <p>{check.message}</p>
            </div>
            <span className={`readiness-check-state readiness-check-${check.status}`}>
              {check.status}
            </span>
          </div>
        ))}
        {checks.length === 0 ? (
          <div className="readiness-empty">Readiness checks have not loaded yet.</div>
        ) : null}
      </div>
      <div className="operator-decision-box">
        <div className="operator-decision-form">
          <select
            value={decisionStatus}
            onChange={(event) => onDecisionStatusChange(event.target.value as OperatorDecisionStatus)}
            title="Readiness decision status"
          >
            {statusOptions.map((option) => (
              <option value={option.value} key={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <input
            value={decisionNote}
            onChange={(event) => onDecisionNoteChange(event.target.value)}
            placeholder="Operator note"
            title="Operator readiness note"
          />
          <button
            className="tertiary-button compact-action"
            onClick={onSaveDecision}
            disabled={!readiness || decisionLoading}
            title="Save this readiness review decision"
            type="button"
          >
            <Save size={15} />
            {decisionLoading ? 'Saving...' : 'Log'}
          </button>
        </div>
        {decisionMessage ? <p className="success-message">{decisionMessage}</p> : null}
        <div className="operator-decision-list">
          {decisions.map((decision) => (
            <div className="operator-decision-row" key={decision.id}>
              <div>
                <strong>{decision.status.replaceAll('_', ' ')}</strong>
                <p>{decision.note || 'No operator note.'}</p>
              </div>
              <span>{shortDateTime(decision.created_at)}</span>
            </div>
          ))}
          {decisions.length === 0 ? (
            <div className="readiness-empty">No operator decisions logged yet.</div>
          ) : null}
        </div>
      </div>
      {error ? <p className="error-message">{error}</p> : null}
    </section>
  );
}

function CutoverChecklistPanel({
  checklist,
  decisionStatus,
  decisionNote,
  decisionLoading,
  decisionMessage,
  runbookExporting,
  simulation,
  simulationLoading,
  assumeSimulationDecisions,
  loading,
  error,
  onRefresh,
  onExportRunbook,
  onSimulateArming,
  onAssumeSimulationDecisionsChange,
  onDecisionStatusChange,
  onDecisionNoteChange,
  onSaveDecision,
}: {
  checklist: LiveCutoverChecklistResponse | null;
  decisionStatus: OperatorDecisionStatus;
  decisionNote: string;
  decisionLoading: boolean;
  decisionMessage: string | null;
  runbookExporting: boolean;
  simulation: LiveArmingSimulationResponse | null;
  simulationLoading: boolean;
  assumeSimulationDecisions: boolean;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
  onExportRunbook: () => void;
  onSimulateArming: () => void;
  onAssumeSimulationDecisionsChange: (assume: boolean) => void;
  onDecisionStatusChange: (status: OperatorDecisionStatus) => void;
  onDecisionNoteChange: (note: string) => void;
  onSaveDecision: () => void;
}) {
  const status = checklist?.status ?? 'watch';
  const items = checklist?.items ?? [];
  const decisions = checklist?.latest_operator_decisions ?? [];
  const requiredDecisionIds = [
    'readiness_review_decision',
    'dry_run_approval_decision',
    'live_cutover_decision',
  ];
  const approvedDecisionCount = items.filter(
    (item) => requiredDecisionIds.includes(item.id) && item.status === 'pass',
  ).length;
  const statusOptions: { value: OperatorDecisionStatus; label: string }[] = [
    { value: 'needs_work', label: 'Needs work' },
    { value: 'approved', label: 'Approved' },
    { value: 'noted', label: 'Noted' },
    { value: 'rejected', label: 'Rejected' },
  ];
  const simulationChanges = simulation?.changes.filter((change) => change.changed) ?? [];
  const simulatedBlockers = simulation?.simulated_blockers ?? [];
  const currentSimulatedBlockers =
    simulation?.current_blockers.length ?? 0;
  const armedSimulatedBlockers =
    simulation?.simulated_blockers.length ?? 0;

  return (
    <section className="panel readiness-panel cutover-panel">
      <div className="panel-title">
        <ShieldCheck size={18} />
        <h2>Live cutover</h2>
        <button
          className="icon-button"
          onClick={onRefresh}
          disabled={loading}
          title="Refresh live cutover checklist"
          type="button"
        >
          <RefreshCcw size={15} />
        </button>
        <button
          className="icon-button"
          onClick={onExportRunbook}
          disabled={runbookExporting}
          title="Export live adapter arming runbook"
          type="button"
        >
          <Download size={15} />
        </button>
        <span className={`readiness-state readiness-${status}`}>{status}</span>
      </div>
      <div className="readiness-score-grid">
        <div className="readiness-score-card">
          <span>Required decisions</span>
          <strong>{loading && !checklist ? '-' : `${approvedDecisionCount}/3`}</strong>
          <p>{checklist?.checked_at ? `Checked ${shortDateTime(checklist.checked_at)}` : 'Checking cutover state.'}</p>
        </div>
        <div className="readiness-score-card">
          <span>Blockers</span>
          <strong>{items.filter((item) => item.status === 'fail').length}</strong>
          <p>{items.filter((item) => item.status === 'warn').length} warnings remain</p>
        </div>
      </div>
      <div className="readiness-list">
        {items.map((item) => (
          <div className={`readiness-row readiness-row-${item.status}`} key={item.id}>
            <div>
              <strong>{item.label}</strong>
              <p>{item.message}</p>
            </div>
            <span className={`readiness-check-state readiness-check-${item.status}`}>
              {item.status}
            </span>
          </div>
        ))}
        {items.length === 0 ? (
          <div className="readiness-empty">Cutover checklist has not loaded yet.</div>
        ) : null}
      </div>
      <div className="operator-decision-box">
        <div className="operator-decision-form">
          <select
            value={decisionStatus}
            onChange={(event) => onDecisionStatusChange(event.target.value as OperatorDecisionStatus)}
            title="Live cutover decision status"
          >
            {statusOptions.map((option) => (
              <option value={option.value} key={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <input
            value={decisionNote}
            onChange={(event) => onDecisionNoteChange(event.target.value)}
            placeholder="Cutover note"
            title="Live cutover note"
          />
          <button
            className="tertiary-button compact-action"
            onClick={onSaveDecision}
            disabled={!checklist || decisionLoading}
            title="Save this live cutover decision"
            type="button"
          >
            <Save size={15} />
            {decisionLoading ? 'Saving...' : 'Log'}
          </button>
        </div>
        {decisionMessage ? <p className="success-message">{decisionMessage}</p> : null}
        <div className="operator-decision-list">
          {decisions.slice(0, 5).map((decision) => (
            <div className="operator-decision-row" key={decision.id}>
              <div>
                <strong>{decision.decision_type.replaceAll('_', ' ')} · {decision.status.replaceAll('_', ' ')}</strong>
                <p>{decision.note || decision.target_id || 'No operator note.'}</p>
              </div>
              <span>{shortDateTime(decision.created_at)}</span>
            </div>
          ))}
          {decisions.length === 0 ? (
            <div className="readiness-empty">No cutover-related decisions logged yet.</div>
          ) : null}
        </div>
      </div>
      <div className="arming-simulation-box">
        <div className="arming-simulation-actions">
          <label className="toggle-inline">
            <input
              checked={assumeSimulationDecisions}
              onChange={(event) => onAssumeSimulationDecisionsChange(event.target.checked)}
              type="checkbox"
            />
            Assume approvals
          </label>
          <button
            className="tertiary-button compact-action"
            onClick={onSimulateArming}
            disabled={simulationLoading}
            title="Preview live flag, ACK, and credential arming"
            type="button"
          >
            <Radio size={15} />
            {simulationLoading ? 'Simulating...' : 'Simulate armed'}
          </button>
        </div>
        {simulation ? (
          <>
            <div className="readiness-score-grid">
              <div className="readiness-score-card">
                <span>Current blockers</span>
                <strong>{currentSimulatedBlockers}</strong>
                <p>{simulation.current.status} at {shortTime(simulation.current.checked_at)}</p>
              </div>
              <div className="readiness-score-card">
                <span>Armed preview</span>
                <strong>{armedSimulatedBlockers}</strong>
                <p>{simulation.simulated.status} · no orders submitted</p>
              </div>
            </div>
            <p className="settings-note">{simulation.summary}</p>
            <div className="readiness-list">
              {simulatedBlockers.map((item) => (
                <div className="readiness-row readiness-row-fail" key={item.id}>
                  <div>
                    <strong>{item.label}</strong>
                    <p>{item.message}</p>
                  </div>
                  <span className="readiness-check-state readiness-check-fail">
                    blocker
                  </span>
                </div>
              ))}
              {simulatedBlockers.length === 0 ? (
                <div className="readiness-empty">No blockers remain in the armed preview.</div>
              ) : null}
            </div>
            <div className="readiness-list">
              {simulationChanges.map((change) => (
                <div
                  className={`readiness-row readiness-row-${change.simulated_status}`}
                  key={change.id}
                >
                  <div>
                    <strong>{change.label}</strong>
                    <p>{change.current_status} to {change.simulated_status}: {change.simulated_message}</p>
                  </div>
                  <span className={`readiness-check-state readiness-check-${change.simulated_status}`}>
                    {change.simulated_status}
                  </span>
                </div>
              ))}
              {simulationChanges.length === 0 ? (
                <div className="readiness-empty">No simulated checklist changes.</div>
              ) : null}
            </div>
          </>
        ) : null}
      </div>
      {error ? <p className="error-message">{error}</p> : null}
    </section>
  );
}

function PostCutoverMonitorPanel({
  monitor,
  loading,
  exporting,
  error,
  onRefresh,
  onExportCloseout,
}: {
  monitor: PostCutoverOrderMonitor | null;
  loading: boolean;
  exporting: boolean;
  error: string | null;
  onRefresh: () => void;
  onExportCloseout: () => void;
}) {
  const status = monitor?.status ?? 'idle';
  const counts = monitor?.counts ?? {};
  const attempts = monitor?.recent_approval_attempts.slice(0, 4) ?? [];
  const openOrders = monitor?.open_orders.slice(0, 4) ?? [];
  const items = monitor?.items ?? [];

  return (
    <section className="panel post-cutover-panel">
      <div className="panel-title">
        <Radio size={18} />
        <h2>Post-cutover monitor</h2>
        <button
          className="icon-button"
          onClick={onRefresh}
          disabled={loading}
          title="Refresh post-cutover order monitor"
          type="button"
        >
          <RefreshCcw size={15} />
        </button>
        <button
          className="icon-button"
          onClick={onExportCloseout}
          disabled={exporting}
          title="Export live-window closeout report"
          type="button"
        >
          <Download size={15} />
        </button>
        <span className={`monitor-state monitor-${status}`}>{status}</span>
      </div>
      <div className="execution-grid">
        <div>
          <span>Approval attempts</span>
          <strong>{counts.approval_attempts ?? 0}</strong>
        </div>
        <div>
          <span>Submitted</span>
          <strong>{counts.submitted ?? 0}</strong>
        </div>
        <div>
          <span>Blocked/failed</span>
          <strong>{(counts.blocked ?? 0) + (counts.failed ?? 0)}</strong>
        </div>
        <div>
          <span>Open orders</span>
          <strong>{counts.open_orders ?? 0}</strong>
        </div>
      </div>
      <p className="execution-refresh-meta">
        {loading ? 'Refreshing post-cutover monitor...' : `Checked ${monitor?.checked_at ? shortDateTime(monitor.checked_at) : '-'}`}
      </p>
      {monitor?.private_snapshot_error ? (
        <p className="error-message">{monitor.private_snapshot_error}</p>
      ) : null}
      <div className="readiness-list">
        {items.map((item) => (
          <div className={`readiness-row readiness-row-${item.status}`} key={item.id}>
            <div>
              <strong>{item.label}</strong>
              <p>{item.message}</p>
            </div>
            <span className={`readiness-check-state readiness-check-${item.status}`}>
              {item.status}
            </span>
          </div>
        ))}
        {items.length === 0 ? (
          <div className="readiness-empty">Post-cutover monitor has not loaded yet.</div>
        ) : null}
      </div>
      <div className="audit-list">
        {attempts.map((audit) => (
          <div className="audit-row" key={audit.id}>
            <div>
              <strong>{audit.market}</strong>
              <span>{audit.side}</span>
              <span>{shortTime(audit.created_at)}</span>
            </div>
            <div>
              <span className={`audit-status audit-${audit.status}`}>{audit.status}</span>
              <span>{audit.reason}</span>
            </div>
          </div>
        ))}
        {attempts.length === 0 ? (
          <div className="audit-empty">No approved live attempts have been recorded.</div>
        ) : null}
      </div>
      {openOrders.length > 0 ? (
        <div className="audit-list">
          {openOrders.map((order) => (
            <div className="audit-row" key={order.uuid}>
              <div>
                <strong>{order.market}</strong>
                <span>{order.side}</span>
                <span>{order.state}</span>
              </div>
              <div>
                <span>{money(order.price ?? undefined)}</span>
                <span>remaining {quantity(order.remaining_volume ?? order.volume ?? undefined)}</span>
              </div>
            </div>
          ))}
        </div>
      ) : null}
      {error ? <p className="error-message">{error}</p> : null}
    </section>
  );
}

function StrategyHealthTracePanel({
  trace,
  loading,
  exporting,
  drillExporting,
  error,
  onRefresh,
  onExport,
  onExportDrill,
}: {
  trace: StrategyHealthTraceResponse | null;
  loading: boolean;
  exporting: boolean;
  drillExporting: boolean;
  error: string | null;
  onRefresh: () => void;
  onExport: () => void;
  onExportDrill: () => void;
}) {
  const traces = trace?.traces.slice(0, 4) ?? [];
  const counts = trace?.counts ?? {};

  return (
    <section className="panel strategy-health-panel">
      <div className="panel-title">
        <TrendingUp size={18} />
        <h2>Strategy health trace</h2>
        <button
          className="icon-button"
          onClick={onRefresh}
          disabled={loading}
          title="Refresh paper to live strategy trace"
          type="button"
        >
          <RefreshCcw size={15} />
        </button>
        <button
          className="icon-button"
          onClick={onExport}
          disabled={exporting || loading}
          title="Export strategy health handoff report"
          type="button"
        >
          <Download size={15} />
        </button>
        <button
          className="icon-button"
          onClick={onExportDrill}
          disabled={drillExporting || loading}
          title="Export crypto live beta drill report"
          type="button"
        >
          <FileText size={15} />
        </button>
        <span className="journal-count">
          {trace?.checked_at ? shortTime(trace.checked_at) : '-'}
        </span>
      </div>
      <div className="execution-grid">
        <div>
          <span>Traces</span>
          <strong>{counts.traces ?? 0}</strong>
        </div>
        <div>
          <span>Healthy</span>
          <strong>{counts.healthy ?? 0}</strong>
        </div>
        <div>
          <span>Watch</span>
          <strong>{counts.watch ?? 0}</strong>
        </div>
        <div>
          <span>Attention</span>
          <strong>{(counts.attention ?? 0) + (counts.blocked ?? 0)}</strong>
        </div>
      </div>
      <div className="strategy-trace-list">
        {traces.map((item) => {
          const firstProblem = item.milestones.find((milestone) => milestone.status !== 'pass');
          return (
            <div className="strategy-trace-row" key={item.id}>
              <div>
                <strong>{item.scenario_name ?? item.market}</strong>
                <p>
                  {item.market} {item.side} · {money(item.simulated_notional ?? undefined)} · closeout {item.closeout_status ?? 'pending'}
                </p>
                <p>
                  {firstProblem ? firstProblem.message : 'Paper trade, dry-run review, and closeout milestones are linked.'}
                </p>
              </div>
              <div>
                <span className={`strategy-health-state strategy-health-${item.status}`}>
                  {item.status}
                </span>
                <span>{item.approval_decisions.length} reviews</span>
                <span>{item.approval_attempts.length} attempts</span>
              </div>
            </div>
          );
        })}
        {traces.length === 0 ? (
          <div className="readiness-empty">No dry-run strategy traces are available yet.</div>
        ) : null}
      </div>
      {error ? <p className="error-message">{error}</p> : null}
    </section>
  );
}

function EnvironmentChecklistPanel({
  settings,
  selfCheck,
  providers,
}: {
  settings: ExecutionSettings | null;
  selfCheck: OpsSelfCheckResponse | null;
  providers: MarketDataProviderStatus[];
}) {
  const alphaProvider = providers.find((provider) => provider.source === 'alpha_vantage');
  const upbitProvider = providers.find((provider) => provider.source === 'upbit');
  const checkedAt = settings?.checked_at ?? upbitProvider?.status_checked_at ?? alphaProvider?.status_checked_at;
  const items: {
    label: string;
    value: string;
    state: ChecklistState;
    detail: string;
  }[] = [
    {
      label: 'ALPHA_VANTAGE_API_KEY',
      value: alphaProvider ? (alphaProvider.configured ? 'configured' : 'missing') : 'checking',
      state: alphaProvider?.configured ? 'ready' : 'warn',
      detail: alphaProvider?.configured
        ? 'US stock/ETF daily data is available.'
        : alphaProvider
          ? 'Real US stock/ETF data is off; sample_us remains available.'
          : 'Checking stock/ETF data provider status.',
    },
    {
      label: 'UPBIT_ACCESS_KEY / SECRET',
      value: settings ? (settings.credential_configured ? 'configured' : 'missing') : 'checking',
      state: settings ? (settings.credential_configured ? 'ready' : 'missing') : 'warn',
      detail: settings?.credential_configured
        ? 'Private reads and Upbit order chance prechecks are enabled.'
        : settings
          ? 'Private reads use the disabled state and prechecks use local defaults.'
          : 'Checking execution credential status.',
    },
    {
      label: 'QUANT_LAB_LIVE_TRADING_ENABLED',
      value: settings ? (settings.live_trading_enabled ? 'on' : 'off') : 'checking',
      state: settings?.live_trading_enabled ? 'ready' : 'warn',
      detail: settings?.live_trading_enabled
        ? 'Live routing can continue to the ACK and confirmation gates.'
        : settings
          ? 'Live exchange orders remain locked.'
          : 'Checking live routing flag.',
    },
    {
      label: 'QUANT_LAB_LIVE_TRADING_ACK',
      value: settings ? (settings.live_ack_configured ? 'set' : 'missing') : 'checking',
      state: settings ? (settings.live_ack_configured ? 'ready' : 'missing') : 'warn',
      detail: `Required value: ${settings?.live_ack_required_value ?? 'REAL_ORDERS_OK'}.`,
    },
    {
      label: 'Approval guardrails',
      value: settings
        ? `${money(settings.min_order_notional_krw)} · ${feeRate(settings.approval_fee_rate)} · ${percent(settings.max_approval_exposure_pct)}`
        : '-',
      state: settings ? 'ready' : 'warn',
      detail: 'Minimum notional, fee assumption, and max post-order exposure.',
    },
    {
      label: 'Ops self-check',
      value: selfCheck ? selfCheck.status : 'checking',
      state: selfCheck ? 'ready' : 'warn',
      detail: selfCheck
        ? `DB ${selfCheck.database_path} · scheduler ${selfCheck.scheduler.enabled ? 'on' : 'off'} every ${selfCheck.scheduler.poll_seconds}s.`
        : 'Checking backend deployment metadata.',
    },
    {
      label: 'Artifact paths',
      value: selfCheck ? Object.keys(selfCheck.artifact_paths).length.toString() : '-',
      state: selfCheck ? 'ready' : 'warn',
      detail: selfCheck
        ? `Drills ${selfCheck.artifact_paths.crypto_drills}; verification ${selfCheck.artifact_paths.verification}.`
        : 'Checking artifact conventions.',
    },
  ];
  const runbooks = selfCheck?.runbooks ?? [];

  return (
    <section className="panel environment-panel">
      <div className="panel-title">
        <KeyRound size={18} />
        <h2>Setup checklist</h2>
        <span className="checklist-updated">
          {checkedAt ? shortDateTime(checkedAt) : '-'}
        </span>
      </div>
      <div className="checklist-list">
        {items.map((item) => (
          <div className="checklist-row" key={item.label}>
            <div>
              <strong>{item.label}</strong>
              <p>{item.detail}</p>
            </div>
            <span className={`checklist-state checklist-${item.state}`}>
              {item.value}
            </span>
          </div>
        ))}
      </div>
      <div className="checklist-list">
        {runbooks.map((runbook) => (
          <a
            className="checklist-row"
            href={`${API_BASE_URL}${runbook.api_path}`}
            key={runbook.id}
            rel="noreferrer"
            target="_blank"
            title={runbook.description}
          >
            <div>
              <strong>{runbook.title}</strong>
              <p>{runbook.path}</p>
            </div>
            <span className="checklist-state checklist-ready">runbook</span>
          </a>
        ))}
      </div>
    </section>
  );
}

function AlertReviewPanel({
  review,
  filters,
  error,
  onRefresh,
  onFiltersChange,
  onAcknowledge,
}: {
  review: AlertReviewResponse | null;
  filters: AlertReviewFilters;
  error: string | null;
  onRefresh: () => void;
  onFiltersChange: (filters: AlertReviewFilters) => void;
  onAcknowledge: (alertId: string, status: 'acknowledged' | 'dismissed') => void;
}) {
  const items = review?.items.slice(0, 6) ?? [];
  const warnings = review?.counts.warning ?? 0;
  const halts = review?.counts.halt ?? 0;
  const errors = review?.counts.error ?? 0;
  const sourceOptions: { value: AlertSourceFilter; label: string }[] = [
    { value: 'all', label: 'All sources' },
    { value: 'portfolio_scan', label: 'Scan alert' },
    { value: 'portfolio_scan_error', label: 'Scan error' },
    { value: 'paper_watchlist_error', label: 'Paper watch error' },
    { value: 'paper_session_risk', label: 'Paper risk' },
    { value: 'paper_session_halt', label: 'Paper halt' },
    { value: 'broker_paper_submission', label: 'Broker paper' },
    { value: 'broker_reconciliation', label: 'Broker reconcile' },
    { value: 'paper_fill_drift', label: 'Fill drift' },
  ];

  return (
    <section className="panel alert-review-panel">
      <div className="panel-title">
        <AlertTriangle size={18} />
        <h2>Alert review</h2>
        <button
          className="icon-button"
          onClick={onRefresh}
          title="Refresh alert review queue"
          type="button"
        >
          <RefreshCcw size={15} />
        </button>
        <span className="alert-reviewed-at">
          {review?.checked_at ? shortTime(review.checked_at) : '-'}
        </span>
      </div>
      <div className="alert-filter-row">
        <select
          value={filters.severity}
          onChange={(event) =>
            onFiltersChange({
              ...filters,
              severity: event.target.value as AlertSeverityFilter,
            })
          }
          title="Filter alerts by severity"
        >
          <option value="all">All severities</option>
          <option value="warning">Warning</option>
          <option value="halt">Halt</option>
          <option value="error">Error</option>
          <option value="info">Info</option>
        </select>
        <select
          value={filters.source}
          onChange={(event) =>
            onFiltersChange({
              ...filters,
              source: event.target.value as AlertSourceFilter,
            })
          }
          title="Filter alerts by source"
        >
          {sourceOptions.map((option) => (
            <option value={option.value} key={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <input
          value={filters.scenario}
          onChange={(event) =>
            onFiltersChange({
              ...filters,
              scenario: event.target.value,
            })
          }
          placeholder="Scenario"
          title="Filter alerts by scenario name or ID"
        />
        <button
          className="icon-button"
          onClick={() => onFiltersChange(defaultAlertFilters)}
          title="Reset alert filters"
          type="button"
        >
          <Trash2 size={15} />
        </button>
      </div>
      <div className="alert-summary-grid">
        <div>
          <span>Warnings</span>
          <strong>{warnings}</strong>
        </div>
        <div>
          <span>Halts</span>
          <strong>{halts}</strong>
        </div>
        <div>
          <span>Errors</span>
          <strong>{errors}</strong>
        </div>
      </div>
      <div className="alert-review-list">
        {items.map((item) => (
          <div className={`alert-review-row alert-level-${item.level}`} key={item.id}>
            <div>
              <strong>{item.title}</strong>
              <p>{item.message}</p>
            </div>
            <div>
              <span>{item.symbol ?? item.scenario_name ?? item.source.replaceAll('_', ' ')}</span>
              <span>{item.rule ? item.rule.replaceAll('_', ' ') : item.source.replaceAll('_', ' ')}</span>
              {item.evaluation_id ? <span>eval {item.evaluation_id.slice(0, 8)}</span> : null}
              {item.reconciliation_id ? <span>recon {item.reconciliation_id.slice(0, 8)}</span> : null}
              <span>{shortDateTime(item.created_at)}</span>
            </div>
            <div className="alert-review-actions">
              <button
                className="tertiary-button compact-action"
                onClick={() => onAcknowledge(item.id, 'acknowledged')}
                title="Mark this alert as reviewed"
                type="button"
              >
                <ShieldCheck size={15} />
                Ack
              </button>
              <button
                className="icon-button"
                onClick={() => onAcknowledge(item.id, 'dismissed')}
                title="Dismiss this alert"
                type="button"
              >
                <Trash2 size={15} />
              </button>
            </div>
          </div>
        ))}
        {items.length === 0 ? (
          <div className="alert-review-empty">No scan or paper watch alerts need review.</div>
        ) : null}
      </div>
      {error ? <p className="error-message">{error}</p> : null}
    </section>
  );
}

function OperationsJournalPanel({
  decisions,
  filters,
  loading,
  exporting,
  runbookLoadingId,
  error,
  onRefresh,
  onExport,
  onExportRunbook,
  onFiltersChange,
}: {
  decisions: OperatorDecisionRecord[];
  filters: OperatorJournalFilters;
  loading: boolean;
  exporting: boolean;
  runbookLoadingId: string | null;
  error: string | null;
  onRefresh: () => void;
  onExport: () => void;
  onExportRunbook: (recordId: string) => void;
  onFiltersChange: (filters: OperatorJournalFilters) => void;
}) {
  const typeOptions: { value: OperatorDecisionTypeFilter; label: string }[] = [
    { value: 'all', label: 'All types' },
    { value: 'readiness_review', label: 'Readiness' },
    { value: 'dry_run_promotion', label: 'Promotion' },
    { value: 'dry_run_approval', label: 'Order review' },
    { value: 'alert_review', label: 'Alert review' },
    { value: 'live_cutover', label: 'Cutover' },
  ];
  const statusOptions: { value: OperatorDecisionStatusFilter; label: string }[] = [
    { value: 'all', label: 'All statuses' },
    { value: 'noted', label: 'Noted' },
    { value: 'needs_work', label: 'Needs work' },
    { value: 'approved', label: 'Approved' },
    { value: 'rejected', label: 'Rejected' },
  ];
  const routeOptions: { value: OperatorRouteStatusFilter; label: string }[] = [
    { value: 'all', label: 'All routes' },
    { value: 'paper_only_review', label: 'Paper-only handoffs' },
    { value: 'dry_run_ready', label: 'Dry-run ready' },
    { value: 'unsupported', label: 'Unsupported' },
  ];

  return (
    <section className="panel operations-journal-panel">
      <div className="panel-title">
        <History size={18} />
        <h2>Operations journal</h2>
        <button
          className="icon-button"
          onClick={onRefresh}
          disabled={loading}
          title="Refresh operations journal"
          type="button"
        >
          <RefreshCcw size={15} />
        </button>
        <button
          className="icon-button"
          onClick={onExport}
          disabled={exporting}
          title="Export operations journal report"
          type="button"
        >
          <Download size={15} />
        </button>
        <span className="journal-count">{decisions.length} logs</span>
      </div>
      <div className="journal-filter-row">
        <select
          value={filters.decisionType}
          onChange={(event) =>
            onFiltersChange({
              ...filters,
              decisionType: event.target.value as OperatorDecisionTypeFilter,
            })
          }
          title="Filter journal by decision type"
        >
          {typeOptions.map((option) => (
            <option value={option.value} key={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <select
          value={filters.status}
          onChange={(event) =>
            onFiltersChange({
              ...filters,
              status: event.target.value as OperatorDecisionStatusFilter,
            })
          }
          title="Filter journal by decision status"
        >
          {statusOptions.map((option) => (
            <option value={option.value} key={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <select
          value={filters.routeStatus}
          onChange={(event) =>
            onFiltersChange({
              ...filters,
              routeStatus: event.target.value as OperatorRouteStatusFilter,
            })
          }
          title="Filter journal by paper-to-live route status"
        >
          {routeOptions.map((option) => (
            <option value={option.value} key={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <input
          value={filters.targetId}
          onChange={(event) =>
            onFiltersChange({
              ...filters,
              targetId: event.target.value,
            })
          }
          placeholder="Target ID"
          title="Filter journal by target ID"
        />
        <button
          className="icon-button"
          onClick={() => onFiltersChange(defaultOperatorJournalFilters)}
          title="Reset journal filters"
          type="button"
        >
          <Trash2 size={15} />
        </button>
      </div>
      <div className="journal-list">
        {decisions.map((decision) => {
          const routeStatus = typeof decision.context.route_status === 'string'
            ? decision.context.route_status
            : null;
          const symbol = typeof decision.context.symbol === 'string'
            ? decision.context.symbol
            : null;
          const adapterLabel = typeof decision.context.adapter_label === 'string'
            ? decision.context.adapter_label
            : null;
          return (
            <div className="journal-row" key={decision.id}>
              <div>
                <strong>{decision.decision_type.replaceAll('_', ' ')}</strong>
                <p>{decision.note || 'No operator note.'}</p>
                {routeStatus ? (
                  <div className="journal-route-meta">
                    <span className={`journal-route journal-route-${routeStatus}`}>
                      {routeStatus.replaceAll('_', ' ')}
                    </span>
                    {symbol ? <span>{symbol}</span> : null}
                    {adapterLabel ? <span>{adapterLabel}</span> : null}
                  </div>
                ) : null}
              </div>
              <div>
                <span className={`journal-state journal-${decision.status}`}>
                  {decision.status.replaceAll('_', ' ')}
                </span>
                <span>{decision.target_id ?? '-'}</span>
                <span>{shortDateTime(decision.created_at)}</span>
                {decision.decision_type === 'dry_run_approval' && decision.target_id ? (
                  <button
                    className="icon-button journal-runbook-button"
                    onClick={() => decision.target_id ? onExportRunbook(decision.target_id) : undefined}
                    disabled={runbookLoadingId === decision.target_id}
                    title="Export linked dry-run approval runbook"
                    type="button"
                  >
                    <Download size={15} />
                  </button>
                ) : null}
              </div>
            </div>
          );
        })}
        {decisions.length === 0 ? (
          <div className="journal-empty">No operator decisions match the current filters.</div>
        ) : null}
      </div>
      {error ? <p className="error-message">{error}</p> : null}
    </section>
  );
}

function OrderReviewPanel({
  status,
  audits,
  prechecks,
  approvingId,
  runbookLoadingId,
  decisionLoading,
  message,
  onApprove,
  onExportRunbook,
  onLogDecision,
}: {
  status: ExecutionStatus | null;
  audits: OrderAuditRecord[];
  prechecks: Record<string, OrderPrecheckResult>;
  approvingId: string | null;
  runbookLoadingId: string | null;
  decisionLoading: boolean;
  message: string | null;
  onApprove: (audit: OrderAuditRecord) => void;
  onExportRunbook: (audit: OrderAuditRecord) => void;
  onLogDecision: (audit: OrderAuditRecord, status: OperatorDecisionStatus) => void;
}) {
  const dryRuns = audits.filter((audit) => audit.status === 'dry_run').slice(0, 5);
  const guardLabel = status?.adapter_ready ? 'ready' : 'locked';

  return (
    <section className="panel order-review-panel">
      <div className="panel-title">
        <ShieldCheck size={18} />
        <h2>Order review</h2>
        <span className={`execution-state execution-${guardLabel === 'ready' ? 'armed' : 'locked'}`}>
          {guardLabel}
        </span>
      </div>
      <p className="review-note">
        Dry-run intents require manual confirmation here and the backend live guard before exchange submission.
      </p>
      {message ? <p className="order-queue-message">{message}</p> : null}
      <div className="review-list">
        {dryRuns.map((audit) => {
          const price = payloadNumber(audit.request_payload.price);
          const volume = payloadNumber(audit.request_payload.volume);
          const precheck = prechecks[audit.id];
          const promotion = promotionContext(audit.response_payload);
          return (
            <div className="review-row" key={audit.id}>
              <div className="review-main">
                <strong>{audit.market}</strong>
                <span>{audit.side}</span>
                <span>{audit.ord_type}</span>
              </div>
              <div>
                <span>Price</span>
                <strong>{money(price)}</strong>
              </div>
              <div>
                <span>Qty</span>
                <strong>{quantity(volume)}</strong>
              </div>
              <div>
                <span>Notional</span>
                <strong>{money(precheck?.estimated_notional ?? estimateNotional(price, volume))}</strong>
              </div>
              <div className="precheck-state-wrap">
                <span>Precheck</span>
                <strong className={`precheck-state precheck-${precheck?.status ?? 'warn'}`}>
                  {precheck?.status ?? 'pending'}
                </strong>
              </div>
              <div className="review-actions">
                <button
                  className="tertiary-button compact-action"
                  onClick={() => onApprove(audit)}
                  disabled={approvingId === audit.id || precheck?.status === 'fail'}
                  title="Approve this dry-run intent through the backend live guard"
                  type="button"
                >
                  <ShieldCheck size={15} />
                  {approvingId === audit.id ? 'Approving...' : 'Approve live'}
                </button>
                <button
                  className="icon-button"
                  onClick={() => onExportRunbook(audit)}
                  disabled={runbookLoadingId === audit.id}
                  title="Export dry-run approval runbook"
                  type="button"
                >
                  <Download size={15} />
                </button>
                <button
                  className="icon-button"
                  onClick={() => onLogDecision(audit, 'approved')}
                  disabled={decisionLoading}
                  title="Log approved dry-run review decision"
                  type="button"
                >
                  <Save size={15} />
                </button>
                <button
                  className="icon-button"
                  onClick={() => onLogDecision(audit, 'needs_work')}
                  disabled={decisionLoading}
                  title="Log needs-work dry-run review decision"
                  type="button"
                >
                  <AlertTriangle size={15} />
                </button>
              </div>
              {promotion ? (
                <div className="promotion-context">
                  <span>Promoted from {promotion.scenario_name ?? 'paper watchlist'}</span>
                  <p>
                    return {'>='} {percent(promotion.promotion_rules?.min_total_return_pct)} · DD {'<='} {percent(promotion.promotion_rules?.max_drawdown_pct)} · orders {'>='} {promotion.promotion_rules?.min_orders ?? '-'}
                  </p>
                </div>
              ) : null}
              {precheck ? (
                <div className="precheck-summary">
                  <div className="precheck-meta">
                    <span>{precheck.order_info_source}</span>
                    <p>
                      checked {shortTime(precheck.order_info_checked_at)} · fee {feeRate(precheck.fee_rate)} · min {money(precheck.min_order_notional)}
                      {precheck.max_order_notional ? ` · max ${money(precheck.max_order_notional)}` : ''}
                    </p>
                  </div>
                  {precheck.checks.map((check) => (
                    <div className={`precheck-line precheck-line-${check.status}`} key={check.name}>
                      <span>{check.name}</span>
                      <p>{check.message}</p>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          );
        })}
        {dryRuns.length === 0 ? (
          <div className="review-empty">Queue dry-run intents from a paper session to review them here.</div>
        ) : null}
      </div>
    </section>
  );
}

function PaperPanel({
  session,
  sessions,
  currency,
  queueLoading,
  queueMessage,
  onQueueOrderIntents,
}: {
  session: PaperTradingSession | LivePaperTradingSession | null;
  sessions: LivePaperTradingSession[];
  currency: DisplayCurrency;
  queueLoading: boolean;
  queueMessage: string | null;
  onQueueOrderIntents: () => void;
}) {
  const summary = session?.summary;
  const latestEvents = session?.risk_events.slice(-4).reverse() ?? [];
  const latestSessions = sessions.slice(0, 4);
  const liveProgress = isLiveSession(session)
    ? `${Math.min(session.next_index, session.total_candles)} / ${session.total_candles}`
    : null;
  const liveProgressLabel =
    isLiveSession(session) && session.mode === 'ticker' ? 'Ticker ticks' : 'Replay progress';
  const canQueueExecution = Boolean(session?.request.symbol.startsWith('KRW-'));

  return (
    <section className="panel paper-panel">
      <div className="panel-title">
        <Radio size={18} />
        <h2>Paper trading</h2>
        <span className={`session-status status-${summary?.status ?? 'idle'}`}>
          {summary?.status ?? 'idle'}
        </span>
      </div>
      <div className="paper-action-row">
        <button
          className="tertiary-button compact-action"
          onClick={onQueueOrderIntents}
          disabled={!session || !canQueueExecution || session.trades.length === 0 || queueLoading}
          title={
            canQueueExecution
              ? 'Queue simulated trades as dry-run order intents'
              : 'Dry-run execution queue is available for KRW crypto sessions'
          }
        >
          <ShieldCheck size={15} />
          {queueLoading ? 'Queueing...' : canQueueExecution ? 'Queue dry-run' : 'Paper only'}
        </button>
        <span>{session ? `${session.trades.length} simulated trades` : 'No active paper session'}</span>
      </div>
      {queueMessage ? <p className="order-queue-message">{queueMessage}</p> : null}
      <div className="paper-grid">
        <div>
          <span>Final equity</span>
          <strong>{money(summary?.final_equity, currency)}</strong>
        </div>
        <div>
          <span>Return</span>
          <strong>{percent(summary?.total_return_pct)}</strong>
        </div>
        <div>
          <span>Open position</span>
          <strong>{percent(summary?.open_position_pct)}</strong>
        </div>
        <div>
          <span>Risk events</span>
          <strong>{summary?.risk_events.toString() ?? '-'}</strong>
        </div>
      </div>
      {summary?.halted_reason ? (
        <p className="halt-message">
          <AlertTriangle size={15} />
          {summary.halted_reason}
        </p>
      ) : null}
      {liveProgress ? (
        <div className="live-progress">
          <span>{liveProgressLabel}</span>
          <strong>{liveProgress}</strong>
        </div>
      ) : null}
      {latestSessions.length > 0 ? (
        <div className="session-history">
          <div className="session-history-title">Recent live sessions</div>
          {latestSessions.map((item) => (
            <div className="session-history-row" key={item.id}>
              <div>
                <strong>{item.request.symbol}</strong>
                <span>{shortTime(item.created_at)}</span>
                <span>{item.mode ?? 'replay'}</span>
              </div>
              <div>
                <span className={`session-status status-${item.summary.status}`}>
                  {item.summary.status}
                </span>
                <span>
                  {Math.min(item.next_index, item.total_candles)} / {item.total_candles}
                </span>
              </div>
            </div>
          ))}
        </div>
      ) : null}
      <div className="risk-events">
        {latestEvents.map((event) => (
          <div className={`risk-event event-${event.level}`} key={`${event.timestamp}-${event.rule}`}>
            <span>{event.rule}</span>
            <p>{event.message}</p>
          </div>
        ))}
        {session && latestEvents.length === 0 ? (
          <div className="risk-event">
            <span>clear</span>
            <p>No guardrail events were triggered in this session.</p>
          </div>
        ) : null}
        {!session ? (
          <div className="risk-event">
            <span>ready</span>
            <p>Create a paper session to test strategy orders against guardrails.</p>
          </div>
        ) : null}
      </div>
    </section>
  );
}

function isLiveSession(
  session: PaperTradingSession | LivePaperTradingSession | null,
): session is LivePaperTradingSession {
  return Boolean(session && 'next_index' in session);
}

function defaultWarmupBars(request: BacktestRequest) {
  const strategyMinimum = strategyWarmupMinimum(request);
  const warmup = Math.max(2, 30, strategyMinimum);
  return Math.min(warmup, Math.max(2, request.candle_limit - 1));
}

function defaultParamsForStrategy(strategy: Strategy): Record<string, number> {
  if (strategy === 'sma_crossover') {
    return { fast_window: 10, slow_window: 30 };
  }
  if (strategy === 'donchian_breakout') {
    return { lookback: 20, exit_lookback: 10 };
  }
  return { rsi_window: 14, buy_below: 30, sell_above: 55 };
}

function sweepCandidateLabel(params: Record<string, number>) {
  return Object.entries(params)
    .map(([key, value]) => `${key.replaceAll('_', ' ')} ${value}`)
    .join(' · ');
}

function strategyWarmupMinimum(request: BacktestRequest) {
  if (request.strategy === 'sma_crossover') {
    return Number(request.params.slow_window ?? 30);
  }
  if (request.strategy === 'donchian_breakout') {
    return Number(request.params.lookback ?? 20) + 1;
  }
  return Number(request.params.rsi_window ?? 14) + 1;
}

function Metrics({
  metrics,
  currency,
}: {
  metrics?: BacktestMetrics;
  currency: DisplayCurrency;
}) {
  const items = [
    ['Final equity', money(metrics?.final_equity, currency)],
    ['Return', percent(metrics?.total_return_pct)],
    ['Buy/hold', percent(metrics?.buy_and_hold_return_pct)],
    ['Edge', percent(metrics?.strategy_edge_pct)],
    ['Max drawdown', percent(metrics?.max_drawdown_pct)],
    ['Sharpe', number(metrics?.sharpe)],
  ];

  return (
    <section className="metrics-grid" aria-label="Backtest metrics">
      {items.map(([label, value]) => (
        <div className="metric-card" key={label}>
          <span>{label}</span>
          <strong>{value}</strong>
        </div>
      ))}
    </section>
  );
}

function PortfolioResearchPanel({
  result,
  presets,
  scenarios,
  scans,
  watchlist,
  paperWatchlist,
  symbols,
  selectedSymbols,
  weights,
  rebalanceFrequency,
  loading,
  scenarioLoading,
  scanLoadingId,
  watchlistLoading,
  paperWatchlistLoading,
  scenarioName,
  watchIntervalMinutes,
  alertThresholds,
  scenarioMessage,
  scenarioError,
  currency,
  onApplyPreset,
  onApplyScenario,
  onOpenScan,
  onScanScenario,
  onAddWatchlist,
  onRunDueWatchlist,
  onDeleteWatchlist,
  onAddPaperWatchlist,
  onRunPaperWatchlist,
  onRunDuePaperWatchlist,
  onDeletePaperWatchlist,
  onPromotePaperWatchlist,
  onLogPaperWatchlistDecision,
  onToggleSymbol,
  onWeightChange,
  onRebalanceChange,
  onScenarioNameChange,
  onWatchIntervalChange,
  onAlertThresholdChange,
  onSaveScenario,
  onDeleteScenario,
  onRun,
}: {
  result: PortfolioResearchResponse | null;
  presets: PortfolioResearchPreset[];
  scenarios: PortfolioResearchScenario[];
  scans: PortfolioResearchScan[];
  watchlist: PortfolioResearchWatchlistItem[];
  paperWatchlist: PortfolioPaperWatchlistItem[];
  symbols: string[];
  selectedSymbols: string[];
  weights: Record<string, number>;
  rebalanceFrequency: PortfolioRebalanceFrequency;
  loading: boolean;
  scenarioLoading: boolean;
  scanLoadingId: string | null;
  watchlistLoading: boolean;
  paperWatchlistLoading: boolean;
  scenarioName: string;
  watchIntervalMinutes: number;
  alertThresholds: PortfolioResearchAlertThresholds;
  scenarioMessage: string | null;
  scenarioError: string | null;
  currency: DisplayCurrency;
  onApplyPreset: (preset: PortfolioResearchPreset) => void;
  onApplyScenario: (scenario: PortfolioResearchScenario) => void;
  onOpenScan: (scan: PortfolioResearchScan) => void;
  onScanScenario: (scenarioId: string) => void;
  onAddWatchlist: (scenarioId: string) => void;
  onRunDueWatchlist: () => void;
  onDeleteWatchlist: (itemId: string) => void;
  onAddPaperWatchlist: (scenarioId: string) => void;
  onRunPaperWatchlist: (itemId: string) => void;
  onRunDuePaperWatchlist: () => void;
  onDeletePaperWatchlist: (itemId: string) => void;
  onPromotePaperWatchlist: (itemId: string) => void;
  onLogPaperWatchlistDecision: (item: PortfolioPaperWatchlistItem) => void;
  onToggleSymbol: (symbol: string) => void;
  onWeightChange: (symbol: string, value: number) => void;
  onRebalanceChange: (value: PortfolioRebalanceFrequency) => void;
  onScenarioNameChange: (value: string) => void;
  onWatchIntervalChange: (value: number) => void;
  onAlertThresholdChange: (key: keyof PortfolioResearchAlertThresholds, value: number) => void;
  onSaveScenario: () => void;
  onDeleteScenario: (scenarioId: string) => void;
  onRun: () => void;
}) {
  const [selectedPresetId, setSelectedPresetId] = React.useState('');
  const [selectedScenarioId, setSelectedScenarioId] = React.useState('');
  const metrics = result?.metrics;
  const canRun = selectedSymbols.length >= 2 && !loading;
  const weightTotal = selectedSymbols.reduce((sum, symbol) => sum + (weights[symbol] ?? 0), 0);
  const selectedPreset = presets.find((preset) => preset.id === selectedPresetId);
  const selectedScenario = scenarios.find((scenario) => scenario.id === selectedScenarioId);

  React.useEffect(() => {
    if (!selectedPresetId && presets.length > 0) {
      setSelectedPresetId(presets[0].id);
    }
  }, [presets, selectedPresetId]);

  React.useEffect(() => {
    if (!selectedScenarioId && scenarios.length > 0) {
      setSelectedScenarioId(scenarios[0].id);
    }
    if (selectedScenarioId && !scenarios.some((scenario) => scenario.id === selectedScenarioId)) {
      setSelectedScenarioId(scenarios[0]?.id ?? '');
    }
  }, [scenarios, selectedScenarioId]);

  return (
    <section className="panel portfolio-panel">
      <div className="panel-title">
        <TrendingUp size={18} />
        <h2>Portfolio research</h2>
        <span className="portfolio-count">{selectedSymbols.length} selected</span>
      </div>
      <div className="portfolio-library">
        <label>
          Preset
          <select
            value={selectedPresetId}
            onChange={(event) => setSelectedPresetId(event.target.value)}
          >
            {presets.map((preset) => (
              <option key={preset.id} value={preset.id}>
                {preset.name}
              </option>
            ))}
          </select>
        </label>
        <button
          className="tertiary-button compact-action"
          disabled={!selectedPreset}
          onClick={() => selectedPreset ? onApplyPreset(selectedPreset) : undefined}
          title={selectedPreset?.description ?? 'Apply portfolio preset'}
          type="button"
        >
          <TrendingUp size={15} />
          Apply
        </button>
        <label>
          Saved
          <select
            value={selectedScenarioId}
            onChange={(event) => setSelectedScenarioId(event.target.value)}
          >
            {scenarios.length === 0 ? (
              <option value="">No saved scenarios</option>
            ) : null}
            {scenarios.map((scenario) => (
              <option key={scenario.id} value={scenario.id}>
                {scenario.name}
              </option>
            ))}
          </select>
        </label>
        <button
          className="tertiary-button compact-action"
          disabled={!selectedScenario}
          onClick={() => selectedScenario ? onApplyScenario(selectedScenario) : undefined}
          title="Load saved portfolio scenario"
          type="button"
        >
          <RefreshCcw size={15} />
          Load
        </button>
        <button
          className="tertiary-button compact-action"
          disabled={!selectedScenario || scanLoadingId === selectedScenario?.id}
          onClick={() => selectedScenario ? onScanScenario(selectedScenario.id) : undefined}
          title="Run and save a scan for this portfolio scenario"
          type="button"
        >
          <Activity size={15} />
          {selectedScenario && scanLoadingId === selectedScenario.id ? 'Scanning...' : 'Scan'}
        </button>
        <button
          className="icon-button"
          disabled={!selectedScenario || scenarioLoading || scanLoadingId === selectedScenario?.id}
          onClick={() => selectedScenario ? onDeleteScenario(selectedScenario.id) : undefined}
          title="Delete saved portfolio scenario"
          type="button"
        >
          <Trash2 size={15} />
        </button>
      </div>
      <div className="portfolio-save-row">
        <label>
          Scenario name
          <input
            maxLength={80}
            value={scenarioName}
            onChange={(event) => onScenarioNameChange(event.target.value)}
          />
        </label>
        <button
          className="tertiary-button compact-action"
          disabled={scenarioLoading || selectedSymbols.length < 2}
          onClick={onSaveScenario}
          title="Save current portfolio research settings"
          type="button"
        >
          <Save size={15} />
          {scenarioLoading ? 'Saving...' : 'Save'}
        </button>
      </div>
      {scenarioMessage ? <p className="success-message">{scenarioMessage}</p> : null}
      {scenarioError ? <p className="error-message">{scenarioError}</p> : null}
      <div className="portfolio-watchlist">
        <div className="portfolio-scan-title">
          <strong>Scheduled scans</strong>
          <button
            className="tertiary-button compact-action"
            disabled={watchlistLoading}
            onClick={onRunDueWatchlist}
            title="Run due scheduled portfolio scans now"
            type="button"
          >
            <RefreshCcw size={15} />
            {watchlistLoading ? 'Checking...' : 'Run due'}
          </button>
        </div>
        <div className="portfolio-watch-action">
          <label>
            Interval min
            <input
              min="1"
              max="1440"
              type="number"
              value={watchIntervalMinutes}
              onChange={(event) => onWatchIntervalChange(Number(event.target.value))}
            />
          </label>
          <button
            className="tertiary-button compact-action"
            disabled={!selectedScenario || watchlistLoading}
            onClick={() => selectedScenario ? onAddWatchlist(selectedScenario.id) : undefined}
            title="Schedule selected saved scenario for recurring scans"
            type="button"
          >
            <Activity size={15} />
            Watch
          </button>
        </div>
        <div className="portfolio-alert-grid">
          <label>
            Max DD %
            <input
              min="0"
              max="100"
              type="number"
              value={alertThresholds.max_drawdown_pct ?? 0}
              onChange={(event) =>
                onAlertThresholdChange('max_drawdown_pct', Number(event.target.value))
              }
            />
          </label>
          <label>
            Min return %
            <input
              type="number"
              value={alertThresholds.min_total_return_pct ?? 0}
              onChange={(event) =>
                onAlertThresholdChange('min_total_return_pct', Number(event.target.value))
              }
            />
          </label>
          <label>
            Min edge %
            <input
              type="number"
              value={alertThresholds.min_average_edge_pct ?? 0}
              onChange={(event) =>
                onAlertThresholdChange('min_average_edge_pct', Number(event.target.value))
              }
            />
          </label>
          <label>
            Drift %
            <input
              min="0"
              type="number"
              value={alertThresholds.max_return_drift_pct ?? 0}
              onChange={(event) =>
                onAlertThresholdChange('max_return_drift_pct', Number(event.target.value))
              }
            />
          </label>
        </div>
        {watchlist.length > 0 ? (
          watchlist.slice(0, 4).map((item) => (
            <div className="portfolio-watch-row" key={item.id}>
              <div>
                <strong>{item.scenario_name}</strong>
                <span>{item.active ? `every ${item.interval_minutes} min` : 'paused'}</span>
              </div>
              <div>
                <span>next {shortDateTime(item.next_run_at)}</span>
                <span>last {shortDateTime(item.last_run_at)}</span>
                <span>{item.last_alerts.length ? `${item.last_alerts.length} alerts` : item.last_scan_id ? 'ok' : 'waiting'}</span>
              </div>
              <button
                className="icon-button"
                disabled={watchlistLoading}
                onClick={() => onDeleteWatchlist(item.id)}
                title="Remove scheduled scan"
                type="button"
              >
                <Trash2 size={15} />
              </button>
              {item.last_alerts.length > 0 ? (
                <p className="warning-message">
                  {item.last_alerts.map((alert) => alert.message).join(' ')}
                </p>
              ) : null}
              {item.last_error ? <p className="warning-message">{item.last_error}</p> : null}
            </div>
          ))
        ) : (
          <div className="portfolio-scan-empty">No scheduled scans yet</div>
        )}
      </div>
      <div className="portfolio-watchlist portfolio-paper-watchlist">
        <div className="portfolio-scan-title">
          <strong>Paper watchlist</strong>
          <button
            className="tertiary-button compact-action"
            disabled={paperWatchlistLoading}
            onClick={onRunDuePaperWatchlist}
            title="Run due portfolio paper sessions now"
            type="button"
          >
            <Play size={15} />
            {paperWatchlistLoading ? 'Running...' : 'Run due'}
          </button>
        </div>
        <div className="portfolio-watch-action">
          <label>
            Interval min
            <input
              min="1"
              max="1440"
              type="number"
              value={watchIntervalMinutes}
              onChange={(event) => onWatchIntervalChange(Number(event.target.value))}
            />
          </label>
          <button
            className="tertiary-button compact-action"
            disabled={!selectedScenario || paperWatchlistLoading}
            onClick={() => selectedScenario ? onAddPaperWatchlist(selectedScenario.id) : undefined}
            title="Promote selected saved scenario into recurring paper sessions"
            type="button"
          >
            <Activity size={15} />
            Paper watch
          </button>
        </div>
        {paperWatchlist.length > 0 ? (
          paperWatchlist.slice(0, 4).map((item) => (
            <div className="portfolio-watch-row" key={item.id}>
              <div>
                <strong>{item.scenario_name}</strong>
                <span>{item.active ? `every ${item.interval_minutes} min` : 'paused'}</span>
              </div>
              <div>
                <span>next {shortDateTime(item.next_run_at)}</span>
                <span>last {shortDateTime(item.last_run_at)}</span>
                <span>{item.last_session_ids.length} sessions</span>
              </div>
              <div className="portfolio-watch-buttons">
                <button
                  className="icon-button"
                  disabled={paperWatchlistLoading}
                  onClick={() => onRunPaperWatchlist(item.id)}
                  title="Run paper sessions for this scenario now"
                  type="button"
                >
                  <Play size={15} />
                </button>
                <button
                  className="icon-button"
                  disabled={paperWatchlistLoading || item.last_session_ids.length === 0}
                  onClick={() => onPromotePaperWatchlist(item.id)}
                  title="Promote eligible sessions to crypto dry-run review or stock/ETF paper-only handoff"
                  type="button"
                >
                  <ShieldCheck size={15} />
                </button>
                <button
                  className="icon-button"
                  disabled={paperWatchlistLoading}
                  onClick={() => onLogPaperWatchlistDecision(item)}
                  title="Log paper promotion review decision"
                  type="button"
                >
                  <Save size={15} />
                </button>
                <button
                  className="icon-button"
                  disabled={paperWatchlistLoading}
                  onClick={() => onDeletePaperWatchlist(item.id)}
                  title="Remove paper watchlist item"
                  type="button"
                >
                  <Trash2 size={15} />
                </button>
              </div>
              {item.last_error ? <p className="warning-message">{item.last_error}</p> : null}
            </div>
          ))
        ) : (
          <div className="portfolio-scan-empty">No paper watch items yet</div>
        )}
      </div>
      <div className="portfolio-scan-list">
        <div className="portfolio-scan-title">
          <strong>Recent scans</strong>
          <span>{scans.length} saved</span>
        </div>
        {scans.length > 0 ? (
          scans.slice(0, 4).map((scan) => (
            <div className="portfolio-scan-row" key={scan.id}>
              <div>
                <strong>{scan.scenario_name}</strong>
                <span>{shortDateTime(scan.created_at)}</span>
              </div>
              <div>
                <span>{money(scan.result.metrics.final_equity, currencyForSource(scan.result.request.source))}</span>
                <span>{percent(scan.result.metrics.total_return_pct)}</span>
                <span>{percent(scan.result.metrics.max_drawdown_pct)} DD</span>
              </div>
              <button
                className="compare-toggle"
                onClick={() => onOpenScan(scan)}
                type="button"
              >
                View
              </button>
            </div>
          ))
        ) : (
          <div className="portfolio-scan-empty">No scenario scans yet</div>
        )}
      </div>
      <div className="portfolio-controls">
        <div className="symbol-chip-grid">
          {symbols.map((symbol) => {
            const selected = selectedSymbols.includes(symbol);
            return (
              <button
                className={`symbol-chip${selected ? ' symbol-chip-active' : ''}`}
                key={symbol}
                onClick={() => onToggleSymbol(symbol)}
                type="button"
              >
                {symbol}
              </button>
            );
          })}
        </div>
        <button
          className="tertiary-button compact-action"
          disabled={!canRun}
          onClick={onRun}
          title="Run portfolio research across selected symbols"
          type="button"
        >
          <TrendingUp size={15} />
          {loading ? 'Researching...' : 'Run portfolio'}
        </button>
      </div>
      <div className="portfolio-rule-row">
        <label>
          Rebalance
          <select
            value={rebalanceFrequency}
            onChange={(event) =>
              onRebalanceChange(event.target.value as PortfolioRebalanceFrequency)
            }
          >
            <option value="none">Let weights drift</option>
            <option value="monthly">Monthly rebalance</option>
          </select>
        </label>
        <span className="portfolio-weight-total">Total {number(weightTotal)}%</span>
      </div>
      {selectedSymbols.length > 0 ? (
        <div className="portfolio-weight-grid">
          {selectedSymbols.map((symbol) => (
            <label key={symbol}>
              {symbol} weight %
              <input
                type="number"
                min="1"
                max="100"
                value={weights[symbol] ?? 0}
                onChange={(event) => onWeightChange(symbol, Number(event.target.value))}
              />
            </label>
          ))}
        </div>
      ) : null}
      {result ? (
        <>
          <div className="portfolio-metrics">
            <div>
              <span>Final equity</span>
              <strong>{money(metrics?.final_equity, currency)}</strong>
            </div>
            <div>
              <span>Return</span>
              <strong>{percent(metrics?.total_return_pct)}</strong>
            </div>
            <div>
              <span>Max DD</span>
              <strong>{percent(metrics?.max_drawdown_pct)}</strong>
            </div>
            <div>
              <span>Best</span>
              <strong>{metrics ? `${metrics.best_symbol} ${percent(metrics.best_return_pct)}` : '-'}</strong>
            </div>
            <div>
              <span>Worst</span>
              <strong>{metrics ? `${metrics.worst_symbol} ${percent(metrics.worst_return_pct)}` : '-'}</strong>
            </div>
            <div>
              <span>Rebalances</span>
              <strong>{metrics?.rebalances.toString() ?? '-'}</strong>
            </div>
            <div>
              <span>Trades</span>
              <strong>{metrics?.trades.toString() ?? '-'}</strong>
            </div>
          </div>
          <PortfolioCurveChart points={result.equity_curve} currency={currency} />
          <div className="portfolio-allocation-list">
            {result.allocations.map((allocation) => (
              <div className="portfolio-allocation-row" key={allocation.symbol}>
                <strong>{allocation.symbol}</strong>
                <span>{percent(allocation.target_weight_pct)} target</span>
                <span>{percent(allocation.final_weight_pct)} final</span>
                <span>{money(allocation.final_equity, currency)}</span>
                <span>{percent(allocation.total_return_pct)}</span>
                <span>{percent(allocation.strategy_edge_pct)} edge</span>
                <span>{allocation.trades} trades</span>
              </div>
            ))}
          </div>
          {result.warnings.map((warning, index) => (
            <p className="warning-message" key={`${warning}-${index}`}>
              {warning}
            </p>
          ))}
        </>
      ) : (
        <div className="portfolio-empty">
          Select two or more symbols, set weights, and run a portfolio comparison.
        </div>
      )}
    </section>
  );
}

function BacktestHistoryPanel({
  runs,
  activeRunId,
  selectedCompareIds,
  loadingRunId,
  onLoad,
  onToggleCompare,
}: {
  runs: BacktestRunSummary[];
  activeRunId: string | null;
  selectedCompareIds: string[];
  loadingRunId: string | null;
  onLoad: (runId: string) => void;
  onToggleCompare: (runId: string) => void;
}) {
  const [sortKey, setSortKey] = React.useState<HistorySortKey>('recent');
  const [sourceFilter, setSourceFilter] = React.useState<HistorySourceFilter>('all');
  const [strategyFilter, setStrategyFilter] = React.useState<HistoryStrategyFilter>('all');
  const [symbolFilter, setSymbolFilter] = React.useState('all');
  const sourceFilteredRuns = runs.filter((run) =>
    sourceFilter === 'all' ? true : run.request.source === sourceFilter,
  );
  const availableSymbols = [...new Set(sourceFilteredRuns.map((run) => run.request.symbol))].sort();
  const availableSymbolKey = availableSymbols.join('|');
  React.useEffect(() => {
    if (symbolFilter !== 'all' && !availableSymbols.includes(symbolFilter)) {
      setSymbolFilter('all');
    }
  }, [availableSymbolKey, symbolFilter]);
  const filteredRuns = sourceFilteredRuns
    .filter((run) =>
      strategyFilter === 'all' ? true : run.request.strategy === strategyFilter,
    )
    .filter((run) => (symbolFilter === 'all' ? true : run.request.symbol === symbolFilter));
  const visibleRuns = [...filteredRuns]
    .sort((a, b) => compareHistoryRuns(a, b, sortKey))
    .slice(0, 8);

  return (
    <section className="panel history-panel">
      <div className="panel-title">
        <History size={18} />
        <h2>Backtest history</h2>
      </div>
      <div className="history-tools">
        <label>
          Sort
          <select
            value={sortKey}
            onChange={(event) => setSortKey(event.target.value as HistorySortKey)}
          >
            <option value="recent">Newest</option>
            <option value="edge">Best edge</option>
            <option value="return">Best return</option>
            <option value="sharpe">Best Sharpe</option>
            <option value="drawdown">Lowest drawdown</option>
          </select>
        </label>
        <label>
          Source
          <select
            value={sourceFilter}
            onChange={(event) => setSourceFilter(event.target.value as HistorySourceFilter)}
          >
            <option value="all">All sources</option>
            {sourceOptions.map((option) => (
              <option value={option.value} key={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Strategy
          <select
            value={strategyFilter}
            onChange={(event) => setStrategyFilter(event.target.value as HistoryStrategyFilter)}
          >
            <option value="all">All strategies</option>
            <option value="sma_crossover">SMA crossover</option>
            <option value="donchian_breakout">Donchian breakout</option>
            <option value="rsi_mean_reversion">RSI mean reversion</option>
          </select>
        </label>
        <label>
          Symbol
          <select
            value={symbolFilter}
            onChange={(event) => setSymbolFilter(event.target.value)}
          >
            <option value="all">All symbols</option>
            {availableSymbols.map((symbol) => (
              <option value={symbol} key={symbol}>
                {symbol}
              </option>
            ))}
          </select>
        </label>
        <span className="history-result-count">
          {visibleRuns.length} / {filteredRuns.length}
        </span>
      </div>
      {visibleRuns.length > 0 ? (
        <div className="history-list">
          {visibleRuns.map((run) => {
            const isActive = run.id === activeRunId;
            const isLoading = run.id === loadingRunId;
            const isSelected = selectedCompareIds.includes(run.id);

            return (
              <div
                className={`history-row${isActive ? ' history-row-active' : ''}`}
                key={run.id}
              >
                <button
                  className="history-open"
                  onClick={() => onLoad(run.id)}
                  disabled={Boolean(loadingRunId)}
                >
                  <div>
                    <strong>{run.request.symbol}</strong>
                    <span>{strategyLabel(run.request.strategy)}</span>
                    <span>{run.request.source}</span>
                    <span>{shortDateTime(run.created_at)}</span>
                  </div>
                  <div>
                    <strong>{historyPrimaryMetric(run, sortKey)}</strong>
                    <span>{percent(run.metrics.strategy_edge_pct)} Edge</span>
                    <span>{number(run.metrics.sharpe)} Sharpe</span>
                    <span>{isLoading ? 'Loading' : isActive ? 'Loaded' : 'Open'}</span>
                  </div>
                </button>
                <button
                  className={`compare-toggle${isSelected ? ' compare-toggle-active' : ''}`}
                  onClick={() => onToggleCompare(run.id)}
                  title={isSelected ? 'Remove from comparison' : 'Add to comparison'}
                >
                  {isSelected ? 'Selected' : 'Compare'}
                </button>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="history-empty">
          {runs.length === 0
            ? 'Run a backtest to start building comparison history.'
            : 'No backtests match the selected filters.'}
        </div>
      )}
    </section>
  );
}

function compareHistoryRuns(
  a: BacktestRunSummary,
  b: BacktestRunSummary,
  sortKey: HistorySortKey,
) {
  if (sortKey === 'recent') {
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  }

  return historySortValue(b, sortKey) - historySortValue(a, sortKey);
}

function historySortValue(run: BacktestRunSummary, sortKey: HistorySortKey) {
  switch (sortKey) {
    case 'edge':
      return run.metrics.strategy_edge_pct ?? Number.NEGATIVE_INFINITY;
    case 'return':
      return run.metrics.total_return_pct;
    case 'sharpe':
      return run.metrics.sharpe;
    case 'drawdown':
      return run.metrics.max_drawdown_pct;
    case 'recent':
    default:
      return new Date(run.created_at).getTime();
  }
}

function historyPrimaryMetric(run: BacktestRunSummary, sortKey: HistorySortKey) {
  switch (sortKey) {
    case 'edge':
      return percent(run.metrics.strategy_edge_pct);
    case 'sharpe':
      return `${number(run.metrics.sharpe)} Sharpe`;
    case 'drawdown':
      return percent(run.metrics.max_drawdown_pct);
    case 'return':
    case 'recent':
    default:
      return percent(run.metrics.total_return_pct);
  }
}

function BacktestComparisonPanel({
  runs,
  detailsById,
  loadingIds,
  error,
}: {
  runs: BacktestRunSummary[];
  detailsById: Record<string, BacktestResponse>;
  loadingIds: string[];
  error: string | null;
}) {
  const leader = [...runs].sort(
    (a, b) => b.metrics.total_return_pct - a.metrics.total_return_pct,
  )[0];
  const overlayRuns = runs
    .map((run) => ({ summary: run, detail: detailsById[run.id] }))
    .filter((run): run is { summary: BacktestRunSummary; detail: BacktestResponse } =>
      Boolean(run.detail),
    );

  return (
    <section className="panel comparison-panel">
      <div className="panel-title">
        <TrendingUp size={18} />
        <h2>Run comparison</h2>
        <span className="comparison-count">{runs.length} / 3</span>
      </div>
      {runs.length > 0 ? (
        <div className="comparison-grid">
          {runs.map((run) => (
            <div
              className={`comparison-card${run.id === leader?.id ? ' comparison-card-leader' : ''}`}
              key={run.id}
            >
              <div className="comparison-card-header">
                <strong>{run.request.symbol}</strong>
                <span>{strategyLabel(run.request.strategy)}</span>
                <span>{shortDateTime(run.created_at)}</span>
              </div>
              <div className="comparison-metrics">
                <div>
                  <span>Return</span>
                  <strong>{percent(run.metrics.total_return_pct)}</strong>
                </div>
                <div>
                  <span>Edge</span>
                  <strong>{percent(run.metrics.strategy_edge_pct)}</strong>
                </div>
                <div>
                  <span>Buy/hold</span>
                  <strong>{percent(run.metrics.buy_and_hold_return_pct)}</strong>
                </div>
                <div>
                  <span>Max DD</span>
                  <strong>{percent(run.metrics.max_drawdown_pct)}</strong>
                </div>
                <div>
                  <span>Sharpe</span>
                  <strong>{number(run.metrics.sharpe)}</strong>
                </div>
                <div>
                  <span>Trades</span>
                  <strong>{run.metrics.trades}</strong>
                </div>
              </div>
              <div className="comparison-footer">
                <span>{run.request.source}</span>
                <strong>{money(run.metrics.final_equity, currencyForSource(run.request.source))}</strong>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="history-empty">Select recent runs to compare strategy outcomes.</div>
      )}
      {runs.length > 0 ? (
        <EquityOverlayChart
          runs={overlayRuns}
          pendingCount={loadingIds.filter((id) => runs.some((run) => run.id === id)).length}
        />
      ) : null}
      {error ? <p className="error-message">{error}</p> : null}
    </section>
  );
}

function EquityOverlayChart({
  runs,
  pendingCount,
}: {
  runs: { summary: BacktestRunSummary; detail: BacktestResponse }[];
  pendingCount: number;
}) {
  const colors = ['#1f7a68', '#5d84be', '#d14d35'];
  const width = 920;
  const height = 260;
  const padding = 30;

  const series = runs
    .map(({ summary, detail }, seriesIndex) => {
      const curve = detail.equity_curve;
      if (curve.length < 2) return null;
      const initial = curve[0].equity || detail.metrics.initial_equity || summary.metrics.initial_equity;
      if (!initial) return null;
      const points = curve.map((point, index) => ({
        x: padding + (index / (curve.length - 1)) * (width - padding * 2),
        yValue: ((point.equity / initial) - 1) * 100,
      }));
      return {
        id: summary.id,
        color: colors[seriesIndex % colors.length],
        label: `${summary.request.symbol} · ${strategyLabel(summary.request.strategy)}`,
        source: summary.request.source,
        finalReturn: summary.metrics.total_return_pct,
        points,
      };
    })
    .filter((item): item is NonNullable<typeof item> => Boolean(item));

  if (series.length === 0) {
    return (
      <div className="comparison-overlay-empty">
        {pendingCount > 0 ? 'Loading selected equity curves...' : 'Equity curves appear after selected runs load.'}
      </div>
    );
  }

  const allValues = series.flatMap((item) => item.points.map((point) => point.yValue));
  const min = Math.min(0, ...allValues);
  const max = Math.max(0, ...allValues);
  const span = Math.max(max - min, 1);
  const yForValue = (value: number) =>
    height - padding - ((value - min) / span) * (height - padding * 2);
  const zeroY = yForValue(0);

  return (
    <div className="comparison-overlay">
      <div className="overlay-chart-wrap">
        <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Selected run equity overlay">
          <line x1={padding} y1={zeroY} x2={width - padding} y2={zeroY} />
          <line x1={padding} y1={padding} x2={padding} y2={height - padding} />
          {series.map((item) => {
            const path = item.points
              .map((point, index) => {
                const y = yForValue(point.yValue);
                return `${index === 0 ? 'M' : 'L'} ${point.x.toFixed(2)} ${y.toFixed(2)}`;
              })
              .join(' ');
            const last = item.points[item.points.length - 1];
            return (
              <g key={item.id}>
                <path d={path} stroke={item.color} />
                <circle cx={last.x} cy={yForValue(last.yValue)} r="4.5" fill={item.color} />
              </g>
            );
          })}
        </svg>
        <div className="chart-scale">
          <span>{percent(max)}</span>
          <span>{percent(min)}</span>
        </div>
      </div>
      <div className="overlay-legend">
        {series.map((item) => (
          <div className="overlay-legend-row" key={item.id}>
            <span className="overlay-swatch" style={{ background: item.color }} />
            <strong>{item.label}</strong>
            <span>{item.source}</span>
            <span>{percent(item.finalReturn)}</span>
          </div>
        ))}
      </div>
      {pendingCount > 0 ? (
        <p className="comparison-loading">Loading {pendingCount} more selected curve{pendingCount > 1 ? 's' : ''}.</p>
      ) : null}
    </div>
  );
}

function PortfolioCurveChart({
  points,
  currency,
}: {
  points: PortfolioEquityPoint[];
  currency: DisplayCurrency;
}) {
  if (points.length < 2) {
    return <div className="portfolio-empty">Portfolio equity curve needs at least two points.</div>;
  }

  const width = 920;
  const height = 220;
  const padding = 26;
  const values = points.map((point) => point.equity);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(max - min, 1);
  const yForEquity = (equity: number) =>
    height - padding - ((equity - min) / span) * (height - padding * 2);
  const path = points
    .map((point, index) => {
      const x = padding + (index / (points.length - 1)) * (width - padding * 2);
      const y = yForEquity(point.equity);
      return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(' ');
  const last = points[points.length - 1];

  return (
    <div className="portfolio-chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Portfolio equity curve">
        <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} />
        <line x1={padding} y1={padding} x2={padding} y2={height - padding} />
        <path className="strategy-path" d={path} />
        <circle
          className="strategy-dot"
          cx={width - padding}
          cy={yForEquity(last.equity)}
          r="4.5"
        />
      </svg>
      <div className="chart-scale">
        <span>{money(max, currency)}</span>
        <span>{money(min, currency)}</span>
      </div>
    </div>
  );
}

function EquityChart({
  points,
  currency,
  request,
  metrics,
}: {
  points: EquityPoint[];
  currency: DisplayCurrency;
  request?: BacktestRequest;
  metrics?: BacktestMetrics;
}) {
  if (points.length < 2) {
    return (
      <div className="chart-empty">
        <Database size={22} />
        Waiting for backtest data
      </div>
    );
  }

  const width = 920;
  const height = 320;
  const padding = 28;
  const benchmark = buildBuyAndHoldBenchmark(points, request);
  const values = [
    ...points.map((point) => point.equity),
    ...benchmark.map((point) => point.equity),
  ];
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(max - min, 1);
  const yForEquity = (equity: number) =>
    height - padding - ((equity - min) / span) * (height - padding * 2);
  const pathFor = (items: { equity: number }[]) =>
    items
      .map((point, index) => {
        const x = padding + (index / (items.length - 1)) * (width - padding * 2);
        const y = yForEquity(point.equity);
        return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`;
      })
      .join(' ');
  const strategyPath = pathFor(points);
  const benchmarkPath = benchmark.length > 1 ? pathFor(benchmark) : null;
  const benchmarkLast = benchmark[benchmark.length - 1];
  const calculatedBenchmarkReturn = benchmarkLast
    ? ((benchmarkLast.equity / (request?.initial_cash ?? points[0].equity)) - 1) * 100
    : undefined;
  const calculatedStrategyReturn = request
    ? ((points[points.length - 1].equity / request.initial_cash) - 1) * 100
    : undefined;
  const strategyReturn = metrics?.total_return_pct ?? calculatedStrategyReturn;
  const benchmarkReturn = metrics?.buy_and_hold_return_pct ?? calculatedBenchmarkReturn;
  const edge = metrics?.strategy_edge_pct ?? (
    benchmarkReturn !== undefined && strategyReturn !== undefined
      ? strategyReturn - benchmarkReturn
      : undefined
  );
  const last = points[points.length - 1];

  return (
    <div className="chart-wrap">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Equity curve">
        <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} />
        <line x1={padding} y1={padding} x2={padding} y2={height - padding} />
        {benchmarkPath ? <path className="benchmark-path" d={benchmarkPath} /> : null}
        <path className="strategy-path" d={strategyPath} />
        {benchmarkLast ? (
          <circle
            className="benchmark-dot"
            cx={width - padding}
            cy={yForEquity(benchmarkLast.equity)}
            r="4"
          />
        ) : null}
        <circle
          className="strategy-dot"
          cx={width - padding}
          cy={yForEquity(last.equity)}
          r="5"
        />
      </svg>
      <div className="chart-scale">
        <span>{money(max, currency)}</span>
        <span>{money(min, currency)}</span>
      </div>
      <div className="chart-legend">
        <span><i className="legend-line strategy-line" /> Strategy {percent(strategyReturn)}</span>
        <span><i className="legend-line benchmark-line" /> Buy and hold {percent(benchmarkReturn)}</span>
        <strong>Edge {percent(edge)}</strong>
      </div>
    </div>
  );
}

function buildBuyAndHoldBenchmark(
  points: EquityPoint[],
  request?: BacktestRequest,
): { equity: number }[] {
  if (!request || points.length < 2) return [];
  const entryClose = points[0].close;
  if (!Number.isFinite(entryClose) || entryClose <= 0) return [];
  const feeRate = request.fee_bps / 10_000;
  const slippageRate = request.slippage_bps / 10_000;
  const entryPrice = entryClose * (1 + slippageRate);
  const quantity = (request.initial_cash / (1 + feeRate)) / entryPrice;
  if (!Number.isFinite(quantity) || quantity <= 0) return [];
  return points.map((point) => ({
    equity: quantity * point.close,
  }));
}

function TradesTable({
  trades,
  currency,
}: {
  trades: Trade[];
  currency: DisplayCurrency;
}) {
  return (
    <section className="panel trades-panel">
      <div className="panel-title">
        <Database size={18} />
        <h2>Orders</h2>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Time</th>
              <th>Side</th>
              <th>Price</th>
              <th>Qty</th>
              <th>Notional</th>
              <th>Fee</th>
            </tr>
          </thead>
          <tbody>
            {trades.slice(-12).map((trade, index) => (
              <tr key={`${trade.timestamp}-${trade.side}-${index}`}>
                <td>{new Date(trade.timestamp).toISOString().slice(0, 10)}</td>
                <td>
                  <span className={`side side-${trade.side}`}>{trade.side}</span>
                </td>
                <td>{money(trade.price, currency)}</td>
                <td>{trade.quantity.toFixed(6)}</td>
                <td>{money(trade.notional, currency)}</td>
                <td>{money(trade.fee, currency)}</td>
              </tr>
            ))}
            {trades.length === 0 ? (
              <tr>
                <td colSpan={6} className="empty-cell">
                  No simulated orders yet
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function defaultSymbolForSource(source: Source) {
  return symbolsBySource[source][0];
}

function equalWeights(symbols: string[]) {
  if (symbols.length === 0) return {};
  const weight = Number((100 / symbols.length).toFixed(2));
  return Object.fromEntries(symbols.map((symbol) => [symbol, weight]));
}

function initialThemeMode(): ThemeMode {
  const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
  if (stored === 'light' || stored === 'dark') return stored;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function isUsdSource(source: Source) {
  return source === 'sample_us' || source === 'alpha_vantage';
}

function currencyForSource(source: Source): DisplayCurrency {
  return isUsdSource(source) ? 'USD' : 'KRW';
}

function money(value?: number, currency: DisplayCurrency = 'KRW') {
  if (value === undefined || Number.isNaN(value)) return '-';
  return new Intl.NumberFormat(currency === 'USD' ? 'en-US' : 'ko-KR', {
    style: 'currency',
    currency,
    maximumFractionDigits: currency === 'USD' ? 2 : 0,
  }).format(value);
}

function compactMoney(value?: number | null, currency: DisplayCurrency = 'KRW') {
  if (value === undefined || value === null || Number.isNaN(value)) return '-';
  return new Intl.NumberFormat(currency === 'USD' ? 'en-US' : 'ko-KR', {
    style: 'currency',
    currency,
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(value);
}

function compactNumber(value?: number | null) {
  if (value === undefined || value === null || Number.isNaN(value)) return '-';
  return new Intl.NumberFormat('ko-KR', {
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(value);
}

function tickerVolumeDisplay(ticker: MarketTicker | null) {
  if (!ticker) return '-';
  if (ticker.quote_volume_24h !== undefined && ticker.quote_volume_24h !== null) {
    return compactMoney(ticker.quote_volume_24h, currencyForSource(ticker.source));
  }
  return compactNumber(ticker.volume_24h);
}

function percent(value?: number) {
  if (value === undefined || Number.isNaN(value)) return '-';
  return `${value.toFixed(2)}%`;
}

function number(value?: number) {
  if (value === undefined || Number.isNaN(value)) return '-';
  return value.toFixed(2);
}

function quantity(value?: number) {
  if (value === undefined || Number.isNaN(value)) return '-';
  return new Intl.NumberFormat('en-US', {
    maximumFractionDigits: 8,
  }).format(value);
}

function feeRate(value?: number) {
  if (value === undefined || Number.isNaN(value)) return '-';
  return `${(value * 100).toFixed(3)}%`;
}

function estimateNotional(price?: number, volume?: number) {
  if (price === undefined || volume === undefined) return undefined;
  return price * volume;
}

function payloadNumber(value: unknown) {
  if (typeof value === 'number') return value;
  if (typeof value === 'string') {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
}

function decisionContextText(decision: OperatorDecisionRecord, key: string) {
  const value = decision.context[key];
  return typeof value === 'string' && value.length > 0 ? value : undefined;
}

function decisionContextNumber(decision: OperatorDecisionRecord, key: string) {
  return payloadNumber(decision.context[key]);
}

function decisionContextObject(decision: OperatorDecisionRecord, key: string) {
  const value = decision.context[key];
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function handoffDecisionKey(decision: OperatorDecisionRecord) {
  return decisionContextText(decision, 'handoff_id') ?? decision.target_id ?? decision.id;
}

function latestDecisionPerHandoff(decisions: OperatorDecisionRecord[]) {
  const seen = new Set<string>();
  const latest: OperatorDecisionRecord[] = [];
  for (const decision of decisions) {
    const key = handoffDecisionKey(decision);
    if (seen.has(key)) continue;
    seen.add(key);
    latest.push(decision);
  }
  return latest;
}

function promotionContext(payload?: Record<string, unknown> | null): PromotionContext | null {
  const context = payload?.context;
  if (!context || typeof context !== 'object') return null;
  const source = (context as PromotionContext).source;
  return source === 'portfolio_paper_watchlist_promotion'
    ? (context as PromotionContext)
    : null;
}

function shortTime(value?: string | null) {
  const parsed = parsedDate(value);
  if (!parsed) return '-';
  return new Intl.DateTimeFormat('ko-KR', {
    hour: '2-digit',
    minute: '2-digit',
  }).format(parsed);
}

function shortDateTime(value?: string | null) {
  const parsed = parsedDate(value);
  if (!parsed) return '-';
  return new Intl.DateTimeFormat('ko-KR', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(parsed);
}

function compactPath(value?: string | null) {
  if (!value) return '-';
  const segments = value.split('/').filter(Boolean);
  if (segments.length <= 2) return value;
  return `.../${segments.slice(-2).join('/')}`;
}

function parsedDate(value?: string | null) {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function strategyLabel(strategy: Strategy) {
  if (strategy === 'sma_crossover') {
    return 'SMA crossover';
  }
  if (strategy === 'donchian_breakout') {
    return 'Donchian breakout';
  }
  return 'RSI mean reversion';
}

function clamp(value: number, min: number, max: number) {
  if (Number.isNaN(value)) return min;
  return Math.min(Math.max(value, min), max);
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
