# logger_config.py
import logging
from datetime import datetime

def setup_logging():
    log_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Forcefully clear any implicit handlers added by early module imports
    if logger.handlers:
        logger.handlers.clear()
        
    import sys
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    logger.addHandler(console_handler)

    file_handler = logging.FileHandler("cab_watcher_production.log", encoding="utf-8")
    file_handler.setFormatter(log_formatter)
    logger.addHandler(file_handler)
        
    return logger

def update_heartbeat(logger):
    try:
        with open("cab_watcher_heartbeat.txt", "w") as f:
            f.write(f"ONLINE | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | TRI-VECTOR REGIME ENGINE")
    except Exception as e:
        logger.error(f"Heartbeat write error: {e}")