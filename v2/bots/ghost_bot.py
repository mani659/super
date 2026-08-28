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

# NOTE: Grid-level TP (+1R combined) and Grid Stop (-3R combined) from
# V1 GridState are NOT yet implemented in V2. Shadow testing against V1
# must not begin until these are ported. See sniper_watcher.py GridState class.

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

    def execute_cycle(self, df: pd.DataFrame, current_dd: float, max_dd: float):
        """
        Main tick cycle.
        df should be M1 timeframe data, at least 20 bars.
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
        # Conviction formula from ghost_sniper.py
        bs_conv = bs_adx * 1.0 + 50.0 * 0.5  # Rough placeholder for conviction

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

            if current_price > recent_high:
                if st_long:
                    logger.info(f"GHOST_ARM_BLOCKED_ST_LONG: {self.config.symbol} - SuperTrend holds long.")
                    return  # Block arming

                h4_snap = self.kr.get_market_state(self.config.symbol, "H4")
                self.arming_h4_direction = "BULLISH" if h4_snap and h4_snap.macd_raw > h4_snap.macd_signal else "BEARISH"
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
                h4_snap = self.kr.get_market_state(self.config.symbol, "H4")
                self.arming_h4_direction = "BULLISH" if h4_snap and h4_snap.macd_raw > h4_snap.macd_signal else "BEARISH"
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
            trigger = False
            
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
                if spread > self.config.spread_max:
                    logger.info(f"Ghost trigger skipped due to spread {spread:.2f} > {self.config.spread_max}")
                    self.armed = None
                    # 204 DECOUPLE: ghost_cache persists
                    self.arming_h4_direction = ""
                    self.arming_m15_regime = ""
                    return

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
                            
                            logger.info(f"[GhostSniper V2] VIRTUAL_FILL magic={sig['magic']} ticket=VIRTUAL price={sig['sl']}")
                            # Synthesize virtual fill using SL or current market price equivalent
                            thesis = TradeThesis(
                                ticket=999999 + sig["magic"],
                                symbol=self.config.symbol,
                                direction=1 if sig["type"] == 0 else -1,
                                bot_system="GhostSniperV2",
                                setup_type=sig["setup"],
                                fill_price=sig["sl"], # Rough virtual approximation for shadow leg
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
        # Unindented to run regardless of the main probe trigger cycle!
        if self.ghost_cache is not None:
            gc_signal = self.ghost_cache.update(current_price, atr)
            if gc_signal is not None:
                # Validate capacity
                existing_legs = [
                    p for p in (self.gateway.positions_get(symbol=self.config.symbol) or [])
                    if p.magic in {201, 202, 204}
                ]
                if len(existing_legs) < GHOST_MAX_LEGS:
                    order_type = mt5.ORDER_TYPE_SELL if gc_signal['order_type'] == 'SELL' else mt5.ORDER_TYPE_BUY
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
                            # Phase 2: Anchor SL
                            sl_target = gc_signal["sl"]
                            mod_req = {
                                "action": mt5.TRADE_ACTION_SLTP,
                                "symbol": self.config.symbol,
                                "position": res.order,
                                "sl": round(sl_target, 3),
                                "tp": 0.0,
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
                                initial_tp=0.0,
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
                else:
                    logger.warning(
                        f"GHOST CACHE BLOCKED — MAX_LEGS cap reached "
                        f"({len(existing_legs)}/{GHOST_MAX_LEGS})"
                    )
