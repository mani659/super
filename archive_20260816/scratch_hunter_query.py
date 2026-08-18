import pandas as pd
import re

# Read hunter log and extract FIRE_201_VIRTUAL events with their context
with open("logs/sniper_hunter.log", "r", errors="replace") as f:
    lines = f.readlines()

# Find FIRE lines (not VIRTUAL_FILL tick logging)
fire_lines = []
for i, l in enumerate(lines):
    if "FIRE UP_PROBE" in l or "FIRE DOWN_PROBE" in l or "FIRE_202" in l or "FIRE_201" in l:
        # Get surrounding context (the adx/conviction from GATES line nearby)
        context = " ".join(lines[max(0,i-3):i+2])
        fire_lines.append({"line": l.strip(), "context": context})

print(f"Total FIRE events in hunter log: {len(fire_lines)}")
for f in fire_lines[:20]:
    print(f["line"][:200])
    print()

# Also extract all GATE lines showing ADX and conviction at fire
gate_lines = [l for l in lines if "GATES |" in l or "adx=" in l.lower() and "conv=" in l.lower()]
print(f"\nGATE decision lines: {len(gate_lines)}")
for g in gate_lines[:10]:
    print(g.strip()[:200])
