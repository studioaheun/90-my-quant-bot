import unittest
from datetime import datetime, timedelta, timezone

from app.backtester import run_backtest
from app.data import generate_sample_candles, generate_sample_us_candles, get_market_ticker
from app.models import BacktestRequest, Candle


class BacktesterTests(unittest.TestCase):
    def test_sma_backtest_produces_metrics_and_trades(self):
        request = BacktestRequest(
            strategy="sma_crossover",
            candle_limit=180,
            params={"fast_window": 8, "slow_window": 24},
        )
        candles = generate_sample_candles("KRW-BTC", "day", 180)

        result = run_backtest(request, candles)

        self.assertEqual(len(result.equity_curve), 180)
        self.assertGreater(result.metrics.final_equity, 0)
        self.assertGreaterEqual(result.metrics.trades, 1)
        self.assertLessEqual(result.metrics.exposure_pct, 100)
        self.assertGreater(result.metrics.buy_and_hold_final_equity, 0)
        self.assertNotEqual(result.metrics.strategy_edge_pct, 0)

    def test_backtest_metrics_include_buy_and_hold_benchmark(self):
        request = BacktestRequest(
            strategy="sma_crossover",
            initial_cash=1_000_000,
            fee_bps=5,
            slippage_bps=2,
            candle_limit=180,
            params={"fast_window": 8, "slow_window": 24},
        )
        candles = generate_sample_candles("KRW-BTC", "day", 180)

        result = run_backtest(request, candles)

        fee_rate = request.fee_bps / 10_000
        slippage_rate = request.slippage_bps / 10_000
        entry_price = candles[0].close * (1 + slippage_rate)
        quantity = (request.initial_cash / (1 + fee_rate)) / entry_price
        expected_final = round(quantity * candles[-1].close, 2)
        expected_return = round((expected_final / request.initial_cash - 1) * 100, 4)
        expected_edge = round(result.metrics.total_return_pct - expected_return, 4)

        self.assertEqual(result.metrics.buy_and_hold_final_equity, expected_final)
        self.assertEqual(result.metrics.buy_and_hold_return_pct, expected_return)
        self.assertLessEqual(result.metrics.buy_and_hold_max_drawdown_pct, 0)
        self.assertEqual(result.metrics.strategy_edge_pct, expected_edge)

    def test_donchian_backtest_keeps_equity_non_negative(self):
        request = BacktestRequest(
            strategy="donchian_breakout",
            candle_limit=180,
            params={"lookback": 18, "exit_lookback": 9},
        )
        candles = generate_sample_candles("KRW-ETH", "day", 180)

        result = run_backtest(request, candles)

        self.assertTrue(all(point.equity >= 0 for point in result.equity_curve))
        self.assertGreaterEqual(result.metrics.max_drawdown_pct, -100)

    def test_rsi_mean_reversion_buys_weakness_and_exits_strength(self):
        request = BacktestRequest(
            strategy="rsi_mean_reversion",
            initial_cash=100_000,
            fee_bps=1,
            slippage_bps=1,
            candle_limit=50,
            params={"rsi_window": 6, "buy_below": 35, "sell_above": 58},
        )
        candles = _trend_reversal_candles()

        result = run_backtest(request, candles)

        self.assertGreaterEqual(result.metrics.trades, 2)
        self.assertEqual(result.trades[0].side, "buy")
        self.assertTrue(any(trade.side == "sell" for trade in result.trades))
        self.assertGreater(result.metrics.final_equity, 0)

    def test_us_stock_sample_backtest_produces_usd_scaled_trades(self):
        request = BacktestRequest(
            symbol="SPY",
            source="sample_us",
            strategy="sma_crossover",
            initial_cash=100_000,
            fee_bps=1,
            slippage_bps=1,
            candle_limit=180,
            params={"fast_window": 8, "slow_window": 24},
        )
        candles = generate_sample_us_candles("SPY", "day", 180)

        result = run_backtest(request, candles)
        ticker = get_market_ticker("SPY", "sample_us")

        self.assertEqual(result.request.source, "sample_us")
        self.assertEqual(len(result.equity_curve), 180)
        self.assertGreater(result.metrics.final_equity, 0)
        self.assertGreaterEqual(result.metrics.trades, 1)
        self.assertLess(result.candles[-1].close, 1000)
        self.assertEqual(ticker.source, "sample_us")
        self.assertEqual(ticker.symbol, "SPY")

    def test_invalid_sma_window_raises(self):
        request = BacktestRequest(
            strategy="sma_crossover",
            params={"fast_window": 30, "slow_window": 10},
        )
        candles = generate_sample_candles("KRW-BTC", "day", 180)

        with self.assertRaises(ValueError):
            run_backtest(request, candles)

    def test_invalid_rsi_thresholds_raise(self):
        request = BacktestRequest(
            strategy="rsi_mean_reversion",
            params={"rsi_window": 14, "buy_below": 60, "sell_above": 40},
        )
        candles = generate_sample_candles("KRW-BTC", "day", 180)

        with self.assertRaises(ValueError):
            run_backtest(request, candles)


def _trend_reversal_candles() -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    closes = [
        *[100 - index * 1.2 for index in range(22)],
        *[74.8 + index * 1.8 for index in range(28)],
    ]
    return [
        Candle(
            timestamp=(start + timedelta(days=index)).isoformat(),
            open=close,
            high=close * 1.01,
            low=close * 0.99,
            close=close,
            volume=1_000 + index,
        )
        for index, close in enumerate(closes)
    ]


if __name__ == "__main__":
    unittest.main()
