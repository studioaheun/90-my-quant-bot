import base64
import hashlib
import hmac
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple

from .brokers import (
    ALPACA_US_EQUITY_PAPER_PREVIEW_CONTRACT,
    ALPACA_US_EQUITY_PAPER_CONTRACT,
    ALPACA_PAPER_TRADING_ACK_VALUE,
    BrokerOrderIntent,
    UPBIT_CRYPTO_SPOT_BROKER_CONTRACT,
    US_EQUITY_PAPER_BROKER_CONTRACT,
    alpaca_us_equity_paper_broker,
    stock_paper_broker_for_adapter,
)
from .models import (
    BrokerPaperFillEstimate,
    BrokerOrderIntentEvaluation,
    BrokerOrderIntentRequest,
    BrokerOrderReconciliation,
    BrokerReadinessCheck,
    BrokerReadinessItem,
    BrokerReadinessResponse,
    ExecutionSettings,
    ExecutionStatus,
    OrderAuditRecord,
    OrderApprovalRequest,
    OrderIntentRequest,
    OrderPrecheckItem,
    OrderPrecheckResult,
    PaperToLiveAdapterProfile,
    PaperToLiveRoute,
    PaperTradingSession,
    StrategyOrderQueueResponse,
    Trade,
    UpbitAccountBalance,
    UpbitOpenOrder,
    UpbitPrivateSnapshot,
)
from .storage import OrderAuditStore


LIVE_TRADING_ACK_VALUE = "REAL_ORDERS_OK"
DEFAULT_MIN_ORDER_NOTIONAL_KRW = 5_000.0
DEFAULT_APPROVAL_FEE_BPS = 5.0
DEFAULT_MAX_APPROVAL_EXPOSURE_PCT = 60.0


UPBIT_CRYPTO_SPOT_ADAPTER = PaperToLiveAdapterProfile(
    id="upbit_crypto_spot",
    label="Upbit crypto spot",
    broker="upbit",
    asset_class="crypto_spot",
    execution_mode="guarded_live",
    live_order_supported=True,
    dry_run_audit_supported=True,
    supported_sources=["sample", "upbit"],
    symbol_hint="KRW-*",
    broker_contract=UPBIT_CRYPTO_SPOT_BROKER_CONTRACT,
    reason="KRW crypto paper signals can become guarded Upbit dry-run audits before any live approval.",
)

US_EQUITY_PAPER_ADAPTER = PaperToLiveAdapterProfile(
    id="us_equity_paper",
    label="US stock/ETF paper handoff",
    broker="paper",
    asset_class="stock_etf",
    execution_mode="paper_only",
    live_order_supported=False,
    dry_run_audit_supported=False,
    supported_sources=["sample_us", "alpha_vantage"],
    symbol_hint="SPY, QQQ, AAPL, MSFT, NVDA, TSLA",
    broker_contract=US_EQUITY_PAPER_BROKER_CONTRACT,
    reason="US stock/ETF signals are paper-only and captured for operator review; no broker live-order adapter is enabled.",
)

ALPACA_US_EQUITY_PAPER_PREVIEW_ADAPTER = PaperToLiveAdapterProfile(
    id="alpaca_us_equity_paper_preview",
    label="Alpaca paper preview",
    broker="alpaca",
    asset_class="stock_etf",
    execution_mode="paper_only",
    live_order_supported=False,
    dry_run_audit_supported=False,
    supported_sources=["sample_us", "alpha_vantage"],
    symbol_hint="US equities/ETFs, e.g. SPY, QQQ, AAPL",
    broker_contract=ALPACA_US_EQUITY_PAPER_PREVIEW_CONTRACT,
    reason=(
        "Alpaca-style paper intents can be validated for shape, fill assumptions, "
        "and credential readiness without any external Alpaca submission."
    ),
)

ALPACA_US_EQUITY_PAPER_ADAPTER = PaperToLiveAdapterProfile(
    id="alpaca_us_equity_paper",
    label="Alpaca paper trading",
    broker="alpaca",
    asset_class="stock_etf",
    execution_mode="paper_only",
    live_order_supported=False,
    dry_run_audit_supported=False,
    supported_sources=["sample_us", "alpha_vantage"],
    symbol_hint="US equities/ETFs, e.g. SPY, QQQ, AAPL",
    broker_contract=ALPACA_US_EQUITY_PAPER_CONTRACT,
    reason=(
        "Credentialed Alpaca paper orders are available only after the paper flag, ACK, "
        "credentials, paper endpoint, and per-request paper submission confirmation are present."
    ),
)


def paper_to_live_adapter_profiles() -> List[PaperToLiveAdapterProfile]:
    return [
        UPBIT_CRYPTO_SPOT_ADAPTER,
        US_EQUITY_PAPER_ADAPTER,
        ALPACA_US_EQUITY_PAPER_PREVIEW_ADAPTER,
        ALPACA_US_EQUITY_PAPER_ADAPTER,
    ]


