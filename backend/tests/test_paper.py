import unittest

from app.data import generate_sample_candles
from app.models import (
    LivePaperTradingRequest,
    MarketTicker,
    PaperAdvanceRequest,
    PaperTradingRequest,
    RiskLimits,
)
from app.paper import (
    advance_live_paper_runtime,
    advance_live_paper_runtime_with_ticker,
    create_live_paper_runtime,
    create_ticker_paper_runtime,
    run_paper_session,
)


class PaperTradingTests(unittest.TestCase):
    def test_kill_switch_blocks_orders(self):
        request = PaperTradingRequest(
            strategy="sma_crossover",
            params={"fast_window": 8, "slow_window": 24},
            risk_limits=RiskLimits(kill_switch=True),
        )
        candles = generate_sample_candles("KRW-BTC", "day", 120)

        session = run_paper_session(request, candles)

        self.assertEqual(session.summary.status, "halted")
        self.assertEqual(session.summary.orders, 0)
        self.assertEqual(session.summary.halted_reason, "kill_switch")

    def test_position_limit_caps_open_exposure(self):
        request = PaperTradingRequest(
            strategy="sma_crossover",
            params={"fast_window": 8, "slow_window": 24},
            risk_limits=RiskLimits(max_position_pct=30, max_order_notional=1_000_000),
        )
        candles = generate_sample_candles("KRW-BTC", "day", 180)

        session = run_paper_session(request, candles)

        self.assertLessEqual(session.summary.open_position_pct, 31)
        self.assertTrue(
            any(event.rule == "max_position_pct" for event in session.risk_events)
        )

    def test_order_limit_blocks_additional_rebalances(self):
        request = PaperTradingRequest(
            strategy="sma_crossover",
            params={"fast_window": 8, "slow_window": 24},
            risk_limits=RiskLimits(max_orders=1, max_order_notional=1_000_000),
        )
        candles = generate_sample_candles("KRW-BTC", "day", 180)

        session = run_paper_session(request, candles)

        exposure_increasing_orders = [
            trade for trade in session.trades if trade.side == "buy"
        ]
        self.assertLessEqual(len(exposure_increasing_orders), 1)
        self.assertTrue(any(event.rule == "max_orders" for event in session.risk_events))

    def test_live_replay_advances_one_candle_at_a_time(self):
        request = LivePaperTradingRequest(
            strategy="sma_crossover",
            candle_limit=120,
            warmup_bars=35,
            params={"fast_window": 8, "slow_window": 24},
            risk_limits=RiskLimits(max_position_pct=50),
        )
        candles = generate_sample_candles("KRW-BTC", "day", 120)
        runtime = create_live_paper_runtime(request, candles)

        self.assertEqual(runtime.session.summary.status, "running")
        self.assertEqual(runtime.session.next_index, 35)

        session = advance_live_paper_runtime(runtime, PaperAdvanceRequest(steps=3))

        self.assertEqual(session.next_index, 38)
        self.assertEqual(len(session.equity_curve), 38)
        self.assertIn(session.summary.status, ["running", "completed", "halted"])

    def test_live_replay_completes_when_all_candles_are_consumed(self):
        request = LivePaperTradingRequest(
            strategy="donchian_breakout",
            candle_limit=60,
            warmup_bars=30,
            params={"lookback": 18, "exit_lookback": 9},
        )
        candles = generate_sample_candles("KRW-ETH", "day", 60)
        runtime = create_live_paper_runtime(request, candles)

        session = advance_live_paper_runtime(runtime, PaperAdvanceRequest(steps=50))

        self.assertEqual(session.summary.status, "completed")
        self.assertEqual(session.next_index, session.total_candles)

    def test_ticker_session_appends_fresh_tick_without_completing(self):
        request = LivePaperTradingRequest(
            strategy="sma_crossover",
            candle_limit=80,
            warmup_bars=30,
            params={"fast_window": 8, "slow_window": 24},
            risk_limits=RiskLimits(max_position_pct=50),
        )
        candles = generate_sample_candles("KRW-BTC", "day", 80)
        runtime = create_ticker_paper_runtime(request, candles)
        ticker = MarketTicker(
            symbol="KRW-BTC",
            source="sample",
            timestamp="2026-05-18T00:00:05+00:00",
            price=candles[-1].close * 1.01,
            change_pct=1,
            volume_24h=1000,
            quote_volume_24h=1000 * candles[-1].close,
        )

        self.assertEqual(runtime.mode, "ticker")
        self.assertEqual(runtime.session.mode, "ticker")
        self.assertEqual(runtime.session.next_index, 30)
        self.assertEqual(runtime.session.total_candles, 30)

        session = advance_live_paper_runtime_with_ticker(runtime, ticker)

        self.assertEqual(session.summary.status, "running")
        self.assertEqual(session.next_index, 31)
        self.assertEqual(session.total_candles, 31)
        self.assertEqual(len(session.equity_curve), 31)


if __name__ == "__main__":
    unittest.main()
