import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import talib
from datetime import datetime

class BacktestEngine:
    def __init__(self, strategy, initial_balance=10000):
        self.strategy = strategy
        self.initial_balance = initial_balance
        self.trades = []
        self.open_position = None
        
    def prepare_data(self, df):
        """Adds all technical indicators required by the SuperTrend strategy"""
        df = df.copy()
        df['hl2'] = (df['high'] + df['low']) / 2
        df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=10)
        df['volume_ma'] = df['tick_volume'].rolling(window=20).mean()
        df['volatility'] = df['close'].rolling(window=10).std()
        # Normalized volatility used for performance clustering
        df['norm_volatility'] = df['volatility'] / df['volatility'].rolling(window=50).mean()
        return df.dropna()

    def run_backtest(self, symbol, start_date, end_date, timeframe):
        # 1. Load historical data
        rates = mt5.copy_rates_range(symbol, timeframe, start_date, end_date)
        if rates is None or len(rates) == 0:
            return f"Error: No data found for {symbol}. Check if symbol is visible in Market Watch."
            
        df_raw = pd.DataFrame(rates)
        df_raw['time'] = pd.to_datetime(df_raw['time'], unit='s')
        
        # 2. Pre-process all indicators
        df = self.prepare_data(df_raw)
        
        balance = self.initial_balance
        equity_curve = []
        
        print(f"Starting backtest for {symbol}...")
        print(f"Processing {len(df)} candles...")

        for i in range(200, len(df)):
            current_df = df.iloc[:i+1].copy()
            current_tick = df.iloc[i]
            
            # A. Check for SL/TP on open position
            if self.open_position:
                self.update_positions(current_tick)
                if self.open_position['status'] == 'closed':
                    balance += self.open_position['profit']
                    self.trades.append(self.open_position)
                    self.open_position = None

            # B. Check for new signals if no position is open
            if not self.open_position:
                signal = self.strategy.generate_signal(current_df)
                if signal:
                    self.place_virtual_trade(signal, current_tick)
            
            # C. Track Equity
            unrealized_pnl = 0
            if self.open_position:
                unrealized_pnl = self.calculate_pnl(self.open_position, current_tick)
            equity_curve.append(balance + unrealized_pnl)
            
        return self.generate_backtest_report(equity_curve)

    def place_virtual_trade(self, signal, tick):
        """Simulates entering a trade using the current candle data"""
        direction = "BUY" if signal == 1 else "SELL"
        entry_price = tick['close']
        
        # Use ATR from the current tick for SL/TP calculation
        atr = tick['atr'] if not pd.isna(tick['atr']) else 0.0001
        
        # Multipliers match your config.json
        sl_dist = atr * 2.0
        tp_dist = atr * 3.0

        self.open_position = {
            'type': direction,
            'entry_price': entry_price,
            'sl': entry_price - sl_dist if direction == "BUY" else entry_price + sl_dist,
            'tp': entry_price + tp_dist if direction == "BUY" else entry_price - tp_dist,
            'status': 'open',
            'profit': 0,
            'time': tick['time']
        }
        print(f"  [SIGNAL] {tick['time']} | {direction} @ {entry_price:.5f}")

    def update_positions(self, tick):
        """Checks if price hit SL or TP during the current candle"""
        pos = self.open_position
        # Simulation using 0.10 lot size (10,000 units)
        contract_size = 10000 
        
        if pos['type'] == "BUY":
            if tick['low'] <= pos['sl']:
                pos['status'] = 'closed'
                pos['profit'] = (pos['sl'] - pos['entry_price']) * contract_size
            elif tick['high'] >= pos['tp']:
                pos['status'] = 'closed'
                pos['profit'] = (pos['tp'] - pos['entry_price']) * contract_size
        else:
            if tick['high'] >= pos['sl']:
                pos['status'] = 'closed'
                pos['profit'] = (pos['entry_price'] - pos['sl']) * contract_size
            elif tick['low'] <= pos['tp']:
                pos['status'] = 'closed'
                pos['profit'] = (pos['entry_price'] - pos['tp']) * contract_size

    def calculate_pnl(self, pos, tick):
        contract_size = 10000
        if pos['type'] == "BUY":
            return (tick['close'] - pos['entry_price']) * contract_size
        return (pos['entry_price'] - tick['close']) * contract_size

    def generate_backtest_report(self, equity_curve):
        if not self.trades:
            return "\nResult: No trades were triggered. Try a longer date range or different symbol."
            
        wins = [t for t in self.trades if t['profit'] > 0]
        total_profit = sum(t['profit'] for t in self.trades)
        win_rate = (len(wins) / len(self.trades)) * 100
        
        report = f"""
==================================================
              BACKTEST RESULTS: {datetime.now().strftime('%Y-%m-%d')}
==================================================
Initial Balance:  ${self.initial_balance:,.2f}
Final Balance:    ${self.initial_balance + total_profit:,.2f}
Total Net Profit: ${total_profit:,.2f}

Total Trades:     {len(self.trades)}
Win Rate:         {win_rate:.2f}%
Winning Trades:   {len(wins)}
Losing Trades:    {len(self.trades) - len(wins)}
==================================================
"""
        return report