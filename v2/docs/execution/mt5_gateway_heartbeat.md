# Execution Layer: MT5 Gateway & Heartbeat
**Paths:** 
- 2/execution/mt5_gateway.py
- 2/execution/failover_heartbeat.py

## 1. MT5 Gateway
The MT5 API is notoriously NOT thread-safe. If two Python threads attempt to send an order or request price data at the exact same millisecond, the terminal can crash or drop the request.

To solve this, the V2 architecture forces all bots to route their MT5 queries through a single MT5Gateway instance. 
- The Gateway utilizes a strict, reentrant 	hreading.Lock().
- Only one thread may interact with the terminal at any given microsecond.
- If a bot's logic thread attempts an action while the gateway is locked, it safely blocks until the lock clears.

## 2. Failover Heartbeat
Because we rely on a Unified Failover script (UnifiedFailover.mq5) inside the MT5 terminal to manage our trailing stops if Python crashes, MT5 needs to know if Python is alive.

The FailoverHeartbeat class runs a dedicated background daemon thread.
- Every 2 seconds (by default), it writes a Unix timestamp to a .txt file.
- **Safety Protocol:** It uses a direct write with a 3-attempt retry loop to bypass WinError 5 locking collisions (which happen when MT5 reads the file at the exact millisecond Python attempts to overwrite it).
- If the MT5 Failover script detects this timestamp is older than its configured threshold, it triggers emergency management mode.
