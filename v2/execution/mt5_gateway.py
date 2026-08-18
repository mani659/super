"""
MT5Gateway — Thread-Safe MetaTrader 5 Interface
================================================
Task: pu-gw (Session 1 — CRITICAL)

Single point of entry for all MT5 API calls across the unified runner.
A single threading.Lock ensures only one thread touches MT5 at a time —
required because MetaTrader5 Python API is NOT thread-safe.

Wraps every call used across SuperTrend, CAB Watcher, Ghost Hunter,
and Ghost Watcher:
    positions_get       — read open positions
    order_send          — place or close orders
    copy_rates_from_pos — fetch OHLCV bars
    symbol_info         — instrument metadata
    symbol_info_tick    — live bid/ask
    account_info        — equity/balance
    terminal_info       — connection health check
    initialize          — connect to MT5 terminal
    login               — authenticate
    shutdown            — clean disconnect

Design notes:
  - Lock is reentrant-safe (each call acquires and releases independently).
  - Failures return None (same contract as raw MT5 API) — callers must
    guard accordingly (they already do in the existing code).
  - All calls are logged at DEBUG level; errors at WARNING/ERROR.
  - last_error() is proxied without the lock (read-only, always safe).
  - _connected flag is set by initialize()/login() so callers can check
    gateway.connected before entering their main loops.

Usage:
    from mt5_gateway import MT5Gateway
    gateway = MT5Gateway()
    gateway.initialize(path=MT5_PATH)
    gateway.login(login=LOGIN, password=PASSWORD, server=SERVER)

    positions = gateway.positions_get(symbol="XAUUSDm")
    tick      = gateway.symbol_info_tick("XAUUSDm")
    result    = gateway.order_send(request_dict)
"""

import threading
import logging
import MetaTrader5 as mt5

logger = logging.getLogger("MT5Gateway")


