import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta

def main():
    if not mt5.initialize():
        print("initialize() failed")
        mt5.shutdown()
        return

    # Get history for the last 7 days
    date_from = datetime.now() - timedelta(days=7)
    date_to = datetime.now() + timedelta(days=1)
    
    deals = mt5.history_deals_get(date_from, date_to)
    if deals is None:
        print("No deals found or error")
        mt5.shutdown()
        return

    df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
    
    # Filter for Ghost magic numbers
    ghost_magics = [201, 202, 204]
    df_ghost = df[df['magic'].isin(ghost_magics)]
    
    if df_ghost.empty:
        print("No Ghost trades found in MT5 history.")
        mt5.shutdown()
        return
        
    # We only want exits (deal type 0 or 1, but entry=DEAL_ENTRY_OUT)
    # entry: 0=IN, 1=OUT
    df_exits = df_ghost[df_ghost['entry'] == 1].copy()
    
    if df_exits.empty:
        print("No Ghost exits found in MT5 history.")
        mt5.shutdown()
        return
        
    print(f"Total MT5 Exits found for Ghost: {len(df_exits)}")
    
    for magic in ghost_magics:
        df_magic = df_exits[df_exits['magic'] == magic]
        count = len(df_magic)
        total_pnl = df_magic['profit'].sum()
        
        winners = df_magic[df_magic['profit'] > 0]
        losers = df_magic[df_magic['profit'] < 0]
        
        avg_win = winners['profit'].mean() if not winners.empty else 0.0
        avg_loss = losers['profit'].mean() if not losers.empty else 0.0
        
        print(f"\n--- Magic {magic} ---")
        print(f"Total Trades: {count}")
        print(f"Total PnL: ${total_pnl:.2f}")
        print(f"Winners: {len(winners)} (Avg: ${avg_win:.2f})")
        print(f"Losers: {len(losers)} (Avg: ${avg_loss:.2f})")

    mt5.shutdown()

if __name__ == "__main__":
    main()
