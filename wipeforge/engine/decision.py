from dataclasses import dataclass
from wipeforge.core.models import DeviceInfo

@dataclass
class WipeStrategy:
    method: str
    reason: str
    estimated_time: str
    risk_level: str
    command_preview: str

def decide_strategy(device: DeviceInfo) -> WipeStrategy:
    # 1. NVMe
    if device.transport == 'nvme' or 'nvme' in device.kernel_name:
        return WipeStrategy(
            method="nvme-format",
            reason="Native NVMe protocol format is the safest and fastest way to wipe NVMe drives.",
            estimated_time="< 1 minute",
            risk_level="HIGH",
            command_preview=f"nvme format {device.stable_id} --ses=1"
        )
        
    # 2. USB
    if device.transport == 'usb':
        # Estimate: e.g. ~50 MB/s for general USBs
        hours = max(0.1, device.size_bytes / (50 * 1024 * 1024 * 3600))
        return WipeStrategy(
            method="dd-zero",
            reason="USB transport detected. Fallback to generic bit-by-bit overwrite (zeroing).",
            estimated_time=f"~{hours:.1f} hours",
            risk_level="CRITICAL",
            command_preview=f"dd if=/dev/zero of={device.stable_id} bs=4M conv=fsync status=progress"
        )
        
    # 3. HDD (Rotational)
    if device.rotational:
        # Estimate: e.g. ~150 MB/s for HDDs
        hours = max(0.1, device.size_bytes / (150 * 1024 * 1024 * 3600))
        return WipeStrategy(
            method="dd-zero",
            reason="Rotational magnetic drive detected. Zeroing entire disk space.",
            estimated_time=f"~{hours:.1f} hours",
            risk_level="HIGH",
            command_preview=f"dd if=/dev/zero of={device.stable_id} bs=4M conv=fsync status=progress"
        )
        
    # 4. SATA SSD (Non-rotational, non-nvme, non-usb)
    return WipeStrategy(
        method="hdparm-secure-erase",
        reason="SATA SSD detected. Using ATA Secure Erase to wipe internal cells.",
        estimated_time="2-10 minutes",
        risk_level="HIGH",
        command_preview=f"hdparm --user-master u --security-erase WIPE {device.stable_id}"
    )
