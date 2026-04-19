import os
import random

def verify_wipe(method: str, target: str, dry_run: bool = False) -> bool:
    if dry_run:
        return True
        
    if method == "dd-zero":
        try:
            with open(target, 'rb') as f:
                # 1. Check first sector
                first = f.read(512)
                if any(b != 0 for b in first):
                    return False
                    
                # 2. Check last sector
                try:
                    f.seek(-512, os.SEEK_END)
                    last = f.read(512)
                    if any(b != 0 for b in last):
                        return False
                except OSError:
                    pass # Some systems don't allow seeking from END on blocks

                # 3. Random samples
                f.seek(0, os.SEEK_END)
                size = f.tell()
                for _ in range(32):
                    offset = random.randint(0, size - 512)
                    f.seek(offset)
                    sample = f.read(512)
                    if any(b != 0 for b in sample):
                        return False

        except OSError:
            return False
            
        return True
    
    elif method in ("nvme-format", "hdparm-secure-erase"):
        # We rely on command success for internal firmware wipes, 
        # but do a quick sanity check of the first sector.
        try:
            with open(target, 'rb') as f:
                first = f.read(512)
                # Not strictly checking for zeros as crypto-erase might leave pseudo-random garbage
                # Just ensuring device is readable post-wipe
        except OSError:
            return False
            
        return True
        
    return False
