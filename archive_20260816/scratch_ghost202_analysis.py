import sys
import io

# Set UTF-8 for stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
import re
import os

# ── STEP 1: Parse MT5 history ────────────────────────────────────────
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
                'symbol': texts[2], 'type': texts[3], 'comment': texts[4],
                'volume': float(texts[5]), 'open_price': float(texts[6]),
                'sl': float(texts[7]) if texts[7] else 0.0,
                'close_time': pd.to_datetime(texts[9], format='%Y.%m.%d %H:%M:%S'),
                'close_price': float(texts[10]),
                'profit': float(texts[13].replace('\xa0','').replace(' ','').replace(',','')) if len(texts)>13 else 0.0,
            })
        except: continue

hist = pd.DataFrame(trades)
if not hist.empty and 'comment' in hist.columns:
    hist = hist[hist['comment'] == 'SNIPER_R'].copy()  # Ghost 202 only
    hist['win'] = hist['profit'] > 0
    hist['is_sl_hit'] = hist['close_price'] == hist['sl']
    hist['hold_min'] = (hist['close_time'] - hist['open_time']).dt.total_seconds() / 60
print(f"Ghost 202 history trades: {len(hist)}")

# ── STEP 2: Load audit CSV ───────────────────────────────────────────
audit_path = "logs/sniper_v51_live_audit.csv" if os.path.exists("logs/sniper_v51_live_audit.csv") else "sniper_v51_live_audit.csv"
audit = pd.read_csv(audit_path)
audit['timestamp'] = pd.to_datetime(audit['timestamp'])
audit = audit[audit['event_type'] == 'ORDER_FILL_V51'].copy()
audit['adx'] = audit['adx_at_fill'].astype(float)
audit['conviction'] = audit['conviction_at_fill'].astype(float)
audit['atr'] = audit['atr_at_fill'].astype(float)
audit['price'] = audit['price'].astype(float)
print(f"Audit fills: {len(audit)}")

# ── STEP 3: Join on price (exact match is reliable — price is unique per probe) ──
merged = pd.merge(
    hist,
    audit[['timestamp','price','session','adx','conviction','atr',
           'h4_direction_at_arm','kr_regime_at_arm','sl']],
    left_on='open_price',
    right_on='price',
    how='inner'
)
print(f"Matched trades: {len(merged)} / {len(hist)}")
print()

