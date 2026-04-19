import os
import sys
import shutil

REQUIRED_BINARIES = ["dd", "nvme", "hdparm"]

def check_root():
    if os.geteuid() != 0:
        print("ERROR: WipeForge is a destructive utility and MUST run as root.")
        sys.exit(1)

def check_binaries():
    missing = [b for b in REQUIRED_BINARIES if shutil.which(b) is None]
    if missing:
        print(f"ERROR: Missing required system tools: {', '.join(missing)}")
        print("Please ensure hdparm and nvme-cli are installed.")
        sys.exit(1)

def entry():
    # Only skip root check in tests or specific dev scenarios if needed.
    # We will enforce root by default for hardening.
    if os.environ.get("WIPEFORGE_DEV") != "1":
        check_root()
        
    check_binaries()

    # DO NOT import heavy modules before safety checks
    from wipeforge.tui.app import WipeForgeApp

    app = WipeForgeApp()
    app.run()

if __name__ == "__main__":
    entry()