def get_broker_readiness() -> BrokerReadinessResponse:
    settings = get_execution_settings()
    upbit_checks = [
        BrokerReadinessCheck(
            id="contract",
            label="Broker contract",
            status="pass",
            message="Upbit private API contract is registered for guarded crypto spot routing.",
        ),
        BrokerReadinessCheck(
            id="live_flag",
            label="Live flag",
            status="pass" if settings.live_trading_enabled else "fail",
            message=(
                "QUANT_LAB_LIVE_TRADING_ENABLED is enabled."
                if settings.live_trading_enabled
                else "QUANT_LAB_LIVE_TRADING_ENABLED is disabled."
            ),
        ),
        BrokerReadinessCheck(
            id="live_ack",
            label="Live ACK",
            status="pass" if settings.live_ack_configured else "fail",
            message=(
                "Live ACK matches the required value."
                if settings.live_ack_configured
                else f"Set QUANT_LAB_LIVE_TRADING_ACK={settings.live_ack_required_value} before live submission."
            ),
        ),
        BrokerReadinessCheck(
            id="credentials",
            label="Credentials",
            status="pass" if settings.credential_configured else "fail",
            message=(
                "Upbit private credentials are configured."
                if settings.credential_configured
                else "UPBIT_ACCESS_KEY and UPBIT_SECRET_KEY are missing."
            ),
        ),
        BrokerReadinessCheck(
            id="per_order_confirmation",
            label="Per-order confirmation",
            status="pass",
            message="Each live approval still requires live_confirmation=true.",
        ),
    ]
    upbit_status = "ready" if settings.adapter_ready else "blocked"

    us_checks = [
        BrokerReadinessCheck(
            id="contract",
            label="Broker contract",
            status="pass",
            message="Mock US equities paper broker contract is registered.",
        ),
        BrokerReadinessCheck(
            id="credentials",
            label="Credentials",
            status="pass",
            message="No stock/ETF broker credentials are required in paper-record mode.",
        ),
        BrokerReadinessCheck(
            id="live_submission",
            label="Live submission",
            status="pass",
            message="Live-confirmed US stock/ETF submissions are blocked by contract.",
        ),
        BrokerReadinessCheck(
            id="external_endpoint",
            label="External endpoint",
            status="pass",
            message="No external brokerage endpoint is wired for stock/ETF routing.",
        ),
    ]
    alpaca_preview_credentials = [
        credential
        for credential in ALPACA_US_EQUITY_PAPER_PREVIEW_CONTRACT.required_credentials
        if os.environ.get(credential)
    ]
    alpaca_checks = [
        BrokerReadinessCheck(
            id="contract",
            label="Broker contract",
            status="pass",
            message="Alpaca-style paper preview contract is registered.",
        ),
        BrokerReadinessCheck(
            id="credentials",
            label="Credentials",
            status="pass" if len(alpaca_preview_credentials) == 3 else "warn",
            message=(
                "Alpaca paper credentials are present for a future external adapter."
                if len(alpaca_preview_credentials) == 3
                else "Alpaca paper credentials are optional here; this preview does not read or submit them."
            ),
        ),
        BrokerReadinessCheck(
            id="live_submission",
            label="Live submission",
            status="pass",
            message="Live-confirmed Alpaca preview submissions are blocked by contract.",
        ),
        BrokerReadinessCheck(
            id="external_endpoint",
            label="External endpoint",
            status="pass",
            message="No Alpaca paper endpoint is called by the preview adapter.",
        ),
    ]
    alpaca_paper_base_url = os.environ.get("ALPACA_PAPER_BASE_URL", "").strip()
    alpaca_paper_credentials_ready = (
        bool(os.environ.get("ALPACA_API_KEY_ID", "").strip())
        and bool(os.environ.get("ALPACA_API_SECRET_KEY", "").strip())
        and bool(alpaca_paper_base_url)
    )
    alpaca_paper_endpoint_ready = alpaca_paper_base_url.startswith(
        "https://paper-api.alpaca.markets"
    )
    alpaca_paper_flag_ready = os.environ.get("ALPACA_PAPER_TRADING_ENABLED", "").lower() == "true"
    alpaca_paper_ack_ready = os.environ.get("ALPACA_PAPER_TRADING_ACK") == ALPACA_PAPER_TRADING_ACK_VALUE
    alpaca_paper_ready = (
        alpaca_paper_credentials_ready
        and alpaca_paper_endpoint_ready
        and alpaca_paper_flag_ready
        and alpaca_paper_ack_ready
    )
    alpaca_paper_checks = [
        BrokerReadinessCheck(
            id="contract",
            label="Broker contract",
            status="pass",
            message="Credentialed Alpaca paper contract is registered for stock/ETF routing.",
        ),
        BrokerReadinessCheck(
            id="paper_flag",
            label="Paper flag",
            status="pass" if alpaca_paper_flag_ready else "fail",
            message=(
                "ALPACA_PAPER_TRADING_ENABLED is true."
                if alpaca_paper_flag_ready
                else "Set ALPACA_PAPER_TRADING_ENABLED=true before Alpaca paper submission."
            ),
        ),
        BrokerReadinessCheck(
            id="paper_ack",
            label="Paper ACK",
            status="pass" if alpaca_paper_ack_ready else "fail",
            message=(
                "Alpaca paper ACK matches the required value."
                if alpaca_paper_ack_ready
                else f"Set ALPACA_PAPER_TRADING_ACK={ALPACA_PAPER_TRADING_ACK_VALUE}."
            ),
        ),
        BrokerReadinessCheck(
            id="credentials",
            label="Credentials",
            status="pass" if alpaca_paper_credentials_ready else "fail",
            message=(
                "Alpaca paper key, secret, and base URL are configured."
                if alpaca_paper_credentials_ready
                else "ALPACA_API_KEY_ID, ALPACA_API_SECRET_KEY, and ALPACA_PAPER_BASE_URL are required."
            ),
        ),
        BrokerReadinessCheck(
            id="paper_endpoint",
            label="Paper endpoint",
            status="pass" if alpaca_paper_endpoint_ready else "fail",
            message=(
                "ALPACA_PAPER_BASE_URL points at Alpaca's paper API domain."
                if alpaca_paper_endpoint_ready
                else "ALPACA_PAPER_BASE_URL must start with https://paper-api.alpaca.markets."
            ),
        ),
        BrokerReadinessCheck(
            id="live_submission",
            label="Live submission",
            status="pass",
            message="This stock/ETF adapter never submits to Alpaca's live trading domain.",
        ),
        BrokerReadinessCheck(
            id="per_order_confirmation",
            label="Paper confirmation",
            status="pass",
            message="Each external paper request must include paper_submit_confirmation=true.",
        ),
    ]

    return BrokerReadinessResponse(
        checked_at=_utc_now_iso(),
        items=[
            BrokerReadinessItem(
                adapter_id=UPBIT_CRYPTO_SPOT_ADAPTER.id,
                label=UPBIT_CRYPTO_SPOT_ADAPTER.label,
                broker=UPBIT_CRYPTO_SPOT_ADAPTER.broker,
                asset_class=UPBIT_CRYPTO_SPOT_ADAPTER.asset_class,
                status=upbit_status,
                live_submission_state="guarded_live" if settings.adapter_ready else "blocked",
                broker_contract=UPBIT_CRYPTO_SPOT_ADAPTER.broker_contract,
                credential_boundary=", ".join(
                    UPBIT_CRYPTO_SPOT_ADAPTER.broker_contract.required_credentials
                ),
                checks=upbit_checks,
                message=settings.reason,
            ),
            BrokerReadinessItem(
                adapter_id=US_EQUITY_PAPER_ADAPTER.id,
                label=US_EQUITY_PAPER_ADAPTER.label,
                broker=US_EQUITY_PAPER_ADAPTER.broker,
                asset_class=US_EQUITY_PAPER_ADAPTER.asset_class,
                status="watch",
                live_submission_state="paper_record_only",
                broker_contract=US_EQUITY_PAPER_ADAPTER.broker_contract,
                credential_boundary="No credentials accepted; paper-record only.",
                checks=us_checks,
                message=US_EQUITY_PAPER_ADAPTER.reason,
            ),
            BrokerReadinessItem(
                adapter_id=ALPACA_US_EQUITY_PAPER_PREVIEW_ADAPTER.id,
                label=ALPACA_US_EQUITY_PAPER_PREVIEW_ADAPTER.label,
                broker=ALPACA_US_EQUITY_PAPER_PREVIEW_ADAPTER.broker,
                asset_class=ALPACA_US_EQUITY_PAPER_PREVIEW_ADAPTER.asset_class,
                status="watch",
                live_submission_state="paper_record_only",
                broker_contract=ALPACA_US_EQUITY_PAPER_PREVIEW_ADAPTER.broker_contract,
                credential_boundary=(
                    "Credentials may be configured for future Alpaca paper routing, "
                    "but this preview adapter never submits externally."
                ),
                checks=alpaca_checks,
                message=ALPACA_US_EQUITY_PAPER_PREVIEW_ADAPTER.reason,
            ),
            BrokerReadinessItem(
                adapter_id=ALPACA_US_EQUITY_PAPER_ADAPTER.id,
                label=ALPACA_US_EQUITY_PAPER_ADAPTER.label,
                broker=ALPACA_US_EQUITY_PAPER_ADAPTER.broker,
                asset_class=ALPACA_US_EQUITY_PAPER_ADAPTER.asset_class,
                status="ready" if alpaca_paper_ready else "blocked",
                live_submission_state="external_paper" if alpaca_paper_ready else "blocked",
                broker_contract=ALPACA_US_EQUITY_PAPER_ADAPTER.broker_contract,
                credential_boundary=(
                    "Requires Alpaca paper key/secret, paper base URL, paper flag, ACK, "
                    "and per-request paper confirmation."
                ),
                checks=alpaca_paper_checks,
                message=ALPACA_US_EQUITY_PAPER_ADAPTER.reason,
            ),
        ],
    )


