import sys
import io

# Set UTF-8 for stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
import re

# Parse full MT5 history
html_file = "ReportHistory-474167713.html"
with open(html_file, "rb") as f:
    raw = f.read()

try:
    content = raw.decode('utf-16')
except Exception:
    try:
        content = raw.decode('utf-8')
    except Exception:
        content = raw.decode('latin-1')

soup = BeautifulSoup(content, 'html.parser')
rows = soup.find_all('tr')
trades = []
for row in rows:
    cells = row.find_all('td')
    if not cells: continue
    texts = [c.get_text(strip=True) for c in cells]
    if len(texts) >= 13 and re.match(r'\d{4}\.\d{2}\.\d{2}', texts[0]) and re.match(r'\d{4}\.\d{2}\.\d{2}', texts[9] if len(texts)>9 else ''):
        try:
            trades.append({
                'open_time': pd.to_datetime(texts[0], format='%Y.%m.%d %H:%M:%S'),
                'close_time': pd.to_datetime(texts[9], format='%Y.%m.%d %H:%M:%S'),
                'symbol': texts[2], 'type': texts[3].lower(), 'comment': texts[4],
                'open_price': float(texts[6]),
                'profit': float(texts[13].replace('\xa0','').replace(' ','').replace(',','')) if len(texts)>13 else 0.0,
            })
        except: continue

hist = pd.DataFrame(trades)
print(f"Total parsed trades: {len(hist)}")
print("Comments found:", hist['comment'].value_counts().to_dict() if not hist.empty else {})

ghost = hist[hist['comment'] == 'SNIPER_R'].copy()
st = hist[hist['comment'].str.contains('SuperTrend', case=False, na=False)].copy()

# For each Ghost 202 SELL entry, check if a SuperTrend BUY on XAUUSDm
# was open at that moment (ST opened before ghost and closed after)
ghost['win'] = ghost['profit'] > 0
ghost['st_long_xau_open'] = False
ghost['st_position_type'] = 'NONE'

xau_st = st[st['symbol'] == 'XAUUSDm'].copy()
print(f"Ghost 202 trades: {len(ghost)}, XAUUSDm SuperTrend trades: {len(xau_st)}")

for idx, g_row in ghost.iterrows():
    g_time = g_row['open_time']
    # Find any XAUUSDm ST trade open at the time of Ghost 202 fire
    overlap = xau_st[(xau_st['open_time'] <= g_time) & (xau_st['close_time'] >= g_time)]
    if len(overlap) > 0:
        types = overlap['type'].values
        if 'buy' in types:
            ghost.at[idx, 'st_long_xau_open'] = True
            ghost.at[idx, 'st_position_type'] = 'LONG'
        elif 'sell' in types:
            ghost.at[idx, 'st_position_type'] = 'SHORT'

print()
print("=== CROSS-BOT: SuperTrend XAUUSDm direction at Ghost 202 fire time ===")
print()
print("Ghost 202 fires when ST has no position on XAUUSDm:")
no_st = ghost[ghost['st_position_type'] == 'NONE']
if len(no_st) > 0:
    print(f"  n={len(no_st)}, win%={no_st['win'].mean()*100:.1f}%, net=${no_st['profit'].sum():.2f}")
else:
    print("  n=0")

print()
print("Ghost 202 fires when ST is LONG XAUUSDm (opposing: Ghost sells, ST buys):")
st_long = ghost[ghost['st_position_type'] == 'LONG']
if len(st_long) > 0:
    print(f"  n={len(st_long)}, win%={st_long['win'].mean()*100:.1f}%, net=${st_long['profit'].sum():.2f}")
else:
    print("  n=0")

print()
print("Ghost 202 fires when ST is SHORT XAUUSDm (aligned: both sell):")
st_short = ghost[ghost['st_position_type'] == 'SHORT']
if len(st_short) > 0:
    print(f"  n={len(st_short)}, win%={st_short['win'].mean()*100:.1f}%, net=${st_short['profit'].sum():.2f}")
else:
    print("  n=0")

print()
print("Interpretation:")
print("  If ST_LONG win% < no_ST win%: opposing ST direction hurts Ghost 202")
print("  This would support the H6 cross-bot synergy hypothesis")
print("  If no difference: bots are truly independent on this pair")
