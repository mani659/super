import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime
import json

# Initialize MT5
if not mt5.initialize():
    print(f"MT5 init failed: {mt5.last_error()}")
    exit()

# Get account snapshot
acc = mt5.account_info()
print(f"=== ACCOUNT SNAPSHOT ===")
print(f"equity={acc.equity} balance={acc.balance}")
print()

# Get trade history Aug 11-15 (Week 4)
date_from = datetime(2026, 8, 10)
date_to = datetime(2026, 8, 16)
history_deals = mt5.history_deals_get(date_from, date_to)

if history_deals and len(history_deals) > 0:
    df = pd.DataFrame(list(history_deals), columns=history_deals[0]._asdict().keys())
    df['time_dt'] = pd.to_datetime(df['time'], unit='s')
    
    # Filter to actual trades (not balance operations)
    # entry=0 is IN, entry=1 is OUT, entry=2 is IN/OUT
    trades_out = df[df['entry'].isin([1, 2])].copy()  # Closings
    trades_in = df[df['entry'] == 0].copy()  # Openings
    
    print(f"=== WEEK 4 DEAL HISTORY (Aug 10-15) ===")
    print(f"Total deals: {len(df)}")
    print(f"Opening deals: {len(trades_in)}")
    print(f"Closing deals: {len(trades_out)}")
    print()
    
    # PnL by magic number
    print(f"=== PNL BY MAGIC NUMBER ===")
    magic_pnl = trades_out.groupby('magic').agg(
        count=('profit', 'count'),
        total_pnl=('profit', 'sum'),
        avg_pnl=('profit', 'mean'),
        wins=('profit', lambda x: (x > 0).sum()),
        losses=('profit', lambda x: (x < 0).sum()),
        breakeven=('profit', lambda x: (x == 0).sum())
    )
    magic_pnl['win_rate'] = magic_pnl['wins'] / (magic_pnl['wins'] + magic_pnl['losses']) * 100
    print(magic_pnl.to_string())
    print()
    
    # PnL by symbol for each magic
    print(f"=== PNL BY MAGIC x SYMBOL ===")
    sym_magic = trades_out.groupby(['magic', 'symbol']).agg(
        count=('profit', 'count'),
        total_pnl=('profit', 'sum'),
        wins=('profit', lambda x: (x > 0).sum()),
        losses=('profit', lambda x: (x < 0).sum()),
    )
    sym_magic['win_rate'] = sym_magic['wins'] / (sym_magic['wins'] + sym_magic['losses']) * 100
    print(sym_magic.to_string())
    print()
    
    # Identify trade comments for context
    print(f"=== TRADE CLOSE COMMENTS (how trades exited) ===")
    comment_counts = trades_out['comment'].value_counts()
    print(comment_counts.to_string())
    print()
    
    # PnL by session time (approximate)
    trades_out['hour'] = trades_out['time_dt'].dt.hour
    def classify_session(hour):
        if 0 <= hour < 7:
            return "ASIAN"
        elif 7 <= hour < 12:
            return "LONDON"
        elif 12 <= hour < 16:
            return "NY_OVERLAP"
        else:
            return "NY_CLOSE"
    trades_out['session'] = trades_out['hour'].apply(classify_session)
    
    print(f"=== PNL BY SESSION (close time) ===")
    session_pnl = trades_out.groupby('session').agg(
        count=('profit', 'count'),
        total_pnl=('profit', 'sum'),
        wins=('profit', lambda x: (x > 0).sum()),
        losses=('profit', lambda x: (x < 0).sum()),
    )
    session_pnl['win_rate'] = session_pnl['wins'] / (session_pnl['wins'] + session_pnl['losses']) * 100
    print(session_pnl.to_string())
    print()
    
    # Ghost bot specific (magic 201, 202, 204)
    ghost_trades = trades_out[trades_out['magic'].isin([201, 202, 204])]
    print(f"=== GHOST BOT TRADES DETAIL ===")
    print(f"Total ghost closings: {len(ghost_trades)}")
    if len(ghost_trades):
        print(ghost_trades[['time_dt', 'symbol', 'magic', 'type', 'volume', 'price', 'profit', 'commission', 'swap', 'comment']].to_string())
    print()
    
    # CAB bot specific (magic 999555)
    cab_trades = trades_out[trades_out['magic'] == 999555]
    print(f"=== CAB BOT TRADES DETAIL ===")
    print(f"Total CAB closings: {len(cab_trades)}")
    if len(cab_trades):
        cab_by_sym = cab_trades.groupby('symbol').agg(
            count=('profit', 'count'),
            total_pnl=('profit', 'sum'),
            wins=('profit', lambda x: (x > 0).sum()),
            losses=('profit', lambda x: (x < 0).sum()),
        )
        cab_by_sym['win_rate'] = cab_by_sym['wins'] / (cab_by_sym['wins'] + cab_by_sym['losses']) * 100
        print(cab_by_sym.to_string())
        print()
        print("CAB exit reasons:")
        print(cab_trades['comment'].value_counts().to_string())
    print()
    
    # SuperTrend bot
    st_magics = {101234, 201567, 301890, 401213}
    st_trades = trades_out[trades_out['magic'].isin(st_magics)]
    print(f"=== SUPERTREND BOT TRADES ===")
    print(f"Total ST closings: {len(st_trades)}")
    if len(st_trades):
        st_by_sym = st_trades.groupby(['magic', 'symbol']).agg(
            count=('profit', 'count'),
            total_pnl=('profit', 'sum'),
        )
        print(st_by_sym.to_string())
    print()
    
    # Net week P&L
    total_profit = trades_out['profit'].sum()
    total_comm = trades_out['commission'].sum()
    total_swap = trades_out['swap'].sum()
    print(f"=== WEEK 4 NET RESULTS ===")
    print(f"Gross profit (trade P&L): ${total_profit:.2f}")
    print(f"Total commission: ${total_comm:.2f}")
    print(f"Total swap: ${total_swap:.2f}")
    print(f"Net P&L: ${total_profit + total_comm + total_swap:.2f}")
    
    # Open positions
    positions = mt5.positions_get()
    if positions:
        print(f"\n=== CURRENT OPEN POSITIONS ({len(positions)}) ===")
        pos_df = pd.DataFrame(list(positions), columns=positions[0]._asdict().keys())
        pos_df['time_dt'] = pd.to_datetime(pos_df['time'], unit='s')
        print(pos_df[['ticket', 'time_dt', 'symbol', 'type', 'magic', 'volume', 'price_open', 'sl', 'tp', 'price_current', 'profit', 'swap', 'comment']].to_string())
        print(f"\nTotal open P&L: ${pos_df['profit'].sum():.2f}")
        print(f"Total open swap: ${pos_df['swap'].sum():.2f}")
else:
    print("No history deals found")

mt5.shutdown()
