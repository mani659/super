import logging
import numpy as np
import pandas as pd
from typing import Optional, List, Dict
from dataclasses import dataclass
import time
import MetaTrader5 as mt5

from v2.core.knowledge_register import KnowledgeRegister
from v2.core.data_models import TradeSignal, TradeThesis
from v2.execution.mt5_gateway import MT5Gateway
from v2.execution.order_router import OrderRouter
from v2.bots.ghost_cache import GhostCache, N_LAYERS_DEFAULT

logger = logging.getLogger("GhostSniperBotV2")

GHOST_MAX_LEGS = 4  # Non-negotiable hard cap — Architecture Principle #7

# Grid-level exits from V1 GridState ARE ported. The state lives in
# v2/execution/grid_state.py and the decisions live in
# TradeManager._manage_ghost_grid(), applied to magic 204:
#     Grid TP        combined R >= +1.0   (V1 GRID_TP_R)
#     Grid Stop      combined R <= -3.0   (V1 GRID_STOP_R)
#     Grid Protector BE at    R >= +0.35   (V1 GRID_PROT_R)
# Verified 1-1 against ghost_super/sniper_watcher.py on Sep 19 2026. The previous
# note here claimed these were "NOT yet implemented" and told the reader not to
# begin shadow testing; both statements were stale.
#
# Still genuinely absent from V2 ghost management (see sniper_watcher.py):
# REAPER_ATR_MULT, EXHAUST_ATR_THRESH / EXHAUST_BODY_THRESH, TREND_ADX_THRESH,
# REGIME_BARS (170), MAX_GRID_AGE_SECONDS, and the calibration / conviction-log
# path. That gap is known, deferred, and quantified in the Sep 19 parity audit.

@dataclass
class GhostConfig:
    symbol: str
    magic_scalp: int = 201
    magic_reversal: int = 202
    volume: float = 0.01  # Fixed volume for ghost legs
    gate_202_adx_block: float = 40.0
    gate_202_conv_block: float = 60.0
    atr_step_multiplier: float = 1.0
    atr_step_floor: float = 0.5
    scalp_rev_sl_atr_mult: float = 0.35
    spread_max: float = 1.5
    cooldown_seconds: int = 45

