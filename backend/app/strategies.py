from typing import Dict, List

from .models import Candle, Number


def target_exposure(
    strategy: str,
    history: List[Candle],
    current_exposure: float,
    params: Dict[str, Number],
) -> float:
    if strategy == "sma_crossover":
        return _sma_crossover(history, params)
    if strategy == "donchian_breakout":
        return _donchian_breakout(history, current_exposure, params)
    if strategy == "rsi_mean_reversion":
        return _rsi_mean_reversion(history, current_exposure, params)
    raise ValueError(f"Unsupported strategy: {strategy}")


def _sma_crossover(history: List[Candle], params: Dict[str, Number]) -> float:
    fast_window = int(params.get("fast_window", 10))
    slow_window = int(params.get("slow_window", 30))
    if fast_window <= 0 or slow_window <= 0:
        raise ValueError("SMA windows must be positive")
    if fast_window >= slow_window:
        raise ValueError("fast_window must be smaller than slow_window")
    if len(history) < slow_window:
        return 0.0

    closes = [candle.close for candle in history]
    fast = sum(closes[-fast_window:]) / fast_window
    slow = sum(closes[-slow_window:]) / slow_window
    return 1.0 if fast > slow else 0.0


def _donchian_breakout(
    history: List[Candle],
    current_exposure: float,
    params: Dict[str, Number],
) -> float:
    lookback = int(params.get("lookback", 20))
    exit_lookback = int(params.get("exit_lookback", 10))
    if lookback <= 1 or exit_lookback <= 1:
        raise ValueError("Donchian windows must be greater than 1")
    if len(history) <= max(lookback, exit_lookback):
        return 0.0

    close = history[-1].close
    entry_high = max(candle.high for candle in history[-lookback - 1 : -1])
    exit_low = min(candle.low for candle in history[-exit_lookback - 1 : -1])

    if current_exposure <= 0 and close > entry_high:
        return 1.0
    if current_exposure > 0 and close < exit_low:
        return 0.0
    return current_exposure


def _rsi_mean_reversion(
    history: List[Candle],
    current_exposure: float,
    params: Dict[str, Number],
) -> float:
    window = int(params.get("rsi_window", 14))
    buy_below = float(params.get("buy_below", 30))
    sell_above = float(params.get("sell_above", 55))
    if window <= 1:
        raise ValueError("RSI window must be greater than 1")
    if not 0 < buy_below < sell_above < 100:
        raise ValueError("RSI thresholds must satisfy 0 < buy_below < sell_above < 100")
    if len(history) <= window:
        return 0.0

    rsi = _relative_strength_index(history[-window - 1 :])
    if current_exposure <= 0 and rsi <= buy_below:
        return 1.0
    if current_exposure > 0 and rsi >= sell_above:
        return 0.0
    return current_exposure


def _relative_strength_index(history: List[Candle]) -> float:
    gains: List[float] = []
    losses: List[float] = []
    for previous, current in zip(history, history[1:]):
        change = current.close - previous.close
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))

    average_gain = sum(gains) / len(gains)
    average_loss = sum(losses) / len(losses)
    if average_gain == 0 and average_loss == 0:
        return 50.0
    if average_loss == 0:
        return 100.0
    relative_strength = average_gain / average_loss
    return 100 - (100 / (1 + relative_strength))
