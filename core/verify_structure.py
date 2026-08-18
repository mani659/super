"""
verify_structure.py
====================
Run from Super\ folder:  python verify_structure.py

Checks:
  1. All expected files exist in the right folders
  2. Each bot file is importable (catches missing dependencies clearly)
  3. supertrend_bot.py is the gateway-patched version (not the original)
  4. mt5_gateway.py is present and importable
  5. config/config.json exists and is valid JSON
  6. ghost_super\ and cab_super\ are recognised as Python packages
"""

import sys
import json
import importlib
from pathlib import Path

ROOT = Path(__file__).parent
OK   = "  OK  "
FAIL = " FAIL "
WARN = " WARN "
results = []

def check(label, passed, detail=""):
    tag = OK if passed else FAIL
    results.append(passed)
    mark = "✓" if passed else "✗"
    line = f"  {mark}  {label}"
    if detail:
        line += f"  →  {detail}"
    print(line)

def section(title):
    print(f"\n{'─'*55}")
    print(f"  {title}")
    print(f"{'─'*55}")

print("=" * 55)
print("  Unified Bot — Structure Verification")
print(f"  Root: {ROOT}")
print("=" * 55)

# ── 1. FOLDER STRUCTURE ───────────────────────────────────────────
section("1. Folder structure")

folders = ["core", "ghost_super", "cab_super", "config", "logs"]
for f in folders:
    p = ROOT / f
    check(f"{f}/  folder exists", p.is_dir())

# ── 2. ROOT-LEVEL FILES ────────────────────────────────────────────
section("2. Root-level files")

root_files = [
    "run_bot.py",
    "unified_runner.py",
    "mt5_gateway.py",
]
for f in root_files:
    check(f"{f}", (ROOT / f).is_file())

# ── 3. CORE FILES ──────────────────────────────────────────────────
section("3. core\\ files")

core_files = ["supertrend_bot.py"]
for f in core_files:
    check(f"core\\{f}", (ROOT / "core" / f).is_file())

# Check it's the gateway-patched version
st_path = ROOT / "core" / "supertrend_bot.py"
if st_path.is_file():
    src = st_path.read_text(encoding="utf-8")
    has_gateway = "self._gw" in src and "self._api" in src
    raw_calls   = sum(src.count(t) for t in [
        "mt5.account_info()", "mt5.symbol_info(", "mt5.positions_get(",
        "mt5.order_send(", "mt5.copy_rates_from_pos(", "mt5.terminal_info()"
    ])
    check("core\\supertrend_bot.py is gateway-patched", has_gateway,
          "gateway code present" if has_gateway else "ORIGINAL file — needs replacing")
    check("core\\supertrend_bot.py has no raw mt5 calls", raw_calls == 0,
          f"{raw_calls} raw calls remaining" if raw_calls else "clean")

# ── 4. GHOST_SUPER FILES ───────────────────────────────────────────
section("4. ghost_super\\ files")

ghost_files = [
    "ghost_sniper_v5_1.py",
    "sniper_watcher_v3_1.py",
    "ghost_cache_204.py",
]
for f in ghost_files:
    check(f"ghost_super\\{f}", (ROOT / "ghost_super" / f).is_file())

# ── 5. CAB_SUPER FILES ────────────────────────────────────────────
section("5. cab_super\\ files")

# Accept either filename variant
cab_candidates = ["cab_watcher_v16_3-1.py", "cab_watcher.py"]
found_cab = None
for c in cab_candidates:
    if (ROOT / "cab_super" / c).is_file():
        found_cab = c
        break
check("cab_super\\cab_watcher file", found_cab is not None,
      found_cab if found_cab else "not found — expected cab_watcher_v16_3-1.py")

# ── 6. CONFIG ─────────────────────────────────────────────────────
section("6. config\\config.json")

cfg_path = ROOT / "config" / "config.json"
check("config\\config.json exists", cfg_path.is_file())
if cfg_path.is_file():
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        has_accounts = "accounts" in cfg
        has_symbols  = "symbols" in cfg
        check("config.json valid JSON with accounts key", has_accounts)
        check("config.json has symbols key", has_symbols)
        if has_accounts:
            accs = list(cfg["accounts"].keys())
            check(f"accounts found: {accs}", len(accs) > 0)
        if has_symbols:
            syms = list(cfg["symbols"].keys())
            check(f"symbols found: {syms}", len(syms) > 0)
    except json.JSONDecodeError as e:
        check("config.json is valid JSON", False, str(e))

# ── 7. PYTHON PACKAGE __init__.py ─────────────────────────────────
section("7. Python package __init__.py files")