def evaluate_broker_order_intent(
    request: BrokerOrderIntentRequest,
) -> BrokerOrderIntentEvaluation:
    broker = stock_paper_broker_for_adapter(request.adapter_id)
    intent = BrokerOrderIntent(
        symbol=request.symbol,
        side=request.side,
        quantity=request.quantity,
        order_type=request.order_type,
        limit_price=request.limit_price,
        time_in_force=request.time_in_force,
        client_order_id=request.client_order_id,
        live_confirmation=request.live_confirmation,
        paper_submit_confirmation=request.paper_submit_confirmation,
    )
    validation = broker.validate_order(intent)
    submission = broker.submit_order(intent)
    return BrokerOrderIntentEvaluation(
        id=str(uuid.uuid4()),
        checked_at=_utc_now_iso(),
        adapter_id=request.adapter_id,
        broker_contract=broker.contract,
        request=request,
        validation_status=validation.status,
        submission_status=submission.status,
        reason=submission.reason,
        normalized_symbol=submission.normalized_symbol or validation.normalized_symbol,
        estimated_notional=submission.estimated_notional
        if submission.estimated_notional is not None
        else validation.estimated_notional,
        broker_order_id=submission.broker_order_id,
        external_submission_attempted=submission.external_submission_attempted,
        live_submission_supported=broker.contract.live_order_supported,
        paper_fill_estimate=_estimate_paper_fill(request=request),
    )


def reconcile_broker_order_evaluation(
    evaluation: BrokerOrderIntentEvaluation,
) -> BrokerOrderReconciliation:
    if evaluation.adapter_id != "alpaca_us_equity_paper":
        return BrokerOrderReconciliation(
            id=str(uuid.uuid4()),
            checked_at=_utc_now_iso(),
            evaluation_id=evaluation.id,
            adapter_id=evaluation.adapter_id,
            local_submission_status=evaluation.submission_status,
            status="unsupported",
            reason="Broker reconciliation is currently supported only for credentialed Alpaca paper evaluations.",
            broker_order_id=evaluation.broker_order_id,
            client_order_id=evaluation.request.client_order_id,
            external_lookup_attempted=False,
        )

    broker = alpaca_us_equity_paper_broker()
    lookup = broker.fetch_order_status(
        broker_order_id=evaluation.broker_order_id,
        client_order_id=evaluation.request.client_order_id,
    )
    if lookup.status == "blocked":
        status = "blocked"
        reason = lookup.reason
    elif lookup.status == "not_found":
        status = "not_found"
        reason = lookup.reason
    elif lookup.status == "error":
        status = "error"
        reason = lookup.reason
    else:
        status, reason = _broker_reconciliation_verdict(evaluation=evaluation, lookup=lookup)

    return BrokerOrderReconciliation(
        id=str(uuid.uuid4()),
        checked_at=_utc_now_iso(),
        evaluation_id=evaluation.id,
        adapter_id=evaluation.adapter_id,
        local_submission_status=evaluation.submission_status,
        status=status,
        reason=reason,
        broker_order_id=lookup.broker_order_id or evaluation.broker_order_id,
        client_order_id=lookup.client_order_id or evaluation.request.client_order_id,
        broker_status=lookup.order_status,
        broker_symbol=lookup.symbol,
        broker_side=lookup.side,
        broker_quantity=lookup.quantity,
        broker_filled_quantity=lookup.filled_quantity,
        broker_avg_fill_price=lookup.average_fill_price,
        broker_filled_notional=lookup.filled_notional,
        broker_fee=lookup.broker_fee,
        broker_partial_fill=lookup.partial_fill,
        broker_fill_activity_count=lookup.fill_activity_count,
        broker_submitted_at=lookup.submitted_at,
        broker_filled_at=lookup.filled_at,
        broker_position_quantity=lookup.position_quantity,
        broker_position_market_value=lookup.position_market_value,
        broker_position_cost_basis=lookup.position_cost_basis,
        broker_position_unrealized_pl=lookup.position_unrealized_pl,
        broker_position_snapshot=lookup.position_snapshot or {},
        broker_account_cash=lookup.account_cash,
        broker_account_equity=lookup.account_equity,
        broker_account_buying_power=lookup.account_buying_power,
        broker_account_snapshot=lookup.account_snapshot or {},
        broker_fill_activities=lookup.fill_activities or [],
        external_lookup_attempted=lookup.external_lookup_attempted,
        broker_payload=lookup.raw_payload or {},
    )


