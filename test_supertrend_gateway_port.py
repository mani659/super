"""
test_supertrend_gateway_port.py
================================
Task: pu-st-port verification
Verifies that core/supertrend_bot.py correctly routes all MT5 API
calls through the gateway when one is provided, and falls back to
raw mt5 in standalone mode. No MT5 terminal required.
Run: python test_supertrend_gateway_port.py
"""

import sys
import unittest
from unittest.mock import MagicMock, call, patch

# ── Mock heavy dependencies before importing ──────────────────────────────────
def _make_mt5_mock():
    m = MagicMock()
    m.TIMEFRAME_M30  = 16408
    m.TIMEFRAME_M1   = 1
    m.TIMEFRAME_M15  = 900
    m.TIMEFRAME_H1   = 3600
    m.TIMEFRAME_H4   = 16388
    m.ORDER_TYPE_BUY  = 0
    m.ORDER_TYPE_SELL = 1
    m.TRADE_ACTION_DEAL  = 1
    m.TRADE_ACTION_SLTP  = 6
    m.ORDER_TIME_GTC     = 0
    m.ORDER_FILLING_IOC  = 1
    m.TRADE_RETCODE_DONE = 10009
    return m

mt5_mock = _make_mt5_mock()
sys.modules["MetaTrader5"] = mt5_mock
sys.modules["talib"]        = MagicMock()
sys.modules["sklearn"]            = MagicMock()
sys.modules["sklearn.cluster"]    = MagicMock()

from core.supertrend_bot import SuperTrendBot, Config, MultiPairRunner  # noqa: E402


def _make_gateway():
    """Return a fresh MagicMock gateway with sensible defaults."""
    gw = MagicMock()
    # account_info
    acc = MagicMock()
    acc.balance  = 10_000.0
    acc.equity   = 10_000.0
    gw.account_info.return_value = acc
    # symbol_info
    sym = MagicMock()
    sym.point             = 0.00001
    sym.trade_tick_size   = 0.00001
    sym.trade_tick_value  = 1.0
    sym.volume_min        = 0.01
    sym.volume_max        = 100.0
    sym.volume_step       = 0.01
    sym.digits            = 5
    sym.trade_stops_level = 0
    sym.trade_tick_size   = 0.00001
    gw.symbol_info.return_value = sym
    # symbol_info_tick
    tick = MagicMock()
    tick.bid = 1.08500
    tick.ask = 1.08510
    gw.symbol_info_tick.return_value = tick
    # positions_get
    gw.positions_get.return_value = ()
    # copy_rates_from_pos — return None so get_data exits early (we just
    # care that the call went to gateway, not that it returns real data)
    gw.copy_rates_from_pos.return_value = None
    # terminal_info
    gw.terminal_info.return_value = MagicMock()
    return gw


def _make_bot(gateway=None):
    cfg = Config(symbol="EURUSDm", magic_number=101234)
    bot = SuperTrendBot(cfg, gateway=gateway)
    bot.is_connected = True
    return bot


