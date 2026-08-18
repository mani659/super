import logging
import time
from mt5_gateway import MT5Gateway
from v2.core.knowledge_register import KnowledgeRegister
from v2.analytics.market_oracle import MarketOracle
from v2.execution.order_router import OrderRouter
from v2.bots.supertrend import SuperTrendBot

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("V2.Runner")

def main():
    log.info("Starting V2 Modular Runner in Dry-Run Mode...")
    
    # 1. Initialize Gateways and Buses
    gateway = MT5Gateway()
    kr = KnowledgeRegister()
    oracle = MarketOracle(gateway)
    router = OrderRouter(gateway, kr)
    
    # 2. Initialize Bots
    st_bot = SuperTrendBot(kr)
    
    symbol = "EURUSDm"
    
    # 3. Execution Loop
    for _ in range(5): # Run 5 cycles for testing
        log.info(f"--- Cycle Start ---")
        
        # Oracle Phase
        state = oracle.evaluate_symbol(symbol)
        if state:
            kr.publish_market_state(state)
            log.info(f"Oracle: {symbol} is in {state.regime} regime.")
            
        # Bot Phase
        signals = st_bot.run_cycle()
        
        # Execution Phase
        router.execute_signals(signals)
        
        time.sleep(1)

if __name__ == "__main__":
    main()