def _broker_reconciliation_verdict(
    *,
    evaluation: BrokerOrderIntentEvaluation,
    lookup,
) -> tuple[Literal["matched", "mismatch"], str]:
    mismatch_reasons: list[str] = []
    expected_symbol = (evaluation.normalized_symbol or evaluation.request.symbol).upper()
    if lookup.symbol and lookup.symbol.upper() != expected_symbol:
        mismatch_reasons.append("broker symbol differs from local evaluation")
    if lookup.side and lookup.side != evaluation.request.side:
        mismatch_reasons.append("broker side differs from local evaluation")
    if lookup.quantity is not None and abs(lookup.quantity - evaluation.request.quantity) > 1e-9:
        mismatch_reasons.append("broker quantity differs from local evaluation")
    if lookup.order_status in {"canceled", "expired", "rejected", "stopped", "suspended"}:
        mismatch_reasons.append(f"broker status is {lookup.order_status}")
    if evaluation.submission_status != "paper_recorded":
        mismatch_reasons.append(f"local submission status is {evaluation.submission_status}")
    if (
        lookup.filled_quantity is not None
        and lookup.quantity is not None
        and lookup.filled_quantity - lookup.quantity > 1e-9
    ):
        mismatch_reasons.append("broker filled quantity exceeds order quantity")

    if mismatch_reasons:
        return "mismatch", "Alpaca paper reconciliation found drift: " + "; ".join(mismatch_reasons) + "."
    evidence_notes: list[str] = []
    if lookup.partial_fill:
        evidence_notes.append(
            f"partial fill captured ({lookup.filled_quantity:g}/{lookup.quantity:g})"
            if lookup.filled_quantity is not None and lookup.quantity is not None
            else "partial fill captured"
        )
    if lookup.average_fill_price is not None:
        evidence_notes.append(f"avg fill {lookup.average_fill_price:g}")
    if lookup.broker_fee is not None:
        evidence_notes.append(f"fee {lookup.broker_fee:g}")
    if lookup.position_quantity is not None:
        evidence_notes.append(f"position qty {lookup.position_quantity:g}")
    if lookup.account_cash is not None:
        evidence_notes.append(f"account cash {lookup.account_cash:g}")
    if evidence_notes:
        return (
            "matched",
            "Alpaca paper order matches the local evaluation with broker fill evidence: "
            + "; ".join(evidence_notes)
            + ".",
        )
    return "matched", "Alpaca paper order matches the local evaluation and has an active or completed paper status."


def _estimate_paper_fill(
    *,
    request: BrokerOrderIntentRequest,
) -> Optional[BrokerPaperFillEstimate]:
    if request.reference_price is None:
        return None

    slippage_multiplier = 1 + (request.paper_slippage_bps / 10_000)
    if request.side == "sell":
        slippage_multiplier = 1 - (request.paper_slippage_bps / 10_000)
    slipped_price = request.reference_price * slippage_multiplier

    fillable = True
    fill_price = slipped_price
    if request.order_type == "limit":
        if request.limit_price is None:
            return BrokerPaperFillEstimate(
                status="not_fillable",
                reason="Limit paper fill estimate requires a limit price.",
                reference_price=request.reference_price,
                quantity=request.quantity,
                fillable=False,
                fee_bps=request.paper_fee_bps,
                slippage_bps=request.paper_slippage_bps,
            )
        if request.side == "buy":
            fillable = slipped_price <= request.limit_price
        else:
            fillable = slipped_price >= request.limit_price
        if fillable:
            fill_price = slipped_price

    if not fillable:
        return BrokerPaperFillEstimate(
            status="not_fillable",
            reason="Reference price and slippage do not satisfy the limit order.",
            reference_price=request.reference_price,
            quantity=request.quantity,
            fillable=False,
            fee_bps=request.paper_fee_bps,
            slippage_bps=request.paper_slippage_bps,
        )

    notional = fill_price * request.quantity
    fee = notional * request.paper_fee_bps / 10_000
    signed_quantity = request.quantity if request.side == "buy" else -request.quantity
    cash_delta = -(notional + fee) if request.side == "buy" else notional - fee
    position_after = request.current_position_quantity + signed_quantity

    cash_after: Optional[float] = None
    cash_sufficient: Optional[bool] = None
    if request.cash_available is not None:
        cash_after = request.cash_available + cash_delta
        cash_sufficient = cash_after >= 0 if request.side == "buy" else True

    position_sufficient: Optional[bool] = None
    if request.side == "sell":
        position_sufficient = request.current_position_quantity >= request.quantity

    status = "estimated_fill"
    reason = "Paper fill estimate is within the supplied cash and position assumptions."
    if cash_sufficient is False:
        status = "cash_shortfall"
        reason = "Paper fill estimate exceeds supplied cash_available."
    elif position_sufficient is False:
        status = "position_shortfall"
        reason = "Paper fill estimate exceeds supplied current_position_quantity."

    equity = request.portfolio_equity
    if equity is None and request.cash_available is not None:
        equity = request.cash_available + (request.current_position_quantity * request.reference_price)
    exposure_pct_after: Optional[float] = None
    if equity and equity > 0:
        exposure_pct_after = abs(position_after * fill_price) / equity * 100

    return BrokerPaperFillEstimate(
        status=status,
        reason=reason,
        reference_price=request.reference_price,
        fill_price=fill_price,
        quantity=request.quantity,
        estimated_notional=notional,
        estimated_fee=fee,
        cash_after=cash_after,
        position_after=position_after,
        exposure_pct_after=exposure_pct_after,
        cash_sufficient=cash_sufficient,
        position_sufficient=position_sufficient,
        fillable=True,
        fee_bps=request.paper_fee_bps,
        slippage_bps=request.paper_slippage_bps,
    )


def paper_to_live_route(session: PaperTradingSession) -> PaperToLiveRoute:
    symbol = session.request.symbol
    source = session.request.source
    if symbol.startswith("KRW-"):
        return PaperToLiveRoute(
            session_id=session.id,
            symbol=symbol,
            source=source,
            adapter=UPBIT_CRYPTO_SPOT_ADAPTER,
            status="dry_run_ready",
            eligible_for_order_audit=True,
            message=UPBIT_CRYPTO_SPOT_ADAPTER.reason,
        )
    if source in {"sample_us", "alpha_vantage"}:
        return PaperToLiveRoute(
            session_id=session.id,
            symbol=symbol,
            source=source,
            adapter=US_EQUITY_PAPER_ADAPTER,
            status="paper_only_review",
            eligible_for_order_audit=False,
            message=US_EQUITY_PAPER_ADAPTER.reason,
        )
    return PaperToLiveRoute(
        session_id=session.id,
        symbol=symbol,
        source=source,
        adapter=US_EQUITY_PAPER_ADAPTER,
        status="unsupported",
        eligible_for_order_audit=False,
        message="No paper-to-live adapter route is configured for this symbol/source pair.",
    )


