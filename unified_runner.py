"""
unified_runner.py — Unified Bot Runner
=======================================
Task: pu-runner (Session 1 — CRITICAL)

Runs all three bots through a single MT5 connection via MT5Gateway.

THREAD ARCHITECTURE:
    Thread 0  main       60s equity heartbeat + health monitor
    Thread 1  SuperTrend 30s cycle (M30 strategy — no rush)
    Thread 2  Ghost      1s  cycle (M1 hunter — needs fast loop)
    Thread 3  CAB        15s cycle (position watcher)

All threads share one MT5Gateway instance. The gateway's internal
threading.Lock serialises every MT5 API call — no other locking needed
at the runner level.

DEMO MODE (enabled by default):
    - SuperTrend equity_filter_enabled = False  (no pause on drawdown)
    - No global position cap enforced           (watch everything)
    - Ghost daily_pairs cap = 999               (effectively unlimited)
    - No spread abort on Ghost hunter fire      (log SKIP_SPREAD, don't abort)
    See DEMO_MODE flag below — set False before going live.

UNIFIED SESSION LOG:
    One CSV row per action across all bots. Columns:
        timestamp | bot | action | symbol | magic | r_multiple |
        regime | conviction | virtual_layer_depth
    Written by log_session_event() — callable from any bot thread.
    Thread-safe via a dedicated csv_lock (separate from MT5 lock).

MAGIC NUMBER ISOLATION:
    SuperTrend : 101234, 201567, 301890, 401213
    Ghost Grid  : 201, 202, 204  (203 removed — trend-follow handed to SuperTrend)
    CAB Watcher : 999555
    Each bot only manages its own magic numbers. Verified in smoke test.

STARTUP SEQUENCE:
    1. MT5Gateway.initialize() + login()
    2. Start Ghost thread  (fastest loop — start first)
    3. Start CAB thread
    4. Start SuperTrend thread
    5. Main thread enters equity heartbeat loop
    6. KeyboardInterrupt → shutdown flag → all threads exit cleanly

USAGE:
    python unified_runner.py [--demo] [--account demo|live]
    python unified_runner.py --help
"""

import csv
import json
import logging
import logging.handlers
import os
import sys
import threading
import time
import argparse
from datetime import datetime
from pathlib import Path

# ── Gateway import ────────────────────────────────────────────────────────────
from mt5_gateway import MT5Gateway
from core.knowledge_register import KnowledgeRegister
from core.shared_intelligence import MarketPulseEngine
from core.kpi_ledger import write_kpi_snapshot

# ── Conditional bot imports (graceful on missing deps for testing) ─────────────
try:
    from core.supertrend_bot import SuperTrendBot, Config as STConfig, MultiPairRunner
    SUPERTREND_AVAILABLE = True
except Exception as _st_err:
    SUPERTREND_AVAILABLE = False
    import logging as _l
    _l.getLogger("UnifiedRunner").warning(
        f"SuperTrend import failed: {_st_err} — "
        f"install missing deps: pip install TA-Lib scikit-learn"
    )

# Ghost and CAB modules are imported inside their thread functions
# so set_gateway() can be called immediately after import.
# CAB uses importlib because the filename contains a hyphen.
GHOST_HUNTER_AVAILABLE  = True   # checked at thread startup
GHOST_WATCHER_AVAILABLE = True
CAB_AVAILABLE           = True

# ──────────────────────────────────────────────────────────────────────────────
#  CONFIGURATION
# ──────────────────────────────────────────────────────────────────────────────

DEMO_MODE = True          # Set False before live deployment (Phase 5)

SUPERTREND_INTERVAL  = 30    # seconds between ST cycles
GHOST_INTERVAL       = 1     # seconds between Ghost hunter ticks
CAB_INTERVAL         = 15    # seconds between CAB watcher cycles
CAB_ENTRY_INTERVAL   = 30    # seconds between CAB entry checks (H4 — no rush)
HEARTBEAT_INTERVAL   = 60    # seconds between main-thread health checks
MAX_GLOBAL_POSITIONS = 30    # fix 5: Circuit Breaker Blindspot (max system open positions)

SESSION_LOG_FILE     = "unified_session_log.csv"
LOG_FILE             = "unified_runner.log"

# fix-regimegate (Tier 3 #6): Ghost Grid is a mean-reversion strategy — the
# regime complementarity map has always said it should be active in
# RANGING/STABLE and stand down in TRENDING, but the actual probe-arming
# logic in ghost_hunter_thread() had no regime check at all before this fix;
# only the 202/203 *leg* gates were regime/conviction-aware, not the decision
# to arm a probe in the first place. UNKNOWN is blocked too — that means the
# M1 regime engine hasn't got enough data yet (cold start), which is not a
# state we want to be opening new probes in either.
GHOST_ARM_BLOCKED_REGIMES = {"TRENDING_UP", "TRENDING_DOWN", "UNKNOWN"}

# Magic number registry — used by isolation check
def _load_supertrend_magics():
    try:
        import json
        from pathlib import Path
        cfg_path = Path(__file__).parent / "config" / "config.json"
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        m = {int(v["magic_number"]) for v in data.get("symbols", {}).values() if "magic_number" in v}
        return m if m else {101234, 201567, 301890, 401213}
    except Exception:
        return {101234, 201567, 301890, 401213}

MAGIC_SUPERTREND = _load_supertrend_magics()
MAGIC_GHOST      = {201, 202, 204}
MAGIC_CAB        = {999555}
ALL_MAGIC        = MAGIC_SUPERTREND | MAGIC_GHOST | MAGIC_CAB

# ──────────────────────────────────────────────────────────────────────────────
#  LOGGING
# ──────────────────────────────────────────────────────────────────────────────

def setup_logging(level: str = "INFO"):
    """
    Two-level logging:
      File (logs/unified_runner.log) : INFO+ — full detail for post-analysis
      Console (stdout)               : WARNING+ — errors and key events only
    Gate evaluations every 1s, regime cycles, cache hits go to file only.
    """
    Path("logs").mkdir(exist_ok=True)
    fmt = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s | %(message)s")

    # File handler: full INFO detail
    fh = logging.handlers.RotatingFileHandler(
        f"logs/{LOG_FILE}", maxBytes=5*1024*1024, backupCount=5, encoding="utf-8"
    )
    fh.setFormatter(fmt)
    fh.setLevel(logging.INFO)

    # Console handler: WARNING+ only
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(message)s"))
    ch.setLevel(logging.WARNING)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(fh)
    root.addHandler(ch)

    # Suppress noisy per-tick loggers from console (still go to file)
    for noisy in ["hunter", "brain"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)