if len(merged) > 0:
    # ── HYPOTHESIS A: ADX bucket → win rate ──────────────────────────────
    print("=== A: ADX BUCKET vs WIN RATE ===")
    merged['adx_bucket'] = pd.cut(merged['adx'], bins=[0,15,20,25,30,35,40],
                                   labels=['<15','15-20','20-25','25-30','30-35','35-40'])
    adx_stats = merged.groupby('adx_bucket', observed=False).agg(
        n=('win','count'), win_pct=('win','mean'),
        avg_profit=('profit','mean'), net_pnl=('profit','sum')
    ).round(3)
    adx_stats['win_pct'] = (adx_stats['win_pct']*100).round(1)
    print(adx_stats.to_string())
    print()

    # ── HYPOTHESIS B+C: Session + H4 direction → win rate ────────────────
    print("=== B+C: SESSION x H4 DIRECTION -> WIN RATE ===")
    sess_h4 = merged.groupby(['session','h4_direction_at_arm'], observed=False).agg(
        n=('win','count'), win_pct=('win','mean'),
        avg_profit=('profit','mean'), net_pnl=('profit','sum')
    ).round(3)
    sess_h4['win_pct'] = (sess_h4['win_pct']*100).round(1)
    print(sess_h4.to_string())
    print()

    # ── HYPOTHESIS D: Conviction bucket → win rate ────────────────────────
    print("=== D: CONVICTION BUCKET vs WIN RATE ===")
    merged['conv_bucket'] = pd.cut(merged['conviction'], bins=[0,20,30,40,50,60],
                                    labels=['<20','20-30','30-40','40-50','50-60'])
    conv_stats = merged.groupby('conv_bucket', observed=False).agg(
        n=('win','count'), win_pct=('win','mean'), avg_profit=('profit','mean')
    ).round(3)
    conv_stats['win_pct'] = (conv_stats['win_pct']*100).round(1)
    print(conv_stats.to_string())
    print()

    # ── HYPOTHESIS E: ATR at fill → SL hit rate ──────────────────────────
    print("=== E: ATR BUCKET vs SL HIT RATE ===")
    merged['atr_bucket'] = pd.cut(merged['atr'], bins=5)
    atr_stats = merged.groupby('atr_bucket', observed=False).agg(
        n=('is_sl_hit','count'), sl_hit_pct=('is_sl_hit','mean'),
        win_pct=('win','mean'), avg_hold_min=('hold_min','mean')
    ).round(3)
    atr_stats['sl_hit_pct'] = (atr_stats['sl_hit_pct']*100).round(1)
    atr_stats['win_pct'] = (atr_stats['win_pct']*100).round(1)
    print(atr_stats.to_string())
    print()

    # ── HYPOTHESIS F: Best/worst session+H4 combos ───────────────────────
    print("=== F: TOP AND BOTTOM COMBOS (session + H4 direction) ===")
    combo = merged.groupby(['session','h4_direction_at_arm'], observed=False).agg(
        n=('profit','count'), net=('profit','sum'), win_pct=('win','mean')
    )
    combo['win_pct'] = (combo['win_pct']*100).round(1)
    combo['per_trade'] = (combo['net']/combo['n']).round(3)
    print(combo.sort_values('per_trade', ascending=False).to_string())
    print()

    # ── HYPOTHESIS G: SL distance vs survival ────────────────────────────
    print("=== G: SL DISTANCE vs SURVIVAL ===")
    merged['sl_dist_audit'] = abs(merged['open_price'] - merged['sl_y'])  # sl from audit
    merged['sl_dist_bucket'] = pd.cut(merged['sl_dist_audit'], bins=5)
    sl_stats = merged.groupby('sl_dist_bucket', observed=False).agg(
        n=('is_sl_hit','count'), sl_hit_pct=('is_sl_hit','mean'), win_pct=('win','mean')
    ).round(3)
    sl_stats['sl_hit_pct'] = (sl_stats['sl_hit_pct']*100).round(1)
    sl_stats['win_pct'] = (sl_stats['win_pct']*100).round(1)
    print(sl_stats.to_string())
    print()

    # ── SUMMARY: WHICH SINGLE FILTER MOST IMPROVES EXPECTANCY ───────────
    print("=== SUMMARY: BEST SINGLE FILTER CANDIDATES ===")
    for label, subset, remaining in [
        ("ASIAN+NY_OVERLAP only", merged[merged['session'].isin(['ASIAN','NY_OVERLAP'])], merged[~merged['session'].isin(['ASIAN','NY_OVERLAP'])]),
        ("H4_DOWN only", merged[merged['h4_direction_at_arm']=='DOWN'], merged[merged['h4_direction_at_arm']=='UP']),
        ("ADX < 25 only", merged[merged['adx']<25], merged[merged['adx']>=25]),
        ("ADX < 30 only", merged[merged['adx']<30], merged[merged['adx']>=30]),
    ]:
        wr = subset['win'].mean()*100
        trades_kept = len(subset)
        trades_cut = len(remaining)
        pnl_kept = subset['profit'].sum()
        pnl_cut = remaining['profit'].sum()
        print(f"{label}:")
        print(f"  Kept: n={trades_kept}, win={wr:.1f}%, net=${pnl_kept:.2f}")
        print(f"  Cut:  n={trades_cut}, net=${pnl_cut:.2f} (P&L avoided)")
        print()

    # Save merged dataset for further analysis
    merged.to_csv("ghost202_merged_analysis.csv", index=False)
    print("Saved: ghost202_merged_analysis.csv")
