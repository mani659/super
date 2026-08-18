import pandas as pd

audit = pd.read_csv("sniper_v51_live_audit.csv")
fills = audit[audit["event_type"] == "ORDER_FILL_V51"].copy()
fills["session"] = fills["session"]
fills["h4_dir"] = fills["h4_direction_at_arm"]
fills["adx"] = fills["adx_at_fill"].astype(float)
fills["conviction"] = fills["conviction_at_fill"].astype(float)

print("Fills by session x H4 direction:")
print(fills.groupby(["session","h4_dir"]).size().unstack(fill_value=0).to_string())

print("\nADX at fill by session:")
print(fills.groupby("session")["adx"].describe().to_string())

print("\nConviction at fill by session:")
print(fills.groupby("session")["conviction"].describe().to_string())