def get_execution_status() -> ExecutionStatus:
    live_enabled = _env_flag("QUANT_LAB_LIVE_TRADING_ENABLED")
    ack_ok = os.environ.get("QUANT_LAB_LIVE_TRADING_ACK") == LIVE_TRADING_ACK_VALUE
    has_keys = bool(os.environ.get("UPBIT_ACCESS_KEY") and os.environ.get("UPBIT_SECRET_KEY"))
    adapter_ready = live_enabled and ack_ok and has_keys

    if not live_enabled:
        reason = "Live order routing is disabled by QUANT_LAB_LIVE_TRADING_ENABLED."
    elif not ack_ok:
        reason = "Set QUANT_LAB_LIVE_TRADING_ACK=REAL_ORDERS_OK to unlock live orders."
    elif not has_keys:
        reason = "UPBIT_ACCESS_KEY and UPBIT_SECRET_KEY are required for live orders."
    else:
        reason = "Upbit private adapter is armed; each request still requires live_confirmation."

    return ExecutionStatus(
        exchange="upbit",
        checked_at=_utc_now_iso(),
        live_trading_enabled=live_enabled,
        adapter_ready=adapter_ready,
        base_url=_upbit_base_url(),
        reason=reason,
    )


def get_execution_settings() -> ExecutionSettings:
    status = get_execution_status()
    credential_configured = _has_upbit_credentials()
    approval_fee_bps = _env_float(
        "QUANT_LAB_APPROVAL_FEE_BPS",
        DEFAULT_APPROVAL_FEE_BPS,
    )

    return ExecutionSettings(
        exchange="upbit",
        checked_at=_utc_now_iso(),
        base_url=_upbit_base_url(),
        live_trading_enabled=status.live_trading_enabled,
        live_ack_configured=os.environ.get("QUANT_LAB_LIVE_TRADING_ACK") == LIVE_TRADING_ACK_VALUE,
        live_ack_required_value=LIVE_TRADING_ACK_VALUE,
        live_confirmation_required=True,
        credential_configured=credential_configured,
        private_reads_enabled=credential_configured,
        adapter_ready=status.adapter_ready,
        order_info_source="upbit_orders_chance" if credential_configured else "local_defaults",
        min_order_notional_krw=_env_float(
            "QUANT_LAB_MIN_ORDER_NOTIONAL_KRW",
            DEFAULT_MIN_ORDER_NOTIONAL_KRW,
        ),
        approval_fee_bps=approval_fee_bps,
        approval_fee_rate=approval_fee_bps / 10_000,
        max_approval_exposure_pct=_env_float(
            "QUANT_LAB_MAX_APPROVAL_EXPOSURE_PCT",
            DEFAULT_MAX_APPROVAL_EXPOSURE_PCT,
        ),
        reason=status.reason,
    )


def get_private_snapshot() -> UpbitPrivateSnapshot:
    has_keys = _has_upbit_credentials()
    if not has_keys:
        return UpbitPrivateSnapshot(
            exchange="upbit",
            checked_at=_utc_now_iso(),
            credential_ready=False,
            base_url=_upbit_base_url(),
            reason="UPBIT_ACCESS_KEY and UPBIT_SECRET_KEY are required for private account reads.",
            balances=[],
            open_orders=[],
        )

    balances = fetch_upbit_accounts()
    open_orders = fetch_upbit_open_orders()
    return UpbitPrivateSnapshot(
        exchange="upbit",
        checked_at=_utc_now_iso(),
        credential_ready=True,
        base_url=_upbit_base_url(),
        reason="Private account reads are available; live order submission remains separately guarded.",
        balances=balances,
        open_orders=open_orders,
    )


def submit_order_intent(
    request: OrderIntentRequest,
    audit_store: OrderAuditStore,
) -> OrderAuditRecord:
    payload = build_upbit_order_payload(request)
    status = get_execution_status()
    created_at = datetime.now(timezone.utc).isoformat()
    record_id = str(uuid.uuid4())

    if not status.adapter_ready:
        record = _audit_record(
            record_id=record_id,
            created_at=created_at,
            request=request,
            status="blocked",
            reason=status.reason,
            request_payload=payload,
        )
        audit_store.save_record(record)
        return record

    if not request.live_confirmation:
        record = _audit_record(
            record_id=record_id,
            created_at=created_at,
            request=request,
            status="blocked",
            reason="Order was not submitted because live_confirmation was false.",
            request_payload=payload,
        )
        audit_store.save_record(record)
        return record

    try:
        response_payload = place_upbit_order(payload)
    except Exception as exc:
        record = _audit_record(
            record_id=record_id,
            created_at=created_at,
            request=request,
            status="failed",
            reason=str(exc),
            request_payload=payload,
        )
        audit_store.save_record(record)
        return record

    record = _audit_record(
        record_id=record_id,
        created_at=created_at,
        request=request,
        status="submitted",
        reason="Order submitted to Upbit private API.",
        request_payload=payload,
        response_payload=response_payload,
    )
    audit_store.save_record(record)
    return record


def queue_strategy_order_intents(
    session: PaperTradingSession,
    audit_store: OrderAuditStore,
    source: str,
    max_intents: int = 5,
    context: Optional[Dict[str, Any]] = None,
) -> StrategyOrderQueueResponse:
    route = paper_to_live_route(session)
    if not route.eligible_for_order_audit:
        raise ValueError(route.message)

    existing_identifiers = _existing_order_identifiers(audit_store)
    records: List[OrderAuditRecord] = []
    skipped_existing = 0

    indexed_trades = list(enumerate(session.trades))[-max_intents:]
    for trade_index, trade in indexed_trades:
        identifier = _strategy_order_identifier(session.id, trade_index)
        if identifier in existing_identifiers:
            skipped_existing += 1
            continue
        records.append(
            _dry_run_record_from_trade(
                session=session,
                trade=trade,
                trade_index=trade_index,
                identifier=identifier,
                context=context,
            )
        )

    for record in records:
        audit_store.save_record(record)

    return StrategyOrderQueueResponse(
        session_id=session.id,
        source=source,
        created=len(records),
        skipped_existing=skipped_existing,
        records=records,
    )


