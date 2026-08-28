"""
SHADOW TESTING READINESS (Step 5.2):
NOT READY. The following must be implemented before shadow testing begins:
1. GhostCache (magic 204) logic — entirely absent from V2. See V1 ghost_super/ghost_cache.py.
2. GridState with GRID_TP_R=+1.0, GRID_STOP_R=-3.0, GRID_PROT_R=+0.35. See V1 sniper_watcher.py.
3. CAB multi-symbol — currently hardcoded to XAUUSDm only. Must cover all config.json symbols.
4. Per-magic management dispatch — TradeManager must route 201/202/204 to grid-aware management,
   SuperTrend to SI-state-machine management, CAB to Fluid Matrix management.
5. The uniform TradeManager exit logic (H1 structural invalidation for all positions) must be
   replaced with per-bot dispatch before any signal-level comparison to V1 is meaningful.
Do not start shadow testing until all five items above are checked off.
"""
import time
import argparse
import logging
import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime
import json
import os

# V2 Core Modules
from v2.core.knowledge_register import KnowledgeRegister
from v2.core.market_oracle import MarketOracle
from v2.execution.mt5_gateway import MT5Gateway
from v2.execution.failover_heartbeat import FailoverHeartbeat
from v2.execution.order_router import OrderRouter
from v2.execution.trade_manager import TradeManager

# V2 Bot Modules
from v2.bots.supertrend_bot import SuperTrendBot, SuperTrendConfig
from v2.bots.ghost_bot import GhostBot, GhostConfig
from v2.bots.cab_bot import CABBot, CABConfig

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("V2Runner")


