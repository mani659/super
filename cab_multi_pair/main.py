"""
==================================================================
          CAB MASTER ENGINE v18.6 - MODULAR PRODUCTION BUILD           
==================================================================
Entry point orchestrator tying together connection, execution, 
trade management, and performance tracking.
==================================================================
"""

import time
import logging
import MetaTrader5 as mt5

import config
import connection
import execution
from trade_manager import manage_open_trades

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def run_brain():
    """Core runtime engine."""
    if not connection.initialize_mt5():
        return

    logging.info("Baseline market synchronization. Pre-locking active macro bars...")
    for sym in config.SYMBOLS:
        rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H4, 0, 1)
        if rates is not None and len(rates) > 0:
            execution.last_h4_bars[sym] = rates[0]['time']

    print(f"==================================================")
    print(f"CAB MASTER v18.6 ONLINE | MODULAR BUILD")
    print(f"==================================================")
    print(f"Ledger Output Path: {config.LEDGER_FILE}")
    print(f"==================================================")
    
    # Pre-fetch and display currently managed open positions
    active_positions = mt5.positions_get()
    managed_count = 0
    if active_positions:
        for pos in active_positions:
            if pos.magic == config.MAGIC_NUMBER and pos.symbol in config.SYMBOLS:
                logging.info(f"Resuming management of open position: {pos.symbol} (Ticket: {pos.ticket})")
                managed_count += 1
    
    if managed_count == 0:
        logging.info("No active CAB positions to resume. Awaiting new signals...")
        
    while True:
        try:
            if not connection.is_connected():
                time.sleep(5)
                continue
                
            # Keep CAB_Global_Sentinel alive[cite: 2]
            connection.write_heartbeat()

            # Core Trading Cycle
            execution.execute_entries()
            manage_open_trades()
            
        except Exception as e: 
            logging.error(f"Global Loop Error: {e}")
            
        time.sleep(2)

if __name__ == "__main__":
    run_brain()