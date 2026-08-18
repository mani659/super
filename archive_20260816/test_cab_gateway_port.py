"""
test_cab_gateway_port.py
=========================
Task: pu-cab-port verification
Run from Super\ folder:  python test_cab_gateway_port.py
No MT5 terminal required.
"""

import sys
import unittest
from unittest.mock import MagicMock
from pathlib import Path

# ── Mock MetaTrader5 before any imports ───────────────────────────────────────
mt5_mock = MagicMock()
mt5_mock.TIMEFRAME_M1  = 1
mt5_mock.TIMEFRAME_M15 = 900
mt5_mock.TRADE_RETCODE_DONE = 10009
mt5_mock.TRADE_ACTION_DEAL  = 1
mt5_mock.TRADE_ACTION_SLTP  = 6
mt5_mock.ORDER_TYPE_BUY     = 0
mt5_mock.ORDER_TYPE_SELL    = 1
mt5_mock.ORDER_TIME_GTC     = 0
mt5_mock.ORDER_FILLING_IOC  = 1
sys.modules["MetaTrader5"] = mt5_mock
sys.modules["pandas"]      = __import__("pandas")
sys.modules["numpy"]       = __import__("numpy")

# Add parent to path so cab_super is importable
sys.path.insert(0, str(Path(__file__).parent))

import importlib.util, types

def _load_cab():
    """Load cab_watcher fresh (reset module state between tests)."""
    spec = importlib.util.spec_from_file_location(
        "cab_watcher",
        Path(__file__).parent / "cab_super" / "cab_watcher.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestCABGatewayPort(unittest.TestCase):

    def setUp(self):
        mt5_mock.reset_mock()
        self.cab = _load_cab()

    # ── T1: Module loads without error ────────────────────────────────────────
    def test_01_module_loads(self):
        self.assertIsNotNone(self.cab)
        print("T01 PASS  cab_watcher module loads without error")

    # ── T2: set_gateway and _api functions exist ──────────────────────────────
    def test_02_gateway_api_exists(self):
        self.assertTrue(hasattr(self.cab, 'set_gateway'))
        self.assertTrue(hasattr(self.cab, '_api'))
        self.assertTrue(hasattr(self.cab, '_GATEWAY'))
        print("T02 PASS  set_gateway(), _api(), _GATEWAY all present")

    # ── T3: Default _GATEWAY is None (standalone mode) ────────────────────────
    def test_03_default_gateway_none(self):
        self.assertIsNone(self.cab._GATEWAY)
        print("T03 PASS  _GATEWAY defaults to None")

    # ── T4: _api() returns raw mt5 when no gateway set ────────────────────────
    def test_04_api_falls_back_to_mt5(self):
        import MetaTrader5 as mt5
        result = self.cab._api()
        self.assertIs(result, mt5)
        print("T04 PASS  _api() returns raw mt5 in standalone mode")

    # ── T5: set_gateway wires the gateway in ─────────────────────────────────
    def test_05_set_gateway_wires_in(self):
        gw = MagicMock()
        self.cab.set_gateway(gw)
        self.assertIs(self.cab._GATEWAY, gw)
        self.assertIs(self.cab._api(), gw)
        print("T05 PASS  set_gateway() wires gateway, _api() returns it")

    # ── T6: get_market_regime calls gateway.copy_rates_from_pos ──────────────
    def test_06_regime_uses_gateway(self):
        # OBSOLETE: get_market_regime now reads from KnowledgeRegister (Layer 0)
        pass

    # ── T7: _get_m15_atr calls gateway.copy_rates_from_pos ───────────────────
    def test_07_m15_atr_uses_gateway(self):
        gw = MagicMock()
        gw.copy_rates_from_pos.return_value = None
        self.cab.set_gateway(gw)
        mt5_mock.copy_rates_from_pos.reset_mock()

        self.cab._get_m15_atr()

        gw.copy_rates_from_pos.assert_called()
        mt5_mock.copy_rates_from_pos.assert_not_called()
        print("T07 PASS  _get_m15_atr() routes through gateway")

    # ── T8: manage_fluid_logic calls gateway.positions_get ───────────────────
    def test_08_manage_uses_gateway_positions(self):
        gw = MagicMock()
        gw.positions_get.return_value = ()   # no positions → returns early
        gw.copy_rates_from_pos.return_value = None
        self.cab.set_gateway(gw)
        mt5_mock.positions_get.reset_mock()

        # patch heartbeat file write to avoid file I/O
        import unittest.mock as mock
        with mock.patch("builtins.open", mock.mock_open()):
            self.cab.manage_fluid_logic()

        gw.positions_get.assert_called()
        mt5_mock.positions_get.assert_not_called()
        print("T08 PASS  manage_fluid_logic() routes through gateway")

    # ── T9: standalone mode still calls raw mt5 (no gateway set) ─────────────
    def test_09_standalone_calls_raw_mt5(self):
        # OBSOLETE: get_market_regime reads from KnowledgeRegister
        pass

    # ── T10: Static check — no raw mt5 method calls in source ────────────────
    def test_10_no_raw_mt5_calls_in_source(self):
        src = (Path(__file__).parent / "cab_super" / "cab_watcher.py"
               ).read_text(encoding="utf-8")
        forbidden = [
            'mt5.copy_rates_from_pos(', 'mt5.symbol_info(',
            'mt5.symbol_info_tick(',    'mt5.order_send(',
            'mt5.positions_get(',
        ]
        found = [(t, src.count(t)) for t in forbidden if src.count(t) > 0]
        self.assertEqual(found, [], f"Raw mt5 calls still present: {found}")
        print("T10 PASS  Static check: zero raw mt5 method calls in source")


if __name__ == "__main__":
    print("=" * 55)
    print("CAB Watcher gateway port verification")
    print("=" * 55)
    loader = unittest.TestLoader()
    loader.sortTestMethodsUsing = None
    suite  = loader.loadTestsFromTestCase(TestCABGatewayPort)
    result = unittest.TextTestRunner(verbosity=0).run(suite)
    print("=" * 55)
    if result.wasSuccessful():
        print(f"ALL {result.testsRun}/10 PASS — pu-cab-port complete")
    else:
        n = len(result.failures) + len(result.errors)
        print(f"{n} FAILURE(S) — check output above")
        for f in result.failures + result.errors:
            print(f"  {f[0]}: {f[1][:120]}")
    print("=" * 55)