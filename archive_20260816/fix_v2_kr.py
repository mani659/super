import re

with open(r'C:\Users\ABRAR\Desktop\MT5Bot\Super\v2\core\knowledge_register.py', 'r', encoding='utf-8') as f:
    content = f.read()

# I am just going to rewrite v2/core/knowledge_register.py without the is_entry_invalidated since it wasn't there originally.
# Wait, let me just restore it to how it was before I mangled it.

bad_chunk1 = '''    def is_entry_invalidated(self, symbol: str, direction: int) -> Tuple[bool, Optional[str]]:
        \"\"\"
        Layer 4 API Read & HARD BLOCK Check.
        Returns (True, reason) if new entries in this direction are blocked across all bots.
        \"\"\"
        if RAW_LOGGING_MODE:
            return False, None
            
        now = time.time()
        with self._lock:
            snapshot = self._market_states.get((symbol, timeframe))
            if snapshot:
                tf_to_seconds = {
                    "M1": 60, "M5": 300, "M15": 900, "M30": 1800,
                    "H1": 3600, "H4": 14400, "D1": 86400
                }
                max_age = tf_to_seconds.get(timeframe, 3600) + 300  # timeframe duration + 5min grace
                if time.time() - snapshot.timestamp > max_age:
                    logger.warning(f"Stale market data blocked for {symbol}_{timeframe}")
                    return None
            return snapshot
'''

bad_chunk2 = '''    def check_portfolio_entry_allowed(
        self,
        symbol: str,
        direction: int,
        requested_volume: float,
        portfolio_equity: float,
        current_open_positions: tuple
    ) -> Tuple[bool, Optional[str]]:
        \"\"\"
        Layer 3: Portfolio Exposure Ledger API
        \"\"\"
        if RAW_LOGGING_MODE:
            return True, None
            
        with self._lock:
            return list(self._theses.values())'''

content = content.replace(bad_chunk1, '')
content = content.replace(bad_chunk2, '')

with open(r'C:\Users\ABRAR\Desktop\MT5Bot\Super\v2\core\knowledge_register.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Restored v2 KR!")
