"""
CAB Legacy Manager — V1 Fluid Matrix Port for V2
=================================================
Ports the complete V1 (cab_watcher.py v16.4-1) position management
logic into V2's architecture. All V1 production-calibrated thresholds
and management features are preserved exactly.

V1 Features Ported:
  - Protector at 1.2R (was 0.7R in V2)
  - Reaper at -0.5R (was -0.25R in V2)
  - Lock Gate at 1.7R (was missing in V2)
  - Partial Harvester: 50% close at 2R, trail remainder at 1.5x ATR
  - Continuous SL Tightening: 10% M15 ATR step between milestones
  - Close Circuit Breaker: 5 retries then 5-min suppress
  - Cost-aware Spread Guard on closes
  - M15 ATR helper for Protector/Lock Gate buffers
  - Full Group Invalidation cascade (unchanged)
  - OSI guard: suppress if protector-active AND in profit

V2 Architecture Preserved:
  - Uses self.gateway (MT5Gateway) instead of raw mt5.*
  - Uses self.kr (KnowledgeRegister) instead of global singleton
  - Uses self.tm (TradeManager) for _close_position / _modify_sl
  - No entry logic changes

Author: CAB Trader  |  Date: 30 August 2026
"""

import logging
import time
import math
from datetime import datetime
from typing import Dict
import MetaTrader5 as mt5
import pandas as pd
import numpy as np

logger = logging.getLogger("CABLegacy")

# ==============================================================================
# V1 PRODUCTION-CALIBRATED THRESHOLDS
# ==============================================================================
PROTECTOR_R = 1.2                    # Move SL to BE + buffer at this R
HARVESTER_R = 2.0                    # Close 50% at this R, trail remainder
REAPER_R    = 0.5                    # Cut loss in trending at -0.5R
GROUP_INVALIDATION_R = -1.5          # Per-symbol cascade exit

# cw-harvpart: partial harvester config
HARVESTER_PARTIAL_FRAC = 0.50        # Close this fraction at 2R
HARVESTER_TRAIL_ATR    = 1.5         # Trail remainder with N x M15 ATR

# cw-reaper: Asian session hours (UTC) — suppress REAPER on XAUUSD
REAPER_ASIAN_SUPPRESS_HOURS = (0, 1, 2, 3, 4, 5, 6)  # 00:00-06:59 UTC


