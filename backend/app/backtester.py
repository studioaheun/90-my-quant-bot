import math
from dataclasses import dataclass
from datetime import datetime
from statistics import mean, pstdev
from typing import List, Tuple

from .models import (
    BacktestMetrics,
    BacktestRequest,
    BacktestResponse,
    Candle,
    EquityPoint,
    Trade,
)
from .strategies import target_exposure


@dataclass
class BacktestState:
    cash: float
    quantity: float = 0.0
    peak_equity: float = 0.0
    bars_in_market: int = 0


@dataclass(frozen=True)
class BuyAndHoldMetrics:
    final_equity: float
    return_pct: float
    max_drawdown_pct: float
    strategy_edge_pct: float


def run_backtest(request: BacktestRequest, candles: List[Candle]) -> BacktestResponse:
    if len(candles) < 2:
        raise ValueError("At least two candles are required")

    ordered = sorted(candles, key=lambda candle: candle.timestamp)
    fee_rate = request.fee_bps / 10_000
    slippage_rate = request.slippage_bps / 10_000
    state = BacktestState(cash=request.initial_cash, peak_equity=request.initial_cash)
    equity_curve: List[EquityPoint] = []
    trades: List[Trade] = []

    for index, candle in enumerate(ordered):
        target = 0.0
        if index > 0:
            history = ordered[:index]
            current_exposure = _current_exposure(state, candle.close)
            target = target_exposure(
                strategy=request.strategy,
                history=history,
                current_exposure=current_exposure,
                params=request.params,
            )
            trade = _rebalance(
                state=state,
                candle=candle,
                target_exposure=target,
                fee_rate=fee_rate,
                slippage_rate=slippage_rate,
            )
            if trade is not None:
                trades.append(trade)

        equity = _equity(state, candle.close)
        state.peak_equity = max(state.peak_equity, equity)
        drawdown_pct = 0.0
        if state.peak_equity > 0:
            drawdown_pct = (equity / state.peak_equity - 1) * 100
        if state.quantity > 0:
            state.bars_in_market += 1

        equity_curve.append(
            EquityPoint(
                timestamp=candle.timestamp,
                equity=round(equity, 2),
                cash=round(state.cash, 2),
                asset_quantity=round(state.quantity, 10),
                close=candle.close,
                target_exposure=round(target, 4),
                drawdown_pct=round(drawdown_pct, 4),
            )
        )

    metrics = _metrics(
        initial_equity=request.initial_cash,
        candles=ordered,
        equity_curve=equity_curve,
        trades=trades,
        bars_in_market=state.bars_in_market,
        fee_bps=request.fee_bps,
        slippage_bps=request.slippage_bps,
    )

    return BacktestResponse(
        request=request,
        metrics=metrics,
        equity_curve=equity_curve,
        trades=trades,
        candles=ordered,
        warnings=[],
    )


def _rebalance(
    state: BacktestState,
    candle: Candle,
    target_exposure: float,
    fee_rate: float,
    slippage_rate: float,
) -> Trade:
    target = min(max(target_exposure, 0.0), 1.0)
    mark_price = candle.close
    equity_before = _equity(state, mark_price)
    current_value = state.quantity * mark_price
    target_value = equity_before * target
    delta = target_value - current_value
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

    equity_after = _equity(state, mark_price)
    return Trade(
        timestamp=candle.timestamp,
        side=side,
        price=round(fill_price, 8),
        quantity=round(quantity, 10),
        notional=round(notional, 2),
        fee=round(fee, 2),
        cash_after=round(state.cash, 2),
        equity_after=round(equity_after, 2),
    )