def check_magic_isolation_v2(gateway, config_data: dict) -> bool:
    symbols_cfg = config_data.get("symbols", {})
    valid_st_magics = {int(v["magic_number"]) for v in symbols_cfg.values() if "magic_number" in v}
    valid_ghost_magics = {201, 202, 204}
    valid_cab_magics = {999555}
    all_valid = valid_st_magics | valid_ghost_magics | valid_cab_magics

    positions = gateway.positions_get()
    if not positions:
        return True

    unknown = [p for p in positions if p.magic not in all_valid]
    if unknown:
        for p in unknown:
            logger.warning(
                f"V2 MAGIC ISOLATION BREACH | "
                f"ticket={p.ticket} magic={p.magic} symbol={p.symbol} | "
                f"not owned by any V2 bot"
            )
        return False
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mt5-path', type=str, default=None)
    args = parser.parse_args()
    logger.info("Initializing V2 Unified Runner...")

    # 1. Foundation
    gateway = MT5Gateway()
    if not gateway.initialize(path=args.mt5_path):
        logger.error("MT5 Initialization failed. Exiting.")
        return
        
    # Use a separate heartbeat file for V2 to prevent conflict with V1
    common_files_dir = r"C:\Users\ABRAR\AppData\Roaming\MetaQuotes\Terminal\Common\Files"
    heartbeat_path = f"{common_files_dir}\\v2_heartbeat.txt"
    heartbeat = FailoverHeartbeat(heartbeat_path)
    heartbeat.start()

    kr = KnowledgeRegister()
    
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "config.json")
    try:
        with open(config_path, "r") as f:
            config_data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return
        
    symbols_cfg = config_data.get("symbols", {})
    all_symbols = list(symbols_cfg.keys())
    
    oracle = MarketOracle(gateway, kr, all_symbols)
    router = OrderRouter(gateway, kr)
    
    st_magics = {int(v["magic_number"]) for v in symbols_cfg.values() if "magic_number" in v}
    manager = TradeManager(gateway, kr, st_magics=st_magics)

    # 2. Instantiate Bots
    # SuperTrend configurations
    st_bots = []
    for sym in all_symbols:
        sym_cfg = symbols_cfg.get(sym, {})
        if "magic_number" not in sym_cfg:
            logger.warning(f"No magic number for {sym} in config.json, skipping SuperTrend.")
            continue
        magic = int(sym_cfg["magic_number"])
        cfg = SuperTrendConfig(symbol=sym, magic_number=magic)
        st_bots.append(SuperTrendBot(cfg, gateway, router, kr))

    # Ghost configurations (XAUUSDm)
    ghost_cfg = GhostConfig(symbol="XAUUSDm")
    ghost_bot = GhostBot(ghost_cfg, gateway, router, kr)

    # CAB configurations
    cab_bots = []
    for sym in all_symbols:
        sym_cfg = symbols_cfg.get(sym, {})
        if "cab_entry" in sym_cfg:
            cab_cfg_dict = sym_cfg["cab_entry"]
            cab_cfg = CABConfig(
                symbol=sym,
                risk_percent=cab_cfg_dict.get("cab_risk_percent", 0.5),
                atr_multiplier=cab_cfg_dict.get("cab_atr_multiplier", 3.0),
                max_spread_points=cab_cfg_dict.get("cab_max_spread", 400),
                max_lot_demo_cap=config_data.get("global_settings", {}).get("cab_max_lot_demo_cap", 0.01)
            )
            cab_bots.append(CABBot(cab_cfg, gateway, router, kr))

    logger.info("All modules initialized. Entering deterministic tick loop.")

    # 3. Deterministic Tick Loop
    last_heartbeat_time = time.time()
    last_isolation_check = time.time()
    
    acc_info = gateway.account_info()
    daily_start_equity = acc_info.equity if acc_info else 0.0

    try:
        while True:
            t0 = time.time()
            
            acc = gateway.account_info()
            if acc and daily_start_equity > 0:
                current_dd = (daily_start_equity - acc.equity) / daily_start_equity * 100.0
            else:
                current_dd = 0.0
                
            max_dd_pct = config_data.get("global_settings", {}).get("max_daily_loss_percent", 10.0)
            
            if current_dd >= max_dd_pct:
                logger.warning(f"CIRCUIT BREAKER: drawdown {current_dd:.2f}% >= {max_dd_pct:.1f}% — entries blocked")
            
            # Phase A: Oracle updates the KnowledgeRegister synchronously
            oracle.tick()

            # Phase B: Strategy Generation
            # SuperTrend (needs M30 data)
            for bot in st_bots:
                rates = gateway.copy_rates_from_pos(bot.config.symbol, mt5.TIMEFRAME_M30, 0, 250)
                if rates is not None and len(rates) >= 200:
                    df = pd.DataFrame(rates)
                    bot.execute_cycle(df, current_dd=current_dd, max_dd=max_dd_pct)

            # Ghost (needs M1 data)
            rates = gateway.copy_rates_from_pos(ghost_cfg.symbol, mt5.TIMEFRAME_M1, 0, 50)
            if rates is not None and len(rates) >= 20:
                df = pd.DataFrame(rates)
                ghost_bot.execute_cycle(df, current_dd=current_dd, max_dd=max_dd_pct)
                
            # CAB (needs H4 data)
            for bot in cab_bots:
                rates = gateway.copy_rates_from_pos(bot.config.symbol, mt5.TIMEFRAME_H4, 0, 50)
                if rates is not None and len(rates) >= 5:
                    df = pd.DataFrame(rates)
                    df["time"] = pd.to_datetime(df["time"], unit="s")
                    bot.execute_cycle(df, current_dd=current_dd, max_dd=max_dd_pct)

            # Phase C: Trade Management
            for m in [999555, 201, 202, 204] + [b.config.magic_number for b in st_bots]: manager.manage_open_positions(m)

            # Phase D: Heartbeat & Sleep
            if time.time() - last_heartbeat_time > 60:
                acc = gateway.account_info()
                if acc:
                    logger.info(f"Runner Heartbeat | Equity={acc.equity:.2f} | Profit={acc.profit:.2f} | DD={current_dd:.2f}%")
                last_heartbeat_time = time.time()
                
            if time.time() - last_isolation_check > 300:
                check_magic_isolation_v2(gateway, config_data)
                last_isolation_check = time.time()

            # Sleep to maintain ~1 second loop
            elapsed = time.time() - t0
            sleep_time = max(0.1, 1.0 - elapsed)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error in main loop: {e}", exc_info=True)
    finally:
        heartbeat.stop()
        oracle.stop()
        gateway.shutdown()
        logger.info("V2 Runner Shutdown Complete.")

if __name__ == "__main__":
    main()
