from datetime import datetime
from typing import Dict, List, Tuple

from .backtester import run_backtest
from .models import (
    BacktestRequest,
    Candle,
    PortfolioAllocationResult,
    PortfolioEquityPoint,
    PortfolioResearchPreset,
    PortfolioResearchMetrics,
    PortfolioResearchRequest,
    PortfolioResearchResponse,
)


def run_portfolio_research(
    request: PortfolioResearchRequest,
    candles_by_symbol: dict[str, List[Candle]],
) -> PortfolioResearchResponse:
    symbols = _unique_symbols(request.symbols)
    if len(symbols) < 2:
        raise ValueError("Portfolio research requires at least two unique symbols.")

    weights = _normalized_weights(symbols=symbols, weights=request.weights)
    allocations: List[PortfolioAllocationResult] = []
    curves_by_symbol: Dict[str, List[PortfolioEquityPoint]] = {}
    warnings: List[str] = []

    for symbol in symbols:
        allocation_cash = request.initial_cash * weights[symbol]
        candles = candles_by_symbol.get(symbol)
        if not candles:
            raise ValueError(f"No candles were provided for {symbol}.")

        backtest_request = BacktestRequest(
            symbol=symbol,
            timeframe=request.timeframe,
            source=request.source,
            strategy=request.strategy,
            initial_cash=allocation_cash,
            fee_bps=request.fee_bps,
            slippage_bps=request.slippage_bps,
            candle_limit=request.candle_limit,
            params=request.params,
        )
        result = run_backtest(request=backtest_request, candles=candles)
        allocations.append(
            PortfolioAllocationResult(
                symbol=symbol,
                target_weight_pct=round(weights[symbol] * 100, 4),
                final_weight_pct=0.0,
                initial_cash=round(allocation_cash, 2),
                final_equity=result.metrics.final_equity,
                total_return_pct=result.metrics.total_return_pct,
                strategy_edge_pct=result.metrics.strategy_edge_pct,
                max_drawdown_pct=result.metrics.max_drawdown_pct,
                sharpe=result.metrics.sharpe,
                trades=result.metrics.trades,
            )
        )
        curves_by_symbol[symbol] = [
            PortfolioEquityPoint(
                timestamp=point.timestamp,
                equity=point.equity,
                drawdown_pct=point.drawdown_pct,
            )
            for point in result.equity_curve
        ]
        warnings.extend(result.warnings)

    portfolio_curve, final_values, rebalances = _aggregate_curves(
        symbols=symbols,
        weights=weights,
        curves_by_symbol=curves_by_symbol,
        rebalance_frequency=request.rebalance_frequency,
    )
    if not portfolio_curve:
        raise ValueError("Portfolio research could not build an aggregate equity curve.")

    final_equity = portfolio_curve[-1].equity
    adjusted_allocations: List[PortfolioAllocationResult] = []
    for allocation in allocations:
        final_value = final_values[allocation.symbol]
        adjusted_allocations.append(
            allocation.model_copy(
                update={
                    "final_equity": round(final_value, 2),
                    "total_return_pct": round(
                        (final_value / allocation.initial_cash - 1) * 100,
                        4,
                    ),
                    "final_weight_pct": round(
                        final_value / final_equity * 100 if final_equity > 0 else 0.0,
                        4,
                    ),
                }
            )
        )

    metrics = _portfolio_metrics(
        initial_equity=request.initial_cash,
        allocations=adjusted_allocations,
        equity_curve=portfolio_curve,
        rebalances=rebalances,
    )
    normalized_request = request.model_copy(
        update={
            "symbols": symbols,
            "weights": {symbol: round(weights[symbol] * 100, 4) for symbol in symbols},
        }
    )

    return PortfolioResearchResponse(
        request=normalized_request,
        metrics=metrics,
        allocations=adjusted_allocations,
        equity_curve=portfolio_curve,
        warnings=warnings,
    )


def portfolio_research_presets() -> List[PortfolioResearchPreset]:
    return [
        PortfolioResearchPreset(
            id="crypto-majors-spot",
            name="Crypto majors spot",
            description="KRW crypto major sleeve for the first spot MVP.",
            request=PortfolioResearchRequest(
                symbols=["KRW-BTC", "KRW-ETH", "KRW-SOL"],
                timeframe="day",
                source="sample",
                strategy="sma_crossover",
                initial_cash=1_000_000,
                fee_bps=5,
                slippage_bps=2,
                candle_limit=180,
                weights={"KRW-BTC": 55, "KRW-ETH": 30, "KRW-SOL": 15},
                rebalance_frequency="monthly",
                params={"fast_window": 10, "slow_window": 30},
            ),
        ),
        PortfolioResearchPreset(
            id="us-core-balanced",
            name="US core balanced",
            description="ETF-led stock paper-trading basket with a measured growth tilt.",
            request=PortfolioResearchRequest(
                symbols=["SPY", "QQQ", "AAPL"],
                timeframe="day",
                source="sample_us",
                strategy="sma_crossover",
                initial_cash=120_000,
                fee_bps=1,
                slippage_bps=1,
                candle_limit=180,
                weights={"SPY": 50, "QQQ": 30, "AAPL": 20},
                rebalance_frequency="monthly",
                params={"fast_window": 8, "slow_window": 24},
            ),
        ),
        PortfolioResearchPreset(
            id="us-growth-tilt",
            name="US growth tilt",
            description="Higher-beta stock/ETF research basket for drawdown-aware comparison.",
            request=PortfolioResearchRequest(
                symbols=["QQQ", "NVDA", "MSFT", "AAPL"],
                timeframe="day",
                source="sample_us",
                strategy="donchian_breakout",
                initial_cash=120_000,
                fee_bps=1,
                slippage_bps=1,
                candle_limit=180,
                weights={"QQQ": 40, "NVDA": 25, "MSFT": 20, "AAPL": 15},
                rebalance_frequency="monthly",
                params={"lookback": 20, "exit_lookback": 10},
            ),
        ),
        PortfolioResearchPreset(
            id="us-etf-rsi-reversion",
            name="US ETF RSI reversion",
            description=(
                "Stock/ETF paper-trading basket for oversold-entry and "
                "strength-exit checks before broker expansion."
            ),
            request=PortfolioResearchRequest(
                symbols=["SPY", "QQQ", "MSFT"],
                timeframe="day",
                source="sample_us",
                strategy="rsi_mean_reversion",
                initial_cash=120_000,
                fee_bps=1,
                slippage_bps=1,
                candle_limit=180,
                weights={"SPY": 45, "QQQ": 35, "MSFT": 20},
                rebalance_frequency="monthly",
                params={"rsi_window": 14, "buy_below": 35, "sell_above": 58},
            ),
        ),
    ]


