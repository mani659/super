import os
import re
import pandas as pd
import glob
from collections import defaultdict
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

LOG_DIR = r"c:\Users\ABRAR\Desktop\MT5Bot\Super\logs"
DATA_DIR = r"c:\Users\ABRAR\Desktop\MT5Bot\Super"

def parse_logs():
    trades = {}
    
    # Parse SuperTrend logs
    for filepath in glob.glob(os.path.join(LOG_DIR, "supertrend_*.log")):
        symbol = os.path.basename(filepath).replace("supertrend_", "").replace(".log", "")
        if symbol == "runner":
            continue
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                # 2026-07-29 08:53:49,564 [XAUUSDm] [INFO] BUY ENTRY | ticket=2061177062 | ref=4034.73900 | vol=0.06
                if " ENTRY " in line and "ticket=" in line:
                    m = re.search(r"ticket=(\d+)", line)
                    if m:
                        t = int(m.group(1))
                        trades[t] = {"bot": "SuperTrend", "symbol": symbol, "pnl": 0.0, "status": "OPEN"}
                # 2026-07-28 20:10:14,813 [EURUSDm] [INFO] CLOSED #2057198152 | DECAYING_TIMEOUT|SI=0.892|ER=0.304 | P&L: 130.13
                elif "CLOSED #" in line and "P&L:" in line:
                    m = re.search(r"CLOSED #(\d+).*P&L:\s*([-.\d]+)", line)
                    if m:
                        t = int(m.group(1))
                        pnl = float(m.group(2))
                        if t in trades:
                            trades[t]["pnl"] = pnl
                            trades[t]["status"] = "CLOSED"
                        else:
                            trades[t] = {"bot": "SuperTrend", "symbol": symbol, "pnl": pnl, "status": "CLOSED"}

    # Parse CAB watcher log
    cab_log = os.path.join(LOG_DIR, "cab_watcher.log")
    if os.path.exists(cab_log):
        with open(cab_log, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                # 2026-07-30 02:59:56,339 [INFO] ENTRY BUY | BTCUSDm | price=63909.53000 | sl=61664.77000 | lot=0.01 | ticket=2069575461
                if "ENTRY BUY" in line or "ENTRY SELL" in line:
                    m = re.search(r"ENTRY (BUY|SELL) \|\s*(\w+)\s*\|.*ticket=(\d+)", line)
                    if m:
                        sym = m.group(2)
                        t = int(m.group(3))
                        trades[t] = {"bot": "CAB", "symbol": sym, "pnl": 0.0, "status": "OPEN"}
                # 2026-07-29 23:56:22,008 [INFO] CLOSED #2068592789 | DECAYING_TIMEOUT|SI=0.951|ER=0.325 | P&L: 4.88
                # 2026-07-30 03:00:01,059 [INFO]   Closed #2065268297 | OSI|H4_INVERSION_AGAINST_SELL|R+0.33 | P&L: 0.98
                elif "losed #" in line and "P&L:" in line:
                    m = re.search(r"losed #(\d+).*P&L:\s*([-.\d]+)", line)
                    if m:
                        t = int(m.group(1))
                        pnl = float(m.group(2))
                        if t in trades:
                            trades[t]["pnl"] = pnl
                            trades[t]["status"] = "CLOSED"
                        else:
                            trades[t] = {"bot": "CAB", "symbol": "UNKNOWN", "pnl": pnl, "status": "CLOSED"}

    # Parse Ghost Conviction CSV for Ghost trades
    ghost_csv = os.path.join(DATA_DIR, "sniper_conviction_log.csv")
    if os.path.exists(ghost_csv):
        try:
            df_g = pd.read_csv(ghost_csv)
            # Find exits
            exits = df_g[df_g["exit_reason"].notna()]
            for _, row in exits.iterrows():
                t = int(row["ticket"])
                pnl = float(row["profit_usd"])
                magic = int(row["magic"])
                bot_name = f"Ghost (Magic {magic})"
                trades[t] = {"bot": bot_name, "symbol": "XAUUSDm", "pnl": pnl, "status": "CLOSED"}
        except Exception as e:
            print("Ghost CSV Error:", e)

    return trades

def generate_pdf(trades):
    closed_trades = [v for v in trades.values() if v["status"] == "CLOSED"]
    df = pd.DataFrame(closed_trades)
    
    if df.empty:
        print("No closed trades found.")
        return
        
    pdf_path = os.path.join(DATA_DIR, "Weekly_Trade_Analysis.pdf")
    with PdfPages(pdf_path) as pdf:
        # 1. Overall Summary Table
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.axis('tight')
        ax.axis('off')
        
        total_pnl = df["pnl"].sum()
        total_trades = len(df)
        wins = len(df[df["pnl"] > 0])
        losses = len(df[df["pnl"] <= 0])
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        summary_data = [
            ["Metric", "Value"],
            ["Total Closed Trades", str(total_trades)],
            ["Total P&L", f"${total_pnl:.2f}"],
            ["Winning Trades", str(wins)],
            ["Losing Trades", str(losses)],
            ["Win Rate", f"{win_rate:.1f}%"]
        ]
        table = ax.table(cellText=summary_data, loc='center', cellLoc='center', colWidths=[0.4, 0.4])
        table.set_fontsize(14)
        table.scale(1, 2)
        plt.title("Weekly Trade Analysis Summary", fontsize=16)
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()
        
        # 2. Performance by Bot/Magic Number
        bot_stats = df.groupby("bot").agg(
            Trades=('pnl', 'count'),
            Total_PnL=('pnl', 'sum'),
            Wins=('pnl', lambda x: (x > 0).sum()),
            Losses=('pnl', lambda x: (x <= 0).sum())
        ).reset_index()
        bot_stats["Win Rate (%)"] = (bot_stats["Wins"] / bot_stats["Trades"] * 100).round(1)
        
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.axis('tight')
        ax.axis('off')
        table_data = [bot_stats.columns.tolist()] + bot_stats.values.tolist()
        table = ax.table(cellText=table_data, loc='center', cellLoc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1, 1.5)
        plt.title("Performance by Bot / Magic Number", fontsize=14)
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()
        
        # 3. Performance by Symbol
        sym_stats = df.groupby("symbol").agg(
            Trades=('pnl', 'count'),
            Total_PnL=('pnl', 'sum'),
            Wins=('pnl', lambda x: (x > 0).sum()),
            Losses=('pnl', lambda x: (x <= 0).sum())
        ).reset_index()
        sym_stats["Win Rate (%)"] = (sym_stats["Wins"] / sym_stats["Trades"] * 100).round(1)
        sym_stats = sym_stats.sort_values("Total_PnL", ascending=False)
        
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.axis('tight')
        ax.axis('off')
        table_data = [sym_stats.columns.tolist()] + sym_stats.values.tolist()
        table = ax.table(cellText=table_data, loc='center', cellLoc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1, 1.5)
        plt.title("Performance by Pair (Symbol)", fontsize=14)
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()
        
        # 4. Bar Chart for P&L by Pair
        fig, ax = plt.subplots(figsize=(10, 6))
        sym_stats.plot(kind='bar', x='symbol', y='Total_PnL', ax=ax, color=['green' if x > 0 else 'red' for x in sym_stats['Total_PnL']], legend=False)
        plt.title("Total P&L by Symbol")
        plt.ylabel("P&L (USD)")
        plt.xticks(rotation=45)
        plt.tight_layout()
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()

        # 5. Bar Chart for P&L by Bot
        fig, ax = plt.subplots(figsize=(10, 6))
        bot_stats.plot(kind='bar', x='bot', y='Total_PnL', ax=ax, color=['green' if x > 0 else 'red' for x in bot_stats['Total_PnL']], legend=False)
        plt.title("Total P&L by Bot / Magic Number")
        plt.ylabel("P&L (USD)")
        plt.xticks(rotation=45)
        plt.tight_layout()
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()
        
    print(f"Report generated at {pdf_path}")

if __name__ == "__main__":
    trades = parse_logs()
    generate_pdf(trades)
