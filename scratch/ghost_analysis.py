import pandas as pd
import datetime

# 1. Analyze 203 in conviction log
print("--- Magic 203 (Conviction Log) ---")
try:
    df = pd.read_csv("sniper_conviction_log.csv", low_memory=False)
    exits = df[df['exit_reason'].notna()].copy()
    exits['timestamp'] = pd.to_datetime(exits['timestamp'])
    print(f"Total 203 Exits: {len(exits)}")
    print(f"First Exit: {exits['timestamp'].min()}")
    print(f"Last Exit: {exits['timestamp'].max()}")
    print(exits['timestamp'].dt.date.value_counts().sort_index())
except Exception as e:
    print("Error reading 203:", e)

# 2. Analyze 201, 202, 204 in v51_live_audit
print("\n--- Magic 201, 202, 204 (v51 Live Audit) ---")
try:
    audit = pd.read_csv("sniper_v51_live_audit.csv", low_memory=False)
    audit['timestamp'] = pd.to_datetime(audit['timestamp'])
    
    # Entries: ORDER_FILL_V51
    entries = audit[audit['event_type'] == 'ORDER_FILL_V51'].copy()
    
    for magic in [201, 202, 204]:
        count = len(entries[entries['magic'] == magic])
        print(f"Magic {magic} Entries: {count}")
    
    # 4. Concurrency of 201 & 202
    # Group by timestamp (to the nearest minute or 5 seconds) to see if they fire together
    entries['time_bucket'] = entries['timestamp'].dt.floor('5S')
    groups = entries.groupby('time_bucket')['magic'].apply(list)
    
    both = 0
    only_202 = 0
    for m_list in groups:
        if 201 in m_list and 202 in m_list:
            both += 1
        elif 202 in m_list and 201 not in m_list:
            only_202 += 1
            
    print(f"\n201 & 202 started together: {both} times")
    print(f"Only 202 started (without 201): {only_202} times")
    print(f"Total 204 activations: {len(entries[entries['magic'] == 204])} times")

except Exception as e:
    print("Error reading audit:", e)
    
print("\n--- Average Winner / Loser ---")
# To get P&L for 201, 202, 204, we have to look into sniper_hunter.log or trade_ledger (which is empty)
# However, Ghost closes them via _close_market and logs them. 
# Did the script parse PnL from hunter log? No, sniper_v51_live_audit.csv doesn't have PnL (it only has fills).
