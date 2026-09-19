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
import logging.handlers
import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime
import json
import os
import sys
import csv
import threading

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

# Setup Logging — dual handler: file INFO, console WARNING (matches V1)
_fmt = logging.Formatter('%(asctime)s [%(name)s] %(levelname)s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

_fh = logging.handlers.RotatingFileHandler(
    "logs/v2_unified_runner.log", maxBytes=5*1024*1024, backupCount=5, encoding="utf-8"
)
_fh.setFormatter(_fmt)
_fh.setLevel(logging.INFO)

_ch = logging.StreamHandler()
_ch.setFormatter(logging.Formatter('%(asctime)s [%(name)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
_ch.setLevel(logging.INFO)

_root = logging.getLogger()
_root.setLevel(logging.INFO)
_root.addHandler(_fh)
_root.addHandler(_ch)

logger = logging.getLogger("V2Runner")

# Suppress noisy per-tick loggers on console (file still gets everything)
for _noisy in ["MarketOracle", "KnowledgeRegister", "FailoverHeartbeat", "MT5Gateway", "SuperTrendBotV2"]:
    logging.getLogger(_noisy).setLevel(logging.WARNING)


# ─────────────────────────────────────────────────────────────
#  RUNTIME SWITCHES  (fix-switches — ported from V1 unified_runner.py:174)
#
#  Re-read from disk every tick so a switch flip takes effect with no redeploy.
#  A switch set to false blocks NEW entries only. Open positions are always
#  still actively managed — that scoping is the entire point, and it is the
#  failure mode the switches block's own _comment in config.json warns about.
# ─────────────────────────────────────────────────────────────

SWITCHES_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "config", "config.json"
)

_DEFAULT_SWITCHES = {
    "supertrend_enabled": True,
    "cab_enabled": True,
    # 203 removed — trend-follow handed off to SuperTrend bot
    "ghost_grid": {"201": True, "202": True, "204": True},
}


def load_switches(config_path: str) -> dict:
    try:
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
        sw = data.get("switches", {})
        return {
            "supertrend_enabled": bool(sw.get("supertrend_enabled", True)),
            "cab_enabled": bool(sw.get("cab_enabled", True)),
            # 203 removed — load_switches no longer exposes a 203 key
            "ghost_grid": {
                "201": bool(sw.get("ghost_grid", {}).get("201", True)),
                "202": bool(sw.get("ghost_grid", {}).get("202", True)),
                "204": bool(sw.get("ghost_grid", {}).get("204", True)),
            },
        }
    except Exception as e:
        logger.warning(
            f"load_switches: could not read {config_path} ({e}) — "
            f"defaulting to all-enabled"
        )
        return {k: (dict(v) if isinstance(v, dict) else v)
                for k, v in _DEFAULT_SWITCHES.items()}


# ─────────────────────────────────────────────────────────────
#  SESSION LOG  (fix-telemetry — ported from V1 unified_runner.py:222)
#
#  Deliberately a V2-specific filename. V1 owns unified_session_log.csv and the
#  two runners must never append to the same file. Until now V2 had no session
#  telemetry at all, so the two books could not be reconciled event-by-event.
# ─────────────────────────────────────────────────────────────

SESSION_LOG_FILE = "v2_session_log.csv"
SESSION_LOG_HEADER = [
    "timestamp", "bot", "action", "symbol", "magic",
    "r_multiple", "regime", "conviction", "virtual_layer_depth",
]
_csv_lock = threading.Lock()


def _init_session_log():
    if not os.path.isfile(SESSION_LOG_FILE):
        with open(SESSION_LOG_FILE, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(SESSION_LOG_HEADER)


def log_session_event(bot, action, symbol="", magic=0, r_multiple=None,
                      regime="", conviction=None, virtual_layer_depth=None):
    """Write one row to the V2 session log.

    Thread-safe via a dedicated csv lock, independent of the MT5 lock.
    Header and row shape are identical to V1's unified_session_log.csv so the
    two files can be concatenated for analysis.
    """
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    row = [
        ts, bot, action, symbol, magic or "",
        f"{r_multiple:.4f}" if r_multiple is not None else "",
        regime,
        f"{conviction:.2f}" if conviction is not None else "",
        virtual_layer_depth if virtual_layer_depth is not None else "",
    ]
    with _csv_lock:
        for _attempt in range(3):
            try:
                with open(SESSION_LOG_FILE, "a", newline="", encoding="utf-8") as f:
                    csv.writer(f).writerow(row)
                break
            except PermissionError:
                if _attempt < 2:
                    time.sleep(0.1)
                else:
                    logger.debug(
                        "Session log locked — skipping row (close the CSV in a viewer)"
                    )


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

    # fix-parity-account (V1 -> V2 alignment): V1 calls gateway.login() explicitly
    # against config.json -> accounts.demo (unified_runner.py:1124) and re-asserts
    # that session every HEARTBEAT_INTERVAL. V2 called initialize() alone, so it
    # silently inherited whichever account the terminal happened to be on. The two
    # runners could therefore never be pinned independently, and a terminal
    # re-login would redirect V2 without emitting a single log line.
    #
    # Config is loaded BEFORE initialize() for exactly this reason.
    config_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "config", "config.json"
    )
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return

    # The V2 account is pinned HERE rather than only in config.json because
    # config/config.json is gitignored (line 78), so it is a local-only file that
    # can be lost or recreated without the pin. accounts.v2_demo overrides these
    # defaults when present; the env vars below override both.
    V2_ACCOUNT_DEFAULT = {
        "login": 474228887,                 # NOT accounts.demo's 474167713
        "server": "Exness-MT5Trial15",
        "password": "",
        "mt5_path": None,
    }
    account_cfg = dict(V2_ACCOUNT_DEFAULT)
    account_cfg.update(config_data.get("accounts", {}).get("v2_demo", {}))
    # Env overrides mirror V1's MT5_PASSWORD / MT5_SERVER / MT5_PATH handling.
    for _env, _key in (("MT5_PASSWORD_V2", "password"),
                       ("MT5_SERVER_V2", "server"),
                       ("MT5_PATH_V2", "mt5_path")):
        if os.environ.get(_env):
            account_cfg[_key] = os.environ[_env]

    if not gateway.initialize(path=account_cfg.get("mt5_path") or args.mt5_path):
        logger.error("MT5 Initialization failed. Exiting.")
        return

    # Pin V2 to its OWN account. V1 and V2 share magic numbers (201/202/204/999555),
    # so they MUST NOT trade the same account — each would see the other's
    # positions as its own and manage them. accounts.v2_demo is a separate login
    # on the same demo server, which is why it is a distinct config key.
    if account_cfg.get("login") and account_cfg.get("password"):
        if not gateway.login(account_cfg["login"], account_cfg["password"],
                             account_cfg.get("server", "")):
            logger.error("MT5Gateway.login() failed for accounts.v2_demo. Exiting.")
            gateway.shutdown()
            return
    else:
        logger.warning(
            "ACCOUNT UNPINNED | accounts.v2_demo has no password in config.json and "
            "MT5_PASSWORD_V2 is unset — V2 will inherit the terminal's account. "
            "Set one of the two to pin it."
        )

    _acc0 = gateway.account_info()
    if _acc0:
        logger.warning(
            f"V2 CONNECTED | Account={_acc0.login} Balance={_acc0.balance:.2f} "
            f"Server={_acc0.server}"
        )
        _expect = account_cfg.get("login")
        if _expect and int(_acc0.login) != int(_expect):
            logger.critical(
                f"ACCOUNT MISMATCH | expected {_expect} but terminal is on "
                f"{_acc0.login} — V1 and V2 share magic numbers and must not "
                f"share an account. Set MT5_PASSWORD_V2 so V2 can log itself in."
            )

    # Use a separate heartbeat file for V2 to prevent conflict with V1
    common_files_dir = r"C:\Users\ABRAR\AppData\Roaming\MetaQuotes\Terminal\Common\Files"
    heartbeat_path = f"{common_files_dir}\\v2_heartbeat.txt"
    heartbeat = FailoverHeartbeat(heartbeat_path)
    heartbeat.start()

    kr = KnowledgeRegister()

    # fix-telemetry (V1 parity): V1 initialises unified_session_log.csv at startup
    # (unified_runner.py:1148). V2 previously wrote no session telemetry at all.
    _init_session_log()

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

    # fix-deploy-provenance: W4-W7 V2 SuperTrend showed zero trades and it took a
    # forensic audit to explain why — the bot module simply did not exist in the running
    # process until it was first imported at 2026-09-06 21:11, ten minutes before its
    # first fill. Absence of trades looks identical to a strategy that is silently
    # gated off, and the two demand opposite responses. Stamping the loaded module
    # mtimes at startup makes every future deployment boundary a one-line check.
    try:
        _prov = []
        for _name, _mod in (("supertrend", SuperTrendBot), ("ghost", GhostBot)):
            _f = getattr(sys.modules.get(_mod.__module__), "__file__", None)
            if _f and os.path.isfile(_f):
                _prov.append(f"{_name}={_f}@{datetime.fromtimestamp(os.path.getmtime(_f)):%Y-%m-%d %H:%M}")
        logger.info(f"DEPLOY_PROVENANCE | pid={os.getpid()} | " + " | ".join(_prov))
    except Exception as _pe:
        logger.debug(f"Deploy provenance log error: {_pe}")

    logger.info("All modules initialized. Entering deterministic tick loop.")

    # 3. Deterministic Tick Loop
    last_heartbeat_time = time.time()
    last_isolation_check = time.time()
    
    acc_info = gateway.account_info()
    daily_start_equity = acc_info.equity if acc_info else 0.0
    _dd_date = datetime.now().date()

    try:
        while True:
            t0 = time.time()

            # V1 parity: daily drawdown baseline resets each UTC day.
            # V2 previously sampled equity once at startup — a loss day
            # would leave entries blocked for the rest of the week.
            if datetime.now().date() != _dd_date:
                _dd_date = datetime.now().date()
                acc_new = gateway.account_info()
                if acc_new:
                    daily_start_equity = acc_new.equity
                    logger.info(f"Daily DD baseline reset | equity={daily_start_equity:.2f}")

            acc = gateway.account_info()
            if acc and daily_start_equity > 0:
                current_dd = (daily_start_equity - acc.equity) / daily_start_equity * 100.0
            else:
                current_dd = 0.0
                
            max_dd_pct = config_data.get("global_settings", {}).get("max_daily_loss_percent", 10.0)
            
            if current_dd >= max_dd_pct:
                logger.warning(f"CIRCUIT BREAKER: drawdown {current_dd:.2f}% >= {max_dd_pct:.1f}% — entries blocked")
                log_session_event(
                    "unified", "CIRCUIT_BREAKER",
                    r_multiple=round(-current_dd / 100.0, 4),
                )
            
            # Phase A: Oracle updates the KnowledgeRegister synchronously
            try:
                oracle.tick()
            except Exception as e:
                logger.error(f"Oracle tick error: {e}", exc_info=True)

            # fix-switches (V1 -> V2 alignment): V1 re-reads config/config.json on
            # every tick (unified_runner.py:454, :603) so a switch flip lands with
            # no redeploy — the contract the switches block's own _comment states.
            # Semantics preserved exactly: false blocks NEW entries only.
            switches = load_switches(config_path)

            # Phase B: Strategy Generation
            # SuperTrend (needs M30 data)
            # V1 parity: V1 get_data() fetches 1000 bars and drops NaN warmup
            # rows (~62). V2 previously fetched 250 -> 188 after dropna, which
            # is below the 200-bar minimum in generate_signal() — the bot could
            # never trade. 1000 bars keeps the shadow identical to V1.
            for bot in st_bots:
                try:
                    rates = gateway.copy_rates_from_pos(bot.config.symbol, mt5.TIMEFRAME_M30, 0, 1000)
                    if rates is not None and len(rates) >= 200:
                        df = pd.DataFrame(rates)
                        bot.execute_cycle(df, current_dd=current_dd, max_dd=max_dd_pct,
                                          allow_new_entry=switches["supertrend_enabled"])
                except Exception as e:
                    logger.error(f"SuperTrend cycle error ({bot.config.symbol}): {e}", exc_info=True)

            # Ghost (needs M1 data)
            try:
                rates = gateway.copy_rates_from_pos(ghost_cfg.symbol, mt5.TIMEFRAME_M1, 0, 50)
                if rates is not None and len(rates) >= 20:
                    df = pd.DataFrame(rates)
                    ghost_bot.execute_cycle(
                        df, current_dd=current_dd, max_dd=max_dd_pct,
                        allow_new_entry=switches["ghost_grid"]["202"],
                        allow_shadow=switches["ghost_grid"]["201"],
                        allow_cache=switches["ghost_grid"]["204"],
                    )
            except Exception as e:
                logger.error(f"Ghost cycle error: {e}", exc_info=True)
                
            # CAB (needs H4 data)
            # fix-switches (V1 parity): V1 gates CAB in the RUNNER, before the bot is
            # called at all (unified_runner.py:997, 'elif not switches["cab_enabled"]'),
            # and its comment records that manage_fluid_logic() keeps running
            # regardless. V2's CAB management lives in TradeManager Phase C below,
            # outside this loop, so skipping the entry pass here is exact V1 scoping.
            if not switches["cab_enabled"]:
                logger.debug("CAB entries blocked — cab_enabled switch is off")
            for bot in (cab_bots if switches["cab_enabled"] else []):
                try:
                    rates = gateway.copy_rates_from_pos(bot.config.symbol, mt5.TIMEFRAME_H4, 0, 50)
                    if rates is not None and len(rates) >= 5:
                        df = pd.DataFrame(rates)
                        df["time"] = pd.to_datetime(df["time"], unit="s")
                        bot.execute_cycle(df, current_dd=current_dd, max_dd=max_dd_pct)
                except Exception as e:
                    logger.error(f"CAB cycle error ({bot.config.symbol}): {e}", exc_info=True)

            # Phase C: Trade Management
            # V1 parity: SuperTrend manages its own positions inside
            # execute_cycle() (V1 run_cycle calls manage_open_positions itself).
            # Only CAB (999555) and Ghost (201/202/204) go through TradeManager.
            for m in [999555, 201, 202, 204]:
                try:
                    manager.manage_open_positions(m)
                except Exception as e:
                    logger.error(f"TradeManager error (magic={m}): {e}", exc_info=True)

            # Phase D: Heartbeat & Sleep
            if time.time() - last_heartbeat_time > 60:
                # fix-parity-reconnect (V1 -> V2 alignment): V1 calls
                # gateway.reconnect_if_needed() every HEARTBEAT_INTERVAL from its main
                # health loop (unified_runner.py:1234 and :1318) and forces a reconnect
                # first when is_healthy flips. MT5Gateway.reconnect_if_needed() existed
                # in V2 with NO caller at all, so a dropped terminal session left V2
                # silently unable to trade while V1 healed itself.
                if not gateway.is_healthy:
                    logger.error(
                        f"IPC failure ({gateway._ipc_fail_count} consecutive) "
                        f"— forcing reconnect"
                    )
                    gateway._ipc_fail_count = 0   # reset so reconnect can proceed
                    gateway.reconnect_if_needed(
                        path=account_cfg.get("mt5_path"),
                        login=account_cfg.get("login"),
                        password=account_cfg.get("password"),
                        server=account_cfg.get("server"),
                    )
                elif not gateway.reconnect_if_needed(
                    path=account_cfg.get("mt5_path"),
                    login=account_cfg.get("login"),
                    password=account_cfg.get("password"),
                    server=account_cfg.get("server"),
                ):
                    logger.critical("MT5 connection could not be restored")

                acc = gateway.account_info()
                if acc:
                    logger.info(f"Runner Heartbeat | Equity={acc.equity:.2f} | Profit={acc.profit:.2f} | DD={current_dd:.2f}%")
                    log_session_event(
                        "unified", "EQUITY_HEARTBEAT",
                        r_multiple=round(acc.profit / max(acc.balance, 1), 4),
                    )
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
