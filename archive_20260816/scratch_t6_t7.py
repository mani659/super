import pandas as pd

# Task 6
df_ghost = pd.read_csv("sniper_v51_live_audit.csv")
t6 = df_ghost[(df_ghost["magic"] == 201) & (df_ghost["event_type"].isin(["ORDER_FILL_V51", "VIRTUAL_FILL"]))]
print(f"Task 6: Ghost 201 shadow fill count = {len(t6)}")
print("-" * 40)

# Task 7
try:
    df_cab = pd.read_csv("log_extract/cab_summary.csv")
    print("Task 7: CAB summary output")
    print(df_cab.columns.tolist())
    print(df_cab.head(20).to_string())
except Exception as e:
    print(f"Failed to read cab_summary.csv: {e}")
