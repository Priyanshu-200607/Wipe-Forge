import subprocess
import re
import time
from typing import Callable

class WipeError(Exception):
    pass

def execute_dd(target: str, size_bytes: int, progress_cb: Callable[[float, str], None], dry_run: bool = False):
    if dry_run:
        for i in range(1, 11):
            progress_cb(i * 10.0, f"Dry run: simulating dd {i*10}%")
            time.sleep(0.2)
        return

    cmd = ["dd", "if=/dev/zero", f"of={target}", "bs=4M", "conv=fsync", "status=progress"]
    proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True)
    
    try:
        while True:
            line = proc.stderr.readline()
            if not line and proc.poll() is not None:
                break
            
            if "bytes" in line and size_bytes > 0:
                match = re.search(r'^(\d+)\s+bytes', line)
                if match:
                    written = int(match.group(1))
                    pct = (written / size_bytes) * 100
                    progress_cb(min(pct, 100.0), f"Written {written} / {size_bytes} bytes")
    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait()

    if proc.returncode != 0:
        raise WipeError(f"dd failed with code {proc.returncode}")

def execute_nvme(target: str, progress_cb: Callable[[float, str], None], dry_run: bool = False):
    if dry_run:
        progress_cb(0.0, "Dry run: skipping NVMe format...")
        time.sleep(1)
        progress_cb(100.0, "Dry run complete.")
        return
        
    cmd = ["nvme", "format", target, "--ses=1"]
    progress_cb(0.0, "Starting NVMe format (may take a few minutes)...")
    
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise WipeError(f"NVMe format failed: {proc.stderr}")
        
    progress_cb(100.0, "NVMe format complete.")

def execute_hdparm(target: str, progress_cb: Callable[[float, str], None], dry_run: bool = False):
    if dry_run:
        progress_cb(0.0, "Dry run: skipping hdparm secure erase...")
        time.sleep(1)
        progress_cb(100.0, "Dry run complete.")
        return
        
    progress_cb(0.0, "Setting temporary ATA password...")
    pwd_cmd = ["hdparm", "--user-master", "u", "--security-set-pass", "WIPE", target]
    res = subprocess.run(pwd_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise WipeError(f"Failed to set ATA password (drive might be frozen): {res.stderr}")
        
    progress_cb(50.0, "Executing secure erase (this will take time)...")
    erase_cmd = ["hdparm", "--user-master", "u", "--security-erase", "WIPE", target]
    res = subprocess.run(erase_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise WipeError(f"Secure erase failed: {res.stderr}")
        
    progress_cb(100.0, "Secure erase complete.")

def execute_wipe(method: str, target: str, size_bytes: int, progress_cb: Callable[[float, str], None], dry_run: bool = False):
    if method == "dd-zero":
        execute_dd(target, size_bytes, progress_cb, dry_run)
    elif method == "nvme-format":
        execute_nvme(target, progress_cb, dry_run)
    elif method == "hdparm-secure-erase":
        execute_hdparm(target, progress_cb, dry_run)
    else:
        raise WipeError(f"Unknown wipe method: {method}")
