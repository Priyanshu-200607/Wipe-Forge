from dataclasses import dataclass
from typing import Optional

@dataclass
class DeviceInfo:
    stable_id: str
    kernel_name: str
    model: str
    serial: str
    size_bytes: int
    rotational: bool
    transport: str
    mounted: bool
    is_system_disk: bool
    dev_path: str
    
    @property
    def is_safe_to_wipe(self) -> bool:
        return not self.mounted and not self.is_system_disk