class GhostBot:
    """
    V2 Ghost Bot: Pure mathematical grid engine.
    Extracts the arming and triggering state machine from V1.
    Generates Scalp (201) and Reversal (202) TradeSignals.
    """
    def __init__(
        self,
        config: GhostConfig,
        gateway: MT5Gateway,
        router: OrderRouter,
        kr: KnowledgeRegister
    ):
        self.config = config
        self.gateway = gateway
        self.router = router
        self.kr = kr
        
        # State Machine
        self.armed: Optional[str] = None  # None, "UP_PROBE", "DOWN_PROBE"
        self.probe_extreme: float = 0.0
        self.break_level: float = 0.0
        self.last_fire_time: float = 0.0
        self.arming_h4_direction: str = ""
        self.arming_m15_regime: str = ""
        
        # Ghost Cache state
        self.ghost_cache: Optional[GhostCache] = None

    def _get_atr(self, df: pd.DataFrame, n: int = 14) -> float:
        """Helper to compute ATR precisely as V1 did."""
        df = df.copy()
        df["tr"] = pd.concat([
            df["high"] - df["low"],
            (df["high"] - df["close"].shift()).abs()
        ], axis=1).max(axis=1)
        return float(df["tr"].rolling(n).mean().iloc[-1])

    def _get_h4_direction(self) -> str:
        """
        V1 parity — ghost_sniper._get_h4_direction() exactly:
        'UP'/'DOWN'/'UNKNOWN' from last closed H4 bar close vs close 3 bars prior.
        """
        try:
            rates = self.gateway.copy_rates_from_pos(self.config.symbol, mt5.TIMEFRAME_H4, 0, 4)
            if rates is None or len(rates) < 4:
                return "UNKNOWN"
            last_close = float(rates[-2]["close"])
            ref_close = float(rates[-4]["close"])
            if last_close > ref_close:
                return "UP"
            elif last_close < ref_close:
                return "DOWN"
            return "UNKNOWN"
        except Exception:
            return "UNKNOWN"

    @staticmethod
    def _normalise_h4_direction(value) -> str:
        """
        fix-h4-vocab: arming_h4_direction was written in two different vocabularies
        across the dataset — BEARISH/BULLISH up to 2026-09-05 and UP/DOWN from
        2026-09-06 — with no version marker, so any groupby on that column silently
        splits one market state into two. Normalises on write so a future schema
        change cannot reintroduce the split silently.
        """
        if value is None:
            return "UNKNOWN"
        v = str(value).strip().upper()
        return {
            "BULLISH": "UP",
            "BEARISH": "DOWN",
        }.get(v, v or "UNKNOWN")

    def _kr_entry_blocked(self, order_type) -> bool:
        """
        V1 parity — ghost_sniper.send_order() KR Layer 2 & 3 hard blocks.
        Returns True when the entry must be blocked.
        """
        kr_dir = 1 if order_type == mt5.ORDER_TYPE_BUY else -1
        invalidated, inv_reason = self.kr.is_entry_invalidated(self.config.symbol, kr_dir)
        if invalidated:
            logger.info(f"Entry BLOCKED by KR Layer 2: {inv_reason}")
            return True
        acc = self.gateway.account_info()
        equity = acc.equity if acc else 10000.0
        allowed, p_reason = self.kr.check_portfolio_entry_allowed(
            symbol=self.config.symbol,
            direction=kr_dir,
            proposed_risk_pct=0.5,
            account_equity=equity
        )
        if not allowed:
            logger.info(f"Entry BLOCKED by KR Layer 3: {p_reason}")
            return True
        return False

    def execute_cycle(self, df: pd.DataFrame, current_dd: float, max_dd: float,
                      allow_new_entry: bool = True, allow_shadow: bool = True,
                      allow_cache: bool = True):
        """
        Main tick cycle.
        df should be M1 timeframe data, at least 20 bars.

        allow_new_entry / allow_cache mirror V1 unified_runner's
        switches["ghost_grid"]["201"/"202"] and ["204"], which wrap the
        send_order() calls in ghost_hunter_thread (unified_runner.py:836,
        :855 for the probe legs and :733 for the cache).

        They gate the SEND only. Arming, the brain-state update, the probe
        state machine and the cooldown all keep running, so a switch turned
        off can never leave an armed probe or an unmanaged open position.
        That is the exact failure mode the switches block in config.json
        warns about.
        """
        if time.time() - self.last_fire_time < self.config.cooldown_seconds:
            return  # In cooldown

        if df is None or len(df) < 20:
            return

        tick = self.gateway.symbol_info_tick(self.config.symbol)
        if not tick:
            return

        current_price = (tick.bid + tick.ask) / 2.0
        spread = tick.ask - tick.bid
        atr = self._get_atr(df)
        dynamic_step = max(atr * self.config.atr_step_multiplier, self.config.atr_step_floor)

        # Pre-fetch KR state
        snapshot = self.kr.get_market_state(self.config.symbol, "M15")
        if not snapshot:
            return

        bs_regime = snapshot.regime if snapshot.regime else "UNKNOWN"
        bs_adx = snapshot.adx_raw
        # V1 brain conviction composite — sniper_watcher.get_market_state() parity:
        #   conviction = min(ADX_raw * 1.0 + momentum_score * 0.5, 100)
        #   momentum_score = (current M1 body / avg M1 body) * 50
        try:
            _df_m = df.copy()
            _df_m["body"] = (_df_m["close"] - _df_m["open"]).abs()
            _avg_body = float(_df_m["body"].mean())
            _cur_body = float(_df_m["body"].iloc[-1])
            momentum_score = (_cur_body / (_avg_body + 1e-9)) * 50
        except Exception:
            momentum_score = 25.0  # V1 neutral fallback
        bs_conv = float(min(bs_adx * 1.0 + momentum_score * 0.5, 100))

        # trigger is only meaningful inside the tracking branch below, but the
        # GC (204) update block after it needs a defined value on EVERY tick —
        # including arming ticks (after a 202 fire, armed=None while ghost_cache
        # persists). Initialize here to prevent NameError killing the runner.
        trigger = False

        # 1. Probe Detection (Arming)
        if self.armed is None:
            # Ghost does not arm if regime is strongly trending
            if bs_regime in ("TRENDING_UP", "TRENDING_DOWN", "UNKNOWN"):
                return

            # F6 Cross-Bot Gate: Prevent UP_PROBE if SuperTrend is LONG
            st_long = False
            for t in self.kr.get_active_theses():
                bot_system = getattr(t, 'bot_system', getattr(t, 'bot_name', ''))
                if t.symbol == self.config.symbol and bot_system == "SuperTrendBotV2" and getattr(t, 'direction', 0) == 1:
                    st_long = True
                    break

            recent_high = df["high"].iloc[-5:].max()
            recent_low  = df["low"].iloc[-5:].min()

            # F15 gate — V1 parity (unified_runner ghost_hunter_thread):
            # block DOWN_PROBE arming when price breaks below 5-bar low while H4 is DOWN
            h4_dir_now = self._get_h4_direction()
            if current_price < recent_low and h4_dir_now == "DOWN":
                logger.info(
                    f"GHOST_ARM_BLOCKED_H4_DOWN | "
                    f"price={current_price:.3f} | "
                    f"h4={h4_dir_now} — DOWN_PROBE suppressed"
                )
                return

            if current_price > recent_high:
                if st_long:
                    logger.info(f"GHOST_ARM_BLOCKED_ST_LONG: {self.config.symbol} - SuperTrend holds long.")
                    return  # Block arming

                self.arming_h4_direction = self._normalise_h4_direction(h4_dir_now)
                self.arming_m15_regime = bs_regime
                self.armed = "UP_PROBE"
                self.probe_extreme = current_price
                self.break_level = current_price - dynamic_step
                self.ghost_cache = GhostCache(
                    probe_direction="UP_PROBE",
                    probe_origin=self.break_level,
                    probe_extreme=current_price,
                    atr_step=dynamic_step,
                    n_layers=N_LAYERS_DEFAULT
                )
                logger.info(f"Ghost ARMED UP_PROBE at {current_price:.3f} (step={dynamic_step:.3f})")
                
            elif current_price < recent_low:
                self.arming_h4_direction = self._normalise_h4_direction(h4_dir_now)
                self.arming_m15_regime = bs_regime
                self.armed = "DOWN_PROBE"
                self.probe_extreme = current_price
                self.break_level = current_price + dynamic_step
                self.ghost_cache = GhostCache(
                    probe_direction="DOWN_PROBE",
                    probe_origin=self.break_level,
                    probe_extreme=current_price,
                    atr_step=dynamic_step,
                    n_layers=N_LAYERS_DEFAULT
                )
                logger.info(f"Ghost ARMED DOWN_PROBE at {current_price:.3f} (step={dynamic_step:.3f})")

        # 2. Tracking and Triggering
        else:
            if self.armed == "UP_PROBE":
                if current_price > self.probe_extreme:
                    self.probe_extreme = current_price
                    self.break_level = current_price - dynamic_step
                trigger = current_price < self.break_level
                
            elif self.armed == "DOWN_PROBE":
                if current_price < self.probe_extreme:
                    self.probe_extreme = current_price
                    self.break_level = current_price + dynamic_step
                trigger = current_price > self.break_level

            if trigger:
                # -- M1 retrace structure at fire (LOGGING ONLY) ------------------
                # V1 parity (ghost_sniper.run_hunter / unified_runner.ghost_hunter_
                # thread). Placed BEFORE the spread guard so quality is captured on
                # blocked fires too. Features for the offline win/loss classifier;
                # try/except keeps it out of the fire path entirely.
                try:
                    _retrace_rates = self.gateway.copy_rates_from_pos(
                        self.config.symbol, mt5.TIMEFRAME_M1, 0, 5
                    )
                    committed_bars = 0
                    retrace_body_ratio = 0.0
                    if _retrace_rates is not None and len(_retrace_rates) >= 2:
                        # UP_PROBE fires SELL, so reversal bars are bearish;
                        # DOWN_PROBE fires BUY, so reversal bars are bullish.
                        for _bar in _retrace_rates[-3:]:
                            _bar_bull = _bar["close"] > _bar["open"]
                            _bar_range = max(_bar["high"] - _bar["low"], 0.0001)
                            _body_ratio = abs(_bar["close"] - _bar["open"]) / _bar_range
                            if self.armed == "UP_PROBE" and not _bar_bull and _body_ratio > 0.35:
                                committed_bars += 1
                            elif self.armed == "DOWN_PROBE" and _bar_bull and _body_ratio > 0.35:
                                committed_bars += 1

                        _last = _retrace_rates[-2]
                        _last_range = max(_last["high"] - _last["low"], 0.0001)
                        retrace_body_ratio = abs(_last["close"] - _last["open"]) / _last_range

                    logger.info(
                        f"GHOST_FIRE_QUALITY | {self.armed} | "
                        f"committed_reversal_bars={committed_bars}/3 | "
                        f"trigger_bar_body_ratio={retrace_body_ratio:.3f} | "
                        f"atr={round(atr, 5)} | "
                        f"conviction={round(float(bs_conv), 1)} | "
                        f"adx={round(float(bs_adx), 2)}"
                    )
                except Exception as _gq:
                    logger.debug(f"Ghost fire quality log error: {_gq}")

                if spread > self.config.spread_max:
                    # V1 parity: unified_runner demo mode does NOT abort on spread
                    # (log SKIP_SPREAD, continue to fire) — sniper_hunter thread:
                    #   if spread > gh.SPREAD_MAX and not demo:  (demo=True -> never abort)
                    logger.info(f"SKIP_SPREAD spread={spread:.3f} (demo parity — no abort, V1 behavior)")

                # Calculate SL for the reversal legs
                sl_dist_tight = self.config.scalp_rev_sl_atr_mult * atr
                
                # If UP_PROBE, price fell back down. We SELL the reversal.
                # If DOWN_PROBE, price bounced up. We BUY the reversal.
                dir_rev = mt5.ORDER_TYPE_SELL if self.armed == "UP_PROBE" else mt5.ORDER_TYPE_BUY
                
                # SL placed above/below the extreme we just rejected
                sl_rev = (self.probe_extreme + sl_dist_tight if self.armed == "UP_PROBE"
                          else self.probe_extreme - sl_dist_tight)
                          
                fill_price = tick.bid if dir_rev == mt5.ORDER_TYPE_SELL else tick.ask

                # Gate Logic
                gate_202 = not (bs_adx > self.config.gate_202_adx_block or bs_conv > self.config.gate_202_conv_block)
                gate_201 = True  # Scalp always open

                # fix-switches (V1 parity): ghost_grid.201 / .202 gate the SEND,
                # not the arming or the probe state machine. These two flags are
                # the V2 equivalent of unified_runner.py:836 and :855, where V1
                # wraps each probe-leg send_order() in switches["ghost_grid"][leg].
                if not allow_new_entry:
                    logger.info(
                        f"GHOST ENTRY BLOCKED | {self.config.symbol} | "
                        f"ghost_grid.202 switch off"
                    )
                    gate_202 = False
                if not allow_shadow:
                    gate_201 = False

                existing_legs = [
                    p for p in (self.gateway.positions_get(symbol=self.config.symbol) or [])
                    if p.magic in {201, 202, 204}
                ]
                if len(existing_legs) >= GHOST_MAX_LEGS:
                    logger.warning(
                        f"GHOST ENTRY BLOCKED — MAX_LEGS cap reached "
                        f"({len(existing_legs)}/{GHOST_MAX_LEGS}) | "
                        f"symbol={self.config.symbol}"
                    )
                    self.armed = None
                    # 204 DECOUPLE: ghost_cache persists
                    self.arming_h4_direction = ""
                    self.arming_m15_regime = ""
                    return

                signals_to_fire = []
                
                # V1 parity — ghost_sniper.send_order() KR Layer 2 & 3 hard blocks
                # run before EVERY order (reversal legs and cache legs alike).
                if self._kr_entry_blocked(dir_rev):
                    self.armed = None
                    self.arming_h4_direction = ""
                    self.arming_m15_regime = ""
                    return

                if gate_202:
                    signals_to_fire.append({
                        "magic": self.config.magic_reversal,
                        "type": dir_rev,
                        "sl": sl_rev,
                        "tp_r": 1.5,
                        "comment": "G_REV_V2",
                        "setup": "REVERSAL"
                    })
                    
                if gate_201:
                    signals_to_fire.append({
                        "magic": self.config.magic_scalp,
                        "type": dir_rev,
                        "sl": sl_rev,
                        "tp_r": 1.0,
                        "comment": "G_SCL_V2",
                        "setup": "SCALP"
                    })

                fired_any = False
                for sig in signals_to_fire:
                    ts = TradeSignal(
                        symbol=self.config.symbol,
                        bot_name="GhostSniperV2",
                        magic_number=sig["magic"],
                        order_type=sig["type"],
                        sl_price=sig["sl"]
                    )
                    
                    if self.router.route_signal(ts, current_dd, max_dd):
                        # --- SHADOW LEG 201 INTERCEPTION ---
                        if sig["magic"] == self.config.magic_scalp:  # Leg 201
                            
                            logger.info(f"[GhostSniper V2] VIRTUAL_FILL magic={sig['magic']} ticket=VIRTUAL price={fill_price}")
                            # V1 parity: virtual fill uses the market price at send time
                            # (ghost_sniper.send_order is_shadow branch: fill_price = tick.ask/bid)
                            thesis = TradeThesis(
                                ticket=999999 + sig["magic"],
                                symbol=self.config.symbol,
                                direction=1 if sig["type"] == 0 else -1,
                                bot_system="GhostSniperV2",
                                setup_type=sig["setup"],
                                fill_price=fill_price,
                                timestamp=time.time(),
                                entry_atr=0.0,
                                regime_at_entry="UNKNOWN",
                                entry_conviction=0.0,
                                arming_h4_direction=self.arming_h4_direction,
                                arming_m15_regime=self.arming_m15_regime,
                                layer_depth=1,
                                initial_sl=sig["sl"],
                                initial_tp=0.0,
                                market_snapshot=None,
                                is_virtual=True
                            )
                            self.kr.unregister_trade_thesis(999999 + sig["magic"])
                            self.kr.register_trade_thesis(thesis)
                            continue  # Bypass actual MT5 order sending

                        # Send Order
                        req = {
                            "action": mt5.TRADE_ACTION_DEAL,
                            "symbol": self.config.symbol,
                            "volume": self.config.volume,
                            "type": sig["type"],
                            "price": fill_price,
                            "sl": 0.0,  # Phase 1: Market execution without SL to prevent 10016 rejection
                            "tp": 0.0,
                            "deviation": 20,
                            "magic": sig["magic"],
                            "comment": sig["comment"],
                            "type_time": mt5.ORDER_TIME_GTC,
                            "type_filling": mt5.ORDER_FILLING_IOC,
                        }
                        res = self.gateway.order_send(req)
                        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                            actual_fill_price = res.price
                            # Phase 2: SL/TP Anchor (Robust retry to clear stops_level)
                            sl_target = sig["sl"]
                            risk_dist = abs(actual_fill_price - sl_target)
                            tp_target = actual_fill_price + (risk_dist * sig["tp_r"]) if sig["type"] == mt5.ORDER_TYPE_BUY else actual_fill_price - (risk_dist * sig["tp_r"])
                            mod_req = {
                                "action": mt5.TRADE_ACTION_SLTP,
                                "symbol": self.config.symbol,
                                "position": res.order,
                                "sl": round(sl_target, 3),
                                "tp": round(tp_target, 3),
                            }
                            
                            sym_info = self.gateway.symbol_info(self.config.symbol)
                            retry_buf = sym_info.point * 50 if sym_info else 0.05
                            
                            for _retry in range(3):
                                mod = self.gateway.order_send(mod_req)
                                if mod and mod.retcode == mt5.TRADE_RETCODE_DONE:
                                    break
                                # If 10016 (Invalid Stops), widen buffer and retry
                                if mod and mod.retcode == 10016:
                                    logger.warning(f"10016 SL Rejected. Widening buffer by {retry_buf}")
                                    time.sleep(0.2)
                                    stops_level = sym_info.trade_stops_level * sym_info.point if sym_info else 0.0
                                    if sig["type"] == mt5.ORDER_TYPE_BUY:
                                        sl_target = actual_fill_price - stops_level - retry_buf
                                    else:
                                        sl_target = actual_fill_price + stops_level + retry_buf
                                    mod_req["sl"] = round(sl_target, 3)
                                    
                                    new_risk = abs(actual_fill_price - sl_target)
                                    tp_target = actual_fill_price + (new_risk * sig["tp_r"]) if sig["type"] == mt5.ORDER_TYPE_BUY else actual_fill_price - (new_risk * sig["tp_r"])
                                    mod_req["tp"] = round(tp_target, 3)
                                    retry_buf *= 2
                                else:
                                    break
                        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                            fired_any = True
                            logger.info(f"Ghost Executed {sig['setup']} | Ticket {res.order}")
                            
                            # Register Thesis
                            thesis = TradeThesis(
                                ticket=res.order,
                                symbol=self.config.symbol,
                                direction=1 if sig["type"] == mt5.ORDER_TYPE_BUY else -1,
                                bot_system="GhostSniperV2",
                                setup_type=sig["setup"],
                                fill_price=actual_fill_price,
                                initial_sl=sig["sl"],
                                initial_tp=round(tp_target, 3),
                                entry_atr=atr,
                                regime_at_entry=snapshot.regime,
                                entry_conviction=bs_conv,
                                arming_h4_direction=self.arming_h4_direction,
                                arming_m15_regime=self.arming_m15_regime,
                                layer_depth=1,
                                timestamp=time.time(),
                                market_snapshot=snapshot
                            )
                            self.kr.register_trade_thesis(thesis)

                if fired_any:
                    self.last_fire_time = time.time()
                
                # Reset state machine
                self.armed = None
                # 204 DECOUPLE: ghost_cache persists after 202 fire.
                self.arming_h4_direction = ""
                self.arming_m15_regime = ""
            
        # GC-Hunter: update GhostCache every tick independently
        # V1 parity: cache update is skipped on the tick where the probe trigger
        # fires (unified_runner ghost_hunter_thread: 'and not trigger').
        # fix-switches (V1 parity): unified_runner.py:733 writes
        #   if ghost_cache is not None and not trigger and switches["ghost_grid"]["204"]:
        # so V1 skips the cache UPDATE as well as the 204 send when the switch
        # is off -- this condition is deliberately identical, not just the send.
        if self.ghost_cache is not None and not trigger and allow_cache:
            gc_signal = self.ghost_cache.update(current_price, atr)
            if gc_signal is not None:
                # V1 parity: GC (204) fires WITHOUT the MAX_LEGS cap check —
                # ghost_hunter_thread calls send_order() directly for 204.
                # KR Layer 2/3 hard blocks still apply (send_order parity).
                order_type = mt5.ORDER_TYPE_SELL if gc_signal['order_type'] == 'SELL' else mt5.ORDER_TYPE_BUY
                if self._kr_entry_blocked(order_type):
                    return
                fill_price = tick.bid if order_type == mt5.ORDER_TYPE_SELL else tick.ask
                ts = TradeSignal(
                    symbol=self.config.symbol,
                    bot_name="GhostSniperV2",
                    magic_number=204, # Magic Ghost Cache
                    order_type=order_type,
                    sl_price=gc_signal['sl']
                )
                if self.router.route_signal(ts, current_dd, max_dd):
                    # Same 2-Phase Execution for 204
                    req = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "symbol": self.config.symbol,
                        "volume": self.config.volume,
                        "type": order_type,
                        "price": fill_price,
                        "sl": 0.0,
                        "tp": 0.0,
                        "deviation": 20,
                        "magic": 204,
                        "comment": "G_CACHE_V2",
                        "type_time": mt5.ORDER_TIME_GTC,
                        "type_filling": mt5.ORDER_FILLING_IOC,
                    }
                    res = self.gateway.order_send(req)
                    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                        actual_fill_price = res.price
                        # Phase 2: Anchor SL + TP (V1 parity: LEG_TP_BY_MAGIC 204 = 2.0R)
                        sl_target = gc_signal["sl"]
                        risk_dist_gc = abs(actual_fill_price - sl_target)
                        tp_target_gc = (
                            actual_fill_price + risk_dist_gc * 2.0
                            if order_type == mt5.ORDER_TYPE_BUY
                            else actual_fill_price - risk_dist_gc * 2.0
                        )
                        mod_req = {
                            "action": mt5.TRADE_ACTION_SLTP,
                            "symbol": self.config.symbol,
                            "position": res.order,
                            "sl": round(sl_target, 3),
                            "tp": round(tp_target_gc, 3),
                        }
                        sym_info = self.gateway.symbol_info(self.config.symbol)
                        retry_buf = sym_info.point * 50 if sym_info else 0.05
                        
                        for _retry in range(3):
                            mod = self.gateway.order_send(mod_req)
                            if mod and mod.retcode == mt5.TRADE_RETCODE_DONE:
                                break
                            if mod and mod.retcode == 10016:
                                time.sleep(0.2)
                                stops_level = sym_info.trade_stops_level * sym_info.point if sym_info else 0.0
                                if order_type == mt5.ORDER_TYPE_BUY:
                                    sl_target = actual_fill_price - stops_level - retry_buf
                                else:
                                    sl_target = actual_fill_price + stops_level + retry_buf
                                mod_req["sl"] = round(sl_target, 3)
                                # Re-derive TP from the widened SL (V1 send_order OOB behavior)
                                risk_dist_gc = abs(actual_fill_price - sl_target)
                                tp_target_gc = (
                                    actual_fill_price + risk_dist_gc * 2.0
                                    if order_type == mt5.ORDER_TYPE_BUY
                                    else actual_fill_price - risk_dist_gc * 2.0
                                )
                                mod_req["tp"] = round(tp_target_gc, 3)
                                retry_buf *= 2
                            else:
                                break
                        
                        logger.info(f"Ghost Executed CACHE (204) | Ticket {res.order}")
                        thesis = TradeThesis(
                            ticket=res.order,
                            symbol=self.config.symbol,
                            direction=1 if order_type == mt5.ORDER_TYPE_BUY else -1,
                            bot_system="GhostSniperV2",
                            setup_type="CACHE",
                            fill_price=actual_fill_price,
                            initial_sl=gc_signal["sl"],
                            initial_tp=round(tp_target_gc, 3),
                            entry_atr=atr,
                            regime_at_entry=bs_regime,
                            entry_conviction=bs_conv,
                            arming_h4_direction=self.arming_h4_direction,
                            arming_m15_regime=self.arming_m15_regime,
                            layer_depth=gc_signal['virtual_layer_depth'],
                            timestamp=time.time(),
                            market_snapshot=snapshot
                        )
                        self.kr.register_trade_thesis(thesis)
                        self.last_fire_time = time.time()
