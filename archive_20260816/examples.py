"""
ML-SuperTrend-MT5 Usage Examples (Uncommented & Fixed for Exness)
"""

import MetaTrader5 as mt5
from core.supertrend_bot import SuperTrendBot, Config
from core.performance_monitor import PerformanceMonitor
from core.risk_manager import RiskManager
import logging
import time
import os
import json
from datetime import datetime, timedelta

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CONFIGURATION FOR EXNESS
EXNESS_PATH = r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe"
EXNESS_LOGIN = 260178085
EXNESS_PASS = "Sal_4659$"
EXNESS_SERVER = "Exness-MT5Trial15"
SYMBOL = "EURUSDm"

def example_basic_usage():
    """Example 1: Basic bot setup and run"""
    print("=== Example 1: Basic Usage ===")
    config = Config(symbol=SYMBOL, timeframe=mt5.TIMEFRAME_M30, risk_percent=1.0)
    bot = SuperTrendBot(config)
    
    # Initialize with specific path
    if mt5.initialize(path=EXNESS_PATH):
        if bot.connect(login=EXNESS_LOGIN, password=EXNESS_PASS, server=EXNESS_SERVER):
            for i in range(3): # Run for 3 cycles for testing
                logger.info(f"Running cycle {i+1}/3")
                bot.run_cycle()
                time.sleep(10)
            bot.shutdown()

def example_multi_symbol():
    """Example 2: Trading multiple symbols"""
    print("\n=== Example 2: Multi-Symbol Trading ===")
    symbols = [SYMBOL, "GBPUSDm"] # Ensure symbols exist in Exness
    bots = []
    
    if mt5.initialize(path=EXNESS_PATH):
        for sym in symbols:
            config = Config(symbol=sym, timeframe=mt5.TIMEFRAME_H1, risk_percent=0.5)
            bot = SuperTrendBot(config)
            if bot.connect(login=EXNESS_LOGIN, password=EXNESS_PASS, server=EXNESS_SERVER):
                bots.append(bot)
        
        import threading
        threads = [threading.Thread(target=b.run, args=(30,)) for b in bots]
        for t in threads: t.start()
        # To stop, you would normally need a signal, this will run until closed

def example_conservative_strategy():
    """Example 3: Conservative trading approach"""
    print("\n=== Example 3: Conservative Strategy ===")
    config = Config(
        symbol=SYMBOL, timeframe=mt5.TIMEFRAME_H4, risk_percent=0.5,
        cluster_choice="Worst", sl_multiplier=3.0, tp_multiplier=2.0
    )
    bot = SuperTrendBot(config)
    if mt5.initialize(path=EXNESS_PATH):
        if bot.connect(login=EXNESS_LOGIN, password=EXNESS_PASS, server=EXNESS_SERVER):
            bot.run()

def example_aggressive_strategy():
    """Example 4: Aggressive trading approach"""
    print("\n=== Example 4: Aggressive Strategy ===")
    config = Config(
        symbol=SYMBOL, timeframe=mt5.TIMEFRAME_M15, risk_percent=2.0,
        cluster_choice="Best", sl_multiplier=1.5, tp_multiplier=4.0
    )
    bot = SuperTrendBot(config)
    if mt5.initialize(path=EXNESS_PATH):
        if bot.connect(login=EXNESS_LOGIN, password=EXNESS_PASS, server=EXNESS_SERVER):
            bot.run()

def example_custom_risk_management():
    """Example 5: Custom risk management"""
    print("\n=== Example 5: Custom Risk Management ===")
    risk_manager = RiskManager(max_daily_loss_percent=3.0, max_correlation=0.7)
    account_balance = 10000
    if risk_manager.check_daily_loss_limit(account_balance):
        logger.info("Daily loss limit OK")
    kelly = risk_manager.calculate_kelly_criterion(55, 50, 30)
    logger.info(f"Recommended risk: {kelly*100:.2f}%")

def example_performance_analysis():
    """Example 6: Performance monitoring and analysis"""
    print("\n=== Example 6: Performance Analysis ===")
    sample_trades = [{"symbol": SYMBOL, "profit": 45.50, "volume": 0.1}]
    with open('trades.json', 'w') as f: json.dump(sample_trades, f)
    monitor = PerformanceMonitor('trades.json')
    monitor.generate_report(days=30)

def example_news_filter():
    """Example 7: Trading with news filter"""
    print("\n=== Example 7: News Filter Example ===")
    from core.news_filter import NewsFilter
    news_filter = NewsFilter()
    if news_filter.is_news_time(SYMBOL):
        logger.info(f"High impact news near for {SYMBOL}")
    else:
        logger.info(f"Safe to trade {SYMBOL}")

def example_backtest():
    """Example 8: Running a backtest"""
    print("\n=== Example 8: Backtest Example ===")
    from backtest_engine import BacktestEngine
    start_date = datetime.now() - timedelta(days=365) # 30 day test
    end_date = datetime.now()
    
    config = Config(symbol=SYMBOL, timeframe=mt5.TIMEFRAME_H1)
    bot = SuperTrendBot(config)
    
    if mt5.initialize(path=EXNESS_PATH):
        backtest = BacktestEngine(strategy=bot, initial_balance=10000)
        results = backtest.run_backtest(SYMBOL, start_date, end_date, mt5.TIMEFRAME_H1)
        print(f"\nRESULTS FOR {SYMBOL}:")
        print(results)

def example_optimization():
    """Example 9: Parameter optimization simulation"""
    print("\n=== Example 9: Parameter Optimization ===")
    logger.info("Grid search would run here using the BacktestEngine...")

def monitor_bot_status(bot):
    """Monitor loop for Example 10"""
    while True:
        try:
            stats = bot.calculate_statistics()
            positions = mt5.positions_get(symbol=SYMBOL)
            os.system('cls' if os.name == 'nt' else 'clear')
            print(f"=== ML-SuperTrend Live Dashboard ===")
            print(f"Account: {EXNESS_LOGIN} | Symbol: {SYMBOL}")
            print(f"Win Rate: {stats.get('win_rate', 0):.2f}% | PF: {stats.get('profit_factor', 0):.2f}")
            print(f"Open Positions: {len(positions) if positions else 0}")
            time.sleep(5)
        except KeyboardInterrupt: break

def example_live_monitoring():
    """Example 10: Live monitoring dashboard"""
    print("\n=== Example 10: Live Monitoring ===")
    config = Config(symbol=SYMBOL, timeframe=mt5.TIMEFRAME_M30)
    bot = SuperTrendBot(config)
    if mt5.initialize(path=EXNESS_PATH):
        if bot.connect(login=EXNESS_LOGIN, password=EXNESS_PASS, server=EXNESS_SERVER):
            monitor_bot_status(bot)

if __name__ == "__main__":
    examples = {'1': example_basic_usage, '2': example_multi_symbol, '3': example_conservative_strategy,
                '4': example_aggressive_strategy, '5': example_custom_risk_management, '6': example_performance_analysis,
                '7': example_news_filter, '8': example_backtest, '9': example_optimization, '10': example_live_monitoring}
    
    print("ML-SuperTrend-MT5 Examples (EURUSDm Ready)")
    print("Available: " + ", ".join(examples.keys()))
    choice = input("\nSelect example (1-10): ")
    if choice in examples: examples[choice]()