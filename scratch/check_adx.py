import MetaTrader5 as mt5
import pandas as pd
import numpy as np

# Need to calculate ADX. We can use the logic from utils/indicators
def calculate_adx(high, low, close, period=14):
    df = pd.DataFrame({'high': high, 'low': low, 'close': close})
    df['tr0'] = abs(df['high'] - df['low'])
    df['tr1'] = abs(df['high'] - df['close'].shift())
    df['tr2'] = abs(df['low'] - df['close'].shift())
    df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)

    df['up'] = df['high'] - df['high'].shift()
    df['down'] = df['low'].shift() - df['low']

    df['+dm'] = np.where((df['up'] > df['down']) & (df['up'] > 0), df['up'], 0.0)
    df['-dm'] = np.where((df['down'] > df['up']) & (df['down'] > 0), df['down'], 0.0)

    # Wilder's Smoothing
    df['tr_smooth'] = df['tr'].ewm(alpha=1/period, adjust=False).mean() * period # Approximation
    # Accurate wilder:
    tr_smooth = np.zeros(len(df))
    pdm_smooth = np.zeros(len(df))
    ndm_smooth = np.zeros(len(df))
    
    tr_smooth[period] = df['tr'][1:period+1].sum()
    pdm_smooth[period] = df['+dm'][1:period+1].sum()
    ndm_smooth[period] = df['-dm'][1:period+1].sum()

    for i in range(period+1, len(df)):
        tr_smooth[i] = tr_smooth[i-1] - (tr_smooth[i-1]/period) + df['tr'].iloc[i]
        pdm_smooth[i] = pdm_smooth[i-1] - (pdm_smooth[i-1]/period) + df['+dm'].iloc[i]
        ndm_smooth[i] = ndm_smooth[i-1] - (ndm_smooth[i-1]/period) + df['-dm'].iloc[i]

    df['+di'] = 100 * (pdm_smooth / tr_smooth)
    df['-di'] = 100 * (ndm_smooth / tr_smooth)
    df['dx'] = 100 * abs(df['+di'] - df['-di']) / (df['+di'] + df['-di'])
    
    adx = np.zeros(len(df))
    dx_sum = df['dx'][period:period*2].sum()
    if not np.isnan(dx_sum):
        adx[period*2 - 1] = dx_sum / period
        for i in range(period*2, len(df)):
            adx[i] = (adx[i-1] * (period - 1) + df['dx'].iloc[i]) / period

    return adx[-1]

TERMINAL_PATH = r"C:\Program Files\MetaTrader 5 EXNESS - Copy\terminal64.exe"

if not mt5.initialize(path=TERMINAL_PATH):
    print("Failed to initialize MT5")
    exit()

positions = mt5.positions_get()
if not positions:
    print("No open positions on cab_multi_pair.")
else:
    for pos in positions:
        rates = mt5.copy_rates_from_pos(pos.symbol, mt5.TIMEFRAME_H4, 0, 100)
        if rates is not None and len(rates) >= 40:
            df = pd.DataFrame(rates)
            adx_val = calculate_adx(df['high'], df['low'], df['close'], 14)
            print(f"[{pos.symbol}] Ticket: {pos.ticket} | Type: {'BUY' if pos.type==0 else 'SELL'} | Profit: {pos.profit} | H4 ADX: {adx_val:.2f}")

mt5.shutdown()
