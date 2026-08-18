with open("logs/cab_watcher.log", "r", errors="replace") as f:
    cab_lines = f.readlines()

osi_lines = [l for l in cab_lines if "OSI" in l]
protector_lines = [l for l in cab_lines if "PROTECTOR" in l]
reaper_lines = [l for l in cab_lines if "REAPER" in l]
close_lines = [l for l in cab_lines if "Closed #" in l]

print(f"OSI fires: {len(osi_lines)}")
print(f"PROTECTOR fires: {len(protector_lines)}")
print(f"REAPER fires: {len(reaper_lines)}")
print(f"Total closes: {len(close_lines)}")

print("\nSample OSI lines:")
for l in osi_lines[:10]:
    print(l.strip()[:200])

print("\nSample close lines (with P&L):")
for l in close_lines[:20]:
    print(l.strip()[:200])
