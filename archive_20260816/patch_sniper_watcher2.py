import re

file_path = r'C:\Users\ABRAR\Desktop\MT5Bot\Super\ghost_super\sniper_watcher.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

if '_no_sl_warned' not in content:
    content = content.replace(
        '_be_locked_tickets: set = set()',
        '_be_locked_tickets: set = set()\n_no_sl_warned: set = set()'
    )
    
    content = content.replace(
        'if pos.sl == 0:\n        logger.warning(f"LEG_TP: ticket={pos.ticket} has no SL — cannot set TP")\n        return False',
        'if pos.sl == 0:\n        if pos.ticket not in _no_sl_warned:\n            logger.warning(f"LEG_TP: ticket={pos.ticket} has no SL — cannot set TP")\n            _no_sl_warned.add(pos.ticket)\n        return False'
    )
    
    content = content.replace(
        'if sl <= 0.0:\n            logger.warning(f"GRID: ticket={ticket} has no SL - deferring add_leg")\n            return',
        'if sl <= 0.0:\n            if ticket not in _no_sl_warned:\n                logger.warning(f"GRID: ticket={ticket} has no SL - deferring add_leg")\n                _no_sl_warned.add(ticket)\n            return'
    )
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched sniper_watcher.py successfully.")
else:
    print("Already patched.")
