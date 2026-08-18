import pandas as pd
import csv
from datetime import datetime

trades = []
with open('v2_parsed_trades.csv', 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    for row in reader:
        if len(row) >= 13:
            try:
                time_in_str = row[0].strip()
                if not time_in_str.startswith('2026'): continue
                
                time_in = datetime.strptime(time_in_str, '%Y.%m.%d %H:%M:%S')
                ticket = row[1].strip()
                symbol = row[2].strip()
                bot_system = row[4].strip()
                
                if row[8] == '':
                    time_out_str = row[9].strip()
                    profit_str = row[-1].replace(' ', '')
                else:
                    time_out_str = row[8].strip()
                    profit_str = row[-1].replace(' ', '')
                
                if time_out_str.startswith('2026'):
                    time_out = datetime.strptime(time_out_str, '%Y.%m.%d %H:%M:%S')
                    profit = float(profit_str)
                    
                    trades.append({
                        'ticket': ticket,
                        'symbol': symbol,
                        'bot': bot_system,
                        'time_in': time_in,
                        'time_out': time_out,
                        'duration_hours': (time_out - time_in).total_seconds() / 3600.0,
                        'hour_of_day': time_in.hour,
                        'day_of_week': time_in.weekday(),
                        'profit': profit,
                        'win': 1 if profit > 0 else 0
                    })
            except Exception as e:
                pass

df = pd.DataFrame(trades)
print(f'Parsed {len(df)} closed trades.')

for bot in df['bot'].unique():
    bot_df = df[df['bot'] == bot].copy()
    print(f'\n=== {bot} ===')
    win_rate = bot_df['win'].mean()
    pnl = bot_df['profit'].sum()
    print(f'Total Trades: {len(bot_df)}, Win Rate: {win_rate:.1%}, PnL: ${pnl:.2f}')
    
    print('\nWin Rate by Hour of Entry:')
    hourly = bot_df.groupby('hour_of_day').agg(
        Count=('win', 'count'),
        Win_Rate=('win', 'mean'),
        PnL=('profit', 'sum')
    )
    print(hourly)
    
    print('\nWin Rate by Trade Duration (Quartiles):')
    bot_df['duration_q'] = pd.qcut(bot_df['duration_hours'], 4, labels=['Q1 (Fastest)', 'Q2', 'Q3', 'Q4 (Longest)'])
    duration = bot_df.groupby('duration_q').agg(
        Count=('win', 'count'),
        Win_Rate=('win', 'mean'),
        PnL=('profit', 'sum'),
        Avg_Duration_Hrs=('duration_hours', 'mean')
    )
    print(duration)