logger = logging.getLogger("UnifiedRunner")

# ──────────────────────────────────────────────────────────────────────────────
#  UNIFIED SESSION LOG
# ──────────────────────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────────────────────
#  RUNTIME SWITCHES  (fix-switches, Tier 3 #7)
# ──────────────────────────────────────────────────────────────────────────────
# Re-read from config.json on every call rather than cached at startup — this
# is what makes it a live toggle instead of a redeploy. The file read is a few
# hundred bytes and happens at most once per thread cycle (1s-30s depending on
# thread), which is negligible next to the MT5 API calls each cycle already
# makes. Defaults are all-enabled and fail open to all-enabled on any error —
# a switches bug should never be the thing that silently stops managing an
# open position; that failure mode is exactly what fix-cabsym addressed above.

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
        logging.getLogger("UnifiedRunner").warning(
            f"load_switches: could not read {config_path} ({e}) — "
            f"defaulting to all-enabled"
        )
        return dict(_DEFAULT_SWITCHES)


SESSION_LOG_HEADER = [
    "timestamp", "bot", "action", "symbol", "magic",
    "r_multiple", "regime", "conviction", "virtual_layer_depth",
]
_csv_lock = threading.Lock()


def _init_session_log():
    if not os.path.isfile(SESSION_LOG_FILE):
        with open(SESSION_LOG_FILE, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(SESSION_LOG_HEADER)


def log_session_event(
    bot: str,
    action: str,
    symbol: str = "",
    magic: int = 0,
    r_multiple: float = None,
    regime: str = "",
    conviction: float = None,
    virtual_layer_depth: int = None,
):
    """
    Write one row to the unified session log.
    Thread-safe — uses dedicated csv_lock (independent of MT5 lock).

    bot    : "supertrend" | "ghost" | "cab"
    action : e.g. "BUY_ENTRY", "SELL_ENTRY", "CLOSE_DEAD", "REAPER",
             "HARVESTER", "PROTECTOR", "GRID_TP", "GRID_STOP",
             "GHOST_CACHE_FIRE", "IDLE"
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
                    time.sleep(0.1)   # brief wait — viewer may release lock
                else:
                    logger.debug(
                        f"Session log locked — skipping row "
                        f"(close the CSV in any viewer)"
                    )


# ──────────────────────────────────────────────────────────────────────────────
#  SHARED STATE  (read by main thread heartbeat, written by bot threads)
# ──────────────────────────────────────────────────────────────────────────────

class SharedState:
    """
    Lightweight in-memory store replacing brain_state_live.csv IPC.
    Ghost Hunter reads market state here instead of from a CSV file.
    Written by Ghost Watcher thread; read by Ghost Hunter thread.
    Protected by a simple RLock (readers/writers are infrequent).

    Also carries the daily equity circuit breaker flag (arch-equity-cb).
    All bot threads read entries_allowed before opening new positions.
    The main thread writes it based on daily drawdown vs max_daily_loss_percent.
    """
    def __init__(self):
        self._lock = threading.RLock()
        self.conviction:  float = 50.0
        self.adx:         float = 0.0
        self.atr:         float = 0.0
        self.regime:      str   = "UNKNOWN"
        self.updated_at:  float = 0.0
        # Adaptive thresholds (replace adaptive_thresholds_live.csv)
        self.adaptive: dict = {}
        # ── arch-equity-cb: daily circuit breaker ─────────────────────────────
        # Set False by main thread when daily drawdown exceeds threshold.
        # All bot threads check this before opening new positions.
        # Resets to True at session start (each run of unified_runner).
        self.entries_allowed:   bool  = True
        self.daily_start_equity: float = 0.0   # sampled once at startup
        self.cb_fired_at:        float = 0.0   # timestamp when CB fired
        self.cb_reason:          str   = ""

    def update_market_state(self, conviction, adx, atr, regime):
        with self._lock:
            self.conviction = conviction
            self.adx        = adx
            self.atr        = atr
            self.regime     = regime
            self.updated_at = time.time()

    def get_market_state(self) -> dict:
        with self._lock:
            return {
                "conviction": self.conviction,
                "adx":        self.adx,
                "atr":        self.atr,
                "regime":     self.regime,
                "updated_utc": datetime.utcfromtimestamp(
                    self.updated_at
                ).strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else "",
            }

    def update_adaptive(self, thresholds: dict):
        with self._lock:
            self.adaptive = dict(thresholds)

    def get_adaptive(self) -> dict:
        with self._lock:
            return dict(self.adaptive)

    # ── arch-equity-cb: circuit breaker interface ──────────────────────────
    def set_daily_start_equity(self, equity: float):
        with self._lock:
            self.daily_start_equity = equity

    def trip_circuit_breaker(self, reason: str):
        """Called by main thread when drawdown exceeds threshold."""
        with self._lock:
            if self.entries_allowed:   # log transition once only
                self.entries_allowed = False
                self.cb_fired_at     = time.time()
                self.cb_reason       = reason

    def reset_circuit_breaker(self):
        """Call at start of new session (new day). Not auto-reset — deliberate."""
        with self._lock:
            self.entries_allowed    = True
            self.daily_start_equity = 0.0
            self.cb_fired_at        = 0.0
            self.cb_reason          = ""

    def check_entries_allowed(self) -> bool:
        with self._lock:
            return self.entries_allowed


# ──────────────────────────────────────────────────────────────────────────────
#  SHUTDOWN COORDINATOR
# ──────────────────────────────────────────────────────────────────────────────

class ShutdownEvent:
    """Simple wrapper so threads can check a shared stop signal."""
    def __init__(self):
        self._event = threading.Event()

    def request(self):
        self._event.set()

    def is_set(self) -> bool:
        return self._event.is_set()

    def wait(self, timeout: float = None):
        self._event.wait(timeout)


# ──────────────────────────────────────────────────────────────────────────────
#  BOT THREAD WRAPPERS
#  Each wrapper is a function that loops independently.
#  They receive the shared gateway and stop_event.
#  In the current phase the bots have their own MT5 connections (legacy);
#  Session 2 will port them to use gateway.X() calls instead.
#  For now the wrappers simply invoke the existing entry points and allow
#  the unified runner to control the lifecycle.
# ──────────────────────────────────────────────────────────────────────────────

def supertrend_thread(gateway: MT5Gateway, shared: SharedState,
                      stop: ShutdownEvent, config_path: str,
                      account: dict, demo: bool):
    """
    SuperTrend wrapper — runs MultiPairRunner.run_cycle_all() every
    SUPERTREND_INTERVAL seconds until stop is requested.

    In demo mode equity_filter_enabled=False so drawdown doesn't pause entries.
    Once pu-st-port is complete, this thread will use gateway directly.
    Until then it relies on SuperTrend's own MT5 initialisation.
    """
    log = logging.getLogger("Thread.SuperTrend")
    log.info("SuperTrend thread starting")

    if not SUPERTREND_AVAILABLE:
        log.warning("SuperTrend module not importable — thread exiting")
        return

    try:
        import MetaTrader5 as mt5
        with open(config_path) as f:
            config_data = json.load(f)
        symbols = list(config_data.get("symbols", {}).keys())
        gs      = config_data.get("global_settings", {})

        bots = []
        for sym in symbols:
            sym_cfg = config_data["symbols"][sym]
            cfg = STConfig(
                symbol=sym,
                magic_number=sym_cfg.get("magic_number", 123456),
                risk_percent=sym_cfg.get("risk_percent", 1.0),
                max_positions=gs.get("max_positions_per_symbol", 4),  # arch-cap-st
                session_gate_enabled=True,
                conviction_gate_enabled=False,   # observation mode
                use_m15_atr_for_sl_buffer=True,
                si_weight_cluster=sym_cfg.get("si_weight_cluster", 0.40),
                si_weight_regime=sym_cfg.get("si_weight_regime", 0.25),
                si_weight_adx=sym_cfg.get("si_weight_adx", 0.20),
                si_weight_volume=sym_cfg.get("si_weight_volume", 0.15),
                max_lot_demo_cap=gs.get("st_max_lot_demo_cap", 0.01),
            )
            bot = SuperTrendBot(cfg, gateway=gateway)
            bot.is_connected = True
            bots.append(bot)

        runner = MultiPairRunner(
            bots=bots,
            interval_seconds=SUPERTREND_INTERVAL,
            # arch-global-cap: global cap removed. Per-symbol max_positions=4
            # on each bot already bounds exposure. Global cap was double-counting
            # protection and blocking uncorrelated cross-pair opportunities.
            # Daily equity circuit breaker in main thread is the correct
            # global safety mechanism — not a position count.
            max_total_positions=999,
            dry_run=False,
            gateway=gateway
        )

        while not stop.is_set():
            cycle_start = time.time()
            try:
                # arch-equity-cb: pass circuit breaker state to runner
                # Watcher logic always runs — only new entries are blocked
                # fix-switches: same principle — supertrend_enabled=False only
                # blocks new entries, manage_open_positions still runs regardless
                cb_allows = shared.check_entries_allowed()
                switches  = load_switches(config_path)
                pos_count = len(gateway.positions_get() or [])
                allow_entries = cb_allows and switches["supertrend_enabled"] and pos_count < MAX_GLOBAL_POSITIONS
                runner.run_cycle_all(circuit_breaker_allows=allow_entries)
                log_session_event("supertrend", "CYCLE_COMPLETE",
                                  regime=shared.get_market_state().get("regime", ""))
            except Exception as e:
                log.error(f"Cycle error: {e}", exc_info=True)
            elapsed = time.time() - cycle_start
            stop.wait(max(0, SUPERTREND_INTERVAL - elapsed))

    except Exception as e:
        log.error(f"SuperTrend thread fatal: {e}", exc_info=True)
    finally:
        log.info("SuperTrend thread stopped")


def ghost_watcher_thread(gateway: MT5Gateway, shared: SharedState,
                         stop: ShutdownEvent):
    """
    Ghost Watcher (Brain) wrapper — runs every HEARTBEAT_INTERVAL.
    Writes market state to shared object instead of brain_state_live.csv.
    (Full IPC replacement is pu-noipc in Session 2; this is the bridge.)
    """
    log = logging.getLogger("Thread.GhostWatcher")
    log.info("Ghost Watcher thread starting")

    if not GHOST_WATCHER_AVAILABLE:
        log.warning("Ghost Watcher module not importable — thread exiting")
        return

    try:
        import ghost_super.sniper_watcher as sw
        sw.set_gateway(gateway)   # wire shared MT5 connection
        log.warning("Ghost Watcher: gateway wired in")
        while not stop.is_set():
            try:
                # Read market state and push to shared object
                conviction, adx, atr, regime = sw.get_market_state()
                shared.update_market_state(conviction, adx, atr, regime)

                # Position management (the watcher's core job)
                positions = gateway.positions_get(symbol=sw.SYMBOL)
                if positions:
                    # Change 5: Grid-level exits — 204 only (was missing from live thread)
                    sw.manage_grid_logic(positions, conviction, adx, atr, regime)
                    # Per-position dispatch (leg TP + BE-lock for 201/202/204)
                    for pos in positions:
                        manager = sw.MAGIC_MANAGERS.get(pos.magic)
                        if manager:
                            manager(pos, conviction, adx, atr, regime)

                sw.compute_adaptive_thresholds()
                shared.update_adaptive(sw.read_adaptive_thresholds())
                log_session_event("ghost", "WATCHER_CYCLE", regime=regime,
                                  conviction=conviction)
            except Exception as e:
                log.error(f"Watcher cycle error: {e}", exc_info=True)

            # KR cleanup: unregister theses for positions broker closed via SL/TP
            # Mirrors the pattern in cab_watcher.py manage_fluid_logic() stale cleanup
            try:
                all_ghost_positions = gateway.positions_get()
                live_ghost_tickets = {
                    p.ticket for p in (all_ghost_positions or [])
                    if p.magic in {201, 202, 204}
                }
                from core.knowledge_register import KnowledgeRegister
                kr_instance = KnowledgeRegister()
                with kr_instance._lock:
                    ghost_registered = {
                        t for t, thesis in kr_instance._theses.items()
                        if thesis and getattr(thesis, 'magic', None) in {201, 202, 204}
                    }
                broker_closed = ghost_registered - live_ghost_tickets
                for ticket in broker_closed:
                    kr_instance.unregister_trade_thesis(ticket)
                    log.debug(f"KR cleanup: thesis #{ticket} unregistered (broker-closed)")
            except Exception as _kr_e:
                log.debug(f"KR cleanup scan error: {_kr_e}")

            stop.wait(2)   # 2s pulse matching v3.1 heartbeat
    except Exception as e:
        log.error(f"Ghost Watcher thread fatal: {e}", exc_info=True)
    finally:
        log.info("Ghost Watcher thread stopped")


def ghost_hunter_thread(gateway: MT5Gateway, shared: SharedState,
                        stop: ShutdownEvent, demo: bool, config_path: str):
    """
    Ghost Hunter wrapper — tight 1s loop for probe detection.
    Reads brain state from shared object (no CSV read).
    """
    log = logging.getLogger("Thread.GhostHunter")
    log.info("Ghost Hunter thread starting")

    if not GHOST_HUNTER_AVAILABLE:
        log.warning("Ghost Hunter module not importable — thread exiting")
        return

    try:
        import ghost_super.ghost_sniper as gh
        # fix-204wire: this was missing entirely. ghost_cache.py is fully
        # built and unit-tested (10/10 pass) but was never instantiated or
        # updated anywhere in this thread, which is the actual live probe
        # loop — the standalone gh.run_hunter() that DOES wire it in is not
        # what runs under unified_runner. Result: magic 204 has fired zero
        # times across the entire demo run, and Gate ② (204 vs 202) has had
        # no data to evaluate. This import + the ARMED/update/reset wiring
        # below brings the live thread in line with the reference design.
        from ghost_super.ghost_cache import GhostCache, N_LAYERS_DEFAULT
        gh.set_gateway(gateway)   # wire shared MT5 connection
        log.warning("Ghost Hunter: gateway wired in")
        import MetaTrader5 as mt5
        from datetime import date

        if demo:
            gh.MAX_DAILY_PAIRS = 999

        armed, break_level, probe_extreme = None, 0.0, 0.0
        ghost_cache = None   # fix-204wire: tracks the active probe's virtual grid
        daily_pairs = 0
        today = date.today()

        while not stop.is_set():
            try:
                # Daily reset
                if date.today() != today:
                    log.info(f"Daily reset: pairs_yesterday={daily_pairs}")
                    daily_pairs, today = 0, date.today()

                tick  = gateway.symbol_info_tick(gh.SYMBOL)
                rates = gateway.copy_rates_from_pos(gh.SYMBOL, mt5.TIMEFRAME_M1, 0, 50)
                if not tick or rates is None or len(rates) < 20:
                    stop.wait(GHOST_INTERVAL)
                    continue

                import pandas as pd
                df            = pd.DataFrame(rates)
                atr           = gh._get_atr(df)
                dynamic_step  = max(atr * gh.ATR_STEP_MULTIPLIER, gh.ATR_STEP_FLOOR)
                current_price = (tick.bid + tick.ask) / 2
                spread        = tick.ask - tick.bid

                # Read brain state from shared (no CSV I/O)
                bs    = shared.get_market_state()
                gates = gh.apply_gates(bs)

                # fix-switches: re-read every tick — cheap, and this is what
                # makes it a live toggle instead of a redeploy
                switches = load_switches(config_path)

                if armed is None:
                    # fix-regimegate: don't arm a new probe when the shared
                    # regime read says conditions don't fit Ghost Grid's
                    # mean-reversion premise. This only gates NEW arming —
                    # an already-armed probe is left to run to its natural
                    # exit even if regime drifts mid-probe; changing that too
                    # is a bigger behavioral change than today's fix covers.
                    current_regime = bs.get("regime", "UNKNOWN")
                    if current_regime in GHOST_ARM_BLOCKED_REGIMES:
                        stop.wait(GHOST_INTERVAL)
                        continue

                    recent_high = df["high"].iloc[-5:].max()
                    recent_low  = df["low"].iloc[-5:].min()

                    # F6 Cross-bot gate: block UP_PROBE when ST holds confirmed LONG
                    st_long_active = False
                    try:
                        from core.knowledge_register import KnowledgeRegister
                        kr = KnowledgeRegister()
                        for thesis in kr._theses.values():
                            if (thesis.symbol == "XAUUSDm" and 
                                thesis.bot_id in ("SuperTrend", "ST") and
                                thesis.direction == 1):
                                st_long_active = True
                                break
                    except Exception:
                        pass  # fail open — never block on KR read failure
                    
                    if gh.SYMBOL == "XAUUSDm" and st_long_active and current_price > recent_high:
                        log.info(
                            f"GHOST_ARM_BLOCKED_ST_LONG | "
                            f"price={round(current_price,3)} | "
                            f"ST LONG thesis active on XAUUSDm — suppressing UP_PROBE"
                        )
                        # Skip arming, continue loop
                        stop.wait(1)
                        continue

                    # F15: block DOWN_PROBE when H4 structural direction is DOWN
                    try:
                        h4_dir = gh._get_h4_direction()
                    except Exception:
                        h4_dir = "UNKNOWN"

                    if current_price < recent_low and h4_dir == "DOWN":
                        log.info(
                            f"GHOST_ARM_BLOCKED_H4_DOWN | "
                            f"price={round(current_price,3)} | "
                            f"h4={h4_dir} — DOWN_PROBE suppressed"
                        )
                        stop.wait(GHOST_INTERVAL)
                        continue

                    # H22 NY_OVERLAP session gate: block all probe arming during NY_OVERLAP
                    # Evidence: three consecutive weeks avg P&L < -$0.68/tr, n>=10 each week
                    try:
                        _current_session = gh.get_session()
                    except Exception:
                        _current_session = "UNKNOWN"
                    if _current_session == "NY_OVERLAP":
                        log.info(
                            f"GHOST_ARM_BLOCKED_SESSION | "
                            f"session={_current_session} | "
                            f"price={round(current_price,3)} — probe arming suppressed"
                        )
                        stop.wait(GHOST_INTERVAL)
                        continue

                    if current_price > recent_high:
                        armed, probe_extreme = "UP_PROBE", current_price
                        break_level = current_price - dynamic_step
                        ghost_cache = GhostCache(
                            probe_direction="UP_PROBE",
                            probe_origin=break_level,
                            probe_extreme=current_price,
                            atr_step=dynamic_step,
                            n_layers=N_LAYERS_DEFAULT,
                        )
                        gh.log_event("ARMED", {
                            "price":          round(current_price, 3),
                            "atr_at_fill":    round(atr, 5),
                            "spread":         round(spread, 3),
                            "comment":        "UP_PROBE",
                            "grid_step_used": round(dynamic_step, 5),
                            "h4_direction_at_arm": gh._get_h4_direction(),
                            "kr_regime_at_arm":    bs.get("regime", ""),
                        })
                        log.info(f"ARMED UP | price={current_price:.3f}")
                    elif current_price < recent_low:
                        armed, probe_extreme = "DOWN_PROBE", current_price
                        break_level = current_price + dynamic_step
                        ghost_cache = GhostCache(
                            probe_direction="DOWN_PROBE",
                            probe_origin=break_level,
                            probe_extreme=current_price,
                            atr_step=dynamic_step,
                            n_layers=N_LAYERS_DEFAULT,
                        )
                        gh.log_event("ARMED", {
                            "price":          round(current_price, 3),
                            "atr_at_fill":    round(atr, 5),
                            "spread":         round(spread, 3),
                            "comment":        "DOWN_PROBE",
                            "grid_step_used": round(dynamic_step, 5),
                            "h4_direction_at_arm": gh._get_h4_direction(),
                            "kr_regime_at_arm":    bs.get("regime", ""),
                        })
                        log.info(f"ARMED DN | price={current_price:.3f}")
                else:
                    if armed == "UP_PROBE":
                        if current_price > probe_extreme:
                            probe_extreme = current_price
                            break_level = current_price - dynamic_step
                        trigger = current_price < break_level
                    else:
                        if current_price < probe_extreme:
                            probe_extreme = current_price
                            break_level = current_price + dynamic_step
                        trigger = current_price > break_level

                    # fix-204wire: update the virtual grid every tick the probe is
                    # still open and NOT currently triggering 201/202/203 — mirrors
                    # ghost_sniper.py's gc-hunter block exactly. GhostCache.update()
                    # self-guards against firing twice (entry_fired/invalidated), so
                    # no extra bookkeeping is needed here beyond calling it.
                    if ghost_cache is not None and not trigger and switches["ghost_grid"]["204"]:
                        gc_signal = ghost_cache.update(current_price, atr)
                        if gc_signal is not None:
                            gc_type = (mt5.ORDER_TYPE_SELL
                                       if gc_signal["order_type"] == "SELL"
                                       else mt5.ORDER_TYPE_BUY)
                            success = gh.send_order(
                                gc_type, gc_signal["sl"], 0.0,
                                gh.MAGIC_GHOST_CACHE, "SNIPER_GC",
                                atr, armed, "GHOST_CACHE", bs, gates,
                            )
                            if not success:
                                log.warning(f"GHOST_CACHE_FIRE_FAILED magic=204 | {gh.SYMBOL}")
                            else:
                                log.warning(
                                    f"GHOST_CACHE_FIRE magic=204 | "
                                f"layer_depth={gc_signal['virtual_layer_depth']} | "
                                f"sl={gc_signal['sl']:.3f}"
                            )
                            log_session_event("ghost", "GHOST_CACHE_FIRE",
                                              symbol=gh.SYMBOL,
                                              magic=gh.MAGIC_GHOST_CACHE,
                                              regime=bs.get("regime", ""),
                                              conviction=float(bs.get("conviction", 0)),
                                              virtual_layer_depth=gc_signal["virtual_layer_depth"])

                    if trigger:
                        # -- M1 retrace structure at fire (LOGGING ONLY) ------
                        # Deliberately placed BEFORE the spread / daily-cap /
                        # circuit-breaker guards so quality is captured even on
                        # blocked fires. Features for the offline win/loss
                        # classifier; try/except keeps it out of the fire path.
                        try:
                            _retrace_rates = gh._api().copy_rates_from_pos(
                                gh.SYMBOL, mt5.TIMEFRAME_M1, 0, 5
                            )
                            committed_bars = 0
                            retrace_body_ratio = 0.0
                            if _retrace_rates is not None and len(_retrace_rates) >= 2:
                                # Direction of retrace: UP_PROBE fires SELL, so reversal bars
                                # are bearish (close < open). DOWN_PROBE fires BUY, reversal bars bullish.
                                for _bar in _retrace_rates[-3:]:
                                    _bar_bull = _bar["close"] > _bar["open"]
                                    _bar_range = max(_bar["high"] - _bar["low"], 0.0001)
                                    _bar_body = abs(_bar["close"] - _bar["open"])
                                    _body_ratio = _bar_body / _bar_range

                                    if armed == "UP_PROBE" and not _bar_bull and _body_ratio > 0.35:
                                        committed_bars += 1
                                    elif armed == "DOWN_PROBE" and _bar_bull and _body_ratio > 0.35:
                                        committed_bars += 1

                                # Body ratio of the triggering bar (most recent completed)
                                _last = _retrace_rates[-2]
                                _last_range = max(_last["high"] - _last["low"], 0.0001)
                                retrace_body_ratio = abs(_last["close"] - _last["open"]) / _last_range

                            log.info(
                                f"GHOST_FIRE_QUALITY | {armed} | "
                                f"committed_reversal_bars={committed_bars}/3 | "
                                f"trigger_bar_body_ratio={retrace_body_ratio:.3f} | "
                                f"atr={round(atr,5)} | "
                                f"conviction={round(float(bs.get('conviction', 50)),1)} | "
                                f"adx={round(float(bs.get('adx', 0)),2)}"
                            )
                        except Exception as _gq:
                            log.debug(f"Ghost fire quality log error: {_gq}")

                        if spread > gh.SPREAD_MAX and not demo:
                            log.info(f"SKIP_SPREAD spread={spread:.3f}")
                            log_session_event("ghost", "SKIP_SPREAD",
                                              symbol=gh.SYMBOL,
                                              regime=bs.get("regime", ""),
                                              conviction=float(bs.get("conviction", 0)))
                            armed = None
                            ghost_cache = None
                        elif daily_pairs >= gh.MAX_DAILY_PAIRS:
                            armed = None
                            ghost_cache = None
                        elif not shared.check_entries_allowed():
                            # arch-equity-cb: circuit breaker active — skip fire
                            log.warning(
                                f"GHOST FIRE BLOCKED — circuit breaker active "
                                f"({shared.cb_reason})"
                            )
                            log_session_event("ghost", "SKIP_CIRCUIT_BREAKER",
                                              symbol=gh.SYMBOL,
                                              regime=bs.get("regime", ""))
                            armed = None
                            ghost_cache = None
                        else:
                            # Fire legs via existing send_order
                            dir_rev = (mt5.ORDER_TYPE_SELL if armed == "UP_PROBE"
                                       else mt5.ORDER_TYPE_BUY)
                            # fix-sltight: reads gh.SCALP_REV_SL_ATR_MULT (0.35,
                            # was 0.2 inline here) so this thread and the
                            # standalone reference in ghost_sniper.py can never
                            # drift apart on this value again.
                            sl_dist = gh.SCALP_REV_SL_ATR_MULT * atr
                            sl_rev  = (probe_extreme + sl_dist if armed == "UP_PROBE"
                                       else probe_extreme - sl_dist)
                            legs_fired_this_probe = 0
                            
                            if gates[201] and switches["ghost_grid"]["201"]:
                                # Shadow leg fires 100% of the time, bypasses MAX_LEGS limit, does not consume pos_count
                                success = gh.send_order(dir_rev, sl_rev, 0.0,
                                              gh.MAGIC_SCALP, "SNIPER_S",
                                              atr, armed, "SCALP", bs, gates, is_shadow=True)
                                if success:
                                    log_session_event("ghost", "FIRE_201_VIRTUAL",
                                                      symbol=gh.SYMBOL,
                                                      magic=gh.MAGIC_SCALP)
                                    # Do NOT increment legs_fired_this_probe
                                    # Do NOT increment pos_count
                                else:
                                    log_session_event("ghost", "FIRE_FAILED_VIRTUAL", symbol=gh.SYMBOL, magic=gh.MAGIC_SCALP)
                            
                            # Fix 5: circuit breaker blindspot max limit
                            pos_count = len(gateway.positions_get() or [])
                            
                            # Prioritize 202
                            # verified: reads gh.MAX_LEGS_PER_PROBE from ghost_sniper module constant
                            if gates[202] and switches["ghost_grid"]["202"] and legs_fired_this_probe < gh.MAX_LEGS_PER_PROBE and pos_count < MAX_GLOBAL_POSITIONS:
                                success = gh.send_order(dir_rev, sl_rev, 0.0,
                                              gh.MAGIC_REVERSAL, "SNIPER_R",
                                              atr, armed, "REVERSAL", bs, gates)
                                if success:
                                    log_session_event("ghost", "FIRE_202",
                                                      symbol=gh.SYMBOL,
                                                      magic=gh.MAGIC_REVERSAL,
                                                      regime=bs.get("regime", ""))
                                    legs_fired_this_probe += 1
                                else:
                                    log_session_event("ghost", "FIRE_FAILED", symbol=gh.SYMBOL, magic=gh.MAGIC_REVERSAL)
                                pos_count += (1 if success else 0)
                                
                            # Leg 203 (Trend-Follow) removed in v5.2:
                            # SuperTrend bot (si_confirmed=0.55) handles all trend entries.
                            daily_pairs += 1
                            armed = None
                            ghost_cache = None
                            stop.wait(gh.COOLDOWN_SECONDS)
                            continue

            except Exception as e:
                log.error(f"Hunter tick error: {e}", exc_info=True)
            stop.wait(GHOST_INTERVAL)

    except Exception as e:
        log.error(f"Ghost Hunter thread fatal: {e}", exc_info=True)
    finally:
        log.info("Ghost Hunter thread stopped")


def cab_watcher_thread(gateway: MT5Gateway, shared: SharedState,
                       stop: ShutdownEvent):
    """
    CAB Watcher wrapper — runs manage_fluid_logic() every CAB_INTERVAL.
    After pu-cab-port it will use gateway instead of direct mt5 calls.
    """
    log = logging.getLogger("Thread.CAB")
    log.info("CAB Watcher thread starting")

    if not CAB_AVAILABLE:
        log.warning("CAB Watcher module not importable — thread exiting")
        return

    try:
        # CAB filename contains a hyphen — use importlib for safe loading
        import importlib.util as _ilu
        _cab_path = Path(__file__).parent / "cab_super" / "cab_watcher.py"
        _spec = _ilu.spec_from_file_location("cab_watcher", _cab_path)
        cab = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(cab)
        cab.set_gateway(gateway)   # wire shared MT5 connection

        # Add file handler for CAB's root-level logging calls
        import logging as _logging
        from logging.handlers import RotatingFileHandler
        _cab_log_path = Path(__file__).parent / "logs" / "cab_watcher.log"
        _cab_fh = RotatingFileHandler(_cab_log_path, maxBytes=5*1024*1024, backupCount=5, encoding="utf-8")
        _cab_fh.setFormatter(_logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        _logging.getLogger().addHandler(_cab_fh)

        log.warning("CAB Watcher: gateway wired in")
        while not stop.is_set():
            cycle_start = time.time()
            try:
                cab.manage_fluid_logic()
                intel = cab.get_market_regime()
                log_session_event("cab", "WATCHER_CYCLE",
                                  symbol=cab.SYMBOL,
                                  magic=cab.MAGIC_NUMBER,
                                  regime=intel.get("regime", ""),
                                  conviction=intel.get("scores", {}).get("adx_rank"))
            except Exception as e:
                log.error(f"CAB cycle error: {e}", exc_info=True)
            stop.wait(max(0, CAB_INTERVAL - (time.time() - cycle_start)))

    except Exception as e:
        log.error(f"CAB thread fatal: {e}", exc_info=True)
    finally:
        log.info("CAB thread stopped")


def cab_entry_thread(gateway: MT5Gateway, shared: SharedState,
                     stop: ShutdownEvent, config_path: str):
    """
    CAB Entry wrapper — runs CABEntryRunner.run_cycle_all() every
    CAB_ENTRY_INTERVAL seconds until stop is requested.

    H4 bars are 4 hours long so a 30-second poll cycle is more than
    sufficient — we catch every new bar within 30 seconds of it opening.

    Heartbeat is written every cycle so CABFailover.mq5 (or
    UnifiedFailover.mq5) knows Python is alive.
    """
    log = logging.getLogger("Thread.CABEntry")
    log.info("CAB Entry thread starting")

    try:
        import json
        import importlib.util as _ilu
        from pathlib import Path as _Path

        # Load cab_entry from cab_super\
        _entry_path = _Path(__file__).parent / "cab_super" / "cab_entry.py"
        _spec = _ilu.spec_from_file_location("cab_entry", _entry_path)
        _mod  = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)

        # Read config to build per-symbol configs + heartbeat path
        with open(config_path) as f:
            config_data = json.load(f)

        configs = _mod.build_cab_entry_configs(config_data)
        hb_path = config_data.get("heartbeat", {}).get("path", "")

        runner = _mod.CABEntryRunner(
            configs,
            gateway=gateway,
            heartbeat_path=hb_path,
            interval_seconds=CAB_ENTRY_INTERVAL,
        )
        log.warning(
            f"CAB Entry: gateway wired | "
            f"symbols={[c.symbol for c in configs]} | "
            f"heartbeat={'ON' if hb_path else 'OFF'}"
        )

        while not stop.is_set():
            cycle_start = time.time()
            try:
                # arch-equity-cb: skip new CAB entries when circuit breaker active
                # fix-switches: same scoping — cab_enabled=False blocks new
                # entries only. cab_watcher_thread's manage_fluid_logic() keeps
                # running regardless, so open positions are never left unmanaged.
                switches = load_switches(config_path)
                pos_count = len(gateway.positions_get() or [])
                if not shared.check_entries_allowed():
                    log.debug(
                        f"CAB entries blocked — circuit breaker active "
                        f"({shared.cb_reason})"
                    )
                elif not switches["cab_enabled"]:
                    log.debug("CAB entries blocked — cab_enabled switch is off")
                elif pos_count >= MAX_GLOBAL_POSITIONS:
                    log.debug("CAB entries blocked — global max positions limit reached")
                else:
                    opened = runner.run_cycle_all()
                    if opened:
                        log_session_event(
                            "cab", "ENTRY_FIRED",
                            symbol="multi",
                            magic=999555,
                            regime=shared.get_market_state().get("regime", ""),
                        )
            except Exception as e:
                log.error(f"CAB entry cycle error: {e}", exc_info=True)
            stop.wait(max(0, CAB_ENTRY_INTERVAL - (time.time() - cycle_start)))

    except Exception as e:
        log.error(f"CAB Entry thread fatal: {e}", exc_info=True)
    finally:
        log.info("CAB Entry thread stopped")


# ──────────────────────────────────────────────────────────────────────────────
#  MAGIC ISOLATION CHECKER
# ──────────────────────────────────────────────────────────────────────────────

def check_magic_isolation(gateway: MT5Gateway) -> bool:
    """
    Verify each open position's magic number belongs to exactly one bot.
    Log any conflicts. Call from main thread health monitor.
    Returns True if isolation is clean.
    """
    positions = gateway.positions_get()
    conflicts = []
    for pos in positions:
        m = pos.magic
        owners = []
        if m in MAGIC_SUPERTREND: owners.append("supertrend")
        if m in MAGIC_GHOST:      owners.append("ghost")
        if m in MAGIC_CAB:        owners.append("cab")
        if len(owners) != 1:
            conflicts.append({
                "ticket": pos.ticket, "magic": m, "symbol": pos.symbol,
                "owners": owners or ["UNKNOWN"],
            })

    if conflicts:
        logger.error(f"MAGIC ISOLATION BREACH: {conflicts}")
        log_session_event("unified", f"MAGIC_ISOLATION_BREACH_{len(conflicts)}")
        # fix-isolationlog: one structured row per offending position, not
        # just a count — this is what makes "which magic number is this"
        # a CSV filter instead of grepping unified_runner.log by hand.
        for c in conflicts:
            log_session_event(
                "unified", "MAGIC_ISOLATION_BREACH_DETAIL",
                symbol=c["symbol"], magic=c["magic"],
                regime=",".join(c["owners"]),   # reused field: comma-joined owner list ("UNKNOWN" if none)
            )
        return False

    logger.info(
        f"Magic isolation OK | {len(positions)} positions | "
        f"all magic numbers recognised"
    )
    return True


# ──────────────────────────────────────────────────────────────────────────────
#  MAIN ENTRY POINT
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Unified Bot Runner")
    parser.add_argument("--account", default="demo", choices=["demo", "live"])
    parser.add_argument("--config",  default="config/config.json")
    parser.add_argument("--no-demo", action="store_true",
                        help="Disable demo mode (apply position caps + equity filter)")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    demo = not args.no_demo   # demo=True by default
    setup_logging(args.log_level)

    logger.info("=" * 60)
    logger.info("  UNIFIED RUNNER — Starting")
    logger.info(f"  Mode       : {'DEMO' if demo else 'LIVE'}")
    logger.info(f"  ST interval: {SUPERTREND_INTERVAL}s")
    logger.info(f"  Ghost int  : {GHOST_INTERVAL}s")
    logger.info(f"  CAB int    : {CAB_INTERVAL}s")
    logger.info("=" * 60)

    # Load config
    try:
        with open(args.config) as f:
            config_data = json.load(f)
    except Exception as e:
        logger.error(f"Config load failed: {e}")
        sys.exit(1)

    account_cfg = config_data.get("accounts", {}).get(args.account)
    if not account_cfg:
        logger.error(f"Account '{args.account}' not in config.json")
        sys.exit(1)

    # fix-credentials (audit finding #9): env vars override config.json's
    # plaintext credentials when set, matching the pattern cab_watcher.py's
    # standalone run_brain() already uses (MT5_LOGIN/MT5_PASSWORD/MT5_SERVER).
    # Fully backward compatible — if none of these are set, behavior is
    # identical to before (reads straight from config.json). This doesn't
    # require changing anything today; it just gives a path off committing
    # credentials to a JSON file whenever you're ready to take it.
    account_cfg = dict(account_cfg)  # don't mutate config_data's own dict
    if os.environ.get("MT5_LOGIN"):
        account_cfg["login"] = int(os.environ["MT5_LOGIN"])
    if os.environ.get("MT5_PASSWORD"):
        account_cfg["password"] = os.environ["MT5_PASSWORD"]
    if os.environ.get("MT5_SERVER"):
        account_cfg["server"] = os.environ["MT5_SERVER"]
    if os.environ.get("MT5_PATH"):
        account_cfg["mt5_path"] = os.environ["MT5_PATH"]

    # Initialise MT5 Gateway
    gateway = MT5Gateway()
    if not gateway.initialize(path=account_cfg.get("mt5_path")):
        logger.error("MT5Gateway.initialize() failed — aborting")
        sys.exit(1)
    if not gateway.login(
        account_cfg["login"], account_cfg["password"], account_cfg["server"]
    ):
        logger.error("MT5Gateway.login() failed — aborting")
        gateway.shutdown()
        sys.exit(1)

    account_info = gateway.account_info()
    logger.warning(
        f"Connected | Account={account_info.login} "
        f"Balance={account_info.balance:.2f} "
        f"Server={account_info.server}"
    )

    # Shared state + shutdown coordinator
    shared = SharedState()
    stop   = ShutdownEvent()
    
    # Layer 0 Knowledge Register & Pulse Engine
    symbols = list(config_data.get("symbols", {}).keys())
    kr = KnowledgeRegister()
    pulse = MarketPulseEngine(gateway, kr, symbols)
    pulse.start()

    _init_session_log()
    log_session_event("unified", "RUNNER_START")

    # Launch bot threads
    threads = []

    t_ghost_watcher = threading.Thread(
        target=ghost_watcher_thread,
        args=(gateway, shared, stop),
        name="GhostWatcher",
        daemon=True,
    )
    threads.append(t_ghost_watcher)

    t_ghost_hunter = threading.Thread(
        target=ghost_hunter_thread,
        args=(gateway, shared, stop, demo, args.config),
        name="GhostHunter",
        daemon=True,
    )
    threads.append(t_ghost_hunter)

    t_cab = threading.Thread(
        target=cab_watcher_thread,
        args=(gateway, shared, stop),
        name="CABWatcher",
        daemon=True,
    )
    threads.append(t_cab)

    t_cab_entry = threading.Thread(
        target=cab_entry_thread,
        args=(gateway, shared, stop, args.config),
        name="CABEntry",
        daemon=True,
    )
    threads.append(t_cab_entry)

    t_st = threading.Thread(
        target=supertrend_thread,
        args=(gateway, shared, stop, args.config, account_cfg, demo),
        name="SuperTrend",
        daemon=True,
    )
    threads.append(t_st)

    for t in threads:
        t.start()
        logger.warning(f"Thread started: {t.name}")
        time.sleep(0.5)   # slight stagger to avoid simultaneous MT5 init

    # ── Main thread: equity heartbeat + health monitor ─────────────────────
    logger.info("Main thread entering heartbeat loop")

    # arch-equity-cb: sample starting equity once at session open
    _start_acc = gateway.account_info()
    if _start_acc:
        shared.set_daily_start_equity(_start_acc.equity)
        logger.warning(
            f"Circuit breaker armed | start_equity={_start_acc.equity:.2f} | "
            f"max_daily_loss={config_data['global_settings'].get('max_daily_loss_percent', 10.0)}%"
        )

    _max_loss_pct = config_data["global_settings"].get("max_daily_loss_percent", 10.0)

    try:
        from data.trade_ledger import write_equity_snapshot
    except ImportError:
        write_equity_snapshot = None

    try:
        last_isolation_check = 0.0
        while True:
            time.sleep(HEARTBEAT_INTERVAL)

            # Thread health
            alive = {t.name: t.is_alive() for t in threads}
            dead  = [name for name, ok in alive.items() if not ok]
            if dead:
                logger.error(
                    f"DEAD THREADS: {dead} — other threads continuing"
                )
                log_session_event("unified", f"THREAD_DEAD_{','.join(dead)}")
                # Log and continue — do NOT stop the runner
            else:
                # Check MT5 connection health and attempt reconnect if IPC dropped
                gateway.reconnect_if_needed(
                    path=account_cfg.get("mt5_path"),
                    login=account_cfg["login"],
                    password=account_cfg["password"],
                    server=account_cfg["server"]
                )
                
                acc = gateway.account_info()
                eq_str = f" | Equity={acc.equity:.2f} P&L={acc.profit:.2f}" if acc else ""
                logger.warning(f"Heartbeat OK | {len(alive)} threads alive{eq_str}")
                log_session_event("unified", "EQUITY_HEARTBEAT",
                                  r_multiple=round(acc.profit / max(acc.balance, 1), 4) if acc else 0.0)
                if acc and write_equity_snapshot:
                    pos_count = len(gateway.positions_get() or [])
                    write_equity_snapshot(acc.equity, acc.balance, acc.profit, pos_count)


                # ── arch-equity-cb: daily drawdown circuit breaker ─────────────
                # Checks every HEARTBEAT_INTERVAL (60s). Trips when current equity
                # has fallen more than max_daily_loss_percent below session-start
                # equity. Blocks ALL new entries across all three bots.
                # Existing positions continue to be managed normally — watchers
                # keep running. Only entry engines are paused.
                # This replaces the position-count cap as the global safety net.
                drawdown_pct = 0.0
                if acc and shared.daily_start_equity > 0:
                    drawdown_pct = (
                        (shared.daily_start_equity - acc.equity)
                        / shared.daily_start_equity * 100.0
                    )
                    if drawdown_pct >= _max_loss_pct and shared.check_entries_allowed():
                        reason = (
                            f"Daily drawdown {drawdown_pct:.2f}% >= "
                            f"limit {_max_loss_pct:.1f}% | "
                            f"start={shared.daily_start_equity:.2f} "
                            f"current={acc.equity:.2f}"
                        )
                        shared.trip_circuit_breaker(reason)
                        logger.error(
                            f"CIRCUIT BREAKER TRIPPED — {reason} | "
                            f"All new entries BLOCKED for this session"
                        )
                        log_session_event("unified", "CIRCUIT_BREAKER_TRIPPED")
                    elif shared.check_entries_allowed():
                        logger.info(
                            f"CB OK | drawdown={drawdown_pct:.2f}% "
                            f"(limit {_max_loss_pct:.1f}%) | entries OPEN"
                        )
                    else:
                        logger.warning(
                            f"CB ACTIVE | drawdown={drawdown_pct:.2f}% | "
                            f"entries BLOCKED since "
                            f"{datetime.fromtimestamp(shared.cb_fired_at).strftime('%H:%M:%S')}"
                        )

                # KPI ledger snapshot — analytical layer, never read by mechanical system
                try:
                    all_pos_for_kpi = gateway.positions_get()
                    ms_xau = shared.get_market_state()
                    write_kpi_snapshot(
                        equity=acc.equity if acc else 0.0,
                        balance=acc.balance if acc else 0.0,
                        open_pnl=acc.profit if acc else 0.0,
                        daily_drawdown_pct=drawdown_pct,
                        entries_allowed=shared.check_entries_allowed(),
                        positions=all_pos_for_kpi,
                        regime_xauusd=ms_xau.get("regime", ""),
                        conviction_xauusd=ms_xau.get("conviction", 0.0),
                    )
                except Exception as _kpi_e:
                    logger.debug(f"KPI ledger write failed: {_kpi_e}")

            # Magic isolation check (every 5 minutes)
            if time.time() - last_isolation_check > 300:
                check_magic_isolation(gateway)
                last_isolation_check = time.time()

            # MT5 connection health — check IPC failure state first
            if not gateway.is_healthy:
                logger.error(
                    f"IPC failure ({gateway._ipc_fail_count} consecutive) "
                    f"— forcing reconnect"
                )
                gateway._ipc_fail_count = 0   # reset so reconnect can proceed
                gateway.reconnect_if_needed(
                    path=account_cfg.get("mt5_path"),
                    login=account_cfg["login"],
                    password=account_cfg["password"],
                    server=account_cfg["server"],
                )
            elif not gateway.reconnect_if_needed(
                path=account_cfg.get("mt5_path"),
                login=account_cfg["login"],
                password=account_cfg["password"],
                server=account_cfg["server"],
            ):
                logger.critical("MT5 connection could not be restored")

    except KeyboardInterrupt:
        logger.info("Shutdown requested (Ctrl+C)")
    finally:
        stop.request()
        logger.info("Stop signal sent to all threads")
        pulse.stop()
        for t in threads:
            t.join(timeout=10)
            if t.is_alive():
                logger.warning(f"Thread {t.name} did not exit cleanly")
        gateway.shutdown()
        log_session_event("unified", "RUNNER_STOP")
        logger.info("Unified Runner stopped cleanly")


if __name__ == "__main__":
    main()