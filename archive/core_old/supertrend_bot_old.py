import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime
import talib
from sklearn.cluster import KMeans
import logging
import time
from dataclasses import dataclass
from typing import Tuple, Optional
import warnings

warnings.filterwarnings('ignore')

# --- ATTRIBUTE ERROR PATCH ---
# Some MT5 library versions or environments fail to expose these constants.
# We define them here if they are missing to prevent the bot from crashing.
if not hasattr(mt5, 'SYMBOL_FILLING_IOC'):
    mt5.SYMBOL_FILLING_IOC = 2
if not hasattr(mt5, 'SYMBOL_FILLING_FOK'):
    mt5.SYMBOL_FILLING_FOK = 1
if not hasattr(mt5, 'ORDER_FILLING_IOC'):
    mt5.ORDER_FILLING_IOC = 1
if not hasattr(mt5, 'ORDER_FILLING_FOK'):
    mt5.ORDER_FILLING_FOK = 0
# ------------------------------

@dataclass
class Config:
    symbol: str = "EURUSDm"
    timeframe: int = mt5.TIMEFRAME_M30
    atr_period: int = 10
    min_factor: float = 1.0
    max_factor: float = 5.0
    factor_step: float = 0.1
    perf_alpha: float = 10.0
    cluster_choice: str = "Best"
    volume_ma_period: int = 20
    volume_multiplier: float = 1.2
    sl_multiplier: float = 2.0
    tp_multiplier: float = 3.0
    use_trailing: bool = True
    trail_activation: float = 1.5
    risk_percent: float = 1.0
    max_positions: int = 1
    magic_number: int = 123456

