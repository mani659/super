"""
test_cab_entry.py
==================
Task: cab-entry-test
Run from Super\ folder:  python test_cab_entry.py
No MT5 terminal required.

Tests cover:
  T01  Module loads without error
  T02  CABEntryEngine._api returns gateway when provided
  T03  CABEntryEngine._api falls back to raw mt5 in standalone mode
  T04  Bullish inversion detected correctly
  T05  Bearish inversion detected correctly
  T06  Doji / no signal — neither inversion
  T07  Bar-aware cache: signal fires only once per H4 bar
  T08  Spread guard blocks entry when spread too wide
  T09  Session gate blocks entry during Asian hours
  T10  Position cap blocks entry when already at max
  T11  Lot sizing formula correct (risk-based, not fixed)
  T12  SL widened when inside broker stops level
  T13  _place_order routes order_send through gateway
  T14  CABEntryRunner._write_heartbeat writes timestamp file
  T15  CABEntryRunner.run_cycle_all calls all engines
  T16  max_lot_demo_cap caps the risk-based lot size (fix-lotcap)
"""

import sys
import os
import unittest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open
from datetime import datetime

# ── Mock MetaTrader5 before any imports ───────────────────────────────────────
mt5_mock = MagicMock()
mt5_mock.TIMEFRAME_H4        = 16388
mt5_mock.ORDER_TYPE_BUY      = 0
mt5_mock.ORDER_TYPE_SELL     = 1
mt5_mock.TRADE_ACTION_DEAL   = 1
mt5_mock.ORDER_TIME_GTC      = 0
mt5_mock.ORDER_FILLING_IOC   = 1
mt5_mock.TRADE_RETCODE_DONE  = 10009
sys.modules["MetaTrader5"] = mt5_mock
sys.modules["pandas"]      = __import__("pandas")
sys.modules["numpy"]       = __import__("numpy")

sys.path.insert(0, str(Path(__file__).parent))

from cab_super.cab_entry import (
    CABEntryEngine, CABEntryConfig, CABEntryRunner, build_cab_entry_configs
)

import pandas as pd
import numpy as np


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_gateway(spread_points=10, position_count=0,
                  equity=10000.0, volume_min=0.01):
    gw = MagicMock()

    # symbol_info
    sym = MagicMock()
    sym.point              = 0.01        # XAUUSD-style
    sym.trade_tick_size    = 0.01
    sym.trade_tick_value   = 1.0
    sym.volume_min         = volume_min
    sym.volume_max         = 100.0
    sym.volume_step        = 0.01
    sym.digits             = 2
    sym.trade_stops_level  = 0
    gw.symbol_info.return_value = sym

    # symbol_info_tick  (spread = spread_points * point)
    tick = MagicMock()
    tick.bid = 2000.00
    tick.ask = 2000.00 + spread_points * sym.point
    gw.symbol_info_tick.return_value = tick

    # account_info
    acc = MagicMock()
    acc.equity = equity
    gw.account_info.return_value = acc

    # positions_get
    positions = [MagicMock() for _ in range(position_count)]
    for p in positions:
        p.magic = 999555
    gw.positions_get.return_value = tuple(positions)

    return gw, sym, tick


def _make_bars(bar2_bull: bool, bar1_bull: bool) -> pd.DataFrame:
    """
    Create a 5-row H4 DataFrame.
    bar2 = index -3 (two bars back)
    bar1 = index -2 (last closed)
    bar0 = index -1 (current, open)
    """
    rows = []
    base_time = pd.Timestamp("2026-01-01 00:00:00")
    for i in range(5):
        rows.append({
            "time":  base_time + pd.Timedelta(hours=4*i),
            "open":  2000.0,
            "high":  2010.0,
            "low":   1990.0,
            "close": 2005.0,  # default bullish
        })
    df = pd.DataFrame(rows)
    # Set bar2 (index -3)
    df.at[df.index[-3], "open"]  = 2000.0
    df.at[df.index[-3], "close"] = 2005.0 if bar2_bull else 1995.0
    # Set bar1 (index -2)
    df.at[df.index[-2], "open"]  = 2000.0
    df.at[df.index[-2], "close"] = 2005.0 if bar1_bull else 1995.0
    return df


