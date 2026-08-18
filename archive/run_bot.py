#!/usr/bin/env python3
"""
ML-SuperTrend-MT5 Bot Runner — v2.3 (Master-Plan Enrichment Edition)
==============================================================
Author: xPOURY4

UPDATES v2.3:
- Passes session_gate, conviction_gate, use_m15_atr_for_sl_buffer to Config.
- equity_filter_enabled defaults to True (was False).
- CLI flags for session gate, conviction gate, M15 ATR buffer.
- Banner updated to show all v2.3 feature states.

fix-runbotwarn (audit finding #8): STANDALONE / LEGACY TOOL — DO NOT RUN
ALONGSIDE unified_runner.py AGAINST THE SAME MT5 TERMINAL.
This connects via raw mt5.initialize()/mt5.login() directly, not through
MT5Gateway's shared, lock-protected connection. Running this at the same
time as unified_runner.py against the same terminal instance means two
independent, uncoordinated connections fighting over one MT5 session —
use this only for isolated single-symbol testing with unified_runner.py
stopped.
"""

import sys
import json
import argparse
import logging
from datetime import datetime
from pathlib import Path

try:
    import MetaTrader5 as mt5
except ImportError:
    print("Error: MetaTrader5 module not found. Install with: pip install MetaTrader5")
    sys.exit(1)

# Import core components
from core.supertrend_bot import SuperTrendBot, Config, MultiPairRunner