class SuperTrendBot:
    def __init__(self, config: Config):
        self.config = config
        self.logger = self._setup_logger()
        self.is_connected = False
        self.last_processed_time = None
        self.login_creds = None 

    def _setup_logger(self):
        logger = logging.getLogger(f'ST_{self.config.symbol}')
        if logger.hasHandlers(): return logger
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        return logger

    def connect(self, login: int, password: str, server: str) -> bool:
        self.login_creds = (login, password, server)
        if not mt5.initialize():
            self.logger.error("MT5 init failed")
            return False
        if not mt5.login(login, password=password, server=server):
            self.logger.error("Login failed")
            return False
        self.is_connected = True
        return True

    def check_connection(self):
        if not mt5.terminal_info() or not mt5.account_info():
            self.logger.warning("Connection lost. Attempting reconnect...")
            if self.login_creds:
                return self.connect(*self.login_creds)
            return False
        return True

    def get_data(self, bars: int = 1000) -> pd.DataFrame:
        rates = mt5.copy_rates_from_pos(self.config.symbol, self.config.timeframe, 1, bars)
        if rates is None: return None
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)
        df['hl2'] = (df['high'] + df['low']) / 2
        df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=self.config.atr_period)
        df['volume_ma'] = df['tick_volume'].rolling(window=self.config.volume_ma_period).mean()
        df['volatility'] = df['close'].rolling(window=self.config.atr_period).std()
        df['norm_volatility'] = df['volatility'] / df['volatility'].rolling(window=50).mean()
        return df.dropna()

    def calculate_supertrends(self, df: pd.DataFrame) -> dict:
        factors = np.arange(self.config.min_factor, self.config.max_factor + self.config.factor_step, self.config.factor_step)
        supertrends = {}
        for factor in factors:
            st = pd.DataFrame(index=df.index)
            st['upper'] = df['hl2'] + (df['atr'] * factor)
            st['lower'] = df['hl2'] - (df['atr'] * factor)
            st['trend'] = 0
            st['output'] = 0.0
            st['perf'] = 0.0
            st['vol_adj_perf'] = 0.0
            
            for i in range(1, len(df)):
                if df['close'].iloc[i] > st['upper'].iloc[i-1]:
                    st.at[st.index[i], 'trend'] = 1
                elif df['close'].iloc[i] < st['lower'].iloc[i-1]:
                    st.at[st.index[i], 'trend'] = 0
                else:
                    st.at[st.index[i], 'trend'] = st['trend'].iloc[i-1]
                
                if st['trend'].iloc[i] == 1:
                    st.at[st.index[i], 'lower'] = max(st['lower'].iloc[i], st['lower'].iloc[i-1]) if st['trend'].iloc[i-1] == 1 else st['lower'].iloc[i]
                    st.at[st.index[i], 'output'] = st['lower'].iloc[i]
                else:
                    st.at[st.index[i], 'upper'] = min(st['upper'].iloc[i], st['upper'].iloc[i-1]) if st['trend'].iloc[i-1] == 0 else st['upper'].iloc[i]
                    st.at[st.index[i], 'output'] = st['upper'].iloc[i]

                alpha = 2 / (self.config.perf_alpha + 1)
                raw_perf = (df['close'].iloc[i] - df['close'].iloc[i-1]) * np.sign(df['close'].iloc[i-1] - st['output'].iloc[i-1])
                st.at[st.index[i], 'vol_adj_perf'] = alpha * (raw_perf / (1 + df['norm_volatility'].iloc[i])) + (1 - alpha) * st['vol_adj_perf'].iloc[i-1]
            supertrends[factor] = st
        return supertrends

    def perform_clustering(self, supertrends: dict) -> float:
        perfs = np.array([st['vol_adj_perf'].iloc[-1] for st in supertrends.values()]).reshape(-1, 1)
        factors = list(supertrends.keys())
        if len(set(perfs.flatten())) < 3: return factors[np.argmax(perfs)]
        
        kmeans = KMeans(n_clusters=3, random_state=42, n_init=10).fit(perfs)
        best_cluster_idx = np.argsort(kmeans.cluster_centers_.flatten())[2 if self.config.cluster_choice == "Best" else 1]
        cluster_factors = [factors[i] for i, label in enumerate(kmeans.labels_) if label == best_cluster_idx]
        return np.mean(cluster_factors)

    def calculate_position_size(self, stop_loss_points: float) -> float:
        acc = mt5.account_info()
        sym = mt5.symbol_info(self.config.symbol)
        if not acc or not sym or stop_loss_points <= 0: return 0.01
        
        risk_val = acc.balance * (self.config.risk_percent / 100)
        point_val = sym.trade_tick_value * (sym.point / sym.trade_tick_size)
        size = risk_val / (stop_loss_points * point_val)
        
        size = max(sym.volume_min, min(size, sym.volume_max))
        return round(size / sym.volume_step) * sym.volume_step

    def get_filling_mode(self):
        """Safely detects filling mode to handle Exness symbol differences."""
        sym = mt5.symbol_info(self.config.symbol)
        if sym is None:
            return mt5.ORDER_FILLING_RETURN

        # Check for IOC (Immediate or Cancel) support
        if sym.filling_mode & mt5.SYMBOL_FILLING_IOC:
            return mt5.ORDER_FILLING_IOC
        # Check for FOK (Fill or Kill) support
        if sym.filling_mode & mt5.SYMBOL_FILLING_FOK:
            return mt5.ORDER_FILLING_FOK
            
        return mt5.ORDER_FILLING_RETURN

    def run_cycle(self):
        if not self.check_connection(): return

        positions = mt5.positions_get(symbol=self.config.symbol)
        if positions:
            rates = mt5.copy_rates_from_pos(self.config.symbol, self.config.timeframe, 0, 1)
            atr = talib.ATR(rates['high'], rates['low'], rates['close'], 10)[-1] if rates is not None else 0
            for p in positions:
                if p.magic == self.config.magic_number:
                    self.update_trailing_stop(p, mt5.symbol_info_tick(self.config.symbol).bid, atr)

        check_rates = mt5.copy_rates_from_pos(self.config.symbol, self.config.timeframe, 0, 2)
        if check_rates is None or len(check_rates) < 2: return
        
        last_closed_time = check_rates[0][0] 
        if self.last_processed_time == last_closed_time:
            return 
        
        df = self.get_data()
        if df is None: return
        
        supertrends = self.calculate_supertrends(df)
        opt_factor = self.perform_clustering(supertrends)
        st = supertrends[min(supertrends.keys(), key=lambda x: abs(x - opt_factor))]
        
        signal = 0
        if st['trend'].iloc[-1] > st['trend'].iloc[-2]: signal = 1
        elif st['trend'].iloc[-1] < st['trend'].iloc[-2]: signal = -1

        if signal != 0 and len([p for p in positions if p.magic == self.config.magic_number]) < self.config.max_positions:
            self.execute_trade(signal, df['close'].iloc[-1], df['atr'].iloc[-1])
            
        self.last_processed_time = last_closed_time

    def execute_trade(self, direction, price, atr):
        sl_dist = atr * self.config.sl_multiplier
        tp_dist = atr * self.config.tp_multiplier
        sl = price - sl_dist if direction == 1 else price + sl_dist
        tp = price + tp_dist if direction == 1 else price - tp_dist
        
        sym = mt5.symbol_info(self.config.symbol)
        vol = self.calculate_position_size(abs(price - sl) / sym.point)
        
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.config.symbol,
            "volume": vol,
            "type": mt5.ORDER_TYPE_BUY if direction == 1 else mt5.ORDER_TYPE_SELL,
            "price": price,
            "sl": sl, "tp": tp,
            "magic": self.config.magic_number,
            "type_filling": self.get_filling_mode(),
        }
        res = mt5.order_send(req)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            self.logger.info(f"Opened {self.config.symbol} | Vol: {vol}")
        else:
            self.logger.error(f"Trade failed: {mt5.last_error()}")

    def update_trailing_stop(self, pos, current_price, atr):
        if not self.config.use_trailing or atr == 0: return
        act_level = atr * self.config.trail_activation
        if pos.type == mt5.ORDER_TYPE_BUY and (current_price - pos.price_open) > act_level:
            new_sl = current_price - (atr * self.config.sl_multiplier)
            if new_sl > pos.sl: self._modify_sl(pos.ticket, new_sl, pos.tp)
        elif pos.type == mt5.ORDER_TYPE_SELL and (pos.price_open - current_price) > act_level:
            new_sl = current_price + (atr * self.config.sl_multiplier)
            if new_sl < pos.sl or pos.sl == 0: self._modify_sl(pos.ticket, new_sl, pos.tp)

    def _modify_sl(self, ticket, sl, tp):
        req = {"action": mt5.TRADE_ACTION_SLTP, "position": ticket, "sl": sl, "tp": tp}
        mt5.order_send(req)

    def run(self, interval_seconds: int = 60):
        self.logger.info(f"Bot started for {self.config.symbol} with interval {interval_seconds}s")
        while True:
            try:
                self.run_cycle()
                time.sleep(interval_seconds)
            except Exception as e:
                self.logger.error(f"Execution Error: {e}")
                time.sleep(10)