"""
cab_entry.py — CAB H4 Inversion Entry Engine
=============================================
Python port of CAB_Unified.mq5 entry logic.
Multi-pair capable — same MultiPairRunner pattern as SuperTrend.

WHAT IT DOES:
  Detects H4 two-bar inversion patterns and opens positions:
    Bullish inversion: bar[-3] bearish  AND  bar[-2] bullish
    Bearish inversion: bar[-3] bullish  AND  bar[-2] bearish

  Bar numbering (Python / MT5 copy_rates_from_pos):
    bars[-1] = bar 0  (current open bar — ignored for signal)
    bars[-2] = bar 1  (last closed bar — same as MQL5 iClose(_,H4,1))
    bars[-3] = bar 2  (one before     — same as MQL5 iClose(_,H4,2))

MULTI-PAIR:
  Run CABEntryRunner with a list of CABEntryConfig instances.
  All positions share magic number 999555 so cab_watcher.py
  manages them automatically regardless of symbol.

GATEWAY:
  Accepts gateway=None (standalone) or MT5Gateway instance (unified).
  Identical pattern to SuperTrendBot._api.

HEARTBEAT:
  CABEntryRunner writes the heartbeat file every cycle so
  CABFailover.mq5 knows Python is alive.

CHANGELOG:
  v1.0  May 2026  — initial port from CAB_Unified.mq5 v16.4
                    multi-pair, gateway-aware, session gate,
                    regime gate hook (reads SharedState if provided)
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import os
import time
import logging
from dataclasses import dataclass, field
from typing import Optional, List
from pathlib import Path
from datetime import datetime

try:
    from data.trade_ledger import write_trade_event
except ImportError:
    write_trade_event = None

logger = logging.getLogger("CABEntry")


# ==============================================================================
#  GATEWAY  (set by unified_runner via constructor; None = standalone)
# ==============================================================================
#  Note: cab_entry uses class-based gateway (like SuperTrendBot), not the
#  module-level pattern used by cab_watcher, because CABEntryEngine is
#  instantiated per symbol and receives the gateway at construction time.

# fix-retrystorm: max order-placement attempts for a single detected pattern
# before giving up on that H4 bar. See CABEntryEngine.__init__ for the bug
# this bounds. 3 attempts × 30s cycle ≈ 90s of retry room for a genuinely
# transient failure (spread blip, momentary connectivity loss) without
# spinning for the full 4-hour bar lifetime on a persistent rejection.
MAX_FIRE_ATTEMPTS_PER_BAR = 3


# ==============================================================================
#  CONFIG
# ==============================================================================
@dataclass
class CABEntryConfig:
    # ── Identity ──────────────────────────────────────────────────────────────
    symbol:         str   = "XAUUSDm"
    magic_number:   int   = 999555      # MUST match cab_watcher.py MAGIC_NUMBER

    # ── Entry parameters (match CAB_Unified.mq5 defaults) ─────────────────────
    risk_percent:   float = 1.0         # % of equity risked per trade
    atr_multiplier: float = 2.5         # SL distance = ATR × this
    atr_period:     int   = 14          # ATR period on H4

    # fix-lotcap: risk-based sizing has no ceiling beyond the broker's own
    # volume_max — on FX pairs this produced 0.14-0.32 lot fills (14x-32x the
    # documented 0.01 demo-phase size) because a tight ATR-based SL distance
    # in price terms still divides out to a large lot at 1% risk on a $10k
    # account. Set to None to disable and fall back to pure risk-based sizing
    # (e.g. once live and intentionally scaling).
    max_lot_demo_cap: Optional[float] = 0.01

    # ── Guards ────────────────────────────────────────────────────────────────
    max_spread_points: int   = 50       # skip entry if spread > this (points)
    max_positions:     int   = 1        # arch-cap-cab: strictly 1 max position.
                                        # Phase 2 will validate whether pyramiding into
                                        # confirmed direction improves combined R.

    # ── Session gate (suppress entries during low-liquidity hours) ─────────────
    session_gate_enabled: bool = True
    # Hours (UTC) during which entries are blocked
    blocked_hours_utc:    tuple = (0, 1, 2, 3, 4, 5, 6)   # Asian session

    # ── Heartbeat ─────────────────────────────────────────────────────────────
    heartbeat_path: str = ""    # set by runner from config; empty = no write


# ==============================================================================
#  SINGLE-SYMBOL ENTRY ENGINE
# ==============================================================================
class CABEntryEngine:
    """
    Single-symbol H4 inversion entry engine.
    Instantiate one per symbol; orchestrate via CABEntryRunner.
    """

    def __init__(self, config: CABEntryConfig, gateway=None):
        self.config = config
        self._gw    = gateway
        # fix-retrystorm: a detected pattern whose order placement fails (spread
        # widened, broker rejection, connectivity blip) previously never marked
        # _last_h4_bar_time, so run_cycle() would retry _place_order() every
        # single cycle (every 30s) for up to 4 hours until the H4 bar rolled
        # over — reproduced directly: 5 consecutive cycles against a
        # persistently-failing mock order produced 5 order_send calls with no
        # let-up. These two fields bound that retry instead of removing it —
        # a genuinely transient failure still gets a few tries before giving up.
        self._fire_attempt_bar_time = None   # which bar we're currently retrying
        self._fire_attempt_count    = 0
        self.logger = logging.getLogger(f"CABEntry.{config.symbol}")
        
        # State persistence — survives restart within same H4 bar
        self._state_file = os.path.join(
            "logs", f"cab_state_{config.symbol.replace('.','_')}.json"
        )
        self._last_h4_bar_time = self._load_bar_state()
        
        import time as _time
        self._startup_time = _time.time()
        self._startup_grace_passed = False

    def _load_bar_state(self):
        """
        Restore last checked H4 bar time from state file if the bar
        is still active (opened less than 4 hours ago).
        Returns the stored bar time as a pd.Timestamp, or None if
        the file does not exist, is corrupt, or the bar has expired.
        """
        import json
        import os
        import pandas as pd
        try:
            if not os.path.exists(self._state_file):
                return None
            with open(self._state_file, "r") as f:
                data = json.load(f)
            stored_time_str = data.get("last_bar_time")
            written_at = data.get("written_at", 0)
            if not stored_time_str:
                return None
            # If more than 4 hours have elapsed since the bar opened,
            # a new bar has started — treat as fresh start
            import time as _time
            stored_ts = pd.Timestamp(stored_time_str)
            bar_age_seconds = _time.time() - written_at
            if bar_age_seconds > 4 * 3600:
                self.logger.info(
                    f"CAB state: stored bar {stored_time_str} expired "
                    f"({bar_age_seconds/3600:.1f}h old) — treating as new"
                )
                return None
            self.logger.info(
                f"CAB state restored: last_bar_time={stored_time_str} "
                f"({bar_age_seconds/60:.0f}min old) — "
                f"entry blocked until next H4 bar"
            )
            return stored_ts
        except Exception as e:
            self.logger.warning(f"CAB state load failed: {e} — starting fresh")
            return None

    def _save_bar_state(self, bar_time):
        """
        Write the current bar time to state file so restart within
        the same H4 bar does not re-fire.
        """
        import json
        import os
        try:
            import time as _time
            os.makedirs("logs", exist_ok=True)
            data = {
                "last_bar_time": str(bar_time),
                "written_at": int(_time.time()),
                "symbol": self.config.symbol
            }
            with open(self._state_file, "w") as f:
                json.dump(data, f)
        except Exception as e:
            self.logger.warning(f"CAB state save failed: {e}")

    def _startup_grace_ok(self, bar1_time) -> bool:
        """
        On first startup (no persisted state), block entries until
        we have observed at least one full H4 bar close after startup.
        This prevents firing on a bar that was already acted on before
        the previous shutdown.
        """
        if self._startup_grace_passed:
            return True
        # If state file gave us a valid bar time, grace is covered
        # by the state file — allow entry
        if self._last_h4_bar_time is not None:
            self._startup_grace_passed = True
            return True
        # No state file: record the first bar seen, block until a
        # different bar appears
        if not hasattr(self, '_startup_bar_seen'):
            self._startup_bar_seen = bar1_time
            self.logger.warning(
                f"CAB STARTUP GRACE: no state file found. "
                f"Blocking entries on bar {bar1_time} until next "
                f"H4 bar closes. This prevents firing on a bar "
                f"that may have already been acted on before restart."
            )
            return False
        if bar1_time != self._startup_bar_seen:
            # New bar has opened — grace period complete
            self._startup_grace_passed = True
            self.logger.info(
                f"CAB STARTUP GRACE complete: new bar {bar1_time} "
                f"confirmed. Entry now permitted."
            )
            return True
        # Still on the startup bar — block
        return False

    @property
    def _api(self):
        """Gateway in unified mode, raw mt5 in standalone mode."""
        return self._gw if self._gw is not None else mt5

    # ── Data ──────────────────────────────────────────────────────────────────
    def _get_h4_bars(self, count: int = 5) -> Optional[pd.DataFrame]:
        """Fetch H4 OHLC bars. Returns DataFrame or None."""
        rates = self._api.copy_rates_from_pos(
            self.config.symbol, mt5.TIMEFRAME_H4, 0, count
        )
        if rates is None or len(rates) < count:
            return None
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        return df

    def _get_h4_atr(self) -> float:
        """
        Consumes canonical H4 ATR from Knowledge Register.
        Returns 1.0 as safe fallback.
        """
        from core.knowledge_register import KnowledgeRegister
        kr = KnowledgeRegister()
        snapshot = kr.get_market_state(self.config.symbol, "H4")
        if snapshot:
            return snapshot.atr_raw
        return 1.0

    # ── Guards ────────────────────────────────────────────────────────────────
    def _spread_ok(self) -> bool:
        tick = self._api.symbol_info_tick(self.config.symbol)
        if tick is None:
            return False
        sym  = self._api.symbol_info(self.config.symbol)
        if sym is None:
            return False
        spread_points = int((tick.ask - tick.bid) / sym.point)
        return spread_points <= self.config.max_spread_points

    def _session_allowed(self) -> bool:
        if not self.config.session_gate_enabled:
            return True
        hour = datetime.utcnow().hour
        return hour not in self.config.blocked_hours_utc

    def _position_count(self) -> int:
        positions = self._api.positions_get(symbol=self.config.symbol)
        if not positions:
            return 0
        return sum(1 for p in positions if p.magic == self.config.magic_number)

    # ── Lot sizing ────────────────────────────────────────────────────────────
    def _calculate_lot(self, sl_dist_price: float) -> float:
        """
        Risk-based lot size. Exact port of MQL5 CalculateLot().
        Uses correct tick formula (same fix applied to SuperTrend v2.3).
        """
        acc = self._api.account_info()
        sym = self._api.symbol_info(self.config.symbol)
        if acc is None or sym is None or sl_dist_price <= 0:
            return 0.01

        risk_money   = acc.equity * (self.config.risk_percent / 100.0)
        sl_ticks     = sl_dist_price / sym.trade_tick_size
        dollar_per_lot = sl_ticks * sym.trade_tick_value

        if dollar_per_lot <= 0:
            return sym.volume_min

        lot = risk_money / dollar_per_lot
        lot = max(sym.volume_min, min(lot, sym.volume_max))

        # fix-lotcap: demo-safety ceiling, applied after the broker bounds
        # above so it can only ever tighten the result, never widen it past
        # what the broker/risk calc already allowed.
        if self.config.max_lot_demo_cap is not None:
            lot = min(lot, self.config.max_lot_demo_cap)
            
        # Ensure we don't violate the broker's absolute minimum (e.g. ETHUSDm min is 0.1)
        lot = max(sym.volume_min, lot)

        lot = round(lot / sym.volume_step) * sym.volume_step
        return round(lot, 2)

    # ── SL guard ──────────────────────────────────────────────────────────────
    def _safe_sl(self, price: float, sl: float, is_buy: bool) -> float:
        """Widen SL if it falls inside broker's stops level."""
        sym = self._api.symbol_info(self.config.symbol)
        if sym is None:
            return sl
        stops_dist = sym.trade_stops_level * sym.point
        buf        = sym.point * 30
        if is_buy  and (price - sl) < stops_dist:
            sl = price - stops_dist - buf
        if not is_buy and (sl - price) < stops_dist:
            sl = price + stops_dist + buf
        return round(sl, sym.digits)

    # ── Order placement ───────────────────────────────────────────────────────
    def _close_position(self, pos) -> bool:
        """Closes a position synchronously for reversal."""
        tick = self._api.symbol_info_tick(self.config.symbol)
        if tick is None:
            return False
        import MetaTrader5 as mt5
        is_buy = (pos.type == 0)
        price = tick.bid if is_buy else tick.ask
        request = {
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       self.config.symbol,
            "volume":       float(pos.volume),
            "type":         mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY,
            "position":     pos.ticket,
            "price":        price,
            "deviation":    20,
            "magic":        self.config.magic_number,
            "comment":      "CAB Reversal Close",
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = self._api.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            self.logger.info(f"REVERSAL CLOSE OK | #{pos.ticket} | {self.config.symbol}")
            return True
        elif result and result.retcode == 10013:
            verify = self._api.positions_get(ticket=pos.ticket)
            if not verify:
                self.logger.info(f"REVERSAL CLOSE OK (concurrently) | #{pos.ticket} | {self.config.symbol}")
                return True
        self.logger.error(f"REVERSAL CLOSE FAILED | #{pos.ticket} | code={result.retcode if result else 'None'}")
        return False
    def _place_order(self, is_buy: bool, sl: float, lot: float) -> Optional[int]:
        """Places the market order. Returns ticket ID if successful, else None."""
        tick = self._api.symbol_info_tick(self.config.symbol)
        sym  = self._api.symbol_info(self.config.symbol)
        if tick is None or sym is None:
            return None

        price      = tick.ask if is_buy else tick.bid
        order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
        sl         = self._safe_sl(price, sl, is_buy)

        request = {
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       self.config.symbol,
            "volume":       lot,
            "type":         order_type,
            "price":        price,
            "sl":           sl,
            "tp":           0.0,          # fluid TP — cab_watcher owns exits
            "deviation":    20,
            "magic":        self.config.magic_number,
            "comment":      "cab_managed",
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = self._api.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            side = "BUY" if is_buy else "SELL"
            self.logger.info(
                f"ENTRY {side} | {self.config.symbol} | "
                f"price={price:.5f} | sl={sl:.5f} | lot={lot:.2f} | "
                f"ticket={result.order}"
            )
            return result.order
        else:
            code = result.retcode if result else "None"
            self.logger.error(
                f"ORDER FAILED | {self.config.symbol} | "
                f"retcode={code}"
            )
            return None

    # ── Main cycle ────────────────────────────────────────────────────────────
    def run_cycle(self) -> bool:
        """
        One entry check cycle. Returns True if a new position was opened.

        Bar logic (mirrors MQL5 CheckForEntries exactly):
          bars[-2] = bar 1 (last closed)  — MQL5 iClose(_,H4,1) / iOpen(_,H4,1)
          bars[-3] = bar 2 (one before)   — MQL5 iClose(_,H4,2) / iOpen(_,H4,2)

        Signal fires ONCE per H4 bar (bar-aware cache on bars[-2].time).
        """
        # ── Guards ────────────────────────────────────────────────────────────
        if not self._session_allowed():
            return False

        if not self._spread_ok():
            self.logger.debug(f"{self.config.symbol}: spread too wide — skip")
            return False

        # ── H4 data ───────────────────────────────────────────────────────────
        df = self._get_h4_bars(count=5)
        if df is None:
            self.logger.warning(f"{self.config.symbol}: no H4 data")
            return False

        # Bar-aware: only fire once per closed bar
        bar1_time = df["time"].iloc[-2]
        if bar1_time == self._last_h4_bar_time:
            return False   # already checked this bar

        # Startup grace: block entry on first bar seen after cold start
        # if no persisted state exists (prevents restart-triggered fires)
        if not self._startup_grace_ok(bar1_time):
            return False

        # ── Pattern detection ─────────────────────────────────────────────────
        bar1_open  = float(df["open"].iloc[-2])
        bar1_close = float(df["close"].iloc[-2])
        bar2_open  = float(df["open"].iloc[-3])
        bar2_close = float(df["close"].iloc[-3])

        bar1_bullish = bar1_close > bar1_open
        bar1_bearish = bar1_close < bar1_open
        bar2_bullish = bar2_close > bar2_open
        bar2_bearish = bar2_close < bar2_open

        # Bullish inversion: bar2 bearish, bar1 bullish
        is_bullish_inversion = bar2_bearish and bar1_bullish
        # Bearish inversion: bar2 bullish, bar1 bearish
        is_bearish_inversion = bar2_bullish and bar1_bearish

        if not (is_bullish_inversion or is_bearish_inversion):
            self._last_h4_bar_time = bar1_time   # mark checked, no signal
            self._save_bar_state(bar1_time)
            self._fire_attempt_bar_time = None
            self._fire_attempt_count = 0
            return False

        # fix-retrystorm: bound how many times we'll retry placing THIS bar's
        # detected pattern. Reset the counter whenever we move to a new bar.
        if self._fire_attempt_bar_time != bar1_time:
            self._fire_attempt_bar_time = bar1_time
            self._fire_attempt_count = 0

        if self._fire_attempt_count >= MAX_FIRE_ATTEMPTS_PER_BAR:
            self.logger.warning(
                f"{self.config.symbol}: giving up on this bar's signal after "
                f"{self._fire_attempt_count} failed attempts — "
                f"will not retry again until the next H4 bar closes"
            )
            self._last_h4_bar_time = bar1_time   # stop retrying this bar
            self._save_bar_state(bar1_time)
            return False

        # ── Auto-Reversal & Max Positions ─────────────────────────────────────
        all_pos = self._api.positions_get(symbol=self.config.symbol)
        my_pos = [p for p in (all_pos or []) if p.magic == self.config.magic_number]
        
        if my_pos:
            pos = my_pos[0]
            is_buy_pos = (pos.type == 0)
            
            if (is_bullish_inversion and is_buy_pos) or (is_bearish_inversion and not is_buy_pos):
                self.logger.info(f"{self.config.symbol}: Signal matches open position #{pos.ticket} direction. Holding trade.")
                self._last_h4_bar_time = bar1_time
                self._save_bar_state(bar1_time)
                return False
            else:
                self.logger.warning(f"{self.config.symbol}: Reversal signal detected! Closing opposite position #{pos.ticket}.")
                if self._close_position(pos):
                    time.sleep(0.5)
                else:
                    return False # retry next cycle
                    
        if self._position_count() >= self.config.max_positions:
            return False

        # ── KR Layer 2 & 3: Hard Blocks ──────────────────────────────────────
        from core.knowledge_register import KnowledgeRegister
        kr = KnowledgeRegister()
        kr_dir = 1 if is_bullish_inversion else -1
        
        invalidated, inv_reason = kr.is_entry_invalidated(self.config.symbol, kr_dir)
        if invalidated:
            self.logger.info(f"Entry BLOCKED by KR Layer 2: {inv_reason}")
            return False
            
        account_info = self._api.account_info()
        equity = account_info.equity if account_info else 10000.0
        allowed, p_reason = kr.check_portfolio_entry_allowed(
            symbol=self.config.symbol,
            direction=kr_dir,
            proposed_risk_pct=self.config.risk_percent,
            account_equity=equity
        )
        if not allowed:
            self.logger.info(f"Entry BLOCKED by KR Layer 3: {p_reason}")
            return False

        # ── ATR and lot ───────────────────────────────────────────────────────
        atr     = self._get_h4_atr()
        sl_dist = atr * self.config.atr_multiplier
        lot     = self._calculate_lot(sl_dist)

        # ── Get current price for SL anchor ───────────────────────────────────
        tick = self._api.symbol_info_tick(self.config.symbol)
        if tick is None:
            return False

        direction = "BULLISH" if is_bullish_inversion else "BEARISH"
        self.logger.info(
            f"{self.config.symbol}: H4 {direction} inversion | "
            f"bar1 o={bar1_open:.5f} c={bar1_close:.5f} | "
            f"bar2 o={bar2_open:.5f} c={bar2_close:.5f} | "
            f"atr={atr:.5f} sl_dist={sl_dist:.5f} lot={lot:.2f} | "
            f"attempt {self._fire_attempt_count + 1}/{MAX_FIRE_ATTEMPTS_PER_BAR}"
        )

        self._fire_attempt_count += 1

        if is_bullish_inversion:
            sl = tick.bid - sl_dist
            ticket = self._place_order(is_buy=True,  sl=sl, lot=lot)
        else:
            sl = tick.ask + sl_dist
            ticket = self._place_order(is_buy=False, sl=sl, lot=lot)

        if ticket:
            # -- Register State to KnowledgeRegister (Change 4) --
            from core.knowledge_register import KnowledgeRegister, TradeThesis
            kr = KnowledgeRegister()
            snapshot = kr.get_market_state(self.config.symbol, "H4")
            if snapshot:
                thesis = TradeThesis(
                    ticket=ticket,
                    magic=self.config.magic_number,
                    symbol=self.config.symbol,
                    direction=1 if is_bullish_inversion else -1,
                    bot_id="CAB",
                    setup_type="H4_INVERSION",
                    fill_price=tick.ask if is_bullish_inversion else tick.bid,
                    fill_time=time.time(),
                    entry_atr=atr,
                    entry_regime=snapshot.regime,
                    entry_conviction=0.0,
                    initial_sl=sl,
                    initial_tp=0.0,
                    market_snapshot=snapshot
                )
                kr.register_trade_thesis(thesis)

            self._last_h4_bar_time = bar1_time
            self._save_bar_state(bar1_time)
            self._fire_attempt_bar_time = None
            self._fire_attempt_count = 0

            # ── Unified Trade Ledger: CAB ENTRY ───────────────────────────
            if write_trade_event:
                is_buy = is_bullish_inversion
                entry_price = tick.ask if is_buy else tick.bid
                spread = tick.ask - tick.bid
                regime_label = snapshot.regime if snapshot else ""
                write_trade_event(
                    bot="CAB", event="ENTRY", ticket=ticket,
                    symbol=self.config.symbol,
                    direction="BUY" if is_buy else "SELL",
                    price=entry_price, sl=sl, tp=0.0, volume=lot,
                    regime=regime_label, atr=atr,
                    spread_at_event=spread,
                    magic=self.config.magic_number,
                )
            return True

        return False


# ==============================================================================
#  MULTI-PAIR RUNNER
# ==============================================================================
class CABEntryRunner:
    """
    Orchestrates multiple CABEntryEngine instances.
    Same pattern as SuperTrend MultiPairRunner.

    Usage in unified_runner thread:
        engines = CABEntryRunner(configs, gateway=gateway,
                                 heartbeat_path=HEARTBEAT_FILE)
        while not stop.is_set():
            engines.run_cycle_all()
            stop.wait(INTERVAL)
    """

    def __init__(
        self,
        configs:        List[CABEntryConfig],
        gateway=None,
        heartbeat_path: str   = "",
        interval_seconds: int = 30,
    ):
        self.engines  = [CABEntryEngine(cfg, gateway=gateway) for cfg in configs]
        self._hb_path = heartbeat_path
        self.interval = interval_seconds
        self.logger   = logging.getLogger("CABEntryRunner")
        syms = [cfg.symbol for cfg in configs]
        self.logger.info(
            f"CABEntryRunner | symbols={syms} | "
            f"magic={configs[0].magic_number if configs else 'n/a'} | "
            f"heartbeat={'ON' if heartbeat_path else 'OFF'}"
        )

    def _write_heartbeat(self):
        """
        Write Unix timestamp to heartbeat file so UnifiedFailover.mq5 knows
        Python is alive.

        Uses direct open('w') with 3-attempt retry instead of atomic rename.
        The tmp→rename pattern caused WinError 5 (Access Denied) because MT5
        holds a read lock on the .txt file at the exact moment Python tried
        to rename the .tmp over it. Direct write with short retry is safer
        on Windows NTFS for small single-line files.
        """
        if not self._hb_path:
            return
        hb = Path(self._hb_path)
        hb.parent.mkdir(parents=True, exist_ok=True)
        ts = str(int(time.time()))
        for attempt in range(3):
            try:
                hb.write_text(ts)
                return
            except Exception as e:
                if attempt < 2:
                    time.sleep(0.05)
                else:
                    self.logger.warning(f"Heartbeat write failed after 3 attempts: {e}")

    def run_cycle_all(self) -> int:
        """
        Run one entry check across all symbols.
        Returns count of new positions opened this cycle.
        """
        self._write_heartbeat()
        opened = 0
        for engine in self.engines:
            try:
                if engine.run_cycle():
                    opened += 1
            except Exception as e:
                self.logger.error(
                    f"[{engine.config.symbol}] Cycle error: {e}", exc_info=True
                )
        return opened

    def run(self, stop_event=None):
        """
        Standalone blocking loop. Pass stop_event (threading.Event)
        for clean shutdown from unified runner.
        """
        self.logger.info("CABEntryRunner STARTED")
        import threading
        _stop = stop_event or threading.Event()
        try:
            while not _stop.is_set():
                cycle_start = time.time()
                self.run_cycle_all()
                elapsed    = time.time() - cycle_start
                sleep_time = max(0, self.interval - elapsed)
                _stop.wait(sleep_time)
        except KeyboardInterrupt:
            self.logger.info("CABEntryRunner stopped by user")
        finally:
            self.logger.info("CABEntryRunner stopped")


# ==============================================================================
#  CONFIG BUILDER — reads from config.json symbols section
# ==============================================================================
def build_cab_entry_configs(config_data: dict) -> List[CABEntryConfig]:
    """
    Build a list of CABEntryConfig from config.json.
    Uses the same symbols section as SuperTrend.
    All CAB positions share magic_number 999555.

    Reads per-symbol overrides from an optional 'cab_entry' key,
    falls back to global_settings, then to dataclass defaults.
    """
    gs   = config_data.get("global_settings", {})
    syms = config_data.get("symbols", {})
    hb   = config_data.get("heartbeat", {})

    configs = []
    for symbol, sym_cfg in syms.items():
        cab = sym_cfg.get("cab_entry", {})

        def get(key, default):
            return cab.get(key, gs.get(key, default))

        cfg = CABEntryConfig(
            symbol            = symbol,
            magic_number      = 999555,
            risk_percent      = get("cab_risk_percent",    1.0),
            atr_multiplier    = get("cab_atr_multiplier",  2.5),
            atr_period        = get("cab_atr_period",      14),
            max_spread_points = get("cab_max_spread",      50),
            max_positions     = get("cab_max_positions",   1),
            session_gate_enabled = get("cab_session_gate", True),
            max_lot_demo_cap  = get("cab_max_lot_demo_cap", 0.01),
            heartbeat_path    = hb.get("path", ""),
        )
        configs.append(cfg)
        logger.info(
            f"CABEntryConfig | {symbol} | "
            f"risk={cfg.risk_percent}% atr_mult={cfg.atr_multiplier} "
            f"session_gate={'ON' if cfg.session_gate_enabled else 'OFF'} "
            f"lot_cap={cfg.max_lot_demo_cap if cfg.max_lot_demo_cap else 'OFF (pure risk-based)'}"
        )

    return configs


# ==============================================================================
#  STANDALONE ENTRY POINT
# ==============================================================================
def main():
    import json
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
        handlers=[
            logging.FileHandler("logs/cab_entry.log", encoding="utf-8"),
            logging.StreamHandler()
        ]
    )

    with open("config/config.json") as f:
        config_data = json.load(f)

    acc_cfg = config_data["accounts"]["demo"]

    if not mt5.initialize(path=acc_cfg.get("mt5_path"), timeout=180_000):
        logger.error(f"MT5 init failed: {mt5.last_error()}")
        return
    if not mt5.login(acc_cfg["login"], password=acc_cfg["password"],
                     server=acc_cfg["server"]):
        logger.error(f"MT5 login failed: {mt5.last_error()}")
        mt5.shutdown()
        return

    logger.info(f"Connected | {mt5.account_info().server}")

    hb_path = config_data.get("heartbeat", {}).get("path", "")
    configs = build_cab_entry_configs(config_data)

    runner = CABEntryRunner(configs, heartbeat_path=hb_path, interval_seconds=30)
    try:
        runner.run()
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()