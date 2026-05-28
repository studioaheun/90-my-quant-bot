import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from .models import (
    Candle,
    EquityPoint,
    LivePaperTradingRequest,
    LivePaperTradingSession,
    MarketTicker,
    PaperAdvanceRequest,
    PaperTradingRequest,
    PaperTradingSession,
    PaperTradingSummary,
    RiskEvent,
    Trade,
)
from .strategies import target_exposure


@dataclass
class PaperState:
    cash: float
    quantity: float = 0.0
    peak_equity: float = 0.0


@dataclass
class LivePaperRuntime:
    candles: List[Candle]
    session: LivePaperTradingSession
    state: PaperState
    mode: str = "replay"


def run_paper_session(
    request: PaperTradingRequest,
    candles: List[Candle],
    session_id: Optional[str] = None,
) -> PaperTradingSession:
    if len(candles) < 2:
        raise ValueError("At least two candles are required")

    ordered = sorted(candles, key=lambda candle: candle.timestamp)
    session_id = session_id or str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    state = PaperState(cash=request.initial_cash, peak_equity=request.initial_cash)
    fee_rate = request.fee_bps / 10_000
    slippage_rate = request.slippage_bps / 10_000
    equity_curve: List[EquityPoint] = []
    trades: List[Trade] = []
    risk_events: List[RiskEvent] = []
    status = "completed"
    halted_reason = None

    if request.risk_limits.kill_switch:
        first = ordered[0]
        risk_events.append(
            RiskEvent(
                timestamp=first.timestamp,
                level="halt",
                rule="kill_switch",
                message="Paper session did not place orders because kill switch is enabled.",
            )
        )
        status = "halted"
        halted_reason = "kill_switch"

    for index, candle in enumerate(ordered):
        desired_target = 0.0
        adjusted_target = 0.0

        if index > 0 and status != "halted":
            history = ordered[:index]
            current_exposure = _current_exposure(state, candle.close)
            desired_target = target_exposure(
                strategy=request.strategy,
                history=history,
                current_exposure=current_exposure,
                params=request.params,
            )
            adjusted_target, events = _apply_pre_trade_risk(
                request=request,
                candle=candle,
                desired_target=desired_target,
                current_exposure=current_exposure,
                trades=trades,
            )
            _extend_risk_events(risk_events, events)

            trade = _execute_rebalance(
                state=state,
                candle=candle,
                target_exposure=adjusted_target,
                fee_rate=fee_rate,
                slippage_rate=slippage_rate,
                max_order_notional=request.risk_limits.max_order_notional,
            )
            if trade is not None:
                trades.append(trade)

        equity = _equity(state, candle.close)
        state.peak_equity = max(state.peak_equity, equity)
        drawdown_pct = (equity / state.peak_equity - 1) * 100 if state.peak_equity else 0.0
        equity_curve.append(
            EquityPoint(
                timestamp=candle.timestamp,
                equity=round(equity, 2),
                cash=round(state.cash, 2),
                asset_quantity=round(state.quantity, 10),
                close=candle.close,
                target_exposure=round(adjusted_target, 4),
                drawdown_pct=round(drawdown_pct, 4),
            )
        )

        if status != "halted":
            loss_pct = (equity / request.initial_cash - 1) * 100
            if loss_pct <= -request.risk_limits.max_session_loss_pct:
                status = "halted"
                halted_reason = "max_session_loss_pct"
                risk_events.append(
                    RiskEvent(
                        timestamp=candle.timestamp,
                        level="halt",
                        rule="max_session_loss_pct",
                        message=(
                            f"Session halted after equity loss reached {loss_pct:.2f}%."
                        ),
                    )
                )

    if request.risk_limits.kill_switch and not equity_curve:
        first = ordered[0]
        equity_curve.append(
            EquityPoint(
                timestamp=first.timestamp,
                equity=round(request.initial_cash, 2),
                cash=round(request.initial_cash, 2),
                asset_quantity=0,
                close=first.close,
                target_exposure=0,
                drawdown_pct=0,
            )
        )

    final_price = equity_curve[-1].close
    final_equity = _equity(state, final_price)
    open_position_pct = _current_exposure(state, final_price) * 100
    max_drawdown_pct = min(point.drawdown_pct for point in equity_curve)
    summary = PaperTradingSummary(
        session_id=session_id,
        status=status,
        halted_reason=halted_reason,
        initial_equity=round(request.initial_cash, 2),
        final_equity=round(final_equity, 2),
        total_return_pct=round((final_equity / request.initial_cash - 1) * 100, 4),
        max_drawdown_pct=round(max_drawdown_pct, 4),
        cash=round(state.cash, 2),
        asset_quantity=round(state.quantity, 10),
        open_position_pct=round(open_position_pct, 4),
        orders=len(trades),
        risk_events=len(risk_events),
    )

    return PaperTradingSession(
        id=session_id,
        created_at=created_at,
        request=request,
        summary=summary,
        equity_curve=equity_curve,
        trades=trades,
        risk_events=risk_events,
        warnings=[],
    )