def _metrics(
    initial_equity: float,
    candles: List[Candle],
    equity_curve: List[EquityPoint],
    trades: List[Trade],
    bars_in_market: int,
    fee_bps: float,
    slippage_bps: float,
) -> BacktestMetrics:
    final_equity = equity_curve[-1].equity
    total_return_pct = (final_equity / initial_equity - 1) * 100
    benchmark = compute_buy_and_hold_metrics(
        initial_equity=initial_equity,
        candles=candles,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        strategy_return_pct=total_return_pct,
    )
    returns = _period_returns(equity_curve)
    cagr_pct = _cagr(initial_equity, final_equity, candles)
    downside = [value for value in returns if value < 0]
    std = pstdev(returns) if len(returns) > 1 else 0.0
    downside_std = pstdev(downside) if len(downside) > 1 else 0.0
    avg = mean(returns) if returns else 0.0
    annualizer = math.sqrt(365)
    sharpe = (avg / std) * annualizer if std > 0 else 0.0
    sortino = (avg / downside_std) * annualizer if downside_std > 0 else 0.0
    max_drawdown_pct = min(point.drawdown_pct for point in equity_curve)
    exposure_pct = bars_in_market / len(equity_curve) * 100

    return BacktestMetrics(
        initial_equity=round(initial_equity, 2),
        final_equity=round(final_equity, 2),
        total_return_pct=round(total_return_pct, 4),
        buy_and_hold_final_equity=benchmark.final_equity,
        buy_and_hold_return_pct=benchmark.return_pct,
        buy_and_hold_max_drawdown_pct=benchmark.max_drawdown_pct,
        strategy_edge_pct=benchmark.strategy_edge_pct,
        cagr_pct=round(cagr_pct, 4),
        max_drawdown_pct=round(max_drawdown_pct, 4),
        sharpe=round(sharpe, 4),
        sortino=round(sortino, 4),
        exposure_pct=round(exposure_pct, 4),
        trades=len(trades),
    )


def compute_buy_and_hold_metrics(
    initial_equity: float,
    candles: List[Candle],
    fee_bps: float,
    slippage_bps: float,
    strategy_return_pct: float,
) -> BuyAndHoldMetrics:
    fee_rate = fee_bps / 10_000
    slippage_rate = slippage_bps / 10_000
    curve = _buy_and_hold_equity_curve(
        initial_equity=initial_equity,
        candles=candles,
        fee_rate=fee_rate,
        slippage_rate=slippage_rate,
    )
    final_equity = curve[-1] if curve else initial_equity
    return_pct = (final_equity / initial_equity - 1) * 100 if initial_equity > 0 else 0.0
    rounded_return_pct = round(return_pct, 4)
    return BuyAndHoldMetrics(
        final_equity=round(final_equity, 2),
        return_pct=rounded_return_pct,
        max_drawdown_pct=round(_max_drawdown_pct(curve), 4),
        strategy_edge_pct=round(round(strategy_return_pct, 4) - rounded_return_pct, 4),
    )


def _buy_and_hold_equity_curve(
    initial_equity: float,
    candles: List[Candle],
    fee_rate: float,
    slippage_rate: float,
) -> List[float]:
    if not candles:
        return []

    entry_close = candles[0].close
    if entry_close <= 0:
        return [initial_equity for _ in candles]

    entry_price = entry_close * (1 + slippage_rate)
    buy_notional = initial_equity / (1 + fee_rate)
    quantity = buy_notional / entry_price
    return [quantity * candle.close for candle in candles]


def _max_drawdown_pct(values: List[float]) -> float:
    if not values:
        return 0.0

    peak = values[0]
    max_drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            max_drawdown = min(max_drawdown, (value / peak - 1) * 100)
    return max_drawdown


def _equity(state: BacktestState, price: float) -> float:
    return state.cash + state.quantity * price


def _current_exposure(state: BacktestState, price: float) -> float:
    equity = _equity(state, price)
    if equity <= 0:
        return 0.0
    return (state.quantity * price) / equity


def _period_returns(equity_curve: List[EquityPoint]) -> List[float]:
    returns: List[float] = []
    for previous, current in zip(equity_curve, equity_curve[1:]):
        if previous.equity > 0:
            returns.append(current.equity / previous.equity - 1)
    return returns


def _cagr(initial_equity: float, final_equity: float, candles: List[Candle]) -> float:
    start, end = _date_bounds(candles)
    days = max((end - start).days, 1)
    years = days / 365
    if initial_equity <= 0 or final_equity <= 0 or years <= 0:
        return 0.0
    return ((final_equity / initial_equity) ** (1 / years) - 1) * 100


def _date_bounds(candles: List[Candle]) -> Tuple[datetime, datetime]:
    return (_parse_datetime(candles[0].timestamp), _parse_datetime(candles[-1].timestamp))


def _parse_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)
