"""
==================================================================
                  CAB MASTER - CONNECTION ENGINE
==================================================================
Handles MT5 terminal initialization, health checks, and 
the system heartbeat writer for CAB_Global_Sentinel failover.
==================================================================
"""

import MetaTrader5 as mt5
import os
import time
import logging
import config

def initialize_mt5() -> bool:
    """Initializes MetaTrader 5 terminal using configured path."""
    initialized = False
    
    if os.path.exists(config.TERMINAL_PATH):
        if mt5.initialize(path=config.TERMINAL_PATH):
            initialized = True
            

    if not initialized:
        logging.error(f"CRITICAL: Initialization failure. Code: {mt5.last_error()}")
        return False
        
    return True

def is_connected() -> bool:
    """Checks active broker terminal connection state."""
    term_info = mt5.terminal_info()
    return term_info is not None and term_info.connected

def write_heartbeat() -> None:
    """
    Writes current system timestamp to shared heartbeat file.
    Monitored by MQL5 CAB_Global_Sentinel for emergency failover.
    """
    try:
        with open(config.HEARTBEAT_FILE, "wb") as f:
            f.write(str(int(time.time())).encode('ascii'))
    except Exception:
        pass