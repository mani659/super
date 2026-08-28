import csv
from collections import defaultdict

def analyze_v2():
    deals = []
    with open('v2_parsed_trades.csv', 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or len(row) < 13: continue
            time_str = row[0]
            if len(time_str) >= 19 and time_str[4] == '.' and time_str[7] == '.':
                profit_str = row[-1].replace(' ', '')
                if not profit_str and len(row) > 1:
                    profit_str = row[-2].replace(' ', '')
                
                # identify bot from comment or type
                # The comment is usually in row[4] for MT5 deals (Wait: Time,Position,Symbol,Type,Volume,Price,S / L,T / P,Time,Price,Commission,Swap,Profit)
                # Let's check row[4] for bot name
                bot_id = row[4] if len(row) > 4 else "UNKNOWN"
                
                try:
                    profit = float(profit_str)
                    deals.append({'bot': bot_id, 'profit': profit})
                except ValueError:
                    continue

    bot_stats = defaultdict(lambda: {'count': 0, 'wins': 0, 'pnl': 0.0})
    total_pnl = 0
    total_trades = len(deals)
    total_wins = 0
    
    for d in deals:
        bot = d['bot']
        bot_stats[bot]['count'] += 1
        bot_stats[bot]['pnl'] += d['profit']
        if d['profit'] > 0:
            bot_stats[bot]['wins'] += 1
            total_wins += 1
            
        total_pnl += d['profit']
        
    print("--- V2 Performance Breakdown ---")
    print(f"Total Trades: {total_trades}")
    if total_trades > 0:
        print(f"Total Win Rate: {total_wins/total_trades*100:.1f}%")
        print(f"Total Net PnL: ${total_pnl:.2f}\n")
    
    print(f"{'Bot Name':<20} {'Trades':<8} {'Win Rate':<10} {'PnL':<10}")
    print("-" * 50)
    for bot, stats in bot_stats.items():
        wr = stats['wins'] / stats['count'] * 100 if stats['count'] > 0 else 0
        print(f"{bot:<20} {stats['count']:<8} {wr:<9.1f}% ${stats['pnl']:<9.2f}")

analyze_v2()
