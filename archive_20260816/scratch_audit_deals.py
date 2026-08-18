import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime

mt5.initialize()
deals = mt5.history_deals_get(datetime(2026, 8, 10, 0, 0, 0), datetime(2026, 8, 16, 0, 0, 0))
df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
closes = df[df['entry'] == 1].copy()

def get_bot(m):
    if m == 202: return "Ghost_202"
    if m == 999555: return "CAB_999555"
    if m in [101234, 201567, 301890, 401213, 402213, 403213, 404213, 405213, 406213, 407213, 408213]:
        return "SuperTrend"
    return "Other"

closes['bot'] = closes['magic'].apply(get_bot)

print("=== ACCURATE WEEK 4 MT5 CLOSING DEALS SUMMARY ===")
print("Total closing deals:", len(closes))
print(f"Total Net PnL: ${closes['profit'].sum():.2f}")
print()
summary = closes.groupby('bot').agg(
    trades=('profit', 'count'),
    pnl=('profit', 'sum'),
    wins=('profit', lambda x: (x > 0).sum()),
    losses=('profit', lambda x: (x < 0).sum()),
    be=('profit', lambda x: (x == 0).sum())
)
summary['win_rate'] = (summary['wins'] / summary['trades'] * 100).round(1)
print(summary.to_string())
print()

print("=== SUPERTREND BY SYMBOL ===")
st_closes = closes[closes['bot'] == "SuperTrend"]
st_sym = st_closes.groupby('symbol').agg(
    trades=('profit', 'count'),
    pnl=('profit', 'sum'),
    wins=('profit', lambda x: (x > 0).sum()),
    losses=('profit', lambda x: (x < 0).sum())
)
st_sym['win_rate'] = (st_sym['wins'] / st_sym['trades'] * 100).round(1)
print(st_sym.to_string())
print()

print("=== CAB BY SYMBOL ===")
cab_closes = closes[closes['bot'] == "CAB_999555"]
cab_sym = cab_closes.groupby('symbol').agg(
    trades=('profit', 'count'),
    pnl=('profit', 'sum'),
    wins=('profit', lambda x: (x > 0).sum()),
    losses=('profit', lambda x: (x < 0).sum())
)
cab_sym['win_rate'] = (cab_sym['wins'] / cab_sym['trades'] * 100).round(1)
print(cab_sym.to_string())

mt5.shutdown()