def create_live_paper_runtime(
    request: LivePaperTradingRequest,
    candles: List[Candle],
    session_id: Optional[str] = None,
) -> LivePaperRuntime:
    if len(candles) < 2:
        raise ValueError("At least two candles are required")

    ordered = sorted(candles, key=lambda candle: candle.timestamp)
    if request.warmup_bars >= len(ordered):
        raise ValueError("warmup_bars must be smaller than the number of candles")

    session_id = session_id or str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    state = PaperState(cash=request.initial_cash, peak_equity=request.initial_cash)
    equity_curve = [
        _equity_point(
            state=state,
            candle=candle,
            target_exposure=0.0,
        )
        for candle in ordered[: request.warmup_bars]
    ]
    status = "running"
    halted_reason = None
    risk_events: List[RiskEvent] = []
    if request.risk_limits.kill_switch:
        status = "halted"
        halted_reason = "kill_switch"
        risk_events.append(
            RiskEvent(
                timestamp=ordered[request.warmup_bars - 1].timestamp,
                level="halt",
                rule="kill_switch",
                message="Live paper replay is halted because kill switch is enabled.",
            )
        )

    summary = _summary(
        session_id=session_id,
        request=request,
        status=status,
        halted_reason=halted_reason,
        state=state,
        equity_curve=equity_curve,
        trades=[],
        risk_events=risk_events,
    )
    session = LivePaperTradingSession(
        id=session_id,
        created_at=created_at,
        request=request,
        summary=summary,
        equity_curve=equity_curve,
        trades=[],
        risk_events=risk_events,
        warnings=[],
        warmup_bars=request.warmup_bars,
        next_index=request.warmup_bars,
        total_candles=len(ordered),
        mode="replay",
    )
    return LivePaperRuntime(candles=ordered, session=session, state=state, mode="replay")


def create_ticker_paper_runtime(
    request: LivePaperTradingRequest,
    candles: List[Candle],
    session_id: Optional[str] = None,
) -> LivePaperRuntime:
    if len(candles) < request.warmup_bars:
        raise ValueError("warmup_bars must be covered by the seed candles")

    ordered = sorted(candles, key=lambda candle: candle.timestamp)
    seed = ordered[-request.warmup_bars :]
    session_id = session_id or str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    state = PaperState(cash=request.initial_cash, peak_equity=request.initial_cash)
    equity_curve = [
        _equity_point(
            state=state,
            candle=candle,
            target_exposure=0.0,
        )
        for candle in seed
    ]
    status = "running"
    halted_reason = None
    risk_events: List[RiskEvent] = []
    if request.risk_limits.kill_switch:
        status = "halted"
        halted_reason = "kill_switch"
        risk_events.append(
            RiskEvent(
                timestamp=seed[-1].timestamp,
                level="halt",
                rule="kill_switch",
                message="Ticker paper session is halted because kill switch is enabled.",
            )
        )

    summary = _summary(
        session_id=session_id,
        request=request,
        status=status,
        halted_reason=halted_reason,
        state=state,
        equity_curve=equity_curve,
        trades=[],
        risk_events=risk_events,
    )
    session = LivePaperTradingSession(
        id=session_id,
        created_at=created_at,
        request=request,
        summary=summary,
        equity_curve=equity_curve,
        trades=[],
        risk_events=risk_events,
        warnings=[],
        warmup_bars=request.warmup_bars,
        next_index=len(seed),
        total_candles=len(seed),
        mode="ticker",
    )
    return LivePaperRuntime(candles=seed, session=session, state=state, mode="ticker")


