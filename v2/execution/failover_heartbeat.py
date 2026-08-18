import time
import logging
import threading
from pathlib import Path

logger = logging.getLogger("FailoverHeartbeat")

class FailoverHeartbeat:
    """
    V2 Failover Heartbeat:
    Writes a Unix timestamp to a file on a set interval.
    The MT5 Terminal (via UnifiedFailover.mq5) reads this file to ensure
    the Python runner is still alive. If it goes stale, MT5 initiates 
    emergency failover protocols.
    
    Uses direct write with 3-attempt retries to avoid WinError 5 locks.
    """
    def __init__(self, filepath: str, interval_seconds: int = 2):
        self.filepath = filepath
        self.interval = interval_seconds
        self.running = False
        self._thread = None
        
        if self.filepath:
            Path(self.filepath).parent.mkdir(parents=True, exist_ok=True)

    def start(self):
        """Starts the heartbeat daemon thread."""
        if not self.filepath:
            logger.warning("No heartbeat path provided. Heartbeat disabled.")
            return
            
        if self.running:
            return
            
        self.running = True
        self._thread = threading.Thread(target=self._pulse_loop, daemon=True, name="HeartbeatDaemon")
        self._thread.start()
        logger.info(f"FailoverHeartbeat started writing to {self.filepath}")

    def stop(self):
        """Stops the heartbeat daemon thread."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            logger.info("FailoverHeartbeat stopped.")

    def _pulse_loop(self):
        while self.running:
            self._write_heartbeat()
            time.sleep(self.interval)

    def _write_heartbeat(self):
        """
        Write Unix timestamp to heartbeat file.
        Uses a short 3-attempt retry loop to bypass transient read-locks from MT5.
        """
        ts = str(int(time.time()))
        for attempt in range(3):
            try:
                with open(self.filepath, 'w', encoding='utf-8') as f:
                    f.write(ts)
                return # Success
            except PermissionError:
                # MT5 is likely reading the file this exact millisecond
                time.sleep(0.05)
            except Exception as e:
                logger.error(f"Failed to write heartbeat: {e}")
                return
        logger.error(f"Failed to write heartbeat after 3 attempts.")