def approve_dry_run_order_intent(
    record_id: str,
    request: OrderApprovalRequest,
    audit_store: OrderAuditStore,
) -> OrderAuditRecord:
    source_record = audit_store.get_record(record_id)
    if source_record is None:
        raise LookupError("Order audit record not found")
    if source_record.status != "dry_run":
        raise ValueError("Only dry-run order audit records can be approved.")

    payload = source_record.request_payload
    precheck = build_order_precheck(source_record)
    approval_request = OrderIntentRequest(
        exchange=source_record.exchange,
        market=source_record.market,
        side=source_record.side,
        ord_type=source_record.ord_type,
        volume=_optional_float(payload.get("volume")),
        price=_optional_float(payload.get("price")),
        identifier=f"approved-{str(payload.get('identifier', source_record.id))}",
        time_in_force=payload.get("time_in_force"),
        live_confirmation=request.live_confirmation,
    )
    status = get_execution_status()
    if status.adapter_ready and precheck.status != "pass":
        result = _audit_record(
            record_id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc).isoformat(),
            request=approval_request,
            status="blocked",
            reason="Pre-approval checks failed before live submission.",
            request_payload=build_upbit_order_payload(approval_request),
            response_payload=_approval_metadata(
                record_id=record_id,
                source_payload=payload,
                request=request,
                precheck=precheck,
            ),
        )
        audit_store.save_record(result)
        return result

    result = submit_order_intent(request=approval_request, audit_store=audit_store)
    result.response_payload = {
        **(result.response_payload or {}),
        **_approval_metadata(
            record_id=record_id,
            source_payload=payload,
            request=request,
            precheck=precheck,
        ),
    }
    audit_store.save_record(result)
    return result


def get_order_precheck(
    record_id: str,
    audit_store: OrderAuditStore,
) -> OrderPrecheckResult:
    record = audit_store.get_record(record_id)
    if record is None:
        raise LookupError("Order audit record not found")
    if record.status != "dry_run":
        raise ValueError("Only dry-run order audit records can be prechecked.")
    return build_order_precheck(record)


def build_order_precheck(record: OrderAuditRecord) -> OrderPrecheckResult:
    if record.status != "dry_run":
        raise ValueError("Only dry-run order audit records can be prechecked.")

    precheck_started_at = _utc_now_iso()
    order_info_checked_at = precheck_started_at
    payload = record.request_payload
    price = _optional_float(payload.get("price"))
    volume = _optional_float(payload.get("volume"))
    if price is None or volume is None:
        raise ValueError("Dry-run limit order requires price and volume for precheck.")

    quote_currency, base_currency = _market_currencies(record.market)
    notional = price * volume
    min_order_notional = _env_float(
        "QUANT_LAB_MIN_ORDER_NOTIONAL_KRW",
        DEFAULT_MIN_ORDER_NOTIONAL_KRW,
    )
    fee_rate = _env_float("QUANT_LAB_APPROVAL_FEE_BPS", DEFAULT_APPROVAL_FEE_BPS) / 10_000
    max_exposure_pct = _env_float(
        "QUANT_LAB_MAX_APPROVAL_EXPOSURE_PCT",
        DEFAULT_MAX_APPROVAL_EXPOSURE_PCT,
    )
    max_order_notional: Optional[float] = None
    price_unit: Optional[float] = None
    order_info_source = "local_defaults"
    checks: List[OrderPrecheckItem] = []
    credential_ready = False
    available_quote_balance: Optional[float] = None
    available_base_balance: Optional[float] = None
    post_order_exposure_pct: Optional[float] = None

    if _has_upbit_credentials():
        try:
            chance = fetch_upbit_order_chance(record.market)
            order_info_checked_at = _utc_now_iso()
            order_info_source = "upbit_orders_chance"
            credential_ready = True
            market_info = _dict_value(chance, "market")
            side_policy = _dict_value(market_info, "bid" if record.side == "bid" else "ask")
            chance_min_total = _optional_float(side_policy.get("min_total"))
            chance_price_unit = _optional_float(side_policy.get("price_unit"))
            chance_fee = _optional_float(chance.get("bid_fee" if record.side == "bid" else "ask_fee"))
            if chance_min_total is not None:
                min_order_notional = chance_min_total
            max_order_notional = _optional_float(market_info.get("max_total"))
            if chance_price_unit is not None:
                price_unit = chance_price_unit
            if chance_fee is not None:
                fee_rate = chance_fee

            bid_account = _dict_value(chance, "bid_account")
            ask_account = _dict_value(chance, "ask_account")
            available_quote_balance = _account_balance(bid_account, quote_currency)
            available_base_balance = _account_balance(ask_account, base_currency)
        except RuntimeError as exc:
            checks.append(
                OrderPrecheckItem(
                    name="order_availability",
                    status="fail",
                    message=f"Upbit order availability check failed: {exc}",
                )
            )

    checks.append(
        _precheck_item(
            name="min_order_notional",
            passed=notional >= min_order_notional,
            message=(
                f"Estimated notional is {notional:.0f} {quote_currency}; "
                f"minimum is {min_order_notional:.0f} {quote_currency}."
            ),
            value=notional,
            threshold=min_order_notional,
        )
    )

    if max_order_notional is not None:
        checks.append(
            _precheck_item(
                name="max_order_notional",
                passed=notional <= max_order_notional,
                message=(
                    f"Estimated notional is {notional:.0f} {quote_currency}; "
                    f"maximum is {max_order_notional:.0f} {quote_currency}."
                ),
                value=notional,
                threshold=max_order_notional,
            )
        )

    if not _has_upbit_credentials():
        checks.append(
            OrderPrecheckItem(
                name="private_balances",
                status="warn",
                message="Private balances are unavailable until UPBIT_ACCESS_KEY and UPBIT_SECRET_KEY are configured.",
            )
        )
        checks.append(
            OrderPrecheckItem(
                name="post_order_exposure",
                status="warn",
                message="Estimated post-order exposure requires private balances.",
            )
        )
    elif credential_ready:
        if record.side == "bid":
            required_quote = notional * (1 + fee_rate)
            checks.append(
                _precheck_item(
                    name="quote_balance",
                    passed=(available_quote_balance or 0.0) >= required_quote,
                    message=(
                        f"{quote_currency} balance is {(available_quote_balance or 0.0):.0f}; "
                        f"estimated requirement is {required_quote:.0f}."
                    ),
                    value=available_quote_balance or 0.0,
                    threshold=required_quote,
                )
            )
        else:
            checks.append(
                _precheck_item(
                    name="base_balance",
                    passed=(available_base_balance or 0.0) >= volume,
                    message=(
                        f"{base_currency} balance is {(available_base_balance or 0.0):.8f}; "
                        f"order quantity is {volume:.8f}."
                    ),
                    value=available_base_balance or 0.0,
                    threshold=volume,
                )
            )

        quote_after = available_quote_balance or 0.0
        base_after = available_base_balance or 0.0
        if record.side == "bid":
            quote_after -= notional * (1 + fee_rate)
            base_after += volume
        else:
            quote_after += notional * max(0.0, 1 - fee_rate)
            base_after -= volume
        equity_after = max(quote_after, 0.0) + max(base_after, 0.0) * price
        if equity_after > 0:
            post_order_exposure_pct = max(base_after, 0.0) * price / equity_after * 100
            checks.append(
                _precheck_item(
                    name="post_order_exposure",
                    passed=post_order_exposure_pct <= max_exposure_pct,
                    message=(
                        f"Estimated post-order {base_currency} exposure is "
                        f"{post_order_exposure_pct:.2f}%; limit is {max_exposure_pct:.2f}%."
                    ),
                    value=post_order_exposure_pct,
                    threshold=max_exposure_pct,
                )
            )
        else:
            checks.append(
                OrderPrecheckItem(
                    name="post_order_exposure",
                    status="fail",
                    message="Estimated post-order equity is not positive.",
                )
            )

    checked_at = _utc_now_iso()
    return OrderPrecheckResult(
        record_id=record.id,
        market=record.market,
        side=record.side,
        checked_at=checked_at,
        status=_precheck_status(checks),
        order_info_source=order_info_source,
        order_info_checked_at=order_info_checked_at,
        order_info_age_seconds=_age_seconds(order_info_checked_at, checked_at),
        estimated_notional=round(notional, 2),
        min_order_notional=round(min_order_notional, 2),
        max_order_notional=round(max_order_notional, 2) if max_order_notional is not None else None,
        price_unit=price_unit,
        fee_rate=fee_rate,
        quote_currency=quote_currency,
        base_currency=base_currency,
        credential_ready=credential_ready,
        available_quote_balance=available_quote_balance,
        available_base_balance=available_base_balance,
        post_order_exposure_pct=(
            round(post_order_exposure_pct, 4)
            if post_order_exposure_pct is not None
            else None
        ),
        max_post_order_exposure_pct=round(max_exposure_pct, 4),
        checks=checks,
    )


