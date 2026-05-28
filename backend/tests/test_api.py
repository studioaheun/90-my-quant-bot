import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

os.environ["QUANT_LAB_DB_PATH"] = str(
    Path(tempfile.gettempdir()) / f"quant_lab_api_tests_{os.getpid()}.sqlite3"
)
os.environ.pop("QUANT_LAB_LIVE_TRADING_ENABLED", None)
os.environ.pop("QUANT_LAB_LIVE_TRADING_ACK", None)
os.environ.pop("UPBIT_ACCESS_KEY", None)
os.environ.pop("UPBIT_SECRET_KEY", None)
os.environ.pop("ALPHA_VANTAGE_API_KEY", None)
os.environ["QUANT_LAB_COLUMNAR_CACHE_ENABLED"] = "true"
os.environ.pop("QUANT_LAB_DUCKDB_PATH", None)
os.environ.pop("QUANT_LAB_CANDLE_PARQUET_PATH", None)

from app import data  # noqa: E402
from app.brokers import BrokerOrderStatusResult  # noqa: E402
from app.main import (  # noqa: E402
    alert_review_store,
    app,
    backtest_run_store,
    broker_intent_evaluation_store,
    broker_order_reconciliation_store,
    paper_fill_order_note_store,
    live_paper_runtimes,
    order_audit_store,
    operator_decision_store,
    portfolio_paper_watchlist_store,
    portfolio_scan_store,
    portfolio_scenario_store,
    portfolio_watchlist_store,
    session_store,
)
from app.models import BrokerOrderReconciliation, PaperFillOrderNote  # noqa: E402
from app.storage import MarketDataStore  # noqa: E402


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        backtest_run_store.clear()
        broker_intent_evaluation_store.clear()
        broker_order_reconciliation_store.clear()
        paper_fill_order_note_store.clear()
        order_audit_store.clear()
        alert_review_store.clear()
        operator_decision_store.clear()
        portfolio_paper_watchlist_store.clear()
        portfolio_scan_store.clear()
        portfolio_scenario_store.clear()
        portfolio_watchlist_store.clear()
        live_paper_runtimes.clear()
        session_store.clear()
        data.set_market_data_store_for_tests(None)

    def tearDown(self):
        data.set_market_data_store_for_tests(None)

    def test_backtest_endpoint_runs(self):
        response = self.client.post(
            "/api/backtests/run",
            json={
                "symbol": "KRW-BTC",
                "timeframe": "day",
                "source": "sample",
                "strategy": "sma_crossover",
                "initial_cash": 1_000_000,
                "fee_bps": 5,
                "slippage_bps": 2,
                "candle_limit": 180,
                "params": {"fast_window": 10, "slow_window": 30},
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("id", payload)
        self.assertIn("created_at", payload)
        self.assertGreater(payload["metrics"]["final_equity"], 0)
        self.assertGreater(payload["metrics"]["buy_and_hold_final_equity"], 0)
        self.assertIn("strategy_edge_pct", payload["metrics"])
        self.assertEqual(len(payload["equity_curve"]), 180)

        runs_response = self.client.get("/api/backtests/runs")
        self.assertEqual(runs_response.status_code, 200)
        runs = runs_response.json()
        self.assertEqual(runs[0]["id"], payload["id"])
        self.assertNotIn("equity_curve", runs[0])
        self.assertEqual(
            runs[0]["metrics"]["strategy_edge_pct"],
            payload["metrics"]["strategy_edge_pct"],
        )

        get_response = self.client.get(f"/api/backtests/runs/{payload['id']}")
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.json()["metrics"], payload["metrics"])

    def test_rsi_strategy_is_exposed_and_runs_through_api(self):
        defaults_response = self.client.get("/api/markets/defaults")
        self.assertEqual(defaults_response.status_code, 200)
        self.assertIn("rsi_mean_reversion", defaults_response.json()["strategies"])

        response = self.client.post(
            "/api/backtests/run",
            json={
                "symbol": "QQQ",
                "timeframe": "day",
                "source": "sample_us",
                "strategy": "rsi_mean_reversion",
                "initial_cash": 100_000,
                "fee_bps": 1,
                "slippage_bps": 1,
                "candle_limit": 180,
                "params": {"rsi_window": 14, "buy_below": 35, "sell_above": 58},
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["request"]["strategy"], "rsi_mean_reversion")
        self.assertEqual(len(payload["equity_curve"]), 180)
        self.assertGreater(payload["metrics"]["final_equity"], 0)

    def test_backtest_sweep_ranks_parameter_candidates_without_persisting(self):
        response = self.client.post(
            "/api/backtests/sweep",
            json={
                "symbol": "QQQ",
                "timeframe": "day",
                "source": "sample_us",
                "strategy": "rsi_mean_reversion",
                "initial_cash": 100_000,
                "fee_bps": 1,
                "slippage_bps": 1,
                "candle_limit": 180,
                "params": {"rsi_window": 14, "buy_below": 35, "sell_above": 58},
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["request"]["strategy"], "rsi_mean_reversion")
        self.assertGreaterEqual(len(payload["candidates"]), 4)
        self.assertEqual(payload["candidates"][0]["rank"], 1)
        self.assertEqual(payload["best"], payload["candidates"][0])
        self.assertGreater(payload["best"]["metrics"]["final_equity"], 0)
        self.assertIn("sample candles", payload["warnings"][0])

        runs_response = self.client.get("/api/backtests/runs")
        self.assertEqual(runs_response.status_code, 200)
        self.assertEqual(runs_response.json(), [])

    def test_backtest_validation_reports_train_test_gap_without_persisting(self):
        response = self.client.post(
            "/api/backtests/validate",
            json={
                "symbol": "QQQ",
                "timeframe": "day",
                "source": "sample_us",
                "strategy": "rsi_mean_reversion",
                "initial_cash": 100_000,
                "fee_bps": 1,
                "slippage_bps": 1,
                "candle_limit": 180,
                "params": {"rsi_window": 14, "buy_below": 35, "sell_above": 58},
                "train_fraction": 0.65,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["request"]["strategy"], "rsi_mean_reversion")
        self.assertEqual(payload["total_candles"], 180)
        self.assertEqual(payload["train"]["candle_count"], 117)
        self.assertEqual(payload["test"]["candle_count"], 63)
        self.assertIn(payload["verdict"], ["pass", "watch", "fail"])
        self.assertIn("robustness_score", payload)
        self.assertIn("Validation uses deterministic US stock/ETF sample candles", payload["warnings"][0])

        runs_response = self.client.get("/api/backtests/runs")
        self.assertEqual(runs_response.status_code, 200)
        self.assertEqual(runs_response.json(), [])

    def test_walk_forward_validation_reports_rolling_folds_without_persisting(self):
        response = self.client.post(
            "/api/backtests/walk-forward",
            json={
                "symbol": "QQQ",
                "timeframe": "day",
                "source": "sample_us",
                "strategy": "rsi_mean_reversion",
                "initial_cash": 100_000,
                "fee_bps": 1,
                "slippage_bps": 1,
                "candle_limit": 180,
                "params": {"rsi_window": 14, "buy_below": 35, "sell_above": 58},
                "train_window": 60,
                "test_window": 30,
                "step_size": 30,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["request"]["strategy"], "rsi_mean_reversion")
        self.assertEqual(payload["total_candles"], 180)
        self.assertEqual(len(payload["folds"]), 4)
        self.assertEqual(payload["folds"][0]["index"], 1)
        self.assertEqual(payload["folds"][0]["train"]["candle_count"], 60)
        self.assertEqual(payload["folds"][0]["test"]["candle_count"], 30)
        self.assertEqual(
            payload["pass_count"] + payload["watch_count"] + payload["fail_count"],
            len(payload["folds"]),
        )
        self.assertIn(payload["verdict"], ["pass", "watch", "fail"])
        self.assertIn("Walk-forward uses deterministic US stock/ETF sample candles", payload["warnings"][0])

        runs_response = self.client.get("/api/backtests/runs")
        self.assertEqual(runs_response.status_code, 200)
        self.assertEqual(runs_response.json(), [])

    def test_rsi_stock_etf_preset_runs_portfolio_research(self):
        presets_response = self.client.get("/api/research/portfolio/presets")
        self.assertEqual(presets_response.status_code, 200)
        presets = presets_response.json()
        preset = next(
            item for item in presets if item["id"] == "us-etf-rsi-reversion"
        )
        self.assertEqual(preset["request"]["source"], "sample_us")
        self.assertEqual(preset["request"]["strategy"], "rsi_mean_reversion")
        self.assertEqual(preset["request"]["params"]["rsi_window"], 14)

        response = self.client.post(
            "/api/research/portfolio",
            json=preset["request"],
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["request"]["strategy"], "rsi_mean_reversion")
        self.assertEqual(payload["request"]["symbols"], ["SPY", "QQQ", "MSFT"])
        self.assertEqual(len(payload["allocations"]), 3)
        self.assertEqual(len(payload["equity_curve"]), 180)
        self.assertGreater(payload["metrics"]["final_equity"], 0)

    def test_legacy_backtest_runs_get_benchmark_metrics_on_read(self):
        response = self.client.post(
            "/api/backtests/run",
            json={
                "symbol": "KRW-BTC",
                "timeframe": "day",
                "source": "sample",
                "strategy": "sma_crossover",
                "initial_cash": 1_000_000,
                "fee_bps": 5,
                "slippage_bps": 2,
                "candle_limit": 180,
                "params": {"fast_window": 10, "slow_window": 30},
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        legacy_payload = json.loads(json.dumps(payload))
        for key in (
            "buy_and_hold_final_equity",
            "buy_and_hold_return_pct",
            "buy_and_hold_max_drawdown_pct",
            "strategy_edge_pct",
        ):
            legacy_payload["metrics"].pop(key)

        with sqlite3.connect(str(backtest_run_store.db_path)) as conn:
            conn.execute(
                "UPDATE backtest_runs SET payload = ? WHERE id = ?",
                (json.dumps(legacy_payload), payload["id"]),
            )

        get_response = self.client.get(f"/api/backtests/runs/{payload['id']}")
        self.assertEqual(get_response.status_code, 200)
        metrics = get_response.json()["metrics"]
        self.assertEqual(metrics["buy_and_hold_return_pct"], payload["metrics"]["buy_and_hold_return_pct"])
        self.assertEqual(metrics["strategy_edge_pct"], payload["metrics"]["strategy_edge_pct"])

        list_response = self.client.get("/api/backtests/runs")
        self.assertEqual(list_response.status_code, 200)
        summary_metrics = list_response.json()[0]["metrics"]
        self.assertEqual(summary_metrics["strategy_edge_pct"], payload["metrics"]["strategy_edge_pct"])

    def test_ops_self_check_exposes_deployment_metadata_and_runbooks(self):
        response = self.client.get("/api/ops/self-check")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["service"], "quant-lab-api")
        self.assertEqual(payload["version"], "0.1.0")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["database_path"], str(backtest_run_store.db_path))
        self.assertIn("artifacts/crypto-drills", payload["artifact_paths"]["crypto_drills"])
        self.assertIn("artifacts/verification", payload["artifact_paths"]["verification"])
        self.assertIn("enabled", payload["scheduler"])
        self.assertIn("poll_seconds", payload["scheduler"])
        self.assertFalse(payload["live_lock"]["live_trading_enabled"])
        self.assertTrue(payload["live_lock"]["live_locked"])
        runbooks = {item["id"]: item for item in payload["runbooks"]}
        self.assertIn("deployment-hardening", runbooks)
        self.assertEqual(
            runbooks["deployment-hardening"]["api_path"],
            "/api/ops/runbooks/deployment-hardening",
        )

        list_response = self.client.get("/api/ops/runbooks")
        self.assertEqual(list_response.status_code, 200)
        self.assertGreaterEqual(len(list_response.json()), 3)

        runbook_response = self.client.get("/api/ops/runbooks/deployment-hardening")
        self.assertEqual(runbook_response.status_code, 200)
        self.assertIn("# Deployment Hardening", runbook_response.text)

        missing_response = self.client.get("/api/ops/runbooks/missing")
        self.assertEqual(missing_response.status_code, 404)

    def test_execution_status_is_locked_by_default(self):
        response = self.client.get("/api/execution/status")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["exchange"], "upbit")
        self.assertIn("checked_at", payload)
        self.assertFalse(payload["live_trading_enabled"])
        self.assertFalse(payload["adapter_ready"])
        self.assertIn("disabled", payload["reason"])

    def test_execution_settings_are_locked_by_default(self):
        response = self.client.get("/api/execution/settings")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["exchange"], "upbit")
        self.assertFalse(payload["live_trading_enabled"])
        self.assertFalse(payload["live_ack_configured"])
        self.assertFalse(payload["credential_configured"])
        self.assertFalse(payload["private_reads_enabled"])
        self.assertFalse(payload["adapter_ready"])
        self.assertEqual(payload["order_info_source"], "local_defaults")
        self.assertEqual(payload["min_order_notional_krw"], 5000)
        self.assertEqual(payload["approval_fee_bps"], 5)
        self.assertEqual(payload["approval_fee_rate"], 0.0005)
        self.assertEqual(payload["max_approval_exposure_pct"], 60)

    def test_private_snapshot_requires_credentials_by_default(self):
        response = self.client.get("/api/execution/private-snapshot")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["exchange"], "upbit")
        self.assertIn("checked_at", payload)
        self.assertFalse(payload["credential_ready"])
        self.assertEqual(payload["balances"], [])
        self.assertEqual(payload["open_orders"], [])
        self.assertIn("UPBIT_ACCESS_KEY", payload["reason"])

    def test_post_cutover_monitor_is_idle_without_live_attempts(self):
        response = self.client.get("/api/execution/post-cutover-monitor")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "idle")
        self.assertEqual(payload["counts"]["approval_attempts"], 0)
        self.assertEqual(payload["counts"]["open_orders"], 0)
        self.assertEqual(payload["open_orders"], [])
        self.assertEqual(payload["recent_approval_attempts"], [])
        self.assertFalse(payload["settings"]["adapter_ready"])
        self.assertFalse(payload["private_snapshot"]["credential_ready"])
        item_ids = {item["id"] for item in payload["items"]}
        self.assertIn("live_window", item_ids)
        self.assertIn("private_snapshot", item_ids)
        self.assertIn("latest_approval_attempt", item_ids)
        self.assertIn("open_orders", item_ids)

        report_response = self.client.get(
            "/api/execution/post-cutover-monitor/closeout-report",
        )
        self.assertEqual(report_response.status_code, 200)
        report = report_response.json()
        self.assertEqual(report["title"], "Live window closeout report")
        self.assertEqual(report["monitor"]["status"], "idle")
        self.assertTrue(report["filename"].endswith(".md"))
        self.assertIn("## Final Audit State", report["markdown"])
        self.assertIn("No approved live attempts", report["markdown"])
        self.assertIn("## Closeout Procedure", report["markdown"])

    def test_order_intent_is_blocked_and_audited_when_live_disabled(self):
        response = self.client.post(
            "/api/execution/order-intents",
            json={
                "exchange": "upbit",
                "market": "KRW-BTC",
                "side": "bid",
                "ord_type": "limit",
                "volume": 0.001,
                "price": 10_000_000,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["request_payload"]["market"], "KRW-BTC")
        self.assertEqual(payload["request_payload"]["side"], "bid")
        self.assertIn("identifier", payload["request_payload"])

        list_response = self.client.get("/api/execution/order-audits")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()[0]["id"], payload["id"])

        get_response = self.client.get(f"/api/execution/order-audits/{payload['id']}")
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.json()["status"], "blocked")

    def test_market_ticker_endpoint_returns_sample_price(self):
        response = self.client.get(
            "/api/markets/ticker",
            params={"symbol": "KRW-BTC", "source": "sample"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["symbol"], "KRW-BTC")
        self.assertEqual(payload["source"], "sample")
        self.assertGreater(payload["price"], 0)
        self.assertIn("timestamp", payload)

    def test_market_provider_status_lists_config_without_secrets(self):
        response = self.client.get("/api/markets/providers/status")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        by_source = {item["source"]: item for item in payload}
        self.assertTrue(by_source["sample"]["available"])
        self.assertIn("status_checked_at", by_source["sample"])
        self.assertTrue(by_source["sample_us"]["available"])
        self.assertTrue(by_source["upbit"]["available"])
        self.assertFalse(by_source["alpha_vantage"]["configured"])
        self.assertFalse(by_source["alpha_vantage"]["available"])
        self.assertEqual(by_source["alpha_vantage"]["credential_name"], "ALPHA_VANTAGE_API_KEY")
        self.assertNotIn("your-alpha-vantage-key", str(payload))

    def test_broker_intent_reconciliation_endpoint_blocks_without_credentials_and_persists(self):
        intent_response = self.client.post(
            "/api/execution/broker-intents/evaluate",
            json={
                "adapter_id": "alpaca_us_equity_paper",
                "symbol": "SPY",
                "side": "buy",
                "quantity": 1,
                "order_type": "market",
                "reference_price": 500,
                "cash_available": 1_000,
                "client_order_id": "api-alpaca-paper-reconcile-1",
            },
        )
        self.assertEqual(intent_response.status_code, 200)
        evaluation = intent_response.json()
        self.assertEqual(evaluation["adapter_id"], "alpaca_us_equity_paper")
        self.assertEqual(evaluation["submission_status"], "blocked")

        reconcile_response = self.client.get(
            f"/api/execution/broker-intents/evaluations/{evaluation['id']}/reconcile"
        )
        self.assertEqual(reconcile_response.status_code, 200)
        reconciliation = reconcile_response.json()
        self.assertEqual(reconciliation["evaluation_id"], evaluation["id"])
        self.assertEqual(reconciliation["adapter_id"], "alpaca_us_equity_paper")
        self.assertEqual(reconciliation["status"], "blocked")
        self.assertFalse(reconciliation["external_lookup_attempted"])
        self.assertIn("ALPACA_PAPER_TRADING_ENABLED", reconciliation["reason"])

        stored = broker_order_reconciliation_store.list_reconciliations(
            evaluation_id=evaluation["id"],
            limit=5,
        )
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].status, "blocked")

        missing_response = self.client.get(
            "/api/execution/broker-intents/evaluations/missing-evaluation/reconcile"
        )
        self.assertEqual(missing_response.status_code, 404)

    def test_broker_intent_report_includes_rich_reconciliation_evidence(self):
        intent_response = self.client.post(
            "/api/execution/broker-intents/evaluate",
            json={
                "adapter_id": "alpaca_us_equity_paper",
                "symbol": "SPY",
                "side": "buy",
                "quantity": 1,
                "order_type": "market",
                "reference_price": 500,
                "cash_available": 1_000,
                "client_order_id": "api-alpaca-paper-rich-reconcile-1",
            },
        )
        self.assertEqual(intent_response.status_code, 200)
        evaluation = intent_response.json()
        broker_order_reconciliation_store.save_reconciliation(
            BrokerOrderReconciliation(
                id="rich-reconciliation-1",
                checked_at="2026-05-23T00:00:00+00:00",
                evaluation_id=evaluation["id"],
                adapter_id="alpaca_us_equity_paper",
                local_submission_status=evaluation["submission_status"],
                status="matched",
                reason="matched with fill evidence",
                broker_order_id="alpaca-order-rich-1",
                client_order_id="api-alpaca-paper-rich-reconcile-1",
                broker_status="partially_filled",
                broker_symbol="SPY",
                broker_side="buy",
                broker_quantity=1,
                broker_filled_quantity=0.4,
                broker_avg_fill_price=501.25,
                broker_filled_notional=200.5,
                broker_fee=0.01,
                broker_partial_fill=True,
                broker_fill_activity_count=1,
                broker_position_quantity=0.4,
                broker_position_market_value=201.0,
                broker_position_cost_basis=200.5,
                broker_position_unrealized_pl=0.5,
                broker_position_snapshot={"symbol": "SPY", "qty": "0.4"},
                broker_account_cash=999.5,
                broker_account_equity=1200.5,
                broker_account_buying_power=1999.0,
                broker_account_snapshot={"cash": "999.5", "equity": "1200.5"},
                broker_fill_activities=[{"id": "fill-1", "qty": "0.4"}],
                external_lookup_attempted=True,
                broker_payload={"status": "partially_filled"},
            )
        )

        report_response = self.client.get("/api/execution/broker-intents/evaluations/report")
        self.assertEqual(report_response.status_code, 200)
        markdown = report_response.json()["markdown"]
        self.assertIn("Latest reconciliation id: rich-reconciliation-1", markdown)
        self.assertIn("Broker avg fill price: $501.25", markdown)
        self.assertIn("Broker fee: $0.01", markdown)
        self.assertIn("Broker partial fill: True", markdown)
        self.assertIn("Broker position market value: $201.00", markdown)
        self.assertIn("Broker account cash: $999.50", markdown)

    def test_reconciliation_endpoint_compares_broker_fill_with_paper_fill_note(self):
        intent_response = self.client.post(
            "/api/execution/broker-intents/evaluate",
            json={
                "adapter_id": "alpaca_us_equity_paper",
                "symbol": "SPY",
                "side": "buy",
                "quantity": 1,
                "order_type": "market",
                "reference_price": 500,
                "cash_available": 1_000,
                "client_order_id": "api-alpaca-paper-fill-compare-1",
            },
        )
        self.assertEqual(intent_response.status_code, 200)
        evaluation = intent_response.json()
        paper_fill_order_note_store.save_note(
            PaperFillOrderNote(
                id="note-fill-compare-1",
                created_at="2026-05-23T00:00:00+00:00",
                session_id="paper-session-fill-compare-1",
                evaluation_id=evaluation["id"],
                adapter_id="alpaca_us_equity_paper",
                symbol="SPY",
                side="buy",
                quantity=1,
                order_type="market",
                paper_fill_status="estimated_fill",
                intended_fill_price=500,
                intended_notional=500,
                intended_fee=0.1,
                comparison_status="matched_trade",
                external_submission_attempted=False,
                note="Compare paper fill estimate with broker-side paper fill.",
            )
        )

        class FakeBroker:
            def fetch_order_status(self, **_kwargs):
                return BrokerOrderStatusResult(
                    status="found",
                    reason="found",
                    broker_order_id="alpaca-order-compare-1",
                    client_order_id="api-alpaca-paper-fill-compare-1",
                    order_status="filled",
                    symbol="SPY",
                    side="buy",
                    quantity=1,
                    filled_quantity=1,
                    average_fill_price=501,
                    filled_notional=501,
                    broker_fee=0.12,
                    partial_fill=False,
                    fill_activity_count=1,
                    position_quantity=1,
                    position_market_value=502,
                    account_cash=499,
                    account_equity=1001,
                    account_buying_power=998,
                    external_lookup_attempted=True,
                    raw_payload={"status": "filled"},
                )

        with patch("app.execution.alpaca_us_equity_paper_broker", return_value=FakeBroker()):
            reconcile_response = self.client.get(
                f"/api/execution/broker-intents/evaluations/{evaluation['id']}/reconcile"
            )

        self.assertEqual(reconcile_response.status_code, 200)
        reconciliation = reconcile_response.json()
        self.assertEqual(reconciliation["linked_paper_fill_note_id"], "note-fill-compare-1")
        self.assertEqual(reconciliation["paper_fill_comparison_status"], "matched")
        self.assertAlmostEqual(reconciliation["paper_fill_price_delta"], 1)
        self.assertAlmostEqual(reconciliation["paper_fill_price_delta_pct"], 0.2)
        self.assertAlmostEqual(reconciliation["paper_fill_notional_delta"], 1)
        self.assertAlmostEqual(reconciliation["paper_fill_fee_delta"], 0.02)
        self.assertAlmostEqual(reconciliation["broker_account_cash"], 499)

    def test_alert_review_includes_broker_submission_reconciliation_and_fill_drift(self):
        intent_response = self.client.post(
            "/api/execution/broker-intents/evaluate",
            json={
                "adapter_id": "alpaca_us_equity_paper",
                "symbol": "SPY",
                "side": "buy",
                "quantity": 1,
                "order_type": "market",
                "reference_price": 500,
                "cash_available": 1_000,
                "client_order_id": "api-alert-alpaca-paper-1",
            },
        )
        self.assertEqual(intent_response.status_code, 200)
        evaluation = intent_response.json()
        self.assertEqual(evaluation["submission_status"], "blocked")

        reconcile_response = self.client.get(
            f"/api/execution/broker-intents/evaluations/{evaluation['id']}/reconcile"
        )
        self.assertEqual(reconcile_response.status_code, 200)

        paper_fill_order_note_store.save_note(
            PaperFillOrderNote(
                id="note-alert-drift-1",
                created_at="2026-05-23T00:00:00+00:00",
                session_id="session-alert-drift-1",
                evaluation_id=evaluation["id"],
                adapter_id="alpaca_us_equity_paper",
                symbol="SPY",
                side="buy",
                quantity=1,
                order_type="market",
                paper_fill_status="estimated_fill",
                intended_fill_price=500,
                intended_notional=500,
                intended_fee=0.05,
                simulated_trade_timestamp="2026-05-23T00:01:00+00:00",
                simulated_fill_price=515,
                simulated_quantity=1,
                simulated_notional=515,
                price_delta=15,
                price_delta_pct=3.0,
                quantity_delta=0,
                notional_delta=15,
                comparison_status="matched_trade",
                external_submission_attempted=False,
                note="Intentional drift fixture.",
            )
        )

        alerts_response = self.client.get("/api/alerts/review")
        self.assertEqual(alerts_response.status_code, 200)
        alerts = alerts_response.json()["items"]
        by_source = {item["source"]: item for item in alerts}
        self.assertIn("broker_paper_submission", by_source)
        self.assertIn("broker_reconciliation", by_source)
        self.assertIn("paper_fill_drift", by_source)
        self.assertEqual(by_source["broker_paper_submission"]["evaluation_id"], evaluation["id"])
        self.assertEqual(by_source["broker_reconciliation"]["evaluation_id"], evaluation["id"])
        self.assertEqual(by_source["paper_fill_drift"]["evaluation_id"], evaluation["id"])
        self.assertEqual(by_source["paper_fill_drift"]["level"], "error")

        source_filter_response = self.client.get(
            "/api/alerts/review",
            params={"source": "broker_reconciliation"},
        )
        self.assertEqual(source_filter_response.status_code, 200)
        filtered = source_filter_response.json()["items"]
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["source"], "broker_reconciliation")

        handoff_report_response = self.client.get(
            "/api/research/strategy-health/handoff-report",
            params={"limit": 5},
        )
        self.assertEqual(handoff_report_response.status_code, 200)
        handoff_markdown = handoff_report_response.json()["markdown"]
        self.assertIn("broker_paper_submission", handoff_markdown)
        self.assertIn("broker_reconciliation", handoff_markdown)
        self.assertIn(evaluation["id"], handoff_markdown)

    def test_live_readiness_tracks_paper_and_dry_run_evidence(self):
        default_response = self.client.get("/api/readiness/live")

        self.assertEqual(default_response.status_code, 200)
        default_payload = default_response.json()
        self.assertIn(default_payload["status"], ["ready", "watch", "blocked"])
        self.assertGreaterEqual(default_payload["score"], 0)
        self.assertLessEqual(default_payload["score"], 100)
        default_checks = {check["id"]: check for check in default_payload["checks"]}
        self.assertIn("upbit_public_data", default_checks)
        self.assertIn("execution_guard", default_checks)
        self.assertIn("private_reads", default_checks)
        self.assertIn("active_alerts", default_checks)
        self.assertIn("crypto_paper_sessions", default_checks)
        self.assertIn("dry_run_audits", default_checks)
        self.assertIn("approval_runbook", default_checks)
        default_breakdowns = {
            breakdown["id"]: breakdown for breakdown in default_payload["breakdowns"]
        }
        self.assertIn("system", default_breakdowns)
        self.assertIn("operator", default_breakdowns)
        self.assertEqual(default_breakdowns["system"]["label"], "System readiness")
        self.assertEqual(default_breakdowns["operator"]["label"], "Operator readiness")
        self.assertIn(
            "execution_guard",
            [check["id"] for check in default_breakdowns["system"]["checks"]],
        )
        self.assertIn(
            "dry_run_audits",
            [check["id"] for check in default_breakdowns["operator"]["checks"]],
        )
        self.assertEqual(default_checks["crypto_paper_sessions"]["status"], "warn")
        self.assertEqual(default_checks["dry_run_audits"]["status"], "warn")

        adapters_response = self.client.get("/api/execution/paper-live-adapters")
        self.assertEqual(adapters_response.status_code, 200)
        adapters = {adapter["id"]: adapter for adapter in adapters_response.json()}
        self.assertTrue(adapters["upbit_crypto_spot"]["dry_run_audit_supported"])
        self.assertEqual(
            adapters["upbit_crypto_spot"]["broker_contract"]["submission_mode"],
            "guarded_live",
        )
        self.assertIn(
            "UPBIT_ACCESS_KEY",
            adapters["upbit_crypto_spot"]["broker_contract"]["required_credentials"],
        )
        self.assertFalse(adapters["us_equity_paper"]["live_order_supported"])
        self.assertEqual(
            adapters["us_equity_paper"]["broker_contract"]["id"],
            "mock_us_equity_paper",
        )
        self.assertEqual(
            adapters["us_equity_paper"]["broker_contract"]["submission_mode"],
            "paper_record_only",
        )
        self.assertFalse(adapters["us_equity_paper"]["broker_contract"]["required_credentials"])
        self.assertFalse(adapters["alpaca_us_equity_paper_preview"]["live_order_supported"])
        self.assertEqual(adapters["alpaca_us_equity_paper_preview"]["broker"], "alpaca")
        self.assertEqual(
            adapters["alpaca_us_equity_paper_preview"]["broker_contract"]["id"],
            "alpaca_us_equity_paper_preview",
        )
        self.assertIn(
            "ALPACA_API_KEY_ID",
            adapters["alpaca_us_equity_paper_preview"]["broker_contract"]["required_credentials"],
        )
        self.assertFalse(adapters["alpaca_us_equity_paper"]["live_order_supported"])
        self.assertEqual(adapters["alpaca_us_equity_paper"]["broker"], "alpaca")
        self.assertEqual(
            adapters["alpaca_us_equity_paper"]["broker_contract"]["submission_mode"],
            "external_paper",
        )
        self.assertIn(
            "ALPACA_PAPER_TRADING_ACK",
            adapters["alpaca_us_equity_paper"]["broker_contract"]["required_credentials"],
        )

        broker_readiness_response = self.client.get("/api/execution/broker-readiness")
        self.assertEqual(broker_readiness_response.status_code, 200)
        broker_readiness = {
            item["adapter_id"]: item for item in broker_readiness_response.json()["items"]
        }
        self.assertEqual(broker_readiness["upbit_crypto_spot"]["status"], "blocked")
        self.assertEqual(
            broker_readiness["upbit_crypto_spot"]["live_submission_state"],
            "blocked",
        )
        self.assertEqual(
            broker_readiness["us_equity_paper"]["live_submission_state"],
            "paper_record_only",
        )
        self.assertEqual(
            broker_readiness["us_equity_paper"]["credential_boundary"],
            "No credentials accepted; paper-record only.",
        )
        self.assertEqual(
            broker_readiness["alpaca_us_equity_paper_preview"]["live_submission_state"],
            "paper_record_only",
        )
        self.assertIn(
            "never submits externally",
            broker_readiness["alpaca_us_equity_paper_preview"]["credential_boundary"],
        )
        self.assertEqual(broker_readiness["alpaca_us_equity_paper"]["status"], "blocked")
        self.assertEqual(
            broker_readiness["alpaca_us_equity_paper"]["live_submission_state"],
            "blocked",
        )
        alpaca_paper_flag = next(
            check
            for check in broker_readiness["alpaca_us_equity_paper"]["checks"]
            if check["id"] == "paper_flag"
        )
        self.assertEqual(alpaca_paper_flag["status"], "fail")
        stock_live_submission = next(
            check
            for check in broker_readiness["us_equity_paper"]["checks"]
            if check["id"] == "live_submission"
        )
        self.assertEqual(stock_live_submission["status"], "pass")
        self.assertIn("blocked", stock_live_submission["message"])

        broker_intent_response = self.client.post(
            "/api/execution/broker-intents/evaluate",
            json={
                "symbol": "spy",
                "side": "buy",
                "quantity": 2,
                "order_type": "limit",
                "limit_price": 500,
                "reference_price": 499,
                "cash_available": 2_000,
                "current_position_quantity": 0,
                "portfolio_equity": 2_000,
                "paper_fee_bps": 1,
                "paper_slippage_bps": 1,
                "client_order_id": "api-broker-eval-1",
            },
        )
        self.assertEqual(broker_intent_response.status_code, 200)
        broker_intent = broker_intent_response.json()
        self.assertEqual(broker_intent["validation_status"], "accepted")
        self.assertEqual(broker_intent["submission_status"], "paper_recorded")
        self.assertIn("id", broker_intent)
        self.assertEqual(broker_intent["normalized_symbol"], "SPY")
        self.assertFalse(broker_intent["external_submission_attempted"])
        self.assertEqual(
            broker_intent["paper_fill_estimate"]["status"],
            "estimated_fill",
        )
        self.assertTrue(broker_intent["paper_fill_estimate"]["cash_sufficient"])
        self.assertGreater(broker_intent["paper_fill_estimate"]["exposure_pct_after"], 0)

        live_stock_intent_response = self.client.post(
            "/api/execution/broker-intents/evaluate",
            json={
                "symbol": "QQQ",
                "side": "sell",
                "quantity": 1,
                "live_confirmation": True,
            },
        )
        self.assertEqual(live_stock_intent_response.status_code, 200)
        live_stock_intent = live_stock_intent_response.json()
        self.assertEqual(live_stock_intent["submission_status"], "blocked")
        self.assertFalse(live_stock_intent["external_submission_attempted"])

        alpaca_preview_intent_response = self.client.post(
            "/api/execution/broker-intents/evaluate",
            json={
                "adapter_id": "alpaca_us_equity_paper_preview",
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 1,
                "order_type": "market",
                "reference_price": 200,
                "cash_available": 1_000,
                "client_order_id": "api-alpaca-preview-1",
            },
        )
        self.assertEqual(alpaca_preview_intent_response.status_code, 200)
        alpaca_preview_intent = alpaca_preview_intent_response.json()
        self.assertEqual(alpaca_preview_intent["adapter_id"], "alpaca_us_equity_paper_preview")
        self.assertEqual(
            alpaca_preview_intent["broker_contract"]["id"],
            "alpaca_us_equity_paper_preview",
        )
        self.assertEqual(alpaca_preview_intent["submission_status"], "paper_recorded")
        self.assertFalse(alpaca_preview_intent["external_submission_attempted"])

        broker_intent_history_response = self.client.get(
            "/api/execution/broker-intents/evaluations",
            params={"limit": 5},
        )
        self.assertEqual(broker_intent_history_response.status_code, 200)
        broker_intent_history = broker_intent_history_response.json()
        self.assertEqual(len(broker_intent_history), 3)
        self.assertEqual(
            {item["submission_status"] for item in broker_intent_history},
            {"paper_recorded", "blocked"},
        )
        self.assertIn(
            "alpaca_us_equity_paper_preview",
            {item["adapter_id"] for item in broker_intent_history},
        )

        alpaca_history_response = self.client.get(
            "/api/execution/broker-intents/evaluations",
            params={"adapter_id": "alpaca_us_equity_paper_preview", "limit": 5},
        )
        self.assertEqual(alpaca_history_response.status_code, 200)
        alpaca_history = alpaca_history_response.json()
        self.assertEqual(len(alpaca_history), 1)
        self.assertEqual(alpaca_history[0]["normalized_symbol"], "AAPL")

        blocked_broker_intent_history_response = self.client.get(
            "/api/execution/broker-intents/evaluations",
            params={"submission_status": "blocked", "limit": 5},
        )
        self.assertEqual(blocked_broker_intent_history_response.status_code, 200)
        blocked_history = blocked_broker_intent_history_response.json()
        self.assertEqual(len(blocked_history), 1)
        self.assertEqual(blocked_history[0]["normalized_symbol"], "QQQ")

        broker_intent_report_response = self.client.get(
            "/api/execution/broker-intents/evaluations/report",
            params={"limit": 5},
        )
        self.assertEqual(broker_intent_report_response.status_code, 200)
        broker_intent_report = broker_intent_report_response.json()
        self.assertEqual(
            broker_intent_report["title"],
            "US Paper Broker Intent Evaluation Report",
        )
        self.assertTrue(broker_intent_report["filename"].endswith(".md"))
        self.assertEqual(broker_intent_report["summary"]["evaluations"], 3)
        self.assertEqual(
            broker_intent_report["summary"]["external_submission_attempted"],
            0,
        )
        self.assertEqual(broker_intent_report["summary"]["fill_estimated_fill"], 2)
        self.assertEqual(broker_intent_report["summary"]["adapter_us_equity_paper"], 2)
        self.assertEqual(
            broker_intent_report["summary"]["adapter_alpaca_us_equity_paper_preview"],
            1,
        )
        self.assertIn("No external broker submissions were attempted.", broker_intent_report["markdown"])
        self.assertIn("Paper fill status: estimated fill", broker_intent_report["markdown"])
        self.assertIn("Adapter id: alpaca_us_equity_paper_preview", broker_intent_report["markdown"])
        self.assertIn("SPY", broker_intent_report["markdown"])
        self.assertIn("QQQ", broker_intent_report["markdown"])
        self.assertIn("AAPL", broker_intent_report["markdown"])

        blocked_broker_intent_report_response = self.client.get(
            "/api/execution/broker-intents/evaluations/report",
            params={"submission_status": "blocked", "limit": 5},
        )
        self.assertEqual(blocked_broker_intent_report_response.status_code, 200)
        blocked_report = blocked_broker_intent_report_response.json()
        self.assertEqual(len(blocked_report["evaluations"]), 1)
        self.assertIn("Submission status filter: blocked", blocked_report["markdown"])
        self.assertNotIn("SPY", blocked_report["markdown"])

        create_response = self.client.post(
            "/api/paper/sessions",
            json={
                "symbol": "KRW-BTC",
                "timeframe": "day",
                "source": "sample",
                "strategy": "sma_crossover",
                "initial_cash": 1_000_000,
                "fee_bps": 5,
                "slippage_bps": 2,
                "candle_limit": 180,
                "params": {"fast_window": 10, "slow_window": 30},
                "risk_limits": {
                    "max_position_pct": 50,
                    "max_order_notional": 500_000,
                    "max_orders": 20,
                    "max_session_loss_pct": 12,
                    "kill_switch": False,
                },
            },
        )
        self.assertEqual(create_response.status_code, 200)
        session = create_response.json()

        queue_response = self.client.post(
            f"/api/paper/sessions/{session['id']}/order-intents",
            json={"max_intents": 2},
        )
        self.assertEqual(queue_response.status_code, 200)

        ready_response = self.client.get("/api/readiness/live")
        self.assertEqual(ready_response.status_code, 200)
        ready_payload = ready_response.json()
        ready_checks = {check["id"]: check for check in ready_payload["checks"]}
        self.assertGreaterEqual(ready_payload["score"], default_payload["score"])
        self.assertEqual(ready_checks["crypto_paper_sessions"]["status"], "pass")
        self.assertEqual(ready_checks["dry_run_audits"]["status"], "pass")
        self.assertEqual(ready_checks["approval_runbook"]["status"], "pass")
        ready_breakdowns = {
            breakdown["id"]: breakdown for breakdown in ready_payload["breakdowns"]
        }
        self.assertGreaterEqual(
            ready_breakdowns["operator"]["score"],
            default_breakdowns["operator"]["score"],
        )

    def test_live_cutover_checklist_requires_operator_decisions(self):
        default_response = self.client.get("/api/execution/cutover-checklist")

        self.assertEqual(default_response.status_code, 200)
        default_payload = default_response.json()
        self.assertEqual(default_payload["status"], "blocked")
        default_items = {item["id"]: item for item in default_payload["items"]}
        self.assertIn("system_readiness", default_items)
        self.assertIn("private_reads", default_items)
        self.assertIn("dry_run_evidence", default_items)
        self.assertIn("readiness_review_decision", default_items)
        self.assertIn("dry_run_approval_decision", default_items)
        self.assertIn("live_cutover_decision", default_items)
        self.assertIn("adapter_guard", default_items)
        self.assertEqual(default_items["private_reads"]["status"], "fail")
        self.assertEqual(default_items["readiness_review_decision"]["status"], "fail")
        runbook_response = self.client.get("/api/execution/cutover-checklist/runbook")
        self.assertEqual(runbook_response.status_code, 200)
        runbook = runbook_response.json()
        self.assertEqual(runbook["title"], "Live adapter arming runbook")
        self.assertTrue(runbook["filename"].endswith(".md"))
        self.assertIn("## Cutover Checklist", runbook["markdown"])
        self.assertIn("Private account prechecks", runbook["markdown"])
        self.assertIn("QUANT_LAB_LIVE_TRADING_ENABLED", runbook["markdown"])
        self.assertIn("### Readiness Views", runbook["markdown"])
        self.assertIn("System readiness", runbook["markdown"])
        self.assertIn("Operator readiness", runbook["markdown"])
        self.assertIn("## Arming Procedure", runbook["markdown"])
        simulation_response = self.client.post(
            "/api/execution/cutover-checklist/simulate-arming",
            json={},
        )
        self.assertEqual(simulation_response.status_code, 200)
        simulation = simulation_response.json()
        self.assertTrue(simulation["no_order_submission"])
        self.assertTrue(simulation["assumptions"]["live_trading_enabled"])
        simulation_items = {item["id"]: item for item in simulation["simulated"]["items"]}
        simulation_changes = {change["id"]: change for change in simulation["changes"]}
        self.assertEqual(simulation_items["private_reads"]["status"], "pass")
        self.assertEqual(simulation_items["adapter_guard"]["status"], "fail")
        self.assertEqual(simulation_changes["private_reads"]["current_status"], "fail")
        self.assertEqual(simulation_changes["private_reads"]["simulated_status"], "pass")
        self.assertGreaterEqual(len(simulation["current_blockers"]), 1)
        self.assertGreaterEqual(len(simulation["simulated_blockers"]), 1)
        self.assertIn(
            "adapter_guard",
            [item["id"] for item in simulation["simulated_blockers"]],
        )
        self.assertIn("no exchange order", simulation["summary"].lower())

        create_response = self.client.post(
            "/api/paper/sessions",
            json={
                "symbol": "KRW-BTC",
                "timeframe": "day",
                "source": "sample",
                "strategy": "sma_crossover",
                "initial_cash": 1_000_000,
                "fee_bps": 5,
                "slippage_bps": 2,
                "candle_limit": 180,
                "params": {"fast_window": 10, "slow_window": 30},
                "risk_limits": {
                    "max_position_pct": 50,
                    "max_order_notional": 500_000,
                    "max_orders": 20,
                    "max_session_loss_pct": 12,
                    "kill_switch": False,
                },
            },
        )
        self.assertEqual(create_response.status_code, 200)
        session = create_response.json()
        queue_response = self.client.post(
            f"/api/paper/sessions/{session['id']}/order-intents",
            json={"max_intents": 2},
        )
        self.assertEqual(queue_response.status_code, 200)
        dry_run_audit_id = queue_response.json()["records"][0]["id"]

        readiness_response = self.client.get("/api/readiness/live")
        self.assertEqual(readiness_response.status_code, 200)
        readiness = readiness_response.json()
        decisions = [
            {
                "decision_type": "readiness_review",
                "target_id": readiness["checked_at"],
                "status": "approved",
                "note": "Readiness review approved for cutover checklist test.",
                "context": {"readiness_status": readiness["status"]},
            },
            {
                "decision_type": "dry_run_approval",
                "target_id": dry_run_audit_id,
                "status": "approved",
                "note": "Dry-run order review approved for cutover checklist test.",
                "context": {"audit_id": dry_run_audit_id},
            },
            {
                "decision_type": "live_cutover",
                "target_id": default_payload["checked_at"],
                "status": "approved",
                "note": "Live cutover reviewed for test.",
                "context": {"checklist_status": default_payload["status"]},
            },
        ]
        for decision in decisions:
            response = self.client.post("/api/operator/decisions", json=decision)
            self.assertEqual(response.status_code, 200)

        reviewed_response = self.client.get("/api/execution/cutover-checklist")
        self.assertEqual(reviewed_response.status_code, 200)
        reviewed_payload = reviewed_response.json()
        reviewed_items = {item["id"]: item for item in reviewed_payload["items"]}
        self.assertEqual(reviewed_payload["status"], "blocked")
        self.assertEqual(reviewed_items["dry_run_evidence"]["status"], "pass")
        self.assertEqual(reviewed_items["readiness_review_decision"]["status"], "pass")
        self.assertEqual(reviewed_items["dry_run_approval_decision"]["status"], "pass")
        self.assertEqual(reviewed_items["live_cutover_decision"]["status"], "pass")
        self.assertEqual(reviewed_items["private_reads"]["status"], "fail")
        self.assertTrue(
            any(
                decision["decision_type"] == "live_cutover"
                for decision in reviewed_payload["latest_operator_decisions"]
            )
        )
        reviewed_runbook_response = self.client.get("/api/execution/cutover-checklist/runbook")
        self.assertEqual(reviewed_runbook_response.status_code, 200)
        reviewed_runbook = reviewed_runbook_response.json()
        self.assertIn("Live cutover reviewed for test.", reviewed_runbook["markdown"])
        self.assertIn("dry run approval", reviewed_runbook["markdown"])
        self.assertIn(dry_run_audit_id, reviewed_runbook["markdown"])
        reviewed_simulation_response = self.client.post(
            "/api/execution/cutover-checklist/simulate-arming",
            json={},
        )
        self.assertEqual(reviewed_simulation_response.status_code, 200)
        reviewed_simulation = reviewed_simulation_response.json()
        self.assertEqual(reviewed_simulation["simulated"]["status"], "ready")
        reviewed_simulation_items = {
            item["id"]: item for item in reviewed_simulation["simulated"]["items"]
        }
        self.assertEqual(reviewed_simulation_items["adapter_guard"]["status"], "pass")
        self.assertEqual(reviewed_simulation_items["private_reads"]["status"], "pass")

    def test_operator_decisions_are_persisted_and_filterable(self):
        readiness_response = self.client.get("/api/readiness/live")
        self.assertEqual(readiness_response.status_code, 200)
        readiness = readiness_response.json()

        create_response = self.client.post(
            "/api/operator/decisions",
            json={
                "decision_type": "readiness_review",
                "target_id": readiness["checked_at"],
                "status": "needs_work",
                "note": "Keep live guard locked until private reads are configured.",
                "context": {
                    "readiness_status": readiness["status"],
                    "readiness_score": readiness["score"],
                    "warning_checks": [
                        check["id"]
                        for check in readiness["checks"]
                        if check["status"] == "warn"
                    ],
                },
            },
        )
        self.assertEqual(create_response.status_code, 200)
        decision = create_response.json()
        self.assertIn("id", decision)
        self.assertEqual(decision["decision_type"], "readiness_review")
        self.assertEqual(decision["target_id"], readiness["checked_at"])
        self.assertEqual(decision["status"], "needs_work")
        self.assertEqual(
            decision["context"]["readiness_status"],
            readiness["status"],
        )

        dry_run_decision_response = self.client.post(
            "/api/operator/decisions",
            json={
                "decision_type": "dry_run_promotion",
                "target_id": "promotion-test",
                "status": "noted",
                "note": "Promotion review placeholder.",
                "context": {"created": 0},
            },
        )
        self.assertEqual(dry_run_decision_response.status_code, 200)

        list_response = self.client.get("/api/operator/decisions")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()), 2)

        filtered_response = self.client.get(
            "/api/operator/decisions",
            params={"decision_type": "readiness_review"},
        )
        self.assertEqual(filtered_response.status_code, 200)
        filtered = filtered_response.json()
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["id"], decision["id"])

        target_response = self.client.get(
            "/api/operator/decisions",
            params={
                "decision_type": "readiness_review",
                "target_id": readiness["checked_at"],
            },
        )
        self.assertEqual(target_response.status_code, 200)
        target_filtered = target_response.json()
        self.assertEqual(len(target_filtered), 1)
        self.assertEqual(target_filtered[0]["target_id"], readiness["checked_at"])

        status_response = self.client.get(
            "/api/operator/decisions",
            params={"status": "needs_work"},
        )
        self.assertEqual(status_response.status_code, 200)
        status_filtered = status_response.json()
        self.assertEqual(len(status_filtered), 1)
        self.assertEqual(status_filtered[0]["status"], "needs_work")

        report_response = self.client.get(
            "/api/operator/decisions/report",
            params={"status": "needs_work"},
        )
        self.assertEqual(report_response.status_code, 200)
        report = report_response.json()
        self.assertEqual(report["title"], "Operations Journal Report")
        self.assertTrue(report["filename"].endswith(".md"))
        self.assertEqual(len(report["decisions"]), 1)
        self.assertIn("Keep live guard locked", report["markdown"])
        self.assertIn("## Summary", report["markdown"])

    def test_columnar_cache_status_and_export_endpoints(self):
        db_path = Path(tempfile.gettempdir()) / f"quant_lab_api_columnar_{os.getpid()}.sqlite3"
        duckdb_path = db_path.with_suffix(".duckdb")
        parquet_path = duckdb_path.parent / f"{duckdb_path.stem}_market_candles.parquet"
        for path in (db_path, duckdb_path, parquet_path):
            if path.exists():
                path.unlink()

        store = MarketDataStore(db_path)
        data.set_market_data_store_for_tests(store)
        try:
            store.save_candles(
                source="alpha_vantage",
                symbol="SPY",
                timeframe="day",
                candles=data.generate_sample_us_candles(
                    symbol="SPY",
                    timeframe="day",
                    limit=5,
                ),
            )

            status_response = self.client.get("/api/markets/cache/columnar/status")
            self.assertEqual(status_response.status_code, 200)
            status = status_response.json()
            self.assertTrue(status["enabled"])
            self.assertEqual(status["rows"], 5)
            self.assertEqual(status["sources"], ["alpha_vantage"])
            self.assertEqual(status["symbols"], ["SPY"])

            export_response = self.client.post(
                "/api/markets/cache/columnar/export",
                params={
                    "source": "alpha_vantage",
                    "symbol": "SPY",
                    "timeframe": "day",
                },
            )
            self.assertEqual(export_response.status_code, 200)
            export = export_response.json()
            self.assertEqual(export["rows"], 5)
            self.assertTrue(Path(export["parquet_path"]).exists())
        finally:
            data.set_market_data_store_for_tests(None)
            for path in (db_path, duckdb_path, parquet_path):
                if path.exists():
                    path.unlink()

    def test_alpha_vantage_source_requires_api_key(self):
        response = self.client.post(
            "/api/backtests/run",
            json={
                "symbol": "SPY",
                "timeframe": "day",
                "source": "alpha_vantage",
                "strategy": "sma_crossover",
                "initial_cash": 100_000,
                "fee_bps": 1,
                "slippage_bps": 1,
                "candle_limit": 80,
                "params": {"fast_window": 8, "slow_window": 24},
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("ALPHA_VANTAGE_API_KEY", response.json()["detail"])

    def test_us_stock_sample_backtest_and_paper_session_run(self):
        request_payload = {
            "symbol": "SPY",
            "timeframe": "day",
            "source": "sample_us",
            "strategy": "sma_crossover",
            "initial_cash": 100_000,
            "fee_bps": 1,
            "slippage_bps": 1,
            "candle_limit": 180,
            "params": {"fast_window": 8, "slow_window": 24},
        }

        backtest_response = self.client.post(
            "/api/backtests/run",
            json=request_payload,
        )
        self.assertEqual(backtest_response.status_code, 200)
        backtest = backtest_response.json()
        self.assertEqual(backtest["request"]["source"], "sample_us")
        self.assertEqual(backtest["request"]["symbol"], "SPY")
        self.assertGreater(backtest["metrics"]["final_equity"], 0)
        self.assertGreaterEqual(backtest["metrics"]["trades"], 1)
        self.assertIn("US stock/ETF", backtest["warnings"][0])

        paper_response = self.client.post(
            "/api/paper/sessions",
            json={
                **request_payload,
                "risk_limits": {
                    "max_position_pct": 50,
                    "max_order_notional": 25_000,
                    "max_orders": 20,
                    "max_session_loss_pct": 12,
                    "kill_switch": False,
                },
            },
        )
        self.assertEqual(paper_response.status_code, 200)
        paper = paper_response.json()
        self.assertEqual(paper["request"]["source"], "sample_us")
        self.assertGreaterEqual(paper["summary"]["orders"], 1)

        queue_response = self.client.post(
            f"/api/paper/sessions/{paper['id']}/order-intents",
            json={"max_intents": 2},
        )
        self.assertEqual(queue_response.status_code, 400)
        self.assertIn("paper-only", queue_response.json()["detail"])

        first_trade = paper["trades"][0]
        broker_note_response = self.client.post(
            "/api/execution/broker-intents/evaluate",
            json={
                "adapter_id": "alpaca_us_equity_paper_preview",
                "symbol": paper["request"]["symbol"],
                "side": first_trade["side"],
                "quantity": first_trade["quantity"],
                "order_type": "market",
                "reference_price": first_trade["price"],
                "cash_available": 250_000,
                "current_position_quantity": (
                    first_trade["quantity"] if first_trade["side"] == "sell" else 0
                ),
                "portfolio_equity": 250_000,
                "paper_fee_bps": 1,
                "paper_slippage_bps": 1,
                "paper_session_id": paper["id"],
                "client_order_id": "session-linked-alpaca-preview",
            },
        )
        self.assertEqual(broker_note_response.status_code, 200)
        broker_note_eval = broker_note_response.json()
        self.assertEqual(broker_note_eval["adapter_id"], "alpaca_us_equity_paper_preview")
        self.assertEqual(
            broker_note_eval["paper_fill_estimate"]["status"],
            "estimated_fill",
        )

        order_notes_response = self.client.get(
            f"/api/paper/sessions/{paper['id']}/order-notes",
        )
        self.assertEqual(order_notes_response.status_code, 200)
        order_notes = order_notes_response.json()
        self.assertEqual(len(order_notes), 1)
        self.assertEqual(order_notes[0]["evaluation_id"], broker_note_eval["id"])
        self.assertEqual(order_notes[0]["adapter_id"], "alpaca_us_equity_paper_preview")
        self.assertEqual(order_notes[0]["comparison_status"], "matched_trade")
        self.assertFalse(order_notes[0]["external_submission_attempted"])
        self.assertIsNotNone(order_notes[0]["simulated_fill_price"])

        drift_response = self.client.get(
            "/api/paper/order-notes/analytics",
            params={
                "adapter_id": "alpaca_us_equity_paper_preview",
                "symbol": paper["request"]["symbol"],
                "limit": 20,
            },
        )
        self.assertEqual(drift_response.status_code, 200)
        drift = drift_response.json()
        self.assertEqual(drift["notes_considered"], 1)
        self.assertEqual(drift["matched_trade_count"], 1)
        self.assertEqual(drift["external_submission_attempted_count"], 0)
        self.assertEqual(len(drift["rows"]), 1)
        self.assertEqual(drift["rows"][0]["symbol"], paper["request"]["symbol"])
        self.assertEqual(drift["rows"][0]["matched_trade_count"], 1)
        self.assertEqual(drift["rows"][0]["latest_evaluation_id"], broker_note_eval["id"])
        self.assertIsNotNone(drift["rows"][0]["avg_abs_price_delta_pct"])

        gate_watch_response = self.client.get(
            "/api/paper/order-notes/quality-gate",
            params={
                "adapter_id": "alpaca_us_equity_paper_preview",
                "symbol": paper["request"]["symbol"],
                "limit": 20,
            },
        )
        self.assertEqual(gate_watch_response.status_code, 200)
        gate_watch = gate_watch_response.json()
        self.assertEqual(gate_watch["status"], "watch")
        self.assertEqual(gate_watch["rows"][0]["status"], "watch")
        self.assertIn("at least 3", gate_watch["rows"][0]["reasons"][0])

        gate_ready_response = self.client.get(
            "/api/paper/order-notes/quality-gate",
            params={
                "adapter_id": "alpaca_us_equity_paper_preview",
                "symbol": paper["request"]["symbol"],
                "limit": 20,
                "min_notes": 1,
                "max_avg_abs_price_delta_pct": 100,
                "max_worst_abs_price_delta_pct": 100,
            },
        )
        self.assertEqual(gate_ready_response.status_code, 200)
        gate_ready = gate_ready_response.json()
        self.assertEqual(gate_ready["status"], "ready")
        self.assertEqual(gate_ready["rows"][0]["status"], "ready")
        self.assertEqual(gate_ready["analytics"]["notes_considered"], 1)

    def test_portfolio_research_runs_multiple_sample_us_symbols(self):
        response = self.client.post(
            "/api/research/portfolio",
            json={
                "symbols": ["SPY", "QQQ", "AAPL"],
                "timeframe": "day",
                "source": "sample_us",
                "strategy": "sma_crossover",
                "initial_cash": 120_000,
                "fee_bps": 1,
                "slippage_bps": 1,
                "candle_limit": 180,
                "weights": {"SPY": 50, "QQQ": 30, "AAPL": 20},
                "rebalance_frequency": "monthly",
                "params": {"fast_window": 8, "slow_window": 24},
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["request"]["symbols"], ["SPY", "QQQ", "AAPL"])
        self.assertEqual(payload["request"]["weights"], {"SPY": 50.0, "QQQ": 30.0, "AAPL": 20.0})
        self.assertEqual(payload["request"]["rebalance_frequency"], "monthly")
        self.assertEqual(len(payload["allocations"]), 3)
        self.assertEqual(len(payload["equity_curve"]), 180)
        self.assertGreater(payload["metrics"]["final_equity"], 0)
        self.assertGreater(payload["metrics"]["rebalances"], 0)
        self.assertIn(payload["metrics"]["best_symbol"], ["SPY", "QQQ", "AAPL"])
        self.assertIn(payload["metrics"]["worst_symbol"], ["SPY", "QQQ", "AAPL"])
        self.assertGreaterEqual(payload["metrics"]["trades"], 1)
        spy = next(item for item in payload["allocations"] if item["symbol"] == "SPY")
        self.assertEqual(spy["target_weight_pct"], 50.0)
        self.assertGreater(spy["final_weight_pct"], 0)
        self.assertIn("Portfolio research", payload["warnings"][-1])

    def test_portfolio_presets_and_saved_scenarios_round_trip(self):
        presets_response = self.client.get("/api/research/portfolio/presets")
        self.assertEqual(presets_response.status_code, 200)
        presets = presets_response.json()
        preset_ids = [preset["id"] for preset in presets]
        self.assertIn("crypto-majors-spot", preset_ids)
        self.assertIn("us-core-balanced", preset_ids)
        self.assertIn("us-etf-rsi-reversion", preset_ids)

        create_response = self.client.post(
            "/api/research/portfolio/scenarios",
            json={
                "name": "Core ETF monthly",
                "request": {
                    "symbols": ["SPY", "QQQ", "AAPL"],
                    "timeframe": "day",
                    "source": "sample_us",
                    "strategy": "sma_crossover",
                    "initial_cash": 120_000,
                    "fee_bps": 1,
                    "slippage_bps": 1,
                    "candle_limit": 180,
                    "weights": {"SPY": 50, "QQQ": 30, "AAPL": 20},
                    "rebalance_frequency": "monthly",
                    "params": {"fast_window": 8, "slow_window": 24},
                },
            },
        )
        self.assertEqual(create_response.status_code, 200)
        created = create_response.json()
        self.assertEqual(created["name"], "Core ETF monthly")
        self.assertIn("id", created)
        self.assertEqual(created["request"]["weights"]["SPY"], 50.0)
        self.assertEqual(created["request"]["rebalance_frequency"], "monthly")

        list_response = self.client.get("/api/research/portfolio/scenarios")
        self.assertEqual(list_response.status_code, 200)
        scenarios = list_response.json()
        self.assertEqual(scenarios[0]["id"], created["id"])

        get_response = self.client.get(
            f"/api/research/portfolio/scenarios/{created['id']}",
        )
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.json()["request"]["symbols"], ["SPY", "QQQ", "AAPL"])

        scan_response = self.client.post(
            f"/api/research/portfolio/scenarios/{created['id']}/scan",
        )
        self.assertEqual(scan_response.status_code, 200)
        scan = scan_response.json()
        self.assertEqual(scan["scenario_id"], created["id"])
        self.assertEqual(scan["scenario_name"], "Core ETF monthly")
        self.assertGreater(scan["result"]["metrics"]["final_equity"], 0)
        self.assertEqual(scan["result"]["request"]["symbols"], ["SPY", "QQQ", "AAPL"])

        scans_response = self.client.get("/api/research/portfolio/scans")
        self.assertEqual(scans_response.status_code, 200)
        scans = scans_response.json()
        self.assertEqual(scans[0]["id"], scan["id"])

        get_scan_response = self.client.get(
            f"/api/research/portfolio/scans/{scan['id']}",
        )
        self.assertEqual(get_scan_response.status_code, 200)
        self.assertEqual(get_scan_response.json()["result"]["metrics"], scan["result"]["metrics"])

        watch_response = self.client.post(
            "/api/research/portfolio/watchlist",
            json={
                "scenario_id": created["id"],
                "interval_minutes": 60,
                "active": True,
                "alert_thresholds": {
                    "max_drawdown_pct": 0.01,
                    "min_total_return_pct": 1_000,
                    "min_average_edge_pct": 1_000,
                    "max_return_drift_pct": 0.01,
                },
            },
        )
        self.assertEqual(watch_response.status_code, 200)
        watch_item = watch_response.json()
        self.assertEqual(watch_item["scenario_id"], created["id"])
        self.assertTrue(watch_item["active"])
        self.assertEqual(watch_item["alert_thresholds"]["max_drawdown_pct"], 0.01)

        due_response = self.client.post("/api/research/portfolio/watchlist/run-due")
        self.assertEqual(due_response.status_code, 200)
        due = due_response.json()
        self.assertEqual(due["due"], 1)
        self.assertEqual(len(due["scanned"]), 1)
        self.assertEqual(len(due["alerts"]), 3)
        self.assertEqual(
            {alert["rule"] for alert in due["alerts"]},
            {"max_drawdown_pct", "min_total_return_pct", "min_average_edge_pct"},
        )
        self.assertEqual(due["errors"], [])

        watchlist_response = self.client.get("/api/research/portfolio/watchlist")
        self.assertEqual(watchlist_response.status_code, 200)
        watchlist = watchlist_response.json()
        self.assertEqual(watchlist[0]["last_scan_id"], due["scanned"][0]["id"])
        self.assertEqual(watchlist[0]["last_alerts"], due["alerts"])
        self.assertIsNotNone(watchlist[0]["last_run_at"])

        paper_watch_response = self.client.post(
            "/api/paper/watchlist",
            json={
                "scenario_id": created["id"],
                "interval_minutes": 120,
                "active": True,
                "risk_limits": {
                    "max_position_pct": 50,
                    "max_order_notional": 50_000,
                    "max_orders": 20,
                    "max_session_loss_pct": 12,
                    "kill_switch": False,
                },
            },
        )
        self.assertEqual(paper_watch_response.status_code, 200)
        paper_watch = paper_watch_response.json()
        self.assertEqual(paper_watch["scenario_id"], created["id"])
        self.assertEqual(paper_watch["risk_limits"]["max_position_pct"], 50)
        self.assertTrue(paper_watch["active"])

        paper_due_response = self.client.post("/api/paper/watchlist/run-due")
        self.assertEqual(paper_due_response.status_code, 200)
        paper_due = paper_due_response.json()
        self.assertEqual(paper_due["due"], 1)
        self.assertEqual(paper_due["errors"], [])
        self.assertEqual(len(paper_due["runs"]), 1)
        paper_run = paper_due["runs"][0]
        self.assertEqual(len(paper_run["sessions"]), 3)
        self.assertEqual(paper_run["sessions"][0]["request"]["source"], "sample_us")
        self.assertEqual(paper_run["sessions"][0]["request"]["initial_cash"], 60_000)
        self.assertGreater(paper_run["sessions"][0]["summary"]["final_equity"], 0)

        paper_watchlist_response = self.client.get("/api/paper/watchlist")
        self.assertEqual(paper_watchlist_response.status_code, 200)
        paper_watchlist = paper_watchlist_response.json()
        self.assertEqual(paper_watchlist[0]["last_session_ids"], [
            session["id"] for session in paper_run["sessions"]
        ])

        stored_session_response = self.client.get(
            f"/api/paper/sessions/{paper_run['sessions'][0]['id']}",
        )
        self.assertEqual(stored_session_response.status_code, 200)
        self.assertEqual(stored_session_response.json()["request"]["symbol"], "SPY")

        alerts_response = self.client.get("/api/alerts/review")
        self.assertEqual(alerts_response.status_code, 200)
        alerts = alerts_response.json()
        alert_sources = {item["source"] for item in alerts["items"]}
        self.assertIn("portfolio_scan", alert_sources)
        self.assertIn("paper_session_risk", alert_sources)
        self.assertGreaterEqual(alerts["counts"]["warning"], 1)

        severity_filter_response = self.client.get(
            "/api/alerts/review",
            params={"severity": "warning"},
        )
        self.assertEqual(severity_filter_response.status_code, 200)
        severity_filtered = severity_filter_response.json()
        self.assertGreaterEqual(len(severity_filtered["items"]), 1)
        self.assertTrue(
            all(item["level"] == "warning" for item in severity_filtered["items"])
        )

        source_filter_response = self.client.get(
            "/api/alerts/review",
            params={"source": "paper_session_risk"},
        )
        self.assertEqual(source_filter_response.status_code, 200)
        source_filtered = source_filter_response.json()
        self.assertGreaterEqual(len(source_filtered["items"]), 1)
        self.assertTrue(
            all(item["source"] == "paper_session_risk" for item in source_filtered["items"])
        )

        scenario_filter_response = self.client.get(
            "/api/alerts/review",
            params={"scenario": "core etf"},
        )
        self.assertEqual(scenario_filter_response.status_code, 200)
        scenario_filtered = scenario_filter_response.json()
        self.assertGreaterEqual(len(scenario_filtered["items"]), 1)
        self.assertTrue(
            all(item["scenario_name"] == "Core ETF monthly" for item in scenario_filtered["items"])
        )

        invalid_filter_response = self.client.get(
            "/api/alerts/review",
            params={"severity": "critical"},
        )
        self.assertEqual(invalid_filter_response.status_code, 400)

        acknowledged_alert_id = alerts["items"][0]["id"]

        ack_response = self.client.post(
            f"/api/alerts/review/{acknowledged_alert_id}/acknowledge",
            json={"status": "acknowledged", "note": "Reviewed in API test."},
        )
        self.assertEqual(ack_response.status_code, 200)
        acknowledgement = ack_response.json()
        self.assertEqual(acknowledgement["alert_id"], acknowledged_alert_id)
        self.assertEqual(acknowledgement["status"], "acknowledged")

        active_alerts_response = self.client.get("/api/alerts/review")
        self.assertEqual(active_alerts_response.status_code, 200)
        active_alert_ids = {item["id"] for item in active_alerts_response.json()["items"]}
        self.assertNotIn(acknowledged_alert_id, active_alert_ids)

        all_alerts_response = self.client.get("/api/alerts/review?include_acknowledged=true")
        self.assertEqual(all_alerts_response.status_code, 200)
        acknowledged_items = [
            item
            for item in all_alerts_response.json()["items"]
            if item["id"] == acknowledged_alert_id
        ]
        self.assertEqual(acknowledged_items[0]["acknowledgement_status"], "acknowledged")

        stock_promote_response = self.client.post(
            f"/api/paper/watchlist/{paper_watch['id']}/promote-order-intents",
            json={
                "max_sessions": 3,
                "max_intents_per_session": 2,
                "rules": {
                    "min_total_return_pct": -100,
                    "max_drawdown_pct": 100,
                    "min_orders": 1,
                },
            },
        )
        self.assertEqual(stock_promote_response.status_code, 200)
        stock_promoted = stock_promote_response.json()
        self.assertEqual(stock_promoted["created"], 0)
        self.assertEqual(stock_promoted["queued"], [])
        self.assertEqual(stock_promoted["skipped_sessions"], [])
        self.assertEqual(len(stock_promoted["paper_only_handoffs"]), 3)
        first_handoff = stock_promoted["paper_only_handoffs"][0]
        self.assertEqual(first_handoff["route"]["status"], "paper_only_review")
        self.assertEqual(first_handoff["route"]["adapter"]["asset_class"], "stock_etf")
        self.assertFalse(first_handoff["route"]["adapter"]["live_order_supported"])
        self.assertEqual(
            first_handoff["route"]["adapter"]["broker_contract"]["id"],
            "mock_us_equity_paper",
        )
        self.assertEqual(
            first_handoff["route"]["adapter"]["broker_contract"]["submission_mode"],
            "paper_record_only",
        )
        self.assertIsNotNone(first_handoff["decision_id"])
        linked_session_response = self.client.get(
            f"/api/paper/sessions/{first_handoff['session_id']}",
        )
        self.assertEqual(linked_session_response.status_code, 200)
        linked_session = linked_session_response.json()
        matching_trade = linked_session["trades"][-1]
        broker_evaluation_response = self.client.post(
            "/api/execution/broker-intents/evaluate",
            json={
                "adapter_id": "alpaca_us_equity_paper_preview",
                "symbol": first_handoff["symbol"],
                "side": matching_trade["side"],
                "quantity": matching_trade["quantity"],
                "order_type": "market",
                "reference_price": matching_trade["price"],
                "cash_available": 1_000_000,
                "current_position_quantity": (
                    matching_trade["quantity"] if matching_trade["side"] == "sell" else 0
                ),
                "portfolio_equity": 1_000_000,
                "paper_fee_bps": 0,
                "paper_slippage_bps": 0,
                "paper_session_id": first_handoff["session_id"],
            },
        )
        self.assertEqual(broker_evaluation_response.status_code, 200)
        broker_evaluation = broker_evaluation_response.json()
        self.assertEqual(
            broker_evaluation["paper_fill_estimate"]["status"],
            "estimated_fill",
        )
        order_notes_response = self.client.get(
            f"/api/paper/sessions/{first_handoff['session_id']}/order-notes",
        )
        self.assertEqual(order_notes_response.status_code, 200)
        order_notes = order_notes_response.json()
        self.assertEqual(len(order_notes), 1)
        self.assertEqual(order_notes[0]["evaluation_id"], broker_evaluation["id"])
        self.assertEqual(order_notes[0]["comparison_status"], "matched_trade")

        journal_response = self.client.get(
            "/api/operator/decisions",
            params={
                "decision_type": "dry_run_promotion",
                "target_id": first_handoff["id"],
            },
        )
        self.assertEqual(journal_response.status_code, 200)
        journal = journal_response.json()
        self.assertEqual(journal[0]["context"]["route_status"], "paper_only_review")
        self.assertEqual(journal[0]["context"]["symbol"], first_handoff["symbol"])

        blocked_handoff_approval_response = self.client.post(
            "/api/operator/decisions",
            json={
                "decision_type": "dry_run_promotion",
                "target_id": first_handoff["id"],
                "status": "approved",
                "note": "Attempt approval before enough fill evidence exists.",
                "context": {
                    **journal[0]["context"],
                    "review_source": "api_test",
                },
            },
        )
        self.assertEqual(blocked_handoff_approval_response.status_code, 400)
        self.assertIn(
            "quality gate ready",
            blocked_handoff_approval_response.json()["detail"],
        )

        for index in range(2):
            extra_broker_evaluation_response = self.client.post(
                "/api/execution/broker-intents/evaluate",
                json={
                    "adapter_id": "alpaca_us_equity_paper_preview",
                    "symbol": first_handoff["symbol"],
                    "side": matching_trade["side"],
                    "quantity": matching_trade["quantity"],
                    "order_type": "market",
                    "reference_price": matching_trade["price"],
                    "cash_available": 1_000_000,
                    "current_position_quantity": (
                        matching_trade["quantity"] if matching_trade["side"] == "sell" else 0
                    ),
                    "portfolio_equity": 1_000_000,
                    "paper_fee_bps": 0,
                    "paper_slippage_bps": 0,
                    "paper_session_id": first_handoff["session_id"],
                    "client_order_id": f"quality-gate-ready-{index}",
                },
            )
            self.assertEqual(extra_broker_evaluation_response.status_code, 200)

        approved_handoff_response = self.client.post(
            "/api/operator/decisions",
            json={
                "decision_type": "dry_run_promotion",
                "target_id": first_handoff["id"],
                "status": "approved",
                "note": "Paper fill quality gate is ready for handoff approval.",
                "context": {
                    **journal[0]["context"],
                    "review_source": "api_test",
                },
            },
        )
        self.assertEqual(approved_handoff_response.status_code, 200)
        approved_handoff = approved_handoff_response.json()
        self.assertEqual(
            approved_handoff["context"]["paper_fill_quality_gate_status"],
            "ready",
        )
        self.assertGreaterEqual(
            approved_handoff["context"]["paper_fill_quality_gate_rows"][0]["note_count"],
            3,
        )

        expansion_response = self.client.get(
            "/api/paper/stock-etf/broker-expansion-readiness",
        )
        self.assertEqual(expansion_response.status_code, 200)
        expansion = expansion_response.json()
        self.assertEqual(expansion["status"], "ready")
        self.assertGreaterEqual(expansion["counts"]["approved_ready"], 1)
        self.assertTrue(
            any(
                candidate["symbol"] == first_handoff["symbol"]
                and candidate["approved_for_broker_expansion"]
                for candidate in expansion["candidates"]
            )
        )

        expansion_report_response = self.client.get(
            "/api/paper/stock-etf/broker-expansion-readiness/report",
        )
        self.assertEqual(expansion_report_response.status_code, 200)
        expansion_report = expansion_report_response.json()
        self.assertEqual(
            expansion_report["title"],
            "Stock/ETF Broker Expansion Readiness",
        )
        self.assertIn(first_handoff["symbol"], expansion_report["markdown"])
        self.assertIn("Approved-ready candidates", expansion_report["markdown"])

        package_response = self.client.get(
            f"/api/paper/stock-etf/broker-expansion-readiness/package/{approved_handoff['id']}",
        )
        self.assertEqual(package_response.status_code, 200)
        package = package_response.json()
        self.assertEqual(package["candidate"]["symbol"], first_handoff["symbol"])
        self.assertTrue(package["candidate"]["approved_for_broker_expansion"])
        self.assertEqual(package["quality_gate"]["status"], "ready")
        self.assertGreaterEqual(len(package["order_payloads"]), 1)
        self.assertFalse(package["order_payloads"][0]["external_submission_attempted"])
        self.assertEqual(package["order_payloads"][0]["payload"]["symbol"], first_handoff["symbol"])
        self.assertIn("Alpaca-Style Paper Order Payloads", package["markdown"])
        self.assertIn("Do not submit these payloads", package["markdown"])

        preflight_response = self.client.get(
            f"/api/paper/stock-etf/broker-expansion-readiness/package/{approved_handoff['id']}/preflight",
        )
        self.assertEqual(preflight_response.status_code, 200)
        preflight = preflight_response.json()
        self.assertEqual(preflight["status"], "pass")
        self.assertEqual(preflight["package"]["candidate"]["symbol"], first_handoff["symbol"])
        self.assertIn("Preflight Checks", preflight["markdown"])
        self.assertEqual(
            {check["status"] for check in preflight["checks"]},
            {"pass"},
        )

        rehearsal_response = self.client.get(
            f"/api/paper/stock-etf/broker-expansion-readiness/package/{approved_handoff['id']}/rehearsal",
        )
        self.assertEqual(rehearsal_response.status_code, 200)
        rehearsal = rehearsal_response.json()
        self.assertEqual(rehearsal["status"], "pass")
        self.assertGreaterEqual(rehearsal["accepted_orders"], 1)
        self.assertEqual(rehearsal["rejected_orders"], 0)
        self.assertFalse(rehearsal["orders"][0]["external_submission_attempted"])
        self.assertIn("This rehearsal is local and paper-only", rehearsal["markdown"])

        route_filtered_response = self.client.get(
            "/api/operator/decisions",
            params={
                "decision_type": "dry_run_promotion",
                "route_status": "paper_only_review",
            },
        )
        self.assertEqual(route_filtered_response.status_code, 200)
        route_filtered = route_filtered_response.json()
        self.assertTrue(
            any(decision["target_id"] == first_handoff["id"] for decision in route_filtered)
        )
        self.assertTrue(
            all(
                decision["context"].get("route_status") == "paper_only_review"
                for decision in route_filtered
            )
        )

        journal_report_response = self.client.get(
            "/api/operator/decisions/report",
            params={
                "decision_type": "dry_run_promotion",
                "route_status": "paper_only_review",
            },
        )
        self.assertEqual(journal_report_response.status_code, 200)
        journal_report = journal_report_response.json()
        self.assertIn("- Route status filter: paper_only_review", journal_report["markdown"])
        self.assertIn(first_handoff["id"], journal_report["markdown"])

        handoff_report_response = self.client.get(
            "/api/research/strategy-health/handoff-report?limit=10&route_status=paper_only_review"
        )
        self.assertEqual(handoff_report_response.status_code, 200)
        self.assertIn(
            "## Paper-Only Strategy Handoffs",
            handoff_report_response.json()["markdown"],
        )
        self.assertIn(
            "- Route status filter: paper_only_review",
            handoff_report_response.json()["markdown"],
        )
        self.assertIn(first_handoff["id"], handoff_report_response.json()["markdown"])
        self.assertIn("#### Broker Intent Evaluations", handoff_report_response.json()["markdown"])
        self.assertIn(broker_evaluation["id"], handoff_report_response.json()["markdown"])
        self.assertIn("Paper fill status: estimated fill", handoff_report_response.json()["markdown"])
        self.assertIn("External submission attempted: False", handoff_report_response.json()["markdown"])
        self.assertIn("#### Paper Fill Order Notes", handoff_report_response.json()["markdown"])
        self.assertIn("Comparison status: matched trade", handoff_report_response.json()["markdown"])

        delete_response = self.client.delete(
            f"/api/research/portfolio/scenarios/{created['id']}",
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(delete_response.json()["status"], "deleted")

        empty_watchlist = self.client.get("/api/research/portfolio/watchlist")
        self.assertEqual(empty_watchlist.status_code, 200)
        self.assertEqual(empty_watchlist.json(), [])

        empty_paper_watchlist = self.client.get("/api/paper/watchlist")
        self.assertEqual(empty_paper_watchlist.status_code, 200)
        self.assertEqual(empty_paper_watchlist.json(), [])

        missing_response = self.client.get(
            f"/api/research/portfolio/scenarios/{created['id']}",
        )
        self.assertEqual(missing_response.status_code, 404)

    def test_crypto_paper_watchlist_promotes_to_dry_run_order_intents(self):
        create_response = self.client.post(
            "/api/research/portfolio/scenarios",
            json={
                "name": "Crypto promotion",
                "request": {
                    "symbols": ["KRW-BTC", "KRW-ETH", "KRW-SOL"],
                    "timeframe": "day",
                    "source": "sample",
                    "strategy": "sma_crossover",
                    "initial_cash": 1_000_000,
                    "fee_bps": 5,
                    "slippage_bps": 2,
                    "candle_limit": 180,
                    "weights": {"KRW-BTC": 50, "KRW-ETH": 30, "KRW-SOL": 20},
                    "rebalance_frequency": "monthly",
                    "params": {"fast_window": 10, "slow_window": 30},
                },
            },
        )
        self.assertEqual(create_response.status_code, 200)
        scenario = create_response.json()

        watch_response = self.client.post(
            "/api/paper/watchlist",
            json={
                "scenario_id": scenario["id"],
                "interval_minutes": 120,
                "active": True,
                "risk_limits": {
                    "max_position_pct": 50,
                    "max_order_notional": 500_000,
                    "max_orders": 20,
                    "max_session_loss_pct": 12,
                    "kill_switch": False,
                },
            },
        )
        self.assertEqual(watch_response.status_code, 200)
        watch_item = watch_response.json()

        run_response = self.client.post(f"/api/paper/watchlist/{watch_item['id']}/run")
        self.assertEqual(run_response.status_code, 200)
        run = run_response.json()
        self.assertEqual(len(run["sessions"]), 3)
        self.assertTrue(
            all(session["request"]["symbol"].startswith("KRW-") for session in run["sessions"])
        )

        promote_response = self.client.post(
            f"/api/paper/watchlist/{watch_item['id']}/promote-order-intents",
            json={
                "max_sessions": 3,
                "max_intents_per_session": 2,
                "rules": {
                    "min_total_return_pct": -100,
                    "max_drawdown_pct": 100,
                    "min_orders": 1,
                },
            },
        )
        self.assertEqual(promote_response.status_code, 200)
        promoted = promote_response.json()
        self.assertGreaterEqual(promoted["created"], 1)
        self.assertEqual(promoted["errors"], [])
        self.assertGreaterEqual(len(promoted["eligible_sessions"]), 1)
        queued_records = [
            record
            for queue_response in promoted["queued"]
            for record in queue_response["records"]
        ]
        self.assertEqual(len(queued_records), promoted["created"])
        self.assertTrue(
            all(record["status"] == "dry_run" for record in queued_records)
        )
        self.assertTrue(
            all(record["market"].startswith("KRW-") for record in queued_records)
        )
        promotion_context = queued_records[0]["response_payload"]["context"]
        self.assertEqual(
            promotion_context["source"],
            "portfolio_paper_watchlist_promotion",
        )
        self.assertEqual(promotion_context["scenario_name"], "Crypto promotion")
        self.assertEqual(
            promotion_context["promotion_rules"]["max_drawdown_pct"],
            100,
        )

        runbook_response = self.client.get(
            f"/api/execution/order-audits/{queued_records[0]['id']}/runbook",
        )
        self.assertEqual(runbook_response.status_code, 200)
        runbook = runbook_response.json()
        self.assertIn("Crypto promotion", runbook["markdown"])
        self.assertIn("## Promotion Rules", runbook["markdown"])

        decision_response = self.client.post(
            "/api/operator/decisions",
            json={
                "decision_type": "dry_run_approval",
                "target_id": queued_records[0]["id"],
                "status": "approved",
                "note": "Promotion trace approved for live handoff.",
                "context": {
                    "scenario_name": "Crypto promotion",
                    "precheck_status": "watch",
                },
            },
        )
        self.assertEqual(decision_response.status_code, 200)
        decision = decision_response.json()
        approval_response = self.client.post(
            f"/api/execution/order-audits/{queued_records[0]['id']}/approve",
            json={"live_confirmation": True},
        )
        self.assertEqual(approval_response.status_code, 200)
        approval_attempt = approval_response.json()
        self.assertEqual(approval_attempt["status"], "blocked")

        trace_response = self.client.get("/api/research/strategy-health/traces")
        self.assertEqual(trace_response.status_code, 200)
        trace_payload = trace_response.json()
        self.assertGreaterEqual(trace_payload["counts"]["traces"], 1)
        trace = next(
            item
            for item in trace_payload["traces"]
            if item["id"] == queued_records[0]["id"]
        )
        self.assertEqual(trace["scenario_name"], "Crypto promotion")
        self.assertEqual(trace["watchlist_id"], watch_item["id"])
        self.assertEqual(trace["promotion_rules"]["max_drawdown_pct"], 100)
        self.assertEqual(trace["dry_run_audit"]["id"], queued_records[0]["id"])
        self.assertEqual(trace["approval_decisions"][0]["status"], "approved")
        self.assertEqual(trace["latest_approval_attempt"]["id"], approval_attempt["id"])
        self.assertEqual(trace["closeout_status"], "blocked")
        milestone_ids = {milestone["id"] for milestone in trace["milestones"]}
        self.assertIn("promotion_rules", milestone_ids)
        self.assertIn("paper_trade", milestone_ids)
        self.assertIn("approval_decision", milestone_ids)
        self.assertIn("closeout_outcome", milestone_ids)

        handoff_response = self.client.get(
            "/api/research/strategy-health/handoff-report?limit=20"
        )
        self.assertEqual(handoff_response.status_code, 200)
        handoff = handoff_response.json()
        self.assertEqual(handoff["title"], "Strategy Health Handoff Report")
        self.assertTrue(handoff["filename"].endswith(".md"))
        self.assertEqual(handoff["closeout_report"]["title"], "Live window closeout report")
        self.assertIn("## Strategy Trace Summary", handoff["markdown"])
        self.assertIn("## Trace Rows", handoff["markdown"])
        self.assertIn("Crypto promotion", handoff["markdown"])
        self.assertIn(queued_records[0]["id"], handoff["markdown"])
        self.assertIn(decision["id"], handoff["markdown"])
        self.assertIn(approval_attempt["id"], handoff["markdown"])
        self.assertIn("## Closeout Snapshot", handoff["markdown"])
        self.assertIn(
            f"/api/execution/order-audits/{queued_records[0]['id']}/runbook",
            handoff["markdown"],
        )
        self.assertIn(
            f"- Trace rows included: {handoff['traces']['counts']['traces']}",
            handoff["markdown"],
        )

        drill_symbol = queued_records[0]["market"]
        drill_response = self.client.get(
            "/api/research/crypto-live-beta-drill/report",
            params={"symbol": drill_symbol, "limit": 5},
        )
        self.assertEqual(drill_response.status_code, 200)
        drill = drill_response.json()
        self.assertEqual(drill["title"], "Crypto Live Beta Drill Report")
        self.assertEqual(drill["symbol"], drill_symbol)
        self.assertTrue(drill["filename"].endswith(".md"))
        self.assertGreaterEqual(len(drill["paper_sessions"]), 1)
        self.assertGreaterEqual(len(drill["dry_run_audits"]), 1)
        self.assertIn(queued_records[0]["id"], drill["prechecks"])
        self.assertGreaterEqual(len(drill["runbooks"]), 1)
        self.assertTrue(drill["cutover_simulation"]["no_order_submission"])
        self.assertEqual(drill["closeout_report"]["title"], "Live window closeout report")
        self.assertIn("## Safety Boundary", drill["markdown"])
        self.assertIn("## Dry-Run Audits And Prechecks", drill["markdown"])
        self.assertIn("## Cutover Simulation", drill["markdown"])
        self.assertIn(queued_records[0]["id"], drill["markdown"])

        invalid_drill_response = self.client.get(
            "/api/research/crypto-live-beta-drill/report",
            params={"symbol": "SPY"},
        )
        self.assertEqual(invalid_drill_response.status_code, 400)

        duplicate_response = self.client.post(
            f"/api/paper/watchlist/{watch_item['id']}/promote-order-intents",
            json={
                "max_sessions": 3,
                "max_intents_per_session": 2,
                "rules": {
                    "min_total_return_pct": -100,
                    "max_drawdown_pct": 100,
                    "min_orders": 1,
                },
            },
        )
        self.assertEqual(duplicate_response.status_code, 200)
        duplicate = duplicate_response.json()
        self.assertEqual(duplicate["created"], 0)
        self.assertGreaterEqual(duplicate["skipped_existing"], promoted["created"])

    def test_paper_session_endpoint_runs_with_guardrails(self):
        response = self.client.post(
            "/api/paper/sessions",
            json={
                "symbol": "KRW-BTC",
                "timeframe": "day",
                "source": "sample",
                "strategy": "sma_crossover",
                "initial_cash": 1_000_000,
                "fee_bps": 5,
                "slippage_bps": 2,
                "candle_limit": 180,
                "params": {"fast_window": 10, "slow_window": 30},
                "risk_limits": {
                    "max_position_pct": 40,
                    "max_order_notional": 500_000,
                    "max_orders": 20,
                    "max_session_loss_pct": 12,
                    "kill_switch": False,
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn(payload["summary"]["status"], ["completed", "halted"])
        self.assertLessEqual(payload["summary"]["open_position_pct"], 41)
        self.assertGreaterEqual(payload["summary"]["orders"], 1)

        get_response = self.client.get(f"/api/paper/sessions/{payload['id']}")
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.json()["id"], payload["id"])

    def test_paper_session_can_queue_dry_run_order_intents(self):
        create_response = self.client.post(
            "/api/paper/sessions",
            json={
                "symbol": "KRW-BTC",
                "timeframe": "day",
                "source": "sample",
                "strategy": "sma_crossover",
                "initial_cash": 1_000_000,
                "fee_bps": 5,
                "slippage_bps": 2,
                "candle_limit": 180,
                "params": {"fast_window": 10, "slow_window": 30},
                "risk_limits": {
                    "max_position_pct": 50,
                    "max_order_notional": 500_000,
                    "max_orders": 20,
                    "max_session_loss_pct": 12,
                    "kill_switch": False,
                },
            },
        )

        self.assertEqual(create_response.status_code, 200)
        session = create_response.json()
        queue_response = self.client.post(
            f"/api/paper/sessions/{session['id']}/order-intents",
            json={"max_intents": 2},
        )

        self.assertEqual(queue_response.status_code, 200)
        queued = queue_response.json()
        self.assertEqual(queued["session_id"], session["id"])
        self.assertEqual(queued["source"], "paper_session")
        self.assertGreaterEqual(queued["created"], 1)
        self.assertLessEqual(queued["created"], 2)
        self.assertEqual(queued["skipped_existing"], 0)
        self.assertEqual(len(queued["records"]), queued["created"])
        first = queued["records"][0]
        self.assertEqual(first["status"], "dry_run")
        self.assertEqual(first["exchange"], "upbit")
        self.assertEqual(first["market"], "KRW-BTC")
        self.assertIn(first["side"], ["bid", "ask"])
        self.assertIn("identifier", first["request_payload"])
        self.assertTrue(first["response_payload"]["dry_run"])

        precheck_response = self.client.get(
            f"/api/execution/order-audits/{first['id']}/precheck",
        )
        self.assertEqual(precheck_response.status_code, 200)
        precheck = precheck_response.json()
        self.assertEqual(precheck["record_id"], first["id"])
        self.assertEqual(precheck["market"], "KRW-BTC")
        self.assertIn("checked_at", precheck)
        self.assertIn("order_info_checked_at", precheck)
        self.assertEqual(precheck["order_info_source"], "local_defaults")
        self.assertGreaterEqual(precheck["order_info_age_seconds"], 0)
        self.assertEqual(precheck["status"], "warn")
        self.assertFalse(precheck["credential_ready"])
        self.assertGreater(precheck["estimated_notional"], 5_000)
        self.assertIn(
            "private_balances",
            [item["name"] for item in precheck["checks"]],
        )
        self.assertIn(
            "post_order_exposure",
            [item["name"] for item in precheck["checks"]],
        )

        decision_response = self.client.post(
            "/api/operator/decisions",
            json={
                "decision_type": "dry_run_approval",
                "target_id": first["id"],
                "status": "approved",
                "note": "Ready after manual order review.",
                "context": {
                    "market": first["market"],
                    "precheck_status": precheck["status"],
                },
            },
        )
        self.assertEqual(decision_response.status_code, 200)

        runbook_response = self.client.get(
            f"/api/execution/order-audits/{first['id']}/runbook",
        )
        self.assertEqual(runbook_response.status_code, 200)
        runbook = runbook_response.json()
        self.assertEqual(runbook["record_id"], first["id"])
        self.assertEqual(runbook["audit"]["id"], first["id"])
        self.assertEqual(runbook["precheck"]["record_id"], first["id"])
        self.assertIn("Dry-run approval runbook", runbook["title"])
        self.assertIn("## Pre-Approval Checks", runbook["markdown"])
        self.assertIn("## Operator Decisions", runbook["markdown"])
        self.assertIn("Ready after manual order review.", runbook["markdown"])
        self.assertIn("## Approval Procedure", runbook["markdown"])
        self.assertTrue(runbook["filename"].endswith(".md"))

        duplicate_response = self.client.post(
            f"/api/paper/sessions/{session['id']}/order-intents",
            json={"max_intents": 2},
        )
        self.assertEqual(duplicate_response.status_code, 200)
        duplicate = duplicate_response.json()
        self.assertEqual(duplicate["created"], 0)
        self.assertEqual(duplicate["skipped_existing"], queued["created"])

        approval_response = self.client.post(
            f"/api/execution/order-audits/{first['id']}/approve",
            json={"live_confirmation": True},
        )
        self.assertEqual(approval_response.status_code, 200)
        approval = approval_response.json()
        self.assertEqual(approval["status"], "blocked")
        self.assertIn("disabled", approval["reason"])
        self.assertEqual(
            approval["response_payload"]["approved_from_record_id"],
            first["id"],
        )
        self.assertEqual(approval["response_payload"]["precheck"]["status"], "warn")
        self.assertTrue(approval["request_payload"]["identifier"].startswith("approved-"))

        monitor_response = self.client.get("/api/execution/post-cutover-monitor")
        self.assertEqual(monitor_response.status_code, 200)
        monitor = monitor_response.json()
        self.assertEqual(monitor["status"], "attention")
        self.assertEqual(monitor["counts"]["approval_attempts"], 1)
        self.assertEqual(monitor["counts"]["blocked"], 1)
        self.assertEqual(monitor["latest_audit"]["id"], approval["id"])
        self.assertEqual(monitor["recent_approval_attempts"][0]["id"], approval["id"])
        monitor_items = {item["id"]: item for item in monitor["items"]}
        self.assertEqual(monitor_items["latest_approval_attempt"]["status"], "fail")
        self.assertEqual(monitor_items["failed_or_blocked_attempts"]["status"], "warn")

        closeout_response = self.client.get(
            "/api/execution/post-cutover-monitor/closeout-report",
        )
        self.assertEqual(closeout_response.status_code, 200)
        closeout = closeout_response.json()
        self.assertEqual(closeout["monitor"]["latest_audit"]["id"], approval["id"])
        self.assertIn(approval["id"], closeout["markdown"])
        self.assertIn("## Approval Attempts", closeout["markdown"])
        self.assertIn("## Private Account Snapshot", closeout["markdown"])
        self.assertIn("## Operator Decisions", closeout["markdown"])

        reject_response = self.client.post(
            f"/api/execution/order-audits/{approval['id']}/approve",
            json={"live_confirmation": True},
        )
        self.assertEqual(reject_response.status_code, 400)

        audits_response = self.client.get("/api/execution/order-audits")
        self.assertEqual(audits_response.status_code, 200)
        self.assertEqual(audits_response.json()[0]["status"], "blocked")

    def test_live_paper_session_can_advance(self):
        create_response = self.client.post(
            "/api/paper/live-sessions",
            json={
                "symbol": "KRW-BTC",
                "timeframe": "day",
                "source": "sample",
                "strategy": "sma_crossover",
                "initial_cash": 1_000_000,
                "fee_bps": 5,
                "slippage_bps": 2,
                "candle_limit": 120,
                "warmup_bars": 35,
                "params": {"fast_window": 10, "slow_window": 30},
                "risk_limits": {
                    "max_position_pct": 50,
                    "max_order_notional": 500_000,
                    "max_orders": 20,
                    "max_session_loss_pct": 12,
                    "kill_switch": False,
                },
            },
        )

        self.assertEqual(create_response.status_code, 200)
        created = create_response.json()
        advance_response = self.client.post(
            f"/api/paper/live-sessions/{created['id']}/advance",
            json={"steps": 5},
        )

        self.assertEqual(advance_response.status_code, 200)
        advanced = advance_response.json()
        self.assertEqual(advanced["next_index"], created["next_index"] + 5)
        self.assertEqual(len(advanced["equity_curve"]), created["warmup_bars"] + 5)

        live_paper_runtimes.clear()
        stored_response = self.client.get(
            f"/api/paper/live-sessions/{created['id']}",
        )
        self.assertEqual(stored_response.status_code, 200)
        self.assertEqual(stored_response.json()["next_index"], advanced["next_index"])

        resumed_response = self.client.post(
            f"/api/paper/live-sessions/{created['id']}/advance",
            json={"steps": 1},
        )
        self.assertEqual(resumed_response.status_code, 200)
        self.assertEqual(
            resumed_response.json()["next_index"],
            advanced["next_index"] + 1,
        )

    def test_ticker_paper_session_can_tick(self):
        create_response = self.client.post(
            "/api/paper/ticker-sessions",
            json={
                "symbol": "KRW-BTC",
                "timeframe": "day",
                "source": "sample",
                "strategy": "sma_crossover",
                "initial_cash": 1_000_000,
                "fee_bps": 5,
                "slippage_bps": 2,
                "candle_limit": 80,
                "warmup_bars": 30,
                "params": {"fast_window": 10, "slow_window": 30},
                "risk_limits": {
                    "max_position_pct": 50,
                    "max_order_notional": 500_000,
                    "max_orders": 20,
                    "max_session_loss_pct": 12,
                    "kill_switch": False,
                },
            },
        )

        self.assertEqual(create_response.status_code, 200)
        created = create_response.json()
        self.assertEqual(created["mode"], "ticker")
        tick_response = self.client.post(
            f"/api/paper/live-sessions/{created['id']}/tick",
        )

        self.assertEqual(tick_response.status_code, 200)
        ticked = tick_response.json()
        self.assertEqual(ticked["mode"], "ticker")
        self.assertEqual(ticked["summary"]["status"], "running")
        self.assertEqual(ticked["next_index"], created["next_index"] + 1)
        self.assertEqual(ticked["total_candles"], created["total_candles"] + 1)


if __name__ == "__main__":
    unittest.main()
