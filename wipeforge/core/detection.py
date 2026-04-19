import os
import pyudev
import psutil
from typing import List, Tuple, Set
from wipeforge.core.models import DeviceInfo

def resolve_base_device(dev_path: str) -> str:
    """Resolve partition paths (e.g. /dev/sda1) to their base device (/dev/sda)."""
    if not dev_path.startswith('/dev/'):
        return dev_path
    dev_name = os.path.basename(dev_path)
    sys_path = f"/sys/class/block/{dev_name}"
    if os.path.exists(sys_path):
        if os.path.exists(os.path.join(sys_path, "partition")):
            parent = os.path.dirname(os.path.realpath(sys_path))
            return os.path.join("/dev", os.path.basename(parent))
    return dev_path

def get_system_base_disks() -> Set[str]:
    """Identify disks hosting critical system mount points."""
    system_mounts = ['/', '/boot', '/boot/efi']
    sys_disks = set()
    for part in psutil.disk_partitions(all=True):
        if part.mountpoint in system_mounts:
            sys_disks.add(resolve_base_device(part.device))
    return sys_disks

def get_mounted_base_disks() -> Set[str]:
    """Identify all disks that have active mounts."""
    mounted = set()
    for part in psutil.disk_partitions(all=True):
        if part.device.startswith('/dev/'):
            mounted.add(resolve_base_device(part.device))
    return mounted

def scan_devices() -> Tuple[List[DeviceInfo], List[DeviceInfo]]:
    """Scan hardware and return (safe_devices, blocked_devices)."""
    context = pyudev.Context()
    system_disks = get_system_base_disks()
    mounted_disks = get_mounted_base_disks()
    
    safe_devices = []
    blocked_devices = []
    
    for device in context.list_devices(subsystem='block', DEVTYPE='disk'):
        dev_path = device.device_node
        if not dev_path or dev_path.startswith('/dev/loop') or dev_path.startswith('/dev/ram'):
            continue
            
        kernel_name = device.sys_name
        
        stable_id = None
        for symlink in device.device_links:
            if symlink.startswith('/dev/disk/by-id/'):
                if any(x in symlink for x in ['/ata-', '/nvme-', '/usb-']):
                    stable_id = symlink
                    break
        
        if not stable_id:
            for symlink in device.device_links:
                if symlink.startswith('/dev/disk/by-id/'):
                    stable_id = symlink
                    break
                    
        if not stable_id:
            stable_id = dev_path
            
        model = device.get('ID_MODEL', 'Unknown')
        serial = device.get('ID_SERIAL_SHORT', 'Unknown')
        
        try:
            with open(f"/sys/class/block/{kernel_name}/size", 'r') as f:
                size_bytes = int(f.read().strip()) * 512
        except Exception:
            size_bytes = 0
            
        try:
            with open(f"/sys/class/block/{kernel_name}/queue/rotational", 'r') as f:
                rotational = f.read().strip() == '1'
        except Exception:
            rotational = True
            
        transport = device.get('ID_BUS', 'unknown')
        if 'nvme' in kernel_name:
            transport = 'nvme'
            
        is_mounted = dev_path in mounted_disks
        is_system = dev_path in system_disks
        
        dev_info = DeviceInfo(
            stable_id=stable_id,
            kernel_name=kernel_name,
            model=model,
            serial=serial,
            size_bytes=size_bytes,
            rotational=rotational,
            transport=transport,
            mounted=is_mounted,
            is_system_disk=is_system,
            dev_path=dev_path
        )
        
        if dev_info.is_safe_to_wipe:
            safe_devices.append(dev_info)
        else:
            blocked_devices.append(dev_info)
            
    return safe_devices, blocked_devices
