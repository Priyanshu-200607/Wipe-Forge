import os
import logging
from datetime import datetime

LOG_DIR = "/var/log/wipeforge"

def setup_logger():
    if not os.path.exists(LOG_DIR):
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
        except PermissionError:
            pass # fallback

    log_file = os.path.join(LOG_DIR, f"wipeforge_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    
    try:
        with open(log_file, 'a'):
            pass
    except PermissionError:
        log_file = f"wipeforge_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

def log_event(event_type: str, details: str):
    logging.info(f"[{event_type}] {details}")

def log_wipe_start(device_id: str, serial: str, method: str):
    log_event("WIPE_START", f"Device: {device_id}, Serial: {serial}, Method: {method}")

def log_wipe_result(device_id: str, success: bool, message: str = ""):
    status = "SUCCESS" if success else "FAILED"
    log_event("WIPE_RESULT", f"Device: {device_id}, Status: {status}, Message: {message}")