def advance_live_paper_runtime(
    runtime: LivePaperRuntime,
    request: PaperAdvanceRequest,
    complete_when_exhausted: bool = True,
) -> LivePaperTradingSession:
    session = runtime.session
    session.total_candles = len(runtime.candles)
    paper_request = session.request
    fee_rate = paper_request.fee_bps / 10_000
    slippage_rate = paper_request.slippage_bps / 10_000

    for _ in range(request.steps):
        if session.summary.status != "running":
            break
        if session.next_index >= len(runtime.candles):
            if complete_when_exhausted:
                _refresh_live_summary(runtime, status="completed")
            break

        index = session.next_index
        candle = runtime.candles[index]
        history = runtime.candles[:index]
        current_exposure = _current_exposure(runtime.state, candle.close)
        desired_target = target_exposure(
            strategy=paper_request.strategy,
            history=history,
            current_exposure=current_exposure,
            params=paper_request.params,
        )
        adjusted_target, events = _apply_pre_trade_risk(
            request=paper_request,
            candle=candle,
            desired_target=desired_target,
            current_exposure=current_exposure,
            trades=session.trades,
        )
        _extend_risk_events(session.risk_events, events)

        trade = _execute_rebalance(
            state=runtime.state,
            candle=candle,
            target_exposure=adjusted_target,
            fee_rate=fee_rate,
            slippage_rate=slippage_rate,
            max_order_notional=paper_request.risk_limits.max_order_notional,
        )
        if trade is not None:
            session.trades.append(trade)

        session.equity_curve.append(
            _equity_point(
                state=runtime.state,
                candle=candle,
                target_exposure=adjusted_target,
            )
        )
        session.next_index += 1
        _refresh_live_summary(runtime)

        final_equity = _equity(runtime.state, candle.close)
        loss_pct = (final_equity / paper_request.initial_cash - 1) * 100
        if loss_pct <= -paper_request.risk_limits.max_session_loss_pct:
            session.risk_events.append(
                RiskEvent(
                    timestamp=candle.timestamp,
                    level="halt",
                    rule="max_session_loss_pct",
                    message=f"Live replay halted after equity loss reached {loss_pct:.2f}%.",
                )
            )
            _refresh_live_summary(
                runtime,
                status="halted",
                halted_reason="max_session_loss_pct",
            )
            break

    if (
        complete_when_exhausted
        and session.next_index >= len(runtime.candles)
        and session.summary.status == "running"
    ):
        _refresh_live_summary(runtime, status="completed")

    return session


def advance_live_paper_runtime_with_ticker(
    runtime: LivePaperRuntime,
    ticker: MarketTicker,
) -> LivePaperTradingSession:
    session = runtime.session
    if session.summary.status != "running":
        return session

    candle = Candle(
        timestamp=ticker.timestamp,
        open=ticker.price,
        high=ticker.price,
        low=ticker.price,
        close=ticker.price,
        volume=ticker.volume_24h or 0.0,
    )
    runtime.candles.append(candle)
    session.total_candles = len(runtime.candles)
    return advance_live_paper_runtime(
        runtime=runtime,
        request=PaperAdvanceRequest(steps=1),
        complete_when_exhausted=False,
    )


def _apply_pre_trade_risk(
    request: PaperTradingRequest,
    candle: Candle,
    desired_target: float,
    current_exposure: float,
    trades: List[Trade],
) -> Tuple[float, List[RiskEvent]]:
    events: List[RiskEvent] = []
    max_target = request.risk_limits.max_position_pct / 100
    adjusted = min(max(desired_target, 0.0), max_target)

    if desired_target > adjusted:
        events.append(
            RiskEvent(
                timestamp=candle.timestamp,
                level="warning",
                rule="max_position_pct",
                message=(
                    f"Target exposure capped from {desired_target * 100:.2f}% "
                    f"to {adjusted * 100:.2f}%."
                ),
            )
        )

    entry_orders = len([trade for trade in trades if trade.side == "buy"])
    if entry_orders >= request.risk_limits.max_orders and adjusted > current_exposure:
        if abs(adjusted - current_exposure) > 0.001:
            events.append(
                RiskEvent(
                    timestamp=candle.timestamp,
                    level="halt",
                    rule="max_orders",
                    message="Order limit reached; exposure-increasing rebalances are blocked.",
                )
            )
        adjusted = current_exposure

    return adjusted, events


def _refresh_live_summary(
    runtime: LivePaperRuntime,
    status: Optional[str] = None,
    halted_reason: Optional[str] = None,
) -> None:
    session = runtime.session
    resolved_status = status or session.summary.status
    session.summary = _summary(
        session_id=session.id,
        request=session.request,
        status=resolved_status,
        halted_reason=halted_reason,
        state=runtime.state,
        equity_curve=session.equity_curve,
        trades=session.trades,
        risk_events=session.risk_events,
    )


