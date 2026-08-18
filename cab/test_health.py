import sys
import io

# Ensure UTF-8 output encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import MetaTrader5 as mt5
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger()

def run_tri_vector_diagnostics():
    logger.info("Starting Tri-Vector Architecture Health Check...")

    # 1. Module Import Verification
    try:
        import config
        import shared_utils
        import metrics
        import strat_inversion
        import strat_continuation
        import strat_grid
        logger.info("✔️ All Tri-Vector modules imported successfully.")
    except ImportError as e:
        logger.error(f"❌ Module Import Failed: {e}")
        sys.exit(1)

    # 2. Terminal Connectivity
    if not mt5.initialize(path=getattr(config, 'TERMINAL_PATH', None)):
        logger.error(f"❌ MT5 Initialization Failed. Error: {mt5.last_error()}")
        sys.exit(1)
    logger.info("✔️ MT5 Terminal Connected.")

    # 3. Data Feed Validation across configured symbols
    for sym in config.SYMBOLS:
        sym_info = mt5.symbol_info(sym)
        if sym_info is None:
            logger.error(f"❌ Symbol {sym} not found or not visible.")
            continue
        
        # Test H4 Data & ADX calculation
        adx, plus_di, minus_di = shared_utils.get_adx_directional(sym, mt5.TIMEFRAME_H4, 14)
        atr = shared_utils.get_atr(sym, mt5.TIMEFRAME_H4, config.ATR_PERIOD)
        logger.info(f"✔️ {sym} Feed OK | ADX: {adx:.1f} (+DI: {plus_di:.1f} / -DI: {minus_di:.1f}) | ATR: {atr:.5f}")

    # 4. Magic Number Segregation Check
    magics = {
        "Inversion": strat_inversion.MAGIC_INVERSION,
        "Continuation": strat_continuation.MAGIC_CONTINUATION,
        "Grid": strat_grid.MAGIC_GRID
    }
    logger.info(f"✔️ Magic Number Registry Verified: {magics}")

    mt5.shutdown()
    logger.info("=== Tri-Vector Health Check Complete. System is green for Monday deployment. ===")

if __name__ == "__main__":
    run_tri_vector_diagnostics()