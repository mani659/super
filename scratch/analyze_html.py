import pandas as pd
import re

# Load deals from previously parsed CSV
df = pd.read_csv("c:/Users/ABRAR/Desktop/MT5Bot/Super/scratch/deals_extracted.csv")
df.columns = ["Time", "Deal", "Symbol", "Type", "Direction", "Volume", "Price", "Order", "Cost", "Commission", "Fee", "Swap", "Profit", "Balance", "Comment"]

# Convert profit strings to float (they have spaces for thousands, e.g. "1 000.00")
def parse_money(val):
    if pd.isna(val) or val == "":
        return 0.0
    val = str(val).replace(" ", "").replace(",", "")
    try:
        return float(val)
    except:
        return 0.0

df['Profit'] = df['Profit'].apply(parse_money)
df['Commission'] = df['Commission'].apply(parse_money)
df['Swap'] = df['Swap'].apply(parse_money)

# We only want trades that closed out (Direction = "out")
# Or if MT5 report translates differently, "in" is entry, "out" is exit.
out_deals = df[df['Direction'].astype(str).str.lower() == 'out'].copy()

# Try to identify Bot from Comment
def identify_bot(row):
    c = str(row['Comment']).lower()
    if 'stv2' in c or 'supertrend' in c:
        return 'SuperTrend'
    if 'cab' in c or 'osi|' in c:
        return 'CAB'
    if 'brain_' in c:
        return 'Ghost'
    
    # If hit SL/TP, the comment might just be "[sl ...]" or "[tp ...]"
    # Let's infer based on symbol (Ghost is only XAUUSDm)
    # But ST and CAB also trade XAUUSDm. 
    # Maybe we just group as "Unidentified" and then infer based on volume?
    return 'Unknown / SL / TP'

out_deals['Bot'] = out_deals.apply(identify_bot, axis=1)
out_deals['Net_Profit'] = out_deals['Profit'] + out_deals['Commission'] + out_deals['Swap']

print(f"Total Out Deals: {len(out_deals)}")

# Group by Bot
summary = out_deals.groupby('Bot').agg(
    Trades=('Deal', 'count'),
    Gross_Profit=('Profit', 'sum'),
    Net_Profit=('Net_Profit', 'sum'),
    Winners=('Net_Profit', lambda x: (x > 0).sum()),
    Losers=('Net_Profit', lambda x: (x <= 0).sum())
).reset_index()

summary['Win_Rate'] = (summary['Winners'] / summary['Trades'] * 100).round(2)
summary['Avg_Winner'] = out_deals[out_deals['Net_Profit'] > 0].groupby('Bot')['Net_Profit'].mean().reindex(summary['Bot']).fillna(0).round(2).values
summary['Avg_Loser'] = out_deals[out_deals['Net_Profit'] <= 0].groupby('Bot')['Net_Profit'].mean().reindex(summary['Bot']).fillna(0).round(2).values

print("\n--- Bot Summary ---")
print(summary.to_string(index=False))

# Group by Symbol
sym_summary = out_deals.groupby('Symbol').agg(
    Trades=('Deal', 'count'),
    Gross_Profit=('Profit', 'sum'),
    Net_Profit=('Net_Profit', 'sum'),
    Winners=('Net_Profit', lambda x: (x > 0).sum()),
    Losers=('Net_Profit', lambda x: (x <= 0).sum())
).reset_index()
sym_summary['Win_Rate'] = (sym_summary['Winners'] / sym_summary['Trades'] * 100).round(2)
sym_summary = sym_summary.sort_values('Net_Profit', ascending=False)
print("\n--- Symbol Summary ---")
print(sym_summary.to_string(index=False))

# Unidentified analysis
unid = out_deals[out_deals['Bot'] == 'Unknown / SL / TP']
print("\n--- Unidentified (SL/TP Hits) Breakdown by Symbol ---")
if not unid.empty:
    print(unid.groupby('Symbol').agg(Trades=('Deal', 'count'), Net_Profit=('Net_Profit', 'sum')).to_string())

