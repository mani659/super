import csv

def parse_mt5_csv(filepath):
    deals = []
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row: continue
            if len(row) < 13: continue
            
            time_str = row[0]
            if len(time_str) >= 19 and time_str[4] == '.' and time_str[7] == '.':
                profit_str = row[-1].replace(' ', '')
                if profit_str == '' and len(row) > 1:
                    profit_str = row[-2].replace(' ', '')
                try:
                    profit = float(profit_str)
                    deals.append(profit)
                except ValueError:
                    continue
    return deals

v2_deals = parse_mt5_csv('v2_parsed_trades.csv')
v2_wins = sum(1 for d in v2_deals if d > 0)
v2_total = len(v2_deals)
v2_pnl = sum(v2_deals)

print(f"V2 Total Trades: {v2_total}")
if v2_total > 0:
    print(f"V2 Win Rate: {v2_wins/v2_total*100:.1f}%")
    print(f"V2 Net PnL: ${v2_pnl:.2f}")

# For V1, the user provided unified_session_log.csv or sniper_v51_live_audit.csv
# But we can also parse ReportHistory-474167713.html directly since we already have a parser.
# Let's write a small parser for the V1 HTML.
from bs4 import BeautifulSoup
import os

if os.path.exists('ReportHistory-474167713.html'):
    v1_deals = []
    with open('ReportHistory-474167713.html', 'r', encoding='utf-16') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
    for tr in soup.find_all('tr'):
        tds = [t.get_text(strip=True) for t in tr.find_all('td')]
        if not tds: continue
        time_str = tds[0]
        if len(time_str) >= 19 and time_str[4] == '.' and time_str[7] == '.':
            if len(tds) > 11:
                # MT5 Deals: usually last column is profit, or -2 if balance
                profit_str = tds[-1].replace(' ', '')
                if not profit_str: profit_str = tds[-2].replace(' ', '')
                try:
                    profit = float(profit_str)
                    # Filter out deposits (huge positive numbers, type might be 'balance')
                    # Let's check deal type in tds
                    deal_type = ""
                    for cell in tds:
                        if cell.lower() in ['buy', 'sell']: deal_type = cell.lower()
                    if deal_type:
                        v1_deals.append(profit)
                except:
                    pass
    
    v1_wins = sum(1 for d in v1_deals if d > 0)
    v1_total = len(v1_deals)
    v1_pnl = sum(v1_deals)
    print(f"\nV1 Total Trades: {v1_total}")
    if v1_total > 0:
        print(f"V1 Win Rate: {v1_wins/v1_total*100:.1f}%")
        print(f"V1 Net PnL: ${v1_pnl:.2f}")