def _aggregate_curves(
    symbols: List[str],
    weights: Dict[str, float],
    curves_by_symbol: Dict[str, List[PortfolioEquityPoint]],
    rebalance_frequency: str,
) -> Tuple[List[PortfolioEquityPoint], Dict[str, float], int]:
    if not curves_by_symbol:
        return [], {}, 0

    length = min(len(curves_by_symbol[symbol]) for symbol in symbols)
    values = {
        symbol: curves_by_symbol[symbol][0].equity
        for symbol in symbols
    }
    aggregated: List[PortfolioEquityPoint] = []
    peak = 0.0
    rebalances = 0

    for index in range(length):
        if index > 0:
            for symbol in symbols:
                previous = curves_by_symbol[symbol][index - 1].equity
                current = curves_by_symbol[symbol][index].equity
                factor = current / previous if previous > 0 else 1.0
                values[symbol] *= factor

            if _should_rebalance(
                previous_timestamp=curves_by_symbol[symbols[0]][index - 1].timestamp,
                current_timestamp=curves_by_symbol[symbols[0]][index].timestamp,
                rebalance_frequency=rebalance_frequency,
            ):
                total = sum(values.values())
                values = {symbol: total * weights[symbol] for symbol in symbols}
                rebalances += 1

        equity = sum(values.values())
        peak = max(peak, equity)
        drawdown_pct = (equity / peak - 1) * 100 if peak > 0 else 0.0
        aggregated.append(
            PortfolioEquityPoint(
                timestamp=curves_by_symbol[symbols[0]][index].timestamp,
                equity=round(equity, 2),
                drawdown_pct=round(drawdown_pct, 4),
            )
        )

    return aggregated, values, rebalances


def _portfolio_metrics(
    initial_equity: float,
    allocations: List[PortfolioAllocationResult],
    equity_curve: List[PortfolioEquityPoint],
    rebalances: int,
) -> PortfolioResearchMetrics:
    final_equity = equity_curve[-1].equity
    total_return_pct = (final_equity / initial_equity - 1) * 100
    best = max(allocations, key=lambda item: item.total_return_pct)
    worst = min(allocations, key=lambda item: item.total_return_pct)
    average_return = sum(item.total_return_pct for item in allocations) / len(allocations)

    return PortfolioResearchMetrics(
        initial_equity=round(initial_equity, 2),
        final_equity=round(final_equity, 2),
        total_return_pct=round(total_return_pct, 4),
        max_drawdown_pct=round(min(point.drawdown_pct for point in equity_curve), 4),
        average_return_pct=round(average_return, 4),
        rebalances=rebalances,
        best_symbol=best.symbol,
        best_return_pct=best.total_return_pct,
        worst_symbol=worst.symbol,
        worst_return_pct=worst.total_return_pct,
        trades=sum(item.trades for item in allocations),
    )


def _normalized_weights(symbols: List[str], weights: Dict[str, float]) -> Dict[str, float]:
    if not weights:
        equal = 1 / len(symbols)
        return {symbol: equal for symbol in symbols}

    normalized_input = {
        symbol.strip().upper(): value
        for symbol, value in weights.items()
    }
    selected = {
        symbol: float(normalized_input.get(symbol, 0.0))
        for symbol in symbols
    }
    if any(value <= 0 for value in selected.values()):
        raise ValueError("Portfolio weights must be positive for every selected symbol.")

    total = sum(selected.values())
    if total <= 0:
        raise ValueError("Portfolio weights must sum to a positive value.")
    return {symbol: value / total for symbol, value in selected.items()}


def _should_rebalance(
    previous_timestamp: str,
    current_timestamp: str,
    rebalance_frequency: str,
) -> bool:
    if rebalance_frequency == "none":
        return False
    if rebalance_frequency != "monthly":
        raise ValueError(f"Unsupported rebalance frequency: {rebalance_frequency}")

    previous = datetime.fromisoformat(previous_timestamp)
    current = datetime.fromisoformat(current_timestamp)
    return (previous.year, previous.month) != (current.year, current.month)


def _unique_symbols(symbols: List[str]) -> List[str]:
    unique: List[str] = []
    seen = set()
    for symbol in symbols:
        normalized = symbol.strip().upper()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return unique
