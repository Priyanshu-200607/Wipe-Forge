from wipeforge.core.models import DeviceInfo
from wipeforge.core.detection import scan_devices
from typing import Optional

class DeviceLockException(Exception):
    pass

class DeviceLock:
    def __init__(self, device: DeviceInfo):
        self.stable_id = device.stable_id
        self.serial = device.serial
        self.size_bytes = device.size_bytes
        self.model = device.model
        self.kernel_name = device.kernel_name

    def verify(self) -> bool:
        """
        Re-scans devices and ensures the locked device still exists
        and its critical properties match.
        """
        safe_devices, blocked_devices = scan_devices()
        all_devices = safe_devices + blocked_devices
        
        current_dev: Optional[DeviceInfo] = None
        for dev in all_devices:
            if dev.stable_id == self.stable_id:
                current_dev = dev
                break
                
        if not current_dev:
            raise DeviceLockException(f"Device {self.stable_id} is no longer detected.")
            
        if current_dev.serial != self.serial:
            raise DeviceLockException(f"Serial mismatch for {self.stable_id}: expected {self.serial}, got {current_dev.serial}")
            
        if current_dev.size_bytes != self.size_bytes:
            raise DeviceLockException(f"Size mismatch for {self.stable_id}: expected {self.size_bytes}, got {current_dev.size_bytes}")
            
        if current_dev.model != self.model:
            raise DeviceLockException(f"Model mismatch for {self.stable_id}: expected {self.model}, got {current_dev.model}")

        if not current_dev.is_safe_to_wipe:
            raise DeviceLockException(f"Device {self.stable_id} is no longer safe to wipe (mounted={current_dev.mounted}, system={current_dev.is_system_disk}).")

        return True
