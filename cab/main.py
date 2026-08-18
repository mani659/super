import MetaTrader5 as mt5
import time
import config
from logger_config import setup_logging, update_heartbeat
from metrics import harvest_closed_trades, track_active_excursions, track_h1_structure
from strat_inversion import execute_inversion_entries, manage_inversion_positions
from strat_continuation import execute_continuation_entries, manage_continuation_positions
from strat_grid import execute_grid_entries, manage_grid_positions

def main():
    logger = setup_logging()
    
    if not mt5.initialize(path=config.TERMINAL_PATH):
        logger.error(f"MT5 Init Failed. Error Code: {mt5.last_error()} | Path: {config.TERMINAL_PATH}")
        return
        
    logger.info("ONLINE | Multi-Regime Architecture Active | Inversion (9995551), Continuation (9995552), Grid (9995553)")
    
    try:
        while True:
            update_heartbeat(logger)
            
            # 1. Inversion Vector (ADX > 60, Parabolic Exhaustion / Mean Reversion)
            execute_inversion_entries()
            manage_inversion_positions()
            
            # 2. Continuation Vector (ADX 30-60, Impulsive Trend Pullback Continuation)
            execute_continuation_entries()
            manage_continuation_positions()
            
            # 3. Range Extraction Grid Vector (ADX < 30, Mean-Reversion Basket)
            execute_grid_entries()
            manage_grid_positions()
            
            # 4. Event-driven background excursion & structural monitors
            track_active_excursions(config.MAGIC_INVERSION)
            track_active_excursions(config.MAGIC_CONTINUATION)
            track_active_excursions(config.MAGIC_GRID)
            
            track_h1_structure(config.MAGIC_INVERSION)
            track_h1_structure(config.MAGIC_CONTINUATION)
            track_h1_structure(config.MAGIC_GRID)
            
            # 5. Post-trade analytics harvest
            harvest_closed_trades(config.MAGIC_INVERSION)
            harvest_closed_trades(config.MAGIC_CONTINUATION)
            harvest_closed_trades(config.MAGIC_GRID)
            
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("CAB REGIME BOT OFFLINE - Shutting down.")
        mt5.shutdown()

if __name__ == "__main__":
    main()