for pkg in ["core", "ghost_super", "cab_super"]:
    init = ROOT / pkg / "__init__.py"
    check(f"{pkg}\\__init__.py", init.is_file(),
          "present" if init.is_file() else "MISSING — imports will fail without this")

# ── 8. IMPORT CHECK: mt5_gateway ─────────────────────────────────
section("8. Import checks (no MT5 terminal needed)")

sys.path.insert(0, str(ROOT))

# Mock MetaTrader5 so imports work without the terminal
from unittest.mock import MagicMock
mt5_mock = MagicMock()
mt5_mock.TIMEFRAME_M30 = 16408; mt5_mock.TIMEFRAME_M1 = 1
mt5_mock.TIMEFRAME_M15 = 900;   mt5_mock.TIMEFRAME_H1 = 3600
mt5_mock.ORDER_TYPE_BUY = 0;    mt5_mock.ORDER_TYPE_SELL = 1
mt5_mock.TRADE_ACTION_DEAL = 1; mt5_mock.TRADE_ACTION_SLTP = 6
mt5_mock.ORDER_TIME_GTC = 0;    mt5_mock.ORDER_FILLING_IOC = 1
mt5_mock.TRADE_RETCODE_DONE = 10009
sys.modules["MetaTrader5"] = mt5_mock
sys.modules["talib"]            = MagicMock()
sys.modules["sklearn"]          = MagicMock()
sys.modules["sklearn.cluster"]  = MagicMock()

try:
    import mt5_gateway
    gw = mt5_gateway.MT5Gateway()
    check("mt5_gateway imports OK", True)
except Exception as e:
    check("mt5_gateway imports OK", False, str(e))

try:
    from core.supertrend_bot import SuperTrendBot, Config, MultiPairRunner
    bot = SuperTrendBot(Config(symbol="EURUSDm"), gateway=MagicMock())
    assert hasattr(bot, '_api'), "no _api property"
    check("core.supertrend_bot imports OK (gateway-aware)", True)
except Exception as e:
    check("core.supertrend_bot imports OK", False, str(e))

try:
    from ghost_super import ghost_sniper_v5_1
    check("ghost_super.ghost_sniper_v5_1 imports OK", True)
except Exception as e:
    check("ghost_super.ghost_sniper_v5_1 imports OK", False, str(e)[:80])

try:
    from ghost_super import sniper_watcher_v3_1
    check("ghost_super.sniper_watcher_v3_1 imports OK", True)
except Exception as e:
    check("ghost_super.sniper_watcher_v3_1 imports OK", False, str(e)[:80])

try:
    from ghost_super import ghost_cache_204
    check("ghost_super.ghost_cache_204 imports OK", True)
except Exception as e:
    check("ghost_super.ghost_cache_204 imports OK", False, str(e)[:80])

try:
    import importlib.util
    cab_file = found_cab or "cab_watcher_v16_3-1.py"
    spec = importlib.util.spec_from_file_location(
        "cab_watcher",
        ROOT / "cab_super" / cab_file
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    check("cab_super\\cab_watcher imports OK", True)
except Exception as e:
    check("cab_super\\cab_watcher imports OK", False, str(e)[:80])

# ── SUMMARY ──────────────────────────────────────────────────────
passed = sum(results)
total  = len(results)
failed = total - passed

print(f"\n{'='*55}")
print(f"  Results: {passed}/{total} checks passed", end="")
if failed:
    print(f"  |  {failed} FAILED")
else:
    print()

if failed == 0:
    print("  ALL CLEAR — structure is correct, ready for next step")
elif any("__init__" in str(r) for r in []):
    pass

# Specific guidance for common failures
src_check = (ROOT / "core" / "supertrend_bot.py").is_file()
if src_check:
    src = (ROOT / "core" / "supertrend_bot.py").read_text(encoding="utf-8")
    if "self._gw" not in src:
        print()
        print("  ACTION: Replace core\\supertrend_bot.py with the patched")
        print("          version from outputs (the one with gateway code).")

missing_inits = [p for p in ["core","ghost_super","cab_super"]
                 if not (ROOT / p / "__init__.py").is_file()]
if missing_inits:
    print()
    print("  ACTION: Create empty __init__.py files in these folders:")
    for p in missing_inits:
        print(f"          {p}\\__init__.py  (empty file is fine)")
    print()
    print("  Quickest way — run this in your Super\\ folder:")
    for p in missing_inits:
        print(f"    type nul > {p}\\__init__.py")

print("=" * 55)
