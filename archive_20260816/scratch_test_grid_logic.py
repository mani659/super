import sys
sys.path.insert(0, 'cab')
import strat_grid
from unittest.mock import MagicMock

# Test 1: Add-on lot progression
sym_info_mock = MagicMock()
sym_info_mock.volume_min = 0.01
sym_info_mock.volume_max = 100.0
sym_info_mock.volume_step = 0.01

lot1 = 0.01
lot2 = strat_grid._calculate_grid_addon_lot(sym_info_mock, lot1)
lot3 = strat_grid._calculate_grid_addon_lot(sym_info_mock, lot2)
lot4 = strat_grid._calculate_grid_addon_lot(sym_info_mock, lot3)

print("Addon lot progression:")
print(f"Layer 1: {lot1} -> Layer 2: {lot2} -> Layer 3: {lot3} -> Layer 4: {lot4}")
assert lot2 == 0.02
assert lot3 == 0.03
assert lot4 == 0.04

print("All Grid unit tests passed successfully!")
