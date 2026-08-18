import os
import csv
import time
import logging
import MetaTrader5 as mt5
import pandas as pd

logger = logging.getLogger("TradeAnalytics")
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    logger.addHandler(ch)
    logger.setLevel(logging.INFO)

class TradeAnalyticsEngine:
    """
    Centralized engine to calculate MAE, MFE, and Drawdown
    when trades are closed across the ecosystem.
    """
    def __init__(self, logs_dir: str = "logs"):
        self.logs_dir = logs_dir
        if not os.path.exists(self.logs_dir):
            os.makedirs(self.logs_dir)
        self.csv_path = os.path.join(self.logs_dir, "trade_excursions.csv")
        self._init_csv()

    def _init_csv(self):
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Timestamp", "Ticket", "BotSystem", "Symbol", "Type",
                    "Volume", "EntryPrice", "ClosePrice", "Profit",
                    "MAE_Points", "MFE_Points", "MaxDrawdown_Points"
                ])

    def log_trade_excursion(self, pos, bot_name: str):
        """
        Calculates exact MAE/MFE by fetching M1 bars from entry to exit,
        and logs the data to the central CSV.
        """
        try:
            # Safely handle position attributes whether it's a namedtuple or dict-like
            ticket = getattr(pos, 'ticket', None)
            symbol = getattr(pos, 'symbol', None)
            pos_type = getattr(pos, 'type', None) # 0 for BUY, 1 for SELL
            volume = getattr(pos, 'volume', 0.0)
            price_open = getattr(pos, 'price_open', 0.0)
            time_setup = getattr(pos, 'time', None)
            
            # Since the position is closing right now, exit time is now
            exit_time = int(time.time())
            
            # Attempt to fetch close price and profit if available (sometimes pos doesn't have it on closure, MT5 history deals does)
            price_current = getattr(pos, 'price_current', 0.0)
            profit = getattr(pos, 'profit', 0.0)
            
            if not all([ticket, symbol, time_setup, pos_type is not None]):
                logger.error(f"Cannot log excursion: Invalid pos object {pos}")
                return

            sym_info = mt5.symbol_info(symbol)
            if not sym_info:
                return
            point = max(sym_info.point, 1e-6)

            # Add buffer to ensure we capture the full range
            rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, time_setup - 60, exit_time + 60)
            if rates is None or len(rates) == 0:
                logger.warning(f"No M1 rates found for MAE/MFE calculation on {ticket}")
                return
            
            df = pd.DataFrame(rates)
            highest_high = df['high'].max()
            lowest_low = df['low'].min()
            
            if pos_type == mt5.ORDER_TYPE_BUY or pos_type == 0:
                type_str = "BUY"
                mfe = highest_high - price_open
                mae = price_open - lowest_low
                max_dd = mae
            else:
                type_str = "SELL"
                mfe = price_open - lowest_low
                mae = highest_high - price_open
                max_dd = mae

            # Convert to points
            mae_pts = round(mae / point, 2)
            mfe_pts = round(mfe / point, 2)
            max_dd_pts = round(max_dd / point, 2)
            
            with open(self.csv_path, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
                    ticket, bot_name, symbol, type_str,
                    volume, price_open, price_current, profit,
                    mae_pts, mfe_pts, max_dd_pts
                ])
                
            logger.info(f"[{bot_name}] #{ticket} Excursions Logged -> MAE: {mae_pts}pts, MFE: {mfe_pts}pts")

        except Exception as e:
            logger.error(f"Error calculating excursion for #{getattr(pos, 'ticket', 'Unknown')}: {e}", exc_info=True)
