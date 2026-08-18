import logging
import time
from datetime import datetime
from typing import Dict
import MetaTrader5 as mt5
import pandas as pd

logger = logging.getLogger("CABLegacy")

PROTECTOR_R = 0.7
HARVESTER_R = 2.0
REAPER_R = 0.25
GROUP_INVALIDATION_R = -1.5
REAPER_ASIAN_SUPPRESS_HOURS = {21, 22, 23, 0, 1}

class CABLegacyManager:
    def __init__(self, gateway, kr, trade_manager):
        self.gateway = gateway
        self.kr = kr
        self.tm = trade_manager
        self.processed_actions = {}
        self._last_macro_bar_time = {}

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

    def _detect_opposite_signal(self, symbol: str, is_buy: bool) -> bool:
        rates = self.gateway.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 0, 3)
        if rates is None or len(rates) < 3:
            return False
        df = pd.DataFrame(rates)
        bar1 = df.iloc[-2]
        bar2 = df.iloc[-3]
        
        bar1_bullish = bar1['close'] > bar1['open']
        bar1_bearish = bar1['close'] < bar1['open']
        bar2_bullish = bar2['close'] > bar2['open']
        bar2_bearish = bar2['close'] < bar2['open']
        
        is_bullish_inversion = bar2_bearish and bar1_bullish
        is_bearish_inversion = bar2_bullish and bar1_bearish
        
        if is_buy and is_bearish_inversion: return True
        if not is_buy and is_bullish_inversion: return True
        return False

    def manage_fluid_logic(self, positions: list):
        if not positions:
            return
            
        symbols_present = sorted({p.symbol for p in positions})
        
        # Grouped Portfolio R-Budgeting
        valid_positions = []
        for sym in symbols_present:
            sym_positions = [p for p in positions if p.symbol == sym]
            sym_rs = []
            for p in sym_positions:
                is_buy = (p.type == 0)
                risk_dist = abs(p.price_open - p.sl)
                if risk_dist == 0: continue
                price_move = (p.price_current - p.price_open) if is_buy else (p.price_open - p.price_current)
                sym_rs.append((p, price_move / risk_dist))
                
            r_total = sum(r for _, r in sym_rs)
            if r_total <= GROUP_INVALIDATION_R:
                logger.warning(f"GROUP INVALIDATION [{sym}] | Total R={r_total:+.2f}")
                sym_rs.sort(key=lambda x: x[1])
                for p, r in sym_rs:
                    if self.tm._close_position(p, f"GROUP_INVALIDATION|R_total={r_total:+.2f}"):
                        if p.ticket not in self.processed_actions:
                            self.processed_actions[p.ticket] = set()
                        self.processed_actions[p.ticket].add("GROUP_INVALIDATION")
                continue
                
            valid_positions.extend(sym_positions)
            
        positions = valid_positions
        if not positions:
            return

        for pos in positions:
            thesis = self.kr.get_entry_snapshot(pos.ticket)
            if not thesis: continue
            
            m15_atr = thesis.entry_atr
            if m15_atr <= 0: m15_atr = 0.001

            if pos.ticket not in self.processed_actions:
                self.processed_actions[pos.ticket] = set()
            done = self.processed_actions[pos.ticket]

            if pos.sl == 0: continue

            is_buy = (pos.type == 0)
            risk_dist = abs(pos.price_open - pos.sl)
            if risk_dist == 0: continue

            price_move = (pos.price_current - pos.price_open) if is_buy else (pos.price_open - pos.price_current)
            current_r = price_move / risk_dist
            
            # Use H4 state from Oracle if available
            state = self.kr.get_market_state(pos.symbol, "H4")
            if state:
                regime = state.regime
                bar_time = state.source_bar_time
            else:
                regime = thesis.regime_at_entry
                bar_time = 0
                
            is_new_h4_bar = (bar_time > self._last_macro_bar_time.get(pos.symbol, 0))

            if is_new_h4_bar:
                # OSI (with profit guard fix)
                if "OSI" not in done:
                    if self._detect_opposite_signal(pos.symbol, is_buy):
                        protector_active = "PROTECTOR" in done or "HARVESTER" in done
                        if protector_active and current_r < 0:
                            logger.info(f"OSI SUPPRESSED #{pos.ticket} - R={current_r:+.2f} | protector_active")
                        else:
                            if self.tm._close_position(pos, f"OSI|H4_INVERSION|R{current_r:+.2f}"):
                                done.add("OSI")
                                continue

                # REAPER
                if regime in ("TRENDING_UP", "TRENDING_DOWN", "TRENDING") and current_r <= -REAPER_R and "REAPER" not in done and "PROTECTOR" not in done:
                    degrad = self.get_micro_degradation(pos.ticket, pos.price_current, m15_atr, thesis)
                    is_degrading = (degrad["decay_factor"] > 0.25)
                    asian_suppressed = (pos.symbol in ("XAUUSDm", "XAUUSD.x") and datetime.utcnow().hour in REAPER_ASIAN_SUPPRESS_HOURS)

                    if is_degrading and not asian_suppressed:
                        if self.tm._close_position(pos, f"REAPER|Macro=TREND_AGAINST|Micro=DEGRADING"):
                            done.add("REAPER")
                            continue

                self._last_macro_bar_time[pos.symbol] = bar_time

            # PROTECTOR
            sym_info = self.gateway.symbol_info(pos.symbol)
            if not sym_info: continue
            
            if current_r >= PROTECTOR_R and "PROTECTOR" not in done:
                buffer = m15_atr * 0.15
                new_sl = (pos.price_open + buffer) if is_buy else (pos.price_open - buffer)
                if self.tm._modify_sl(pos, new_sl, sym_info.digits, "PROTECTOR"):
                    done.add("PROTECTOR")

            # LOCK GATE
            lock_gate_r = PROTECTOR_R + 0.5
            if current_r >= lock_gate_r and "LOCK_GATE" not in done:
                buffer = m15_atr * 0.5
                new_sl = (pos.price_open + buffer) if is_buy else (pos.price_open - buffer)
                if (is_buy and new_sl > pos.sl) or (not is_buy and new_sl < pos.sl):
                    if self.tm._modify_sl(pos, new_sl, sym_info.digits, "LOCK_GATE"):
                        done.add("LOCK_GATE")

            # CONTINUOUS TRAIL
            if current_r >= lock_gate_r:
                trail_sl = (pos.price_current - (1.0 * risk_dist)) if is_buy else (pos.price_current + (1.0 * risk_dist))
                if (is_buy and trail_sl > pos.sl) or (not is_buy and trail_sl < pos.sl):
                    self.tm._modify_sl(pos, trail_sl, sym_info.digits, "CONTINUOUS_TRAIL")

            # HARVESTER
            if current_r >= HARVESTER_R and "HARVESTER" not in done:
                buffer = m15_atr * 1.5
                new_sl = (pos.price_open + buffer) if is_buy else (pos.price_open - buffer)
                if self.tm._modify_sl(pos, new_sl, sym_info.digits, "HARVESTER_SL_LOCK"):
                    half_vol = round(pos.volume / 2.0, 2)
                    if half_vol >= sym_info.volume_min:
                        req = {
                            "action": mt5.TRADE_ACTION_DEAL,
                            "symbol": pos.symbol,
                            "volume": half_vol,
                            "type": mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY,
                            "position": pos.ticket,
                            "price": pos.price_current,
                            "deviation": 20,
                            "magic": pos.magic,
                            "comment": "HARVESTER_CLOSE",
                            "type_time": mt5.ORDER_TIME_GTC,
                            "type_filling": mt5.ORDER_FILLING_IOC,
                        }
                        res = self.gateway.order_send(req)
                        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                            logger.info(f"HARVESTER FIRED #{pos.ticket}")
                    done.add("HARVESTER")
