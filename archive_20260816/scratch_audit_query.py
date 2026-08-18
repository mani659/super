import pandas as pd

df = pd.read_csv("sniper_v51_live_audit.csv")
print("Columns:", df.columns.tolist())
print("Total rows:", len(df))
print("Date range:", df["timestamp"].iloc[0], "to", df["timestamp"].iloc[-1])

# H2: DOWN_PROBE into H4 UP
armed_fire = df[df["event_type"].isin(["ARMED", "ORDER_FILL_V51", "ORDER_ERROR"])]
down = armed_fire[armed_fire["probe_direction"] == "DOWN_PROBE"]
up = armed_fire[armed_fire["probe_direction"] == "UP_PROBE"]
print(f"\nH2 DOWN_PROBE total: {len(down)}")
print(f"  into H4 UP: {len(down[down['h4_direction_at_arm']=='UP'])} ({len(down[down['h4_direction_at_arm']=='UP'])/max(len(down),1)*100:.1f}%)")
print(f"  into H4 DOWN: {len(down[down['h4_direction_at_arm']=='DOWN'])} ({len(down[down['h4_direction_at_arm']=='DOWN'])/max(len(down),1)*100:.1f}%)")
print(f"\nH2 UP_PROBE total: {len(up)}")
print(f"  into H4 UP: {len(up[up['h4_direction_at_arm']=='UP'])} ({len(up[up['h4_direction_at_arm']=='UP'])/max(len(up),1)*100:.1f}%)")
print(f"  into H4 DOWN: {len(up[up['h4_direction_at_arm']=='DOWN'])} ({len(up[up['h4_direction_at_arm']=='DOWN'])/max(len(up),1)*100:.1f}%)")

# H4: RANGING label during H4 directional move
print(f"\nH4 kr_regime_at_arm value counts:")
print(armed_fire["kr_regime_at_arm"].value_counts().to_string())
print(f"\nRANGING label with H4 directional bias:")
rang = armed_fire[armed_fire["kr_regime_at_arm"]=="RANGING"]
print(rang["h4_direction_at_arm"].value_counts().to_string())

# H1: 201 virtual fill ADX/conviction distribution
fills_201 = df[df["magic"]==201]
fills_202 = df[df["magic"]==202]
print(f"\nH1 Magic 201 fills: {len(fills_201)}")
if len(fills_201):
    print(fills_201[["adx_at_fill","conviction_at_fill"]].describe().to_string())
print(f"\nH3 Magic 202 fills: {len(fills_202)}")
if len(fills_202):
    print(fills_202[["adx_at_fill","conviction_at_fill","gate_201","gate_202"]].describe().to_string())