def _make_engine(gateway=None, session_gate=False,
                 max_positions=1, pos_count=0, spread=10):
    gw, sym, tick = _make_gateway(spread_points=spread,
                                   position_count=pos_count)
    if gateway:
        gw = gateway
    cfg = CABEntryConfig(
        symbol="XAUUSDm",
        magic_number=999555,
        risk_percent=1.0,
        atr_multiplier=2.5,
        atr_period=14,
        max_spread_points=50,
        max_positions=max_positions,
        session_gate_enabled=session_gate,
    )
    engine = CABEntryEngine(cfg, gateway=gw)
    import tempfile
    import os
    engine._state_file = os.path.join(tempfile.gettempdir(), f"cab_state_test_{os.urandom(4).hex()}.json")
    engine._last_h4_bar_time = engine._load_bar_state()
    # Bypass startup grace for legacy tests (T18 tests it explicitly)
    engine._startup_grace_passed = True
    return engine, gw, sym, tick


# ==============================================================================
#  TESTS
# ==============================================================================
class TestCABEntryEngine(unittest.TestCase):

    # ── T01: Module loads ─────────────────────────────────────────────────────
    def test_01_module_loads(self):
        from cab_super.cab_entry import CABEntryEngine, CABEntryConfig
        self.assertIsNotNone(CABEntryEngine)
        print("T01 PASS  cab_entry module loads without error")

    # ── T02: _api returns gateway ─────────────────────────────────────────────
    def test_02_api_returns_gateway(self):
        gw = MagicMock()
        cfg = CABEntryConfig(symbol="XAUUSDm")
        engine = CABEntryEngine(cfg, gateway=gw)
        self.assertIs(engine._api, gw)
        print("T02 PASS  _api returns gateway when provided")

    # ── T03: _api falls back to raw mt5 ──────────────────────────────────────
    def test_03_api_falls_back_to_mt5(self):
        import sys
        cfg = CABEntryEngine(CABEntryConfig(symbol="XAUUSDm"), gateway=None)
        self.assertIsNotNone(cfg._api)
        print("T03 PASS  _api falls back to raw mt5 in standalone mode")

    # ── T04: Bullish inversion detected ───────────────────────────────────────
    def test_04_bullish_inversion_detected(self):
        engine, gw, sym, tick = _make_engine()
        # bar2 bearish, bar1 bullish → bullish inversion
        df = _make_bars(bar2_bull=False, bar1_bull=True)
        engine._get_h4_bars   = MagicMock(return_value=df)
        engine._get_h4_atr    = MagicMock(return_value=2.0)
        engine._session_allowed = MagicMock(return_value=True)

        result_mock = MagicMock()
        result_mock.retcode = mt5_mock.TRADE_RETCODE_DONE
        result_mock.order   = 12345
        gw.order_send.return_value = result_mock

        fired = engine.run_cycle()
        self.assertTrue(fired)
        # Confirm it was a BUY
        req = gw.order_send.call_args[0][0]
        self.assertEqual(req["type"], mt5_mock.ORDER_TYPE_BUY)
        print("T04 PASS  Bullish inversion -> BUY order placed")

    # ── T05: Bearish inversion detected ───────────────────────────────────────
    def test_05_bearish_inversion_detected(self):
        engine, gw, sym, tick = _make_engine()
        # bar2 bullish, bar1 bearish -> bearish inversion
        df = _make_bars(bar2_bull=True, bar1_bull=False)
        engine._get_h4_bars   = MagicMock(return_value=df)
        engine._get_h4_atr    = MagicMock(return_value=2.0)
        engine._session_allowed = MagicMock(return_value=True)

        result_mock = MagicMock()
        result_mock.retcode = mt5_mock.TRADE_RETCODE_DONE
        result_mock.order   = 12346
        gw.order_send.return_value = result_mock

        fired = engine.run_cycle()
        self.assertTrue(fired)
        req = gw.order_send.call_args[0][0]
        self.assertEqual(req["type"], mt5_mock.ORDER_TYPE_SELL)
        print("T05 PASS  Bearish inversion -> SELL order placed")

    # ── T06: No signal — same direction bars ──────────────────────────────────
    def test_06_no_signal_same_direction(self):
        engine, gw, _, _ = _make_engine()
        # bar2 bullish, bar1 bullish -> no inversion
        df = _make_bars(bar2_bull=True, bar1_bull=True)
        engine._get_h4_bars   = MagicMock(return_value=df)
        engine._get_h4_atr    = MagicMock(return_value=2.0)
        engine._session_allowed = MagicMock(return_value=True)

        fired = engine.run_cycle()
        self.assertFalse(fired)
        gw.order_send.assert_not_called()
        print("T06 PASS  No inversion (same direction bars) -> no order")

    # ── T07: Bar-aware cache fires once per bar ────────────────────────────────
    def test_07_bar_aware_cache(self):
        engine, gw, _, _ = _make_engine()
        df = _make_bars(bar2_bull=False, bar1_bull=True)
        engine._get_h4_bars   = MagicMock(return_value=df)
        engine._get_h4_atr    = MagicMock(return_value=2.0)
        engine._session_allowed = MagicMock(return_value=True)

        result_mock = MagicMock()
        result_mock.retcode = mt5_mock.TRADE_RETCODE_DONE
        result_mock.order   = 99
        gw.order_send.return_value = result_mock

        fired1 = engine.run_cycle()   # first call — should fire
        fired2 = engine.run_cycle()   # same bar — should NOT fire again
        fired3 = engine.run_cycle()   # same bar — still no

        self.assertTrue(fired1)
        self.assertFalse(fired2)
        self.assertFalse(fired3)
        self.assertEqual(gw.order_send.call_count, 1)
        print("T07 PASS  Bar-aware cache: fires once, blocked on repeat calls")

    # ── T08: Spread guard blocks entry ────────────────────────────────────────
    def test_08_spread_guard(self):
        # spread_points=100 > max_spread_points=50
        engine, gw, _, _ = _make_engine(spread=100)
        engine._session_allowed = MagicMock(return_value=True)

        fired = engine.run_cycle()
        self.assertFalse(fired)
        gw.order_send.assert_not_called()
        print("T08 PASS  Spread guard: wide spread blocks entry")

    # ── T09: Session gate blocks during Asian hours ───────────────────────────
    def test_09_session_gate(self):
        engine, gw, _, _ = _make_engine(session_gate=True)
        # Force Asian hour (3 AM UTC)
        with patch("cab_super.cab_entry.datetime") as mock_dt:
            mock_dt.utcnow.return_value = datetime(2026, 1, 1, 3, 0, 0)
            fired = engine.run_cycle()

        self.assertFalse(fired)
        gw.order_send.assert_not_called()
        print("T09 PASS  Session gate: Asian hour blocks entry")

    # ── T10: Position cap blocks entry ────────────────────────────────────────
    def test_10_position_cap(self):
        # Already at max_positions=1, pos_count=1
        engine, gw, _, _ = _make_engine(max_positions=1, pos_count=1)
        engine._session_allowed = MagicMock(return_value=True)

        fired = engine.run_cycle()
        self.assertFalse(fired)
        gw.order_send.assert_not_called()
        print("T10 PASS  Position cap: max_positions=1 already filled -> blocked")

    # ── T11: Lot sizing formula ────────────────────────────────────────────────
    def test_11_lot_sizing(self):
        """
        equity=10000, risk=1% → risk_money=100
        sl_dist=2.0 (price), tick_size=0.01, tick_value=1.0
        sl_ticks = 2.0/0.01 = 200
        dollar_per_lot = 200 × 1.0 = 200
        lot = 100/200 = 0.5

        fix-lotcap: max_lot_demo_cap defaults to 0.01 in production now, which
        would cap this result before it ever reaches the formula's raw output.
        This test is specifically about the risk-based formula itself, so the
        cap is explicitly disabled here — see test_16 for the cap's own test.
        """
        engine, gw, _, _ = _make_engine()
        engine.config.max_lot_demo_cap = None
        lot = engine._calculate_lot(sl_dist_price=2.0)
        self.assertAlmostEqual(lot, 0.5, places=2)
        print(f"T11 PASS  Lot sizing: risk=1%, equity=10k, sl=2.0 -> lot={lot:.2f}")

    # ── T12: SL widened when inside stops level ───────────────────────────────
    def test_12_sl_stops_level_guard(self):
        engine, gw, sym, tick = _make_engine()
        sym.trade_stops_level = 100   # 100 points minimum distance
        sym.point = 0.01
        # price=2000, proposed sl=1999.9 — only 10 points away (< 100)
        safe = engine._safe_sl(price=2000.0, sl=1999.9, is_buy=True)
        min_dist = 100 * 0.01 + 30 * 0.01   # stops + buffer
        self.assertLessEqual(safe, 2000.0 - min_dist + 0.001)
        print(f"T12 PASS  SL guard: sl widened from 1999.9 -> {safe:.2f}")

    # ── T13: _place_order routes through gateway ──────────────────────────────
    def test_13_place_order_uses_gateway(self):
        engine, gw, _, _ = _make_engine()
        mt5_mock.order_send.reset_mock()

        result_mock = MagicMock()
        result_mock.retcode = mt5_mock.TRADE_RETCODE_DONE
        result_mock.order   = 777
        gw.order_send.return_value = result_mock

        fired = engine._place_order(is_buy=True, sl=1990.0, lot=0.01)
        self.assertTrue(fired)
        gw.order_send.assert_called_once()
        mt5_mock.order_send.assert_not_called()
        print("T13 PASS  _place_order routes order_send through gateway")

    # ── T14: CABEntryRunner writes heartbeat ──────────────────────────────────
    def test_14_heartbeat_written(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hb_path = os.path.join(tmpdir, "cab_heartbeat.txt")
            cfg = CABEntryConfig(symbol="XAUUSDm", heartbeat_path=hb_path)
            gw, _, _ = _make_gateway()
            runner = CABEntryRunner([cfg], gateway=gw, heartbeat_path=hb_path)
            runner._write_heartbeat()
            self.assertTrue(os.path.isfile(hb_path))
            content = Path(hb_path).read_text().strip()
            self.assertTrue(content.isdigit())
            print(f"T14 PASS  Heartbeat written: {content} (unix timestamp)")

    # ── T15: CABEntryRunner calls all engines ─────────────────────────────────
    def test_15_runner_calls_all_engines(self):
        cfg1 = CABEntryConfig(symbol="EURUSDm")
        cfg2 = CABEntryConfig(symbol="XAUUSDm")
        gw, _, _ = _make_gateway()
        runner = CABEntryRunner([cfg1, cfg2], gateway=gw)

        # Patch run_cycle on both engines
        runner.engines[0].run_cycle = MagicMock(return_value=False)
        runner.engines[1].run_cycle = MagicMock(return_value=True)

        opened = runner.run_cycle_all()
        runner.engines[0].run_cycle.assert_called_once()
        runner.engines[1].run_cycle.assert_called_once()
        self.assertEqual(opened, 1)
        print("T15 PASS  CABEntryRunner calls all engines, counts openings")

    # ── T16: max_lot_demo_cap caps the risk-based result ──────────────────────
    def test_16_lot_demo_cap_applies(self):
        """
        Same scenario as T11 (risk formula alone gives 0.5 lot), but with
        max_lot_demo_cap left at its default (0.01) — the production default.
        This is the fix for the 0.14-0.32 lot FX fills found in the two-week
        review: risk-based sizing with no ceiling beyond the broker's own
        volume_max.
        """
        engine, gw, _, _ = _make_engine()
        self.assertEqual(engine.config.max_lot_demo_cap, 0.01,
                         "default cap should be 0.01 unless explicitly overridden")
        lot = engine._calculate_lot(sl_dist_price=2.0)
        self.assertAlmostEqual(lot, 0.01, places=2)
        print(f"T16 PASS  Demo lot cap: raw formula=0.50 -> capped to {lot:.2f}")


        print(f"T16 PASS  Demo lot cap: raw formula=0.50 -> capped to {lot:.2f}")

    # ── T17: State file persistence blocks re-entry on same bar ──────────
    def test_17_state_file_blocks_restart_refire(self):
        """
        Simulate a restart mid-H4-bar. After a fire on bar1_time X,
        a new engine instance reading the state file should have
        _last_h4_bar_time = X and block a second fire on bar X.
        """
        import tempfile, os, json, time
        engine, gw, sym, tick = _make_engine()

        # Override state file to a temp location
        tmpdir = tempfile.mkdtemp()
        engine._state_file = os.path.join(tmpdir, "cab_state_test.json")

        df = _make_bars(bar2_bull=False, bar1_bull=True)
        engine._get_h4_bars   = MagicMock(return_value=df)
        engine._get_h4_atr    = MagicMock(return_value=2.0)
        engine._session_allowed = MagicMock(return_value=True)

        result_mock = MagicMock()
        result_mock.retcode = mt5_mock.TRADE_RETCODE_DONE
        result_mock.order   = 88888
        gw.order_send.return_value = result_mock

        # First fire — should succeed and write state file
        fired1 = engine.run_cycle()
        self.assertTrue(fired1, "First fire should succeed")
        self.assertTrue(os.path.exists(engine._state_file),
                        "State file should be written after fire")

        # Simulate restart: new engine instance in same temp dir
        engine2, gw2, _, _ = _make_engine()
        engine2._state_file = engine._state_file

        # Manually trigger state load (normally called in __init__)
        engine2._last_h4_bar_time = engine2._load_bar_state()

        # Simulate the state was just written (within grace window)
        # Patch written_at to be recent
        with open(engine2._state_file, "r") as f:
            data = json.load(f)
        data["written_at"] = int(time.time())
        with open(engine2._state_file, "w") as f:
            json.dump(data, f)
        engine2._last_h4_bar_time = engine2._load_bar_state()

        self.assertIsNotNone(engine2._last_h4_bar_time,
                             "State file should restore bar time")

        # run_cycle on same bar should return False
        engine2._get_h4_bars   = MagicMock(return_value=df)
        engine2._get_h4_atr    = MagicMock(return_value=2.0)
        engine2._session_allowed = MagicMock(return_value=True)
        fired2 = engine2.run_cycle()
        self.assertFalse(fired2, "Second engine should block on same bar")
        gw2.order_send.assert_not_called()
        print("T17 PASS  State file persistence blocks re-entry on restart")

    # ── T18: Startup grace blocks entry when no state file exists ─────────
    def test_18_startup_grace_blocks_cold_start(self):
        """
        When no state file exists, the first bar seen at startup should
        be blocked. Entry should only be permitted on a subsequent
        different bar.
        """
        engine, gw, sym, tick = _make_engine()
        # Ensure no state file
        import os
        if os.path.exists(engine._state_file):
            os.remove(engine._state_file)
        engine._last_h4_bar_time = None
        engine._startup_grace_passed = False
        if hasattr(engine, '_startup_bar_seen'):
            del engine._startup_bar_seen

        df_bar_A = _make_bars(bar2_bull=False, bar1_bull=True)
        engine._get_h4_bars   = MagicMock(return_value=df_bar_A)
        engine._get_h4_atr    = MagicMock(return_value=2.0)
        engine._session_allowed = MagicMock(return_value=True)

        # First cycle on bar A — startup grace should block
        fired1 = engine.run_cycle()
        self.assertFalse(fired1,
            "Startup grace should block first bar after cold start")
        gw.order_send.assert_not_called()

        # Second cycle on bar A — still blocked
        fired2 = engine.run_cycle()
        self.assertFalse(fired2,
            "Startup grace should still block on same bar")

        # Simulate new bar B opening (different timestamp)
        df_bar_B = _make_bars(bar2_bull=False, bar1_bull=True)
        new_time = pd.Timestamp("2026-01-02 04:00:00")
        df_bar_B.at[df_bar_B.index[-2], "time"] = new_time
        engine._get_h4_bars = MagicMock(return_value=df_bar_B)

        result_mock = MagicMock()
        result_mock.retcode = mt5_mock.TRADE_RETCODE_DONE
        result_mock.order   = 77777
        gw.order_send.return_value = result_mock

        fired3 = engine.run_cycle()
        self.assertTrue(fired3,
            "After grace period, new bar should allow entry")
        print("T18 PASS  Startup grace blocks cold-start re-entry")

    # ── T19: London Open session gate ──────────────────────────────────────
    def test_19_london_open_session_blocked(self):
        """London Open (07-11 UTC) should be blocked after F5 gate."""
        from cab_super.cab_entry import CABEntryConfig
        cfg = CABEntryConfig()
        # London Open hours must all be in blocked list
        london_hours = [7, 8, 9, 10, 11]
        for h in london_hours:
            self.assertIn(h, cfg.blocked_hours_utc,
                f"Hour {h}:00 UTC (London Open) should be blocked")
        # NY_OVERLAP must NOT be blocked
        ny_hours = [13, 14, 15, 16]
        for h in ny_hours:
            self.assertNotIn(h, cfg.blocked_hours_utc,
                f"Hour {h}:00 UTC (NY session) must not be blocked")
        print("T19 PASS  London Open session gate covers 07:00-11:59 UTC")

if __name__ == "__main__":
    print("=" * 60)
    print("CAB Entry Engine verification")
    print("=" * 60)
    loader = unittest.TestLoader()
    loader.sortTestMethodsUsing = None
    suite  = loader.loadTestsFromTestCase(TestCABEntryEngine)
    result = unittest.TextTestRunner(verbosity=0).run(suite)
    print("=" * 60)
    if result.wasSuccessful():
        print(f"ALL {result.testsRun}/19 PASS - cab-entry-test complete")
    else:
        n = len(result.failures) + len(result.errors)
        print(f"{n} FAILURE(S) - fix before wiring into unified_runner")
        for f in result.failures + result.errors:
            print(f"  {f[0]}: {f[1][:200]}")
    print("=" * 60)
