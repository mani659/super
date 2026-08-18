import os
import re

search_terms = [
    'entry_conviction', 
    '50.0', 
    '50', 
    'arming_h4_direction', 
    'register_trade_thesis', 
    'TradeThesis'
]

search_dirs = ['cab_multi_pair', 'cab_super', 'v2', 'core']

print("=== SEARCHING CAB THESIS REGISTRATION & CONVICTION ===")
for term in ['entry_conviction', 'arming_h4_direction', 'register_trade_thesis', 'TradeThesis']:
    print(f"\n>>> Matches for: '{term}'")
    found = False
    for sdir in search_dirs:
        if not os.path.exists(sdir): continue
        for root, _, files in os.walk(sdir):
            for file in files:
                if not file.endswith('.py'): continue
                fpath = os.path.join(root, file)
                try:
                    with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                        for idx, line in enumerate(f, 1):
                            if term in line:
                                print(f"  {fpath}:{idx} -> {line.strip()}")
                                found = True
                except Exception:
                    pass
    if not found:
        print("  (not found)")

print("\n=== TradeThesis fields in v2/core/data_models.py & core/knowledge_register.py ===")
for target in ['v2/core/data_models.py', 'core/knowledge_register.py']:
    if os.path.exists(target):
        print(f"\n--- {target} ---")
        with open(target, 'r', encoding='utf-8', errors='replace') as f:
            for idx, line in enumerate(f, 1):
                if any(k in line for k in ['TradeThesis', 'entry_conviction', 'arming_h4', 'arming_m15', 'setup_type', 'regime']):
                    print(f"  Line {idx}: {line.strip()}")
