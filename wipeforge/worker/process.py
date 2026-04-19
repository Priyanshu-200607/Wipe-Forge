import multiprocessing as mp
import traceback
from wipeforge.core.models import DeviceInfo
from wipeforge.engine.decision import WipeStrategy
from wipeforge.engine.wipe import execute_wipe
from wipeforge.engine.verify import verify_wipe
from wipeforge.core.lock import DeviceLock

def wipe_worker(device: DeviceInfo, strategy: WipeStrategy, dry_run: bool, queue: mp.Queue):
    try:
        queue.put({"type": "status", "message": "Locking and re-validating device..."})
        lock = DeviceLock(device)
        lock.verify()
        
        queue.put({"type": "status", "message": "Executing wipe..."})
        
        def progress_cb(pct: float, msg: str):
            queue.put({"type": "progress", "pct": pct, "message": msg})
            
        execute_wipe(strategy.method, device.stable_id, device.size_bytes, progress_cb, dry_run)
        
        queue.put({"type": "status", "message": "Verifying wipe..."})
        verified = verify_wipe(strategy.method, device.stable_id, dry_run)
        
        if not verified:
            raise Exception("Verification failed. Data might not be fully destroyed.")
            
        queue.put({"type": "complete", "message": "Device successfully wiped and verified."})
    except Exception as e:
        queue.put({"type": "error", "message": str(e), "traceback": traceback.format_exc()})