def _summary(
    session_id: str,
    request: PaperTradingRequest,
    status: str,
    halted_reason: Optional[str],
    state: PaperState,
    equity_curve: List[EquityPoint],
    trades: List[Trade],
    risk_events: List[RiskEvent],
) -> PaperTradingSummary:
    final_price = equity_curve[-1].close
    final_equity = _equity(state, final_price)
    open_position_pct = _current_exposure(state, final_price) * 100
    max_drawdown_pct = min(point.drawdown_pct for point in equity_curve)
    return PaperTradingSummary(
        session_id=session_id,
        status=status,
        halted_reason=halted_reason,
        initial_equity=round(request.initial_cash, 2),
        final_equity=round(final_equity, 2),
        total_return_pct=round((final_equity / request.initial_cash - 1) * 100, 4),
        max_drawdown_pct=round(max_drawdown_pct, 4),
        cash=round(state.cash, 2),
        asset_quantity=round(state.quantity, 10),
        open_position_pct=round(open_position_pct, 4),
        orders=len(trades),
        risk_events=len(risk_events),
    )


def _equity_point(
    state: PaperState,
    candle: Candle,
    target_exposure: float,
) -> EquityPoint:
    equity = _equity(state, candle.close)
    state.peak_equity = max(state.peak_equity, equity)
    drawdown_pct = (equity / state.peak_equity - 1) * 100 if state.peak_equity else 0.0
    return EquityPoint(
        timestamp=candle.timestamp,
        equity=round(equity, 2),
        cash=round(state.cash, 2),
        asset_quantity=round(state.quantity, 10),
        close=candle.close,
        target_exposure=round(target_exposure, 4),
        drawdown_pct=round(drawdown_pct, 4),
    )


def _extend_risk_events(target: List[RiskEvent], events: List[RiskEvent]) -> None:
    for event in events:
        if any(
            existing.rule == event.rule and existing.message == event.message
            for existing in target
        ):
            continue
        target.append(event)


def _execute_rebalance(
    state: PaperState,
    candle: Candle,
    target_exposure: float,
    fee_rate: float,
    slippage_rate: float,
    max_order_notional: Optional[float],
) -> Optional[Trade]:
    target = min(max(target_exposure, 0.0), 1.0)
    mark_price = candle.close
    equity_before = _equity(state, mark_price)
    current_value = state.quantity * mark_price
    target_value = equity_before * target
    delta = target_value - current_value
    if max_order_notional is not None:
        delta = _clamp_notional(delta, max_order_notional)
    min_trade_value = max(1.0, equity_before * 0.0005)

    if abs(delta) < min_trade_value:
        return None

    if delta > 0:
        buy_notional = min(delta, state.cash / (1 + fee_rate))
        if buy_notional <= 0:
            return None
        fill_price = mark_price * (1 + slippage_rate)
        quantity = buy_notional / fill_price
        fee = buy_notional * fee_rate
        state.cash -= buy_notional + fee
        state.quantity += quantity
        side = "buy"
        notional = buy_notional
    else:
        fill_price = mark_price * (1 - slippage_rate)
        sell_notional = min(abs(delta), state.quantity * fill_price)
        if sell_notional <= 0:
            return None
        quantity = sell_notional / fill_price
        fee = sell_notional * fee_rate
        state.cash += sell_notional - fee
        state.quantity -= quantity
        if state.quantity < 1e-12:
            state.quantity = 0.0
        side = "sell"
        notional = sell_notional

    return Trade(
        timestamp=candle.timestamp,
        side=side,
        price=round(fill_price, 8),
        quantity=round(quantity, 10),
        notional=round(notional, 2),
        fee=round(fee, 2),
        cash_after=round(state.cash, 2),
        equity_after=round(_equity(state, mark_price), 2),
    )


def _clamp_notional(delta: float, maximum: float) -> float:
    if delta > 0:
        return min(delta, maximum)
    return max(delta, -maximum)


def _equity(state: PaperState, price: float) -> float:
    return state.cash + state.quantity * price


def _current_exposure(state: PaperState, price: float) -> float:
    equity = _equity(state, price)
    if equity <= 0:
        return 0.0
    return (state.quantity * price) / equity