def fetch_upbit_accounts() -> List[UpbitAccountBalance]:
    payload = _authenticated_upbit_get("/v1/accounts")
    return [
        UpbitAccountBalance(
            currency=str(item.get("currency", "")),
            balance=_optional_float(item.get("balance")) or 0.0,
            locked=_optional_float(item.get("locked")) or 0.0,
            avg_buy_price=_optional_float(item.get("avg_buy_price")),
            unit_currency=item.get("unit_currency"),
        )
        for item in payload
    ]


def fetch_upbit_order_chance(market: str) -> Dict[str, Any]:
    payload = _authenticated_upbit_get(
        "/v1/orders/chance",
        params=[("market", market)],
    )
    if not isinstance(payload, dict):
        raise RuntimeError("Upbit order availability response was not an object.")
    return payload


def fetch_upbit_open_orders(
    market: Optional[str] = None,
    states: Sequence[str] = ("wait", "watch"),
    limit: int = 50,
) -> List[UpbitOpenOrder]:
    params: List[Tuple[str, object]] = [
        ("states[]", state)
        for state in states
    ]
    params.extend(
        [
            ("page", 1),
            ("limit", min(max(limit, 1), 100)),
            ("order_by", "desc"),
        ]
    )
    if market:
        params.insert(0, ("market", market))

    payload = _authenticated_upbit_get("/v1/orders/open", params=params)
    return [
        UpbitOpenOrder(
            uuid=str(item.get("uuid", "")),
            market=str(item.get("market", "")),
            side=str(item.get("side", "")),
            ord_type=str(item.get("ord_type", "")),
            state=str(item.get("state", "")),
            price=_optional_float(item.get("price")),
            volume=_optional_float(item.get("volume")),
            remaining_volume=_optional_float(item.get("remaining_volume")),
            created_at=item.get("created_at"),
            identifier=item.get("identifier"),
        )
        for item in payload
    ]


def build_upbit_order_payload(request: OrderIntentRequest) -> Dict[str, str]:
    _validate_order_intent(request)
    payload: Dict[str, str] = {
        "market": request.market,
        "side": request.side,
        "ord_type": request.ord_type,
        "identifier": request.identifier or f"quantlab-{uuid.uuid4()}",
    }

    if request.volume is not None:
        payload["volume"] = _numeric_string(request.volume)
    if request.price is not None:
        payload["price"] = _numeric_string(request.price)
    if request.time_in_force is not None:
        payload["time_in_force"] = request.time_in_force

    return payload


