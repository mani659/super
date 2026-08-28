import pandas as pd
import json
import os
from bs4 import BeautifulSoup
from datetime import datetime

def parse_mt5_html(filepath):
    try:
        with open(filepath, 'r', encoding='utf-16') as f:
            soup = BeautifulSoup(f.read(), 'html.parser')
    except UnicodeError:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f.read(), 'html.parser')
        except FileNotFoundError:
            return []

    trs = soup.find_all('tr')
    deals = []
    
    for tr in trs:
        tds = tr.find_all('td')
        if len(tds) < 10:
            continue
            
        row = [td.get_text(strip=True) for td in tds]
        time_str = row[0]
        
        if len(time_str) >= 19 and time_str[4] == '.' and time_str[7] == '.':
            try:
                profit_str = row[-1].replace(' ', '')
                if profit_str == '' and len(row) > 1:
                    profit_str = row[-2].replace(' ', '')
                    
                profit = float(profit_str)
                symbol = row[2]
                deal_type = row[3]
                
                # identify bot by magic/comment if possible, or just aggregate
                comment = ""
                # MT5 HTML usually doesn't show magic numbers cleanly in standard deals unless customized.
                deals.append({'time': time_str, 'symbol': symbol, 'type': deal_type, 'profit': profit, 'raw': row})
            except Exception as e:
                pass

    return deals

def analyze():
    print("--- V1 vs V2 Quant Analysis ---")
    
    # Analyze V2 from v2_trade_ledger.jsonl
    v2_trades = []
    if os.path.exists("v2_trade_ledger.jsonl"):
        with open("v2_trade_ledger.jsonl", "r") as f:
            for line in f:
                if line.strip():
                    try:
                        v2_trades.append(json.loads(line))
                    except:
                        pass
    
    v2_df = pd.DataFrame(v2_trades)
    if not v2_df.empty:
        # Assuming format has 'pnl', 'magic', 'bot_name', etc.
        print("V2 Dataset (v2_trade_ledger.jsonl) columns:", v2_df.columns.tolist())
        if 'pnl' in v2_df.columns:
            v2_pnl = v2_df['pnl'].sum()
            v2_wins = (v2_df['pnl'] > 0).sum()
            v2_total = len(v2_df)
            print(f"V2 Total Trades: {v2_total}")
            print(f"V2 Win Rate: {v2_wins/v2_total*100:.1f}%")
            print(f"V2 Net PnL: ${v2_pnl:.2f}")
            if 'bot_name' in v2_df.columns:
                print(v2_df.groupby('bot_name').agg({'pnl': ['count', 'sum', lambda x: (x>0).mean()]}))
            
    # Analyze V1 from HTML
    v1_deals = parse_mt5_html("ReportHistory-474167713.html")
    if v1_deals:
        v1_df = pd.DataFrame(v1_deals)
        v1_pnl = v1_df['profit'].sum()
        v1_wins = (v1_df['profit'] > 0).sum()
        v1_total = len(v1_df)
        print(f"\nV1 Total Trades (from MT5 export): {v1_total}")
        print(f"V1 Win Rate: {v1_wins/v1_total*100:.1f}%")
        print(f"V1 Net PnL: ${v1_pnl:.2f}")
    
    # Also check v2_parsed_trades.csv
    print("\n--- V2 Parsed Trades CSV manual parse ---")
    v2_csv_deals = parse_mt5_html("v2_parsed_trades.csv")
    if v2_csv_deals:
        v2c_df = pd.DataFrame(v2_csv_deals)
        v2c_pnl = v2c_df['profit'].sum()
        v2c_wins = (v2c_df['profit'] > 0).sum()
        v2c_total = len(v2c_df)
        print(f"V2 (parsed csv) Total Trades: {v2c_total}")
        print(f"V2 (parsed csv) Win Rate: {v2c_wins/v2c_total*100:.1f}%")
        print(f"V2 (parsed csv) Net PnL: ${v2c_pnl:.2f}")

analyze()