class TestSupertrendGatewayPort(unittest.TestCase):

    # ── T1: _api returns gateway when one is provided ─────────────────────────
    def test_01_api_returns_gateway(self):
        gw  = MagicMock()
        bot = _make_bot(gateway=gw)
        self.assertIs(bot._api, gw)
        print("T01 PASS  _api returns gateway when provided")

    # ── T2: _api returns raw mt5 when no gateway ──────────────────────────────
    def test_02_api_falls_back_to_mt5(self):
        import MetaTrader5 as mt5
        bot = _make_bot(gateway=None)
        self.assertIs(bot._api, mt5)
        print("T02 PASS  _api falls back to raw mt5 in standalone mode")

    # ── T3: get_data calls gateway.copy_rates_from_pos, not mt5 ──────────────
    def test_03_get_data_uses_gateway(self):
        gw = _make_gateway()
        bot = _make_bot(gateway=gw)
        mt5_mock.copy_rates_from_pos.reset_mock()
        bot.get_data(bars=100)
        gw.copy_rates_from_pos.assert_called_once()
        mt5_mock.copy_rates_from_pos.assert_not_called()
        print("T03 PASS  get_data routes through gateway.copy_rates_from_pos")

    # ── T4: _get_market_regime calls gateway for M1 data ─────────────────────
    def test_04_regime_uses_gateway(self):
        # OBSOLETE: _get_market_regime now reads from KnowledgeRegister (Layer 0)
        # instead of calling copy_rates_from_pos directly.
        pass

    # ── T5: calculate_position_size calls gateway.account_info ───────────────
    def test_05_position_size_uses_gateway_account(self):
        gw = _make_gateway()
        bot = _make_bot(gateway=gw)
        mt5_mock.account_info.reset_mock()
        bot.calculate_position_size(stop_loss_points=50)
        gw.account_info.assert_called()
        mt5_mock.account_info.assert_not_called()
        print("T05 PASS  calculate_position_size uses gateway.account_info")

    # ── T6: calculate_position_size calls gateway.symbol_info ────────────────
    def test_06_position_size_uses_gateway_symbol(self):
        gw = _make_gateway()
        bot = _make_bot(gateway=gw)
        mt5_mock.symbol_info.reset_mock()
        bot.calculate_position_size(stop_loss_points=50)
        gw.symbol_info.assert_called()
        mt5_mock.symbol_info.assert_not_called()
        print("T06 PASS  calculate_position_size uses gateway.symbol_info")

    # ── T7: _get_m15_atr calls gateway for M15 data ───────────────────────────
    def test_07_m15_atr_uses_gateway(self):
        gw = _make_gateway()
        bot = _make_bot(gateway=gw)
        mt5_mock.copy_rates_from_pos.reset_mock()
        bot._get_m15_atr()
        gw.copy_rates_from_pos.assert_called()
        mt5_mock.copy_rates_from_pos.assert_not_called()
        print("T07 PASS  _get_m15_atr routes through gateway")

    # ── T8: manage_open_positions calls gateway.positions_get ─────────────────
    def test_08_manage_positions_uses_gateway(self):
        gw  = _make_gateway()
        gw.positions_get.return_value = ()
        bot = _make_bot(gateway=gw)
        mt5_mock.positions_get.reset_mock()
        # Needs supertrends + regime data to run; pass minimal stubs
        import pandas as pd, numpy as np
        df = pd.DataFrame({
            "open": [1.085]*50, "high": [1.086]*50,
            "low":  [1.084]*50, "close":[1.0851]*50,
            "tick_volume":[1000]*50, "atr":[0.001]*50,
            "volume_ma":[900]*50,
        })
        supertrends = {1.5: MagicMock(**{"trend": pd.Series([1]*50),
                                         "output": pd.Series([1.084]*50)})}
        regime = {"regime":"STABLE","reason":"test","scores":{"adx_rank":50,"atr_rank":50},"atr_raw":0.001}
        bot.manage_open_positions(df, supertrends, 1.5, regime)
        gw.positions_get.assert_called()
        mt5_mock.positions_get.assert_not_called()
        print("T08 PASS  manage_open_positions uses gateway.positions_get")

    # ── T9: standalone mode (gateway=None) still calls raw mt5 ───────────────
    def test_09_standalone_calls_raw_mt5(self):
        bot = _make_bot(gateway=None)
        mt5_mock.copy_rates_from_pos.reset_mock()
        mt5_mock.copy_rates_from_pos.return_value = None
        bot.get_data(bars=50)
        mt5_mock.copy_rates_from_pos.assert_called()
        print("T09 PASS  standalone mode calls raw mt5 (backward compat)")

    # ── T10: no raw mt5 method calls in patched source ────────────────────────
    def test_10_no_raw_mt5_calls_in_source(self):
        """
        Static check: the patched .py file must have zero raw mt5 method
        calls in the SuperTrendBot / MultiPairRunner class bodies.
        Allowed to remain: mt5.initialize, mt5.login, mt5.shutdown,
        mt5.last_error (standalone infrastructure).
        """
        src = open("core/supertrend_bot.py").read()
        # These must be ZERO after patching
        forbidden = [
            "mt5.account_info()",
            "mt5.symbol_info(",
            "mt5.symbol_info_tick(",
            "mt5.copy_rates_from_pos(",
            "mt5.positions_get(",
            "mt5.order_send(",
            "mt5.terminal_info()",
        ]
        failures = [(t, src.count(t)) for t in forbidden if src.count(t) > 0]
        self.assertEqual(failures, [],
            f"Raw mt5 calls still present: {failures}")
        print("T10 PASS  Static check: zero raw mt5 method calls in source")

    # ── T11: MultiPairRunner._api property exists ─────────────────────────────
    def test_11_runner_has_api_property(self):
        gw = _make_gateway()
        bot = _make_bot(gateway=gw)
        runner = MultiPairRunner(bots=[bot], gateway=gw)
        self.assertIs(runner._api, gw)
        print("T11 PASS  MultiPairRunner._api returns gateway")

    # ── T12: MultiPairRunner standalone still works ───────────────────────────
    def test_12_runner_standalone(self):
        import MetaTrader5 as mt5
        bot = _make_bot(gateway=None)
        runner = MultiPairRunner(bots=[bot])  # no gateway
        self.assertIs(runner._api, mt5)
        print("T12 PASS  MultiPairRunner standalone falls back to raw mt5")


if __name__ == "__main__":
    print("=" * 60)
    print("SuperTrend gateway port verification")
    print("=" * 60)
    loader = unittest.TestLoader()
    loader.sortTestMethodsUsing = None
    suite  = loader.loadTestsFromTestCase(TestSupertrendGatewayPort)
    result = unittest.TextTestRunner(verbosity=0).run(suite)
    print("=" * 60)
    if result.wasSuccessful():
        print(f"ALL {result.testsRun}/12 PASS — pu-st-port complete")
    else:
        n_fail = len(result.failures) + len(result.errors)
        print(f"{n_fail} FAILURE(S) — fix before proceeding")
    print("=" * 60)
