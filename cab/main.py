import faulthandler
import MetaTrader5 as mt5
import time
import traceback
import config
from logger_config import setup_logging, update_heartbeat
from metrics import harvest_closed_trades, track_active_excursions, track_h1_structure
from strat_inversion import execute_inversion_entries, manage_inversion_positions
from strat_continuation import execute_continuation_entries, manage_continuation_positions
from strat_grid import execute_grid_entries, manage_grid_positions
from shared_utils import enforce_loss_caps

# All three vectors are managed as one book for the purposes of the loss cap.
MANAGED_MAGICS = (config.MAGIC_INVERSION, config.MAGIC_CONTINUATION, config.MAGIC_GRID)

# If the MetaTrader5 C-extension hard-terminates the process (terminal loss,
# LiveUpdate restart, duplicate-instance conflict), dump the Python stack to
# stderr (captured in crash.log) so silent exits become diagnosable.
faulthandler.enable()

# The terminal needs time to sync quotes/history after a cold launch. Trading
# during that window caused silent process deaths on Sep 6 (network rescan,
# LiveUpdate restart). Grace before the first trading cycle.
STARTUP_GRACE_SECONDS = 45


def _ensure_connection(logger):
    """Re-establish the MT5 connection if the terminal dropped it. True when usable."""
    try:
        if mt5.terminal_info() is not None and mt5.account_info() is not None:
            return True
    except Exception:
        pass
    logger.warning("MT5 connection lost — shutting down and re-initializing.")
    try:
        mt5.shutdown()
    except Exception:
        pass
    time.sleep(5)
    if not mt5.initialize(path=config.TERMINAL_PATH):
        logger.error(f"MT5 Re-Init Failed. Error Code: {mt5.last_error()} | Path: {config.TERMINAL_PATH}")
        return False
    return True


def main():
    logger = setup_logging()
    
    if not mt5.initialize(path=config.TERMINAL_PATH):
        logger.error(f"MT5 Init Failed. Error Code: {mt5.last_error()} | Path: {config.TERMINAL_PATH}")
        return
        
    logger.info("ONLINE | Multi-Regime Architecture Active | Inversion (9995551), Continuation (9995552), Grid (9995553)")
    if not config.ENABLE_CONTINUATION:
        logger.info("CONTINUATION ENTRIES DISABLED (post-gate plan 13 Sep 2026) | manage_continuation still active")
    
    # Startup grace: let the freshly-launched terminal finish syncing before trading.
    time.sleep(STARTUP_GRACE_SECONDS)
    
    # Report existing managed positions on startup
    positions = mt5.positions_get()
    if positions:
        managed = [p for p in positions if p.magic in (config.MAGIC_INVERSION, config.MAGIC_CONTINUATION, config.MAGIC_GRID)]
        for pos in managed:
            logger.info(f"[STARTUP] Resuming management of open position: {pos.symbol} #{pos.ticket} (Magic: {pos.magic})")
        if not managed:
            logger.info("[STARTUP] No active CAB positions to resume. Awaiting new signals.")
    
    try:
        while True:
            update_heartbeat(logger)
            
            try:
                # 0. Hard loss caps — runs before anything else in the cycle so a
                #    blown basket is flattened before new entries are considered.
                #    fix-loss-cap: previously nothing bounded floating loss; crash.log
                #    records a single USOILm leg at -$5,741. On a trip we skip the entry
                #    vectors for this cycle but still run the monitors/harvest below, and
                #    still fall through to the connection check and sleep (no early
                #    `continue` here — that would bypass time.sleep(60) and spin).
                closed_by_cap = enforce_loss_caps(MANAGED_MAGICS, logger)
                if closed_by_cap:
                    logger.warning(
                        f"[LOSS CAP] cycle flattened {closed_by_cap} position(s) — "
                        f"entry vectors skipped this cycle"
                    )
                else:
                    # 1. Inversion Vector (ADX > 60, Parabolic Exhaustion / Mean Reversion)
                    execute_inversion_entries()
                    manage_inversion_positions()

                    # 2. Continuation Vector (ADX 30-60, Impulsive Trend Pullback Continuation)
                    if config.ENABLE_CONTINUATION:
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
            except Exception:
                logger.error(f"CYCLE ERROR — logging and continuing:\n{traceback.format_exc()}")
            
            # Connection health: if the terminal dropped (update/restart/duplicate
            # instance), reconnect instead of dying silently.
            if not _ensure_connection(logger):
                logger.error("MT5 connection unrecoverable — waiting 60s before retry.")
                time.sleep(60)
                continue
            
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("CAB REGIME BOT OFFLINE - Shutting down.")
        mt5.shutdown()

if __name__ == "__main__":
    main()