def place_upbit_order(payload: Dict[str, str]) -> Dict[str, object]:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    query_string = build_query_string(list(payload.items()))
    token = _authenticated_token(query_string=query_string)
    request = urllib.request.Request(
        f"{_upbit_base_url().rstrip('/')}/v1/orders",
        data=body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise RuntimeError(f"Upbit order request failed with {exc.code}: {detail}") from exc


def build_query_string(params: Sequence[Tuple[str, object]]) -> str:
    parts = []
    for key, value in params:
        encoded_key = urllib.parse.quote_plus(str(key), safe="[]")
        encoded_value = urllib.parse.quote_plus(str(value))
        parts.append(f"{encoded_key}={encoded_value}")
    return "&".join(parts)


def create_upbit_jwt(access_key: str, secret_key: str, query_string: str = "") -> str:
    payload = {
        "access_key": access_key,
        "nonce": str(uuid.uuid4()),
    }
    if query_string:
        payload["query_hash"] = hashlib.sha512(query_string.encode("utf-8")).hexdigest()
        payload["query_hash_alg"] = "SHA512"

    header_segment = _base64url_json({"alg": "HS512", "typ": "JWT"})
    payload_segment = _base64url_json(payload)
    signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
    signature = hmac.new(
        secret_key.encode("utf-8"),
        signing_input,
        hashlib.sha512,
    ).digest()
    signature_segment = _base64url(signature)
    return f"{header_segment}.{payload_segment}.{signature_segment}"


def _validate_order_intent(request: OrderIntentRequest) -> None:
    if request.exchange != "upbit":
        raise ValueError("Only the Upbit exchange adapter is available.")
    if not request.market.startswith("KRW-"):
        raise ValueError("This MVP only allows KRW spot markets such as KRW-BTC.")
    if request.ord_type == "limit" and (request.volume is None or request.price is None):
        raise ValueError("Limit orders require both volume and price.")
    if request.ord_type == "price" and (request.side != "bid" or request.price is None):
        raise ValueError("Market buy orders require side=bid and price.")
    if request.ord_type == "market" and (request.side != "ask" or request.volume is None):
        raise ValueError("Market sell orders require side=ask and volume.")
    if request.ord_type == "best" and request.time_in_force not in {"ioc", "fok"}:
        raise ValueError("Best orders require time_in_force=ioc or fok.")


def _authenticated_upbit_get(
    path: str,
    params: Optional[Sequence[Tuple[str, object]]] = None,
) -> object:
    query_string = build_query_string(params or [])
    token = _authenticated_token(query_string=query_string)
    suffix = f"?{query_string}" if query_string else ""
    request = urllib.request.Request(
        f"{_upbit_base_url().rstrip('/')}{path}{suffix}",
        method="GET",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise RuntimeError(f"Upbit private request failed with {exc.code}: {detail}") from exc


def _authenticated_token(query_string: str = "") -> str:
    access_key = os.environ.get("UPBIT_ACCESS_KEY")
    secret_key = os.environ.get("UPBIT_SECRET_KEY")
    if not access_key or not secret_key:
        raise RuntimeError("Missing Upbit API credentials.")
    return create_upbit_jwt(
        access_key=access_key,
        secret_key=secret_key,
        query_string=query_string,
    )


def _audit_record(
    record_id: str,
    created_at: str,
    request: OrderIntentRequest,
    status: str,
    reason: str,
    request_payload: Dict[str, str],
    response_payload: Optional[Dict[str, object]] = None,
) -> OrderAuditRecord:
    return OrderAuditRecord(
        id=record_id,
        created_at=created_at,
        exchange=request.exchange,
        market=request.market,
        side=request.side,
        ord_type=request.ord_type,
        status=status,
        reason=reason,
        request_payload=request_payload,
        response_payload=response_payload,
    )


def _dry_run_record_from_trade(
    session: PaperTradingSession,
    trade: Trade,
    trade_index: int,
    identifier: str,
    context: Optional[Dict[str, Any]] = None,
) -> OrderAuditRecord:
    request = OrderIntentRequest(
        market=session.request.symbol,
        side="bid" if trade.side == "buy" else "ask",
        ord_type="limit",
        volume=trade.quantity,
        price=trade.price,
        identifier=identifier,
        live_confirmation=False,
    )
    payload = build_upbit_order_payload(request)
    response_payload: Dict[str, Any] = {
        "dry_run": True,
        "source_session_id": session.id,
        "source_trade_index": trade_index,
        "source_trade_timestamp": trade.timestamp,
        "simulated_side": trade.side,
        "simulated_notional": trade.notional,
        "simulated_fee": trade.fee,
        "simulated_cash_after": trade.cash_after,
        "simulated_equity_after": trade.equity_after,
    }
    if context:
        response_payload["context"] = context

    return _audit_record(
        record_id=str(uuid.uuid4()),
        created_at=datetime.now(timezone.utc).isoformat(),
        request=request,
        status="dry_run",
        reason="Dry-run strategy signal from paper trading; no exchange request was made.",
        request_payload=payload,
        response_payload=response_payload,
    )


def _existing_order_identifiers(audit_store: OrderAuditStore) -> set[str]:
    identifiers = set()
    for record in audit_store.list_records(limit=1000):
        identifier = record.request_payload.get("identifier")
        if isinstance(identifier, str):
            identifiers.add(identifier)
    return identifiers


def _strategy_order_identifier(session_id: str, trade_index: int) -> str:
    return f"paper-{session_id}-{trade_index}"


def _approval_metadata(
    record_id: str,
    source_payload: Dict[str, object],
    request: OrderApprovalRequest,
    precheck: OrderPrecheckResult,
) -> Dict[str, object]:
    return {
        "approved_from_record_id": record_id,
        "approved_from_identifier": source_payload.get("identifier"),
        "approval_live_confirmation": request.live_confirmation,
        "precheck": precheck.model_dump(mode="json"),
    }


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _age_seconds(timestamp: str, now: str) -> float:
    try:
        then = datetime.fromisoformat(timestamp)
        current = datetime.fromisoformat(now)
    except ValueError:
        return 0.0
    return round(max(0.0, (current - then).total_seconds()), 3)


def _market_currencies(market: str) -> Tuple[str, str]:
    if "-" in market:
        quote, base = market.split("-", 1)
        return quote, base
    if "/" in market:
        base, quote = market.split("/", 1)
        return quote, base
    return "KRW", market


def _dict_value(payload: Dict[str, Any], key: str) -> Dict[str, Any]:
    value = payload.get(key)
    if isinstance(value, dict):
        return value
    return {}


def _precheck_item(
    name: str,
    passed: bool,
    message: str,
    value: Optional[float] = None,
    threshold: Optional[float] = None,
) -> OrderPrecheckItem:
    return OrderPrecheckItem(
        name=name,
        status="pass" if passed else "fail",
        message=message,
        value=value,
        threshold=threshold,
    )


def _precheck_status(checks: List[OrderPrecheckItem]) -> str:
    if any(check.status == "fail" for check in checks):
        return "fail"
    if any(check.status == "warn" for check in checks):
        return "warn"
    return "pass"


def _balance_for_currency(balances: List[UpbitAccountBalance], currency: str) -> float:
    for balance in balances:
        if balance.currency == currency:
            return balance.balance
    return 0.0


def _account_balance(account: Dict[str, Any], currency: str) -> float:
    if account.get("currency") != currency:
        return 0.0
    return _optional_float(account.get("balance")) or 0.0


def _numeric_string(value: float) -> str:
    return f"{value:.12f}".rstrip("0").rstrip(".")


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw in (None, ""):
        return default
    return float(raw)


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").lower() in {"1", "true", "yes", "on"}


def _has_upbit_credentials() -> bool:
    return bool(os.environ.get("UPBIT_ACCESS_KEY") and os.environ.get("UPBIT_SECRET_KEY"))


def _upbit_base_url() -> str:
    return os.environ.get("UPBIT_BASE_URL", "https://api.upbit.com")


def _optional_float(value: object) -> Optional[float]:
    if value in (None, ""):
        return None
    return float(value)


def _base64url_json(payload: Dict[str, object]) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return _base64url(raw)


def _base64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")