# ==============================================================================
#  LOGGING SETUP
# ==============================================================================
def setup_logging(log_level: str = "INFO") -> logging.Logger:
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    # Ensure logs directory exists
    Path("logs").mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=log_format,
        handlers=[
            logging.FileHandler(f"logs/bot_{datetime.now().strftime('%Y%m%d')}.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger(__name__)


# ==============================================================================
#  MT5 CONNECTION (FIXED FOR MULTIPLE TERMINALS)
# ==============================================================================
def connect_mt5(login: int, password: str, server: str, logger, mt5_path: str = None):
    """Initializes MT5 using a specific terminal path if provided."""
    init_params = {"timeout": 180000}
    if mt5_path:
        logger.info(f"Targeting specific terminal: {mt5_path}")
        init_params["path"] = mt5_path

    if not mt5.initialize(**init_params):
        logger.error(f"MT5 initialize failed: {mt5.last_error()}")
        return None

    if not mt5.login(login, password=password, server=server):
        error = mt5.last_error()
        mt5.shutdown()
        logger.error(f"Login failed: {error}")
        return None

    account_info = mt5.account_info()
    if account_info is None:
        mt5.shutdown()
        logger.error("Failed to get account info")
        return None
    return account_info


# ==============================================================================
#  TIMEFRAME MAPPING
# ==============================================================================
TIMEFRAME_MAP = {
    "M1":  mt5.TIMEFRAME_M1, "M5":  mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30,
    "H1":  mt5.TIMEFRAME_H1, "H4":  mt5.TIMEFRAME_H4,
    "D1":  mt5.TIMEFRAME_D1,
}


# ==============================================================================
#  CONFIG BUILDER
# ==============================================================================
def build_config(symbol: str, config_data: dict, args) -> Config:
    gs = config_data.get("global_settings", {})
    sym = config_data.get("symbols", {}).get(symbol, {})

    def get_val(sym_key, gs_key=None, default=None):
        if sym_key in sym: return sym[sym_key]
        k = gs_key or sym_key
        return gs[k] if k in gs else default

    # Priority: CLI Flag > Config.json > Default
    enable_pc = args.partial_close or bool(get_val("enable_partial_close", default=False))

    return Config(
        symbol=symbol,
        timeframe=TIMEFRAME_MAP.get(get_val("timeframe", default="M30"), mt5.TIMEFRAME_M30),
        atr_period=get_val("atr_period", "atr_period", 10),
        min_factor=get_val("min_factor", 1.0),
        max_factor=get_val("max_factor", 5.0),
        factor_step=get_val("factor_step", 0.5),
        perf_alpha=get_val("perf_alpha", "performance_alpha", 10.0),
        cluster_choice=get_val("cluster_choice", "Best"),
        volume_ma_period=get_val("volume_ma_period", "volume_ma_period", 20),
        volume_multiplier=get_val("volume_multiplier", 1.2),
        risk_percent=get_val("risk_percent", 1.0),
        max_positions=get_val("max_positions", "max_positions_per_symbol", 1),
        magic_number=get_val("magic_number", "magic_number", 123456),
        sl_multiplier=get_val("sl_multiplier", 2.0),
        tp_safety_multiplier=get_val("tp_multiplier", 10.0),
        incubation_bars_trending=get_val("incubation_bars_trending", "incubation_bars_trending", 2),
        incubation_bars_stable=get_val("incubation_bars_stable", "incubation_bars_stable", 2),
        incubation_bars_exhaustion=get_val("incubation_bars_exhaustion", "incubation_bars_exhaustion", 3),
        enable_partial_close=enable_pc,
        si_partial_close_min=args.partial_close_si or get_val("si_partial_close_min", 0.85),
        partial_close_profit_atr_mult=args.partial_close_atr or get_val("partial_close_profit_atr_mult", 3.0),
        partial_close_fraction=args.partial_close_frac or get_val("partial_close_fraction", 0.50),
        # ── v2.3 NEW fields ────────────────────────────────────────────────────
        session_gate_enabled=not args.no_session_gate,
        conviction_gate_enabled=args.conviction_gate,
        conviction_min_threshold=get_val("conviction_min_threshold", default=45.0),
        use_m15_atr_for_sl_buffer=not args.no_m15_atr,
    )


# ==============================================================================
#  DYNAMIC BANNER
# ==============================================================================
def print_banner(symbols: list, args):
    print("=" * 64)
    print("  SuperTrend Bot v2.3 — Master-Plan Enrichment Edition")
    print("  ** STANDALONE/LEGACY — do not run alongside unified_runner.py **")
    print("  ** against the same MT5 terminal (separate raw connection,   **")
    print("  ** not via MT5Gateway — see fix-runbotwarn in module docstring) **")
    print(f"  Symbols        : {', '.join(symbols)}")
    print(f"  Equity Filter  : {'ON' if not getattr(args, 'no_equity_filter', False) else 'OFF'}")
    print(f"  Session Gate   : {'ON' if not args.no_session_gate else 'OFF'}")
    print(f"  Conviction Gate: {'ON' if args.conviction_gate else 'OFF'}")
    print(f"  M15 ATR Buffer : {'ON' if not args.no_m15_atr else 'OFF'}")
    print(f"  Partial Close  : {'ON' if args.partial_close else 'OFF'}")
    print(f"  Mode           : {'DRY RUN' if args.dry_run else 'LIVE'}")
    print("=" * 64)


# ==============================================================================
#  MAIN RUNNER
# ==============================================================================
def main():
    parser = argparse.ArgumentParser(description="ML-SuperTrend Trading Bot v2.2")
    parser.add_argument("--account", default="demo", choices=["demo", "live"])
    parser.add_argument("--symbols", default="EURUSDm", help="Comma-separated symbols")
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--max-total-positions", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--partial-close", action="store_true")
    # Equity filter (v2.3: ON by default — use --no-equity-filter to disable)
    parser.add_argument("--no-equity-filter", action="store_true",
                        help="Disable equity curve filter (ON by default in v2.3)")
    parser.add_argument("--equity-filter-period", type=int, default=20)
    parser.add_argument("--equity-filter-ratio", type=float, default=0.97)
    # Session gate (v2.3: ON by default — use --no-session-gate to disable)
    parser.add_argument("--no-session-gate", action="store_true",
                        help="Disable Asian-session entry suppression (ON by default)")
    # Conviction gate (v2.3: OFF by default — enable with --conviction-gate)
    parser.add_argument("--conviction-gate", action="store_true",
                        help="Enable conviction score pre-entry gate (OFF by default)")
    # M15 ATR buffer (v2.3: ON by default — use --no-m15-atr to disable)
    parser.add_argument("--no-m15-atr", action="store_true",
                        help="Disable M15 ATR for SL buffer (ON by default)")
    parser.add_argument("--partial-close-si", type=float, default=0.85)
    parser.add_argument("--partial-close-atr", type=float, default=3.0)
    parser.add_argument("--partial-close-frac", type=float, default=0.50)
    parser.add_argument("--monitor", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--config", default="config/config.json")
    
    args = parser.parse_args()
    logger = setup_logging(args.log_level)

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    print_banner(symbols, args)

    # Load Configuration
    try:
        with open(args.config, "r") as f:
            config_data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        sys.exit(1)

    account_cfg = config_data["accounts"].get(args.account)
    if not account_cfg:
        logger.error(f"Account '{args.account}' not found in config.json")
        sys.exit(1)

    # Connect to MT5 (Passes mt5_path from config)
    account_info = connect_mt5(
        account_cfg["login"], 
        account_cfg["password"], 
        account_cfg["server"], 
        logger,
        mt5_path=account_cfg.get("mt5_path")
    )
    
    if not account_info:
        sys.exit(1)

    logger.info(f"Connected | Account: {account_info.login} | Balance: {account_info.balance}")

    # Build Bots
    bots = []
    for sym in symbols:
        cfg = build_config(sym, config_data, args)
        bot = SuperTrendBot(cfg)
        bot.is_connected = True
        bots.append(bot)

    # Run
    try:
        runner = MultiPairRunner(
            bots=bots,
            interval_seconds=args.interval,
            max_total_positions=args.max_total_positions,
            dry_run=args.dry_run,
            equity_filter_enabled=not args.no_equity_filter,   # v2.3: ON by default
            equity_filter_period=args.equity_filter_period,
            equity_filter_min_ratio=args.equity_filter_ratio
        )
        runner.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    finally:
        mt5.shutdown()
        logger.info("MT5 connection closed")

if __name__ == "__main__":
    main()