class MT5Gateway:
    """
    Thread-safe wrapper around the MetaTrader5 Python API.
    Instantiate once; pass to all bot instances as a shared dependency.
    """

    def __init__(self):
        self._lock            = threading.Lock()
        self._connected       = False
        self._ipc_fail_count  = 0          # consecutive IPC failures
        self._ipc_fail_limit  = 5          # trigger reconnect after N failures
        self._last_reconnect  = 0.0        # timestamp of last reconnect attempt
        logger.info("MT5Gateway created — lock initialised")

    @property
    def is_healthy(self) -> bool:
        """False when consecutive IPC failures exceed threshold."""
        return self._ipc_fail_count < self._ipc_fail_limit

    # ── Connection ──────────────────────────────────────────────────────────

    def initialize(self, path: str = None, timeout: int = 180_000) -> bool:
        """Connect to the MT5 terminal. Returns True on success."""
        with self._lock:
            kwargs = {"timeout": timeout}
            if path:
                kwargs["path"] = path
            ok = mt5.initialize(**kwargs)
            if ok:
                logger.info(f"MT5Gateway.initialize() OK | path={path or 'auto'}")
            else:
                logger.error(f"MT5Gateway.initialize() FAILED | {mt5.last_error()}")
            return ok

    def login(self, login: int, password: str, server: str) -> bool:
        """Authenticate against the broker. Returns True on success."""
        with self._lock:
            ok = mt5.login(login, password=password, server=server)
            if ok:
                self._connected = True
                logger.info(f"MT5Gateway.login() OK | account={login} server={server}")
            else:
                logger.error(f"MT5Gateway.login() FAILED | {mt5.last_error()}")
            return ok

    def shutdown(self):
        """Disconnect from MT5 terminal."""
        with self._lock:
            mt5.shutdown()
            self._connected = False
            logger.info("MT5Gateway.shutdown() — connection closed")

    @property
    def connected(self) -> bool:
        return self._connected

    # ── Read — market data ──────────────────────────────────────────────────

    def copy_rates_from_pos(self, symbol: str, timeframe: int,
                             start_pos: int, count: int):
        """
        Fetch OHLCV bars. Returns numpy structured array or None.
        Identical contract to mt5.copy_rates_from_pos().
        """
        with self._lock:
            result = mt5.copy_rates_from_pos(symbol, timeframe, start_pos, count)
        if result is None:
            logger.debug(
                f"copy_rates_from_pos({symbol}, tf={timeframe}, "
                f"pos={start_pos}, n={count}) → None | {mt5.last_error()}"
            )
        else:
            self._ipc_fail_count = 0
        return result

    def symbol_info(self, symbol: str):
        """Returns SymbolInfo object or None."""
        with self._lock:
            result = mt5.symbol_info(symbol)
        if result is None:
            logger.warning(f"symbol_info({symbol}) → None | {mt5.last_error()}")
        return result

    def symbol_info_tick(self, symbol: str):
        """Returns Tick object (bid, ask, last, volume, time) or None."""
        with self._lock:
            result = mt5.symbol_info_tick(symbol)
        if result is None:
            err = mt5.last_error()
            self._ipc_fail_count += 1
            if self._ipc_fail_count == 1 or self._ipc_fail_count % 10 == 0:
                # Log first failure and every 10th — not every single one
                logger.warning(
                    f"symbol_info_tick({symbol}) → None | {err} "
                    f"(consecutive failures: {self._ipc_fail_count})"
                )
        else:
            self._ipc_fail_count = 0   # reset on success
        return result

    def account_info(self):
        """Returns AccountInfo object or None."""
        with self._lock:
            result = mt5.account_info()
        if result is None:
            logger.warning(f"account_info() → None | {mt5.last_error()}")
        return result

    def terminal_info(self):
        """Returns TerminalInfo object or None. Use to check connection health."""
        with self._lock:
            result = mt5.terminal_info()
        return result

    # ── Read — positions ────────────────────────────────────────────────────

    def positions_get(self, symbol: str = None, magic: int = None,
                      group: str = None):
        """
        Fetch open positions. Accepts optional filters:
            symbol — filter by instrument
            magic  — filter by magic number (post-process, not MT5 native)
            group  — filter by symbol group pattern

        Returns tuple of TradePosition or empty tuple, never None.
        """
        with self._lock:
            kwargs = {}
            if symbol is not None:
                kwargs["symbol"] = symbol
            if group is not None:
                kwargs["group"] = group
            result = mt5.positions_get(**kwargs)

        if result is None:
            return ()

        # Optional magic filter (MT5 API doesn't support native magic filter)
        if magic is not None:
            result = tuple(p for p in result if p.magic == magic)

        return result

    def positions_total(self) -> int:
        """Returns total number of open positions."""
        with self._lock:
            return mt5.positions_total() or 0

    # ── Write — orders ──────────────────────────────────────────────────────

    def order_send(self, request: dict):
        """
        Send a trade request. Returns OrderSendResult or None.
        The request dict is unchanged — same structure as raw mt5.order_send().

        Logs the retcode on every call so all order events appear in the
        gateway log regardless of which bot placed them.
        """
        with self._lock:
            result = mt5.order_send(request)

        if result is None:
            logger.error(
                f"order_send() → None | magic={request.get('magic')} "
                f"symbol={request.get('symbol')} | {mt5.last_error()}"
            )
        elif result.retcode != mt5.TRADE_RETCODE_DONE:
            if result.retcode == 10036:
                logger.debug(
                    f"order_send() retcode=10036 (Invalid Ticket) | "
                    f"Position likely closed concurrently | "
                    f"magic={request.get('magic')} symbol={request.get('symbol')}"
                )
            else:
                logger.warning(
                    f"order_send() retcode={result.retcode} | "
                    f"comment='{result.comment}' | "
                    f"magic={request.get('magic')} symbol={request.get('symbol')}"
                )
        else:
            logger.debug(
                f"order_send() OK | retcode={result.retcode} | "
                f"order={result.order} | magic={request.get('magic')}"
            )
        return result

    # ── Utilities ───────────────────────────────────────────────────────────

    def last_error(self):
        """Proxy to mt5.last_error() — no lock needed (read-only)."""
        return mt5.last_error()

    def reconnect_if_needed(self, path: str = None, login: int = None,
                             password: str = None, server: str = None) -> bool:
        """
        Check terminal health and attempt re-init if connection dropped.
        Call from main thread health monitor loop.
        Returns True if connected (or reconnected), False if still down.
        """
        info = self.terminal_info()
        if info is not None:
            return True  # still up

        logger.warning("MT5Gateway: terminal dropped — attempting re-init")
        ok = self.initialize(path=path)
        if ok and login and password and server:
            ok = self.login(login, password, server)
        if ok:
            logger.info("MT5Gateway: reconnect successful")
        else:
            logger.error("MT5Gateway: reconnect FAILED")
        return ok

    # ── Context manager support ─────────────────────────────────────────────

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.shutdown()

    def __repr__(self):
        return (
            f"MT5Gateway(connected={self._connected}, "
            f"lock_locked={self._lock.locked()})"
        )