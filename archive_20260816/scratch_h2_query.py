import pandas as pd

df = pd.read_csv("sniper_v51_live_audit.csv")

# Filter to ARMED and FIRE events only
events = df[df["event_type"].isin(["ARMED", "FIRE", "ORDER_FILL_V51"])]

# H2: DOWN_PROBE firing into H4 UP direction
down_probes = events[events["probe_direction"] == "DOWN_PROBE"]
total_down = len(down_probes)
down_into_up = len(down_probes[down_probes["h4_direction_at_arm"] == "UP"])
print(f"H2 CHECK: DOWN_PROBE total={total_down}, firing into H4_UP={down_into_up}, rate={down_into_up/max(total_down,1)*100:.1f}%")

# H4: RANGING label active during H4 directional move
ranging_entries = events[events["kr_regime_at_arm"] == "RANGING"]
ranging_with_direction = ranging_entries[ranging_entries["h4_direction_at_arm"].isin(["UP","DOWN"])]
print(f"H4 CHECK: RANGING label total={len(ranging_entries)}, with H4 directional bias={len(ranging_with_direction)}, rate={len(ranging_with_direction)/max(len(ranging_entries),1)*100:.1f}%")

# Breakdown by magic
for magic in [201, 202]:
    m = events[events["magic"] == magic]
    print(f"\nMagic {magic}: total fills={len(m)}")
    if len(m):
        print(m.groupby(["h4_direction_at_arm","kr_regime_at_arm"]).size().to_string())
