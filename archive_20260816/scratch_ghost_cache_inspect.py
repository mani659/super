import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

with open("ghost_super/ghost_sniper.py", "r", encoding="utf-8", errors="replace") as f:
    lines = f.readlines()

print("All 'ghost_cache = None' or 'ghost_cache=None' lines in ghost_super/ghost_sniper.py:")
for i, line in enumerate(lines, 1):
    if 'ghost_cache' in line and ('= None' in line or '=None' in line):
        print(f"  Line {i}: {line.rstrip()}")
        # Show context: 3 lines before and after
        print("  Context:")
        for j in range(max(0,i-4), min(len(lines),i+3)):
            marker = ">>>" if j == i-1 else "   "
            print(f"    {marker} {j+1}: {lines[j].rstrip()}")
        print()

# Also show where ghost_cache is initialised (set to GhostCache object)
print("\nAll ghost_cache = GhostCache(...) assignments:")
for i, line in enumerate(lines, 1):
    if 'ghost_cache' in line and 'GhostCache(' in line:
        print(f"  Line {i}: {line.rstrip()}")

# Proposed fix description
print()
print("=== PROPOSED 204 FIX ===")
print("Remove ghost_cache = None from inside the 'if trigger:' block")
print("Keep ghost_cache = None ONLY in the block that resets armed = None")
print("This allows 204 to survive a 202 fire and continue tracking deeper extension")
print()
print("Verify: after fix, ghost_cache persists across 202 fire events")
print("Test: in test_ghost_gateway_port.py, add a test where trigger fires")
print("      (202 fires) and ghost_cache is still non-None afterward")