class CABLegacyManager:
    def __init__(self, gateway, kr, trade_manager):
        self.gateway = gateway
        self.kr = kr
        self.tm = trade_manager
        self.processed_actions = {}
        self._last_macro_bar_time = {}
        # Circuit breaker state for _close_position: {ticket: (fail_count, suppress_until)}
        self._close_suppressed = {}

    # ==========================================================================
    # M15 ATR HELPER
    # ==========================================================================
    def _get_m15_atr(self, symbol: str, period: int = 14) -> float:
        """M15 ATR for Protector buffer and Harvester trail — same as V1."""
        rates = self.gateway.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, period + 5)
        if rates is None or len(rates) < period:
            return 1.0
        df = pd.DataFrame(rates)
        df["tr"] = np.maximum(
            df["high"] - df["low"],
            np.maximum(
                (df["high"] - df["close"].shift(1)).abs(),
                (df["low"] - df["close"].shift(1)).abs()
            )
        )
        val = df["tr"].rolling(period).mean().iloc[-1]
        return float(val) if not pd.isna(val) else 1.0

    # ==========================================================================
    # COST-AWARE SPREAD GUARD (from V1)
    # ==========================================================================
    def _spread_allows_close(self, pos, tick, sym_info) -> tuple:
        """Same cost-aware spread logic as V1 cab_watcher."""
        if sym_info is None or sym_info.point <= 0:
            return True, "no_sym_info"
        spread_pts = (tick.ask - tick.bid) / sym_info.point
        if spread_pts > 500:
            return False, f"spread {spread_pts:.0f}pts > 500pt emergency limit"
        if spread_pts <= 100:
            return True, "normal_spread"
        try:
            spread_cost = (
                (tick.ask - tick.bid) / sym_info.trade_tick_size
                * sym_info.trade_tick_value * pos.volume
            )
        except Exception:
            spread_cost = 0.0
        profit = pos.profit
        if profit > 0 and profit >= spread_cost:
            return True, f"profit {profit:.2f} covers spread"
        if profit < 0 and abs(profit) >= spread_cost * 2:
            return True, f"loss dominates spread"
        return False, f"spread {spread_pts:.0f}pts — near breakeven, deferring"

    # ==========================================================================
    # CLOSE POSITION — with V1 circuit breaker + spread guard
    # ==========================================================================
    def _close_position_cab(self, pos, reason: str) -> bool:
        """
        Market-close a position with V1's circuit breaker and spread guard.
        - Cost-aware spread guard: blocks close when spread is wide and
          profit is near breakeven (defers to next cycle).
        - Circuit breaker: after 5 consecutive failures, suppress for 5 minutes.
        - Retries silently until suppressed window expires.
        """
        sym_info = self.gateway.symbol_info(pos.symbol)
        tick = self.gateway.symbol_info_tick(pos.symbol)

        if tick is None or sym_info is None:
            logger.warning(
                f"  Close DEFERRED #{pos.ticket} — tick or sym_info unavailable "
                f"({reason[:40]}) — will retry next cycle"
            )
            return False

        # Circuit breaker: check suppression
        suppressed = self._close_suppressed.get(pos.ticket)
        if suppressed:
            fail_count, suppress_until = suppressed
            if time.time() < suppress_until:
                return False  # silently skip
            else:
                del self._close_suppressed[pos.ticket]

        # Cost-aware spread guard
        allow, reason_spread = self._spread_allows_close(pos, tick, sym_info)
        if not allow:
            logger.warning(f"  Close BLOCKED #{pos.ticket} — {reason_spread}")
            return False

        is_buy = (pos.type == 0)
        order_type = mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY
        price = tick.bid if is_buy else tick.ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": pos.ticket,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": order_type,
            "price": price,
            "deviation": 20,
            "magic": pos.magic,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        res = self.gateway.order_send(request)

        if res is None:
            error = self.gateway.last_error()
            logger.error(f"  Close FAILED #{pos.ticket} | order_send returned None | err={error}")
            return False

        if res.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"  Closed #{pos.ticket} | {reason} | P&L: {pos.profit:.2f}")
            # Cleanup
            try:
                self.kr.unregister_trade_thesis(pos.ticket)
            except Exception:
                pass
            self._close_suppressed.pop(pos.ticket, None)
            return True

        elif res.retcode == 10036:
            # Already closed by broker (SL/TP hit)
            logger.info(f"  #{pos.ticket} already closed by broker — skipping")
            self._close_suppressed.pop(pos.ticket, None)
            return False

        else:
            # Circuit breaker: track failures
            prev = self._close_suppressed.get(pos.ticket, (0, 0.0))
            new_count = prev[0] + 1
            suppress_seconds = 300  # 5 minutes

            if res.retcode == 10018:  # Market closed
                self._close_suppressed[pos.ticket] = (new_count, time.time() + suppress_seconds)
                logger.warning(
                    f"  Close SUPPRESSED #{pos.ticket} | Market closed (10018) | "
                    f"will retry in {suppress_seconds}s"
                )
            elif new_count >= 5:
                self._close_suppressed[pos.ticket] = (new_count, time.time() + suppress_seconds)
                logger.warning(
                    f"  Close SUPPRESSED #{pos.ticket} | {new_count} consecutive failures | "
                    f"last code={res.retcode} | will retry in {suppress_seconds}s"
                )
            else:
                self._close_suppressed[pos.ticket] = (new_count, 0.0)
                logger.error(
                    f"  Close FAILED #{pos.ticket} | "
                    f"code={res.retcode} | {res.comment} | attempt {new_count}/5"
                )
            return False

    # ==========================================================================
    # MICRO DEGRADATION (for Reaper)
    # ==========================================================================
    def get_micro_degradation(self, ticket: int, current_price: float, current_atr: float, thesis) -> Dict[str, float]:
        time_held_hours = max((time.time() - thesis.timestamp) / 3600.0, 0.01)

        if thesis.direction == 1:
            price_diff = current_price - thesis.fill_price
        else:
            price_diff = thesis.fill_price - current_price

        initial_risk = abs(thesis.fill_price - thesis.initial_sl)
        if initial_risk <= 0:
            initial_risk = current_atr * 1.5

        r_multiple = price_diff / initial_risk
        r_velocity = r_multiple / time_held_hours
        decay_factor = max(0.0, (time_held_hours / 12.0) - max(0.0, r_multiple))

        return {
            "r_multiple": round(r_multiple, 4),
            "r_velocity": round(r_velocity, 4),
            "decay_factor": round(decay_factor, 4)
        }

    # ==========================================================================
    # OSI DETECTION (from V1 with bar-time guard)
    # ==========================================================================
    _osi_fired_bars: dict = {}  # {symbol: last_bar_time_that_triggered_OSI}

    def _detect_opposite_signal(self, symbol: str, is_buy: bool) -> bool:
        """
        Opposite Signal Invalidation (OSI) — V1 cab_watcher v16.4-1.
        Same implementation. Returns True on bearish inversion (invalidates BUY)
        or bullish inversion (invalidates SELL). Same H4 bar fires only once.
        """
        try:
            rates = self.gateway.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 0, 3)
            if rates is None or len(rates) < 3:
                return False

            bar2 = rates[-3]   # two bars ago
            bar1 = rates[-2]   # last closed bar
            current_bar_time = int(bar1["time"])

            # Guard: only fire once per H4 bar per symbol
            if self._osi_fired_bars.get(symbol) == current_bar_time:
                return False

            bar2_bullish = bar2["close"] > bar2["open"]
            bar1_bullish = bar1["close"] > bar1["open"]

            # Inversion against BUY: bar[-3] bullish -> bar[-2] bearish
            if is_buy and bar2_bullish and not bar1_bullish:
                self._osi_fired_bars[symbol] = current_bar_time
                logger.info(
                    f"  OSI detected [{symbol}] bearish H4 inversion "
                    f"— invalidates BUY"
                )
                return True

            # Inversion against SELL: bar[-3] bearish -> bar[-2] bullish
            if not is_buy and not bar2_bullish and bar1_bullish:
                self._osi_fired_bars[symbol] = current_bar_time
                logger.info(
                    f"  OSI detected [{symbol}] bullish H4 inversion "
                    f"— invalidates SELL"
                )
                return True

            return False
        except Exception as e:
            logger.debug(f"  OSI check error [{symbol}]: {e}")
            return False

    # ==========================================================================
    # V1 FLUID MATRIX — COMPLETE PORT
    # ==========================================================================
    def manage_fluid_logic(self, positions: list):
        """
        Complete V1 fluid matrix port. Manages all open CAB positions
        using the full production-calibrated decision hierarchy:
          1. Group Invalidation (per-symbol R cascade)
          2. OSI (on H4 bar close)
          3. Reaper (on H4 bar close, trending only)
          4. Protector (every cycle)
          5. Lock Gate (every cycle)
          6. Continuous SL Tightening (every cycle, live tick)
          7. Partial Harvester (every cycle, 50% close + trail)
        """
        if not positions:
            return

        # -- Grouped Portfolio R-Budgeting ---------------------------------------
        symbols_present = sorted({p.symbol for p in positions})
        valid_positions = []

        for sym in symbols_present:
            sym_positions = [p for p in positions if p.symbol == sym]
            sym_rs = []
            for p in sym_positions:
                is_buy = (p.type == 0)
                risk_dist = abs(p.price_open - p.sl)
                if risk_dist == 0:
                    continue
                price_move = (p.price_current - p.price_open) if is_buy else (p.price_open - p.price_current)
                sym_rs.append((p, price_move / risk_dist))

            r_total = sum(r for _, r in sym_rs)
            if r_total <= GROUP_INVALIDATION_R:
                logger.warning(f"GROUP INVALIDATION [{sym}] | Total R={r_total:+.2f}")
                sym_rs.sort(key=lambda x: x[1])
                for p, r in sym_rs:
                    if self._close_position_cab(p, f"GROUP_INVALIDATION|R_total={r_total:+.2f}"):
                        if p.ticket not in self.processed_actions:
                            self.processed_actions[p.ticket] = set()
                        self.processed_actions[p.ticket].add("GROUP_INVALIDATION")
                continue

            valid_positions.extend(sym_positions)

        positions = valid_positions
        if not positions:
            return

        # -- Per-symbol Regime + M15 ATR ----------------------------------------
        symbols_present = sorted({p.symbol for p in positions})
        regime_by_symbol = {}
        atr_by_symbol = {}

        for sym in symbols_present:
            # Get regime from Knowledge Register
            state = self.kr.get_market_state(sym, "H4")
            if state:
                regime_str = state.regime.value if hasattr(state.regime, 'value') else str(state.regime)
                if regime_str.startswith("TRENDING"):
                    regime_str = "TRENDING"
                regime_by_symbol[sym] = {
                    "regime": regime_str,
                    "source_bar_time": state.source_bar_time
                }
            else:
                regime_by_symbol[sym] = {"regime": "STABLE", "source_bar_time": 0}

            atr_by_symbol[sym] = self._get_m15_atr(sym)

        # -- Position Loop — Full Fluid Matrix -----------------------------------
        for pos in positions:
            intel = regime_by_symbol[pos.symbol]
            regime = intel["regime"]

            # Fetch immutable entry ATR if available
            thesis = self.kr.get_entry_snapshot(pos.ticket)
            if thesis and thesis.entry_atr > 0:
                m15_atr = thesis.entry_atr
            else:
                m15_atr = atr_by_symbol[pos.symbol]

            if pos.ticket not in self.processed_actions:
                self.processed_actions[pos.ticket] = set()

            if pos.sl == 0:
                continue

            done = self.processed_actions[pos.ticket]

            # -- R calculation (price-distance method) ---------------------------
            is_buy = (pos.type == 0)
            risk_dist = abs(pos.price_open - pos.sl)
            if risk_dist == 0:
                continue

            price_move = (
                (pos.price_current - pos.price_open) if is_buy
                else (pos.price_open - pos.price_current)
            )
            current_r = price_move / risk_dist

            side = "BUY" if is_buy else "SELL"
            logger.debug(
                f"  #{pos.ticket} {side} | "
                f"R={current_r:+.2f} | "
                f"Regime={regime} | "
                f"Done={done}"
            )

            # -- MACRO GATE: OSI & REAPER (H4 bar close only) --------------------
            bar_time = intel.get("source_bar_time", 0)
            is_new_h4_bar = (bar_time > self._last_macro_bar_time.get(pos.symbol, 0))

            if is_new_h4_bar:
                # OSI: Opposite Signal Invalidation
                if "OSI" not in done:
                    osi_triggered = self._detect_opposite_signal(pos.symbol, is_buy)
                    if osi_triggered:
                        # Publish invalidation to KR
                        try:
                            kr_dir = 1 if is_buy else -1
                            self.kr.publish_invalidation(
                                symbol=pos.symbol,
                                direction=kr_dir,
                                source_bot="CAB",
                                reason="CAB OSI",
                                ttl_seconds=14400.0
                            )
                        except Exception:
                            pass

                        protector_active = "PROTECTOR" in done or "HARVESTER" in done
                        if protector_active and current_r >= 0:
                            logger.info(
                                f"  OSI SUPPRESSED #{pos.ticket} - "
                                f"R={current_r:+.2f} | protector_active=True"
                            )
                        else:
                            if self._close_position_cab(pos, f"OSI|H4_INVERSION|R{current_r:+.2f}"):
                                done.add("OSI")
                                continue

                # Reaper: Dual-Vector Reaper (trending only)
                if (
                    regime == "TRENDING"
                    and current_r <= -REAPER_R
                    and "REAPER" not in done
                    and "PROTECTOR" not in done
                ):
                    degrad = self.get_micro_degradation(
                        pos.ticket, pos.price_current, m15_atr, thesis
                    ) if thesis else {"decay_factor": 0.0}
                    is_degrading = (degrad["decay_factor"] > 0.25)
                    asian_suppressed = (
                        pos.symbol in ("XAUUSDm", "XAUUSD.x")
                        and datetime.utcnow().hour in REAPER_ASIAN_SUPPRESS_HOURS
                    )

                    if is_degrading and not asian_suppressed:
                        if self._close_position_cab(
                            pos, f"REAPER|Macro=TREND_AGAINST|Micro=DEGRADING"
                        ):
                            done.add("REAPER")
                            logger.warning(
                                f"  * REAPER FIRED #{pos.ticket} | "
                                f"R={current_r:+.2f} | Vector=DEGRADING"
                            )
                            continue
                    else:
                        suppress_reason = (
                            "ASIAN_SESSION" if asian_suppressed
                            else "MICRO_VECTOR_HEALTHY"
                        )
                        logger.info(f"  REAPER BLOCKED #{pos.ticket} | R={current_r:+.2f} | {suppress_reason}")

                self._last_macro_bar_time[pos.symbol] = bar_time

            # -- PROTECTOR (V1 threshold: 1.2R) ----------------------------------
            if current_r >= PROTECTOR_R and "PROTECTOR" not in done:
                buffer = m15_atr * 0.15
                new_sl = (pos.price_open + buffer) if is_buy else (pos.price_open - buffer)
                sym_info = self.gateway.symbol_info(pos.symbol)
                if self.tm._modify_sl(pos, new_sl, sym_info.digits if sym_info else 3, "PROTECTOR"):
                    done.add("PROTECTOR")
                    logger.info(
                        f"  * PROTECTOR FIRED #{pos.ticket} | "
                        f"R={current_r:+.2f} | New SL={new_sl:.5f} | Buffer={buffer:.5f}"
                    )

            # -- LOCK GATE (V1: protector_r + 0.5 = 1.7R) -----------------------
            lock_gate_r = PROTECTOR_R + 0.5
            if current_r >= lock_gate_r and "LOCK_GATE" not in done:
                buffer = m15_atr * 0.5
                new_sl = (pos.price_open + buffer) if is_buy else (pos.price_open - buffer)
                # Only tighten
                if (is_buy and new_sl > pos.sl) or (not is_buy and new_sl < pos.sl):
                    sym_info = self.gateway.symbol_info(pos.symbol)
                    if self.tm._modify_sl(pos, new_sl, (sym_info.digits if sym_info else 3), "LOCK_GATE"):
                        done.add("LOCK_GATE")
                        logger.info(
                            f"  * LOCK GATE FIRED #{pos.ticket} | "
                            f"R={current_r:+.2f} | New SL={new_sl:.5f}"
                        )

            # -- FRESH TICK (shared by CONT_TIGHTEN and HARVESTER) ---------------
            live_tick = self.gateway.symbol_info_tick(pos.symbol)
            live_price = None
            if live_tick:
                live_price = live_tick.bid if is_buy else live_tick.ask

            # -- CONTINUOUS SL TIGHTENING (V1: 10% M15 ATR step) -----------------
            # Light SL tightening every cycle between milestones.
            # Only tightens (never loosens). Uses live tick price.
            if current_r > 0 and "PROTECTOR" in done and "HARVESTER" not in done and live_price:
                trail_dist = m15_atr * 0.10   # 10% of M15 ATR
                new_sl = (
                    (live_price - trail_dist) if is_buy
                    else (live_price + trail_dist)
                )
                if (is_buy and new_sl > pos.sl) or (not is_buy and new_sl < pos.sl):
                    sym_info = self.gateway.symbol_info(pos.symbol)
                    self.tm._modify_sl(pos, new_sl, sym_info.digits if sym_info else 3, "CONT_TIGHTEN")

            # -- PARTIAL HARVESTER (V1: 50% close at 2R + trail remainder) -------
            if (
                current_r >= HARVESTER_R
                and "HARVESTER" not in done
                and live_tick
                and live_price
            ):
                sym_info = self.gateway.symbol_info(pos.symbol)
                if sym_info:
                    # Calculate partial volume (50%), rounded to volume_step
                    partial_vol = round(
                        pos.volume * HARVESTER_PARTIAL_FRAC / sym_info.volume_step
                    ) * sym_info.volume_step
                    remainder = round(pos.volume - partial_vol, 8)

                    if remainder >= sym_info.volume_min:
                        # Partial close
                        order_type = (mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY)
                        req = {
                            "action": mt5.TRADE_ACTION_DEAL,
                            "position": pos.ticket,
                            "symbol": pos.symbol,
                            "volume": partial_vol,
                            "type": order_type,
                            "price": live_price,
                            "deviation": 20,
                            "magic": pos.magic,
                            "type_time": mt5.ORDER_TIME_GTC,
                            "type_filling": mt5.ORDER_FILLING_IOC,
                        }
                        res = self.gateway.order_send(req)
                        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                            done.add("HARVESTER")
                            # Trail SL for remainder
                            trail_sl = (
                                (live_price - m15_atr * HARVESTER_TRAIL_ATR)
                                if is_buy
                                else (live_price + m15_atr * HARVESTER_TRAIL_ATR)
                            )
                            self.tm._modify_sl(pos, trail_sl, sym_info.digits, "HARVESTER_TRAIL")
                            logger.warning(
                                f"  * HARVESTER PARTIAL #{pos.ticket} | "
                                f"closed {partial_vol} lots | "
                                f"remainder={remainder} trailing | "
                                f"R={current_r:+.2f}"
                            )
                    else:
                        # Remainder too small — full close
                        if self._close_position_cab(pos, f"HARVESTER_FULL|R{current_r:+.2f}"):
                            done.add("HARVESTER")
                            logger.warning(
                                f"  * HARVESTER FULL #{pos.ticket} | "
                                f"R={current_r:+.2f}"
                            )

        # -- Cleanup: purge stale processed_actions entries ----------------------
        live_tickets = {p.ticket for p in positions}
        stale = [t for t in list(self.processed_actions) if t not in live_tickets]
        for t in stale:
            self.processed_actions.pop(t, None)
        if stale:
            logger.debug(f"  Cleaned {len(stale)} stale processed_actions entries")

        # -- Periodic state snapshot (every ~60s via DEBUG) ----------------------
        if self.processed_actions:
            active = {t: list(v) for t, v in self.processed_actions.items() if v}
            if active:
                logger.debug(f"  Processed actions state: {active}")
