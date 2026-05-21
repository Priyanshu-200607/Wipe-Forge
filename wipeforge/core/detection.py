import os
import pyudev
import psutil
from typing import List, Tuple, Set
from wipeforge.core.models import DeviceInfo

def resolve_base_device(dev_path: str) -> str:
    """Resolve partition paths (e.g. /dev/sda1) to their base device (/dev/sda)."""
    real_path = os.path.realpath(dev_path)
    if not real_path.startswith('/dev/'):
        return real_path
    dev_name = os.path.basename(real_path)
    sys_path = f"/sys/class/block/{dev_name}"
    if os.path.exists(sys_path):
        if os.path.exists(os.path.join(sys_path, "partition")):
            parent = os.path.dirname(os.path.realpath(sys_path))
            return os.path.join("/dev", os.path.basename(parent))
    return real_path

def resolve_physical_devices(dev_path: str) -> Set[str]:
    """Recursively resolve virtual or partition paths (LVM, LUKS, RAID) to their parent physical disks."""
    real_path = os.path.realpath(dev_path)
    if not real_path.startswith('/dev/'):
        return {real_path}
        
    dev_name = os.path.basename(real_path)
    sys_path = f"/sys/class/block/{dev_name}"
    
    slaves_dir = os.path.join(sys_path, "slaves")
    if os.path.isdir(slaves_dir):
        try:
            slaves = os.listdir(slaves_dir)
            if slaves:
                physical_devices = set()
                for slave in slaves:
                    slave_path = os.path.join("/dev", slave)
                    physical_devices.update(resolve_physical_devices(slave_path))
                return physical_devices
        except Exception:
            pass
            
    return {resolve_base_device(real_path)}

def get_swap_base_disks() -> Set[str]:
    """Identify disks hosting active swap space."""
    swap_disks = set()
    try:
        if os.path.exists("/proc/swaps"):
            with open("/proc/swaps", "r") as f:
                lines = f.readlines()
            for line in lines[1:]:  # skip header
                parts = line.split()
                if parts and parts[0].startswith("/dev/"):
                    swap_disks.update(resolve_physical_devices(parts[0]))
    except Exception:
        pass
    return swap_disks

def get_system_base_disks() -> Set[str]:
    """Identify disks hosting critical system mount points."""
    system_mounts = ['/', '/boot', '/boot/efi']
    sys_disks = set()
    for part in psutil.disk_partitions(all=True):
        if part.mountpoint in system_mounts:
            sys_disks.update(resolve_physical_devices(part.device))
    return sys_disks

def get_mounted_base_disks() -> Set[str]:
    """Identify all disks that have active mounts or swaps."""
    mounted = set()
    for part in psutil.disk_partitions(all=True):
        if part.device.startswith('/dev/'):
            mounted.update(resolve_physical_devices(part.device))
    mounted.update(get_swap_base_disks())
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
            
    if os.environ.get("WIPEFORGE_DEV") == "1":
        mock_safe_usb = DeviceInfo(
            stable_id="/dev/disk/by-id/usb-SanDisk_Ultra_Fit_1234567890-0:0",
            kernel_name="sdb",
            model="SanDisk Ultra Fit USB 3.0",
            serial="1234567890",
            size_bytes=64 * 1024**3,  # 64 GB
            rotational=False,
            transport="usb",
            mounted=False,
            is_system_disk=False,
            dev_path="/dev/sdb"
        )
        mock_safe_hdd = DeviceInfo(
            stable_id="/dev/disk/by-id/ata-WDC_WD10EZEX-00WN4A0_WD-WCC6Y1XS7Z4F",
            kernel_name="sdc",
            model="WDC WD10EZEX-00WN4A0 (Blue HDD)",
            serial="WD-WCC6Y1XS7Z4F",
            size_bytes=1000 * 1024**3,  # 1 TB
            rotational=True,
            transport="ata",
            mounted=False,
            is_system_disk=False,
            dev_path="/dev/sdc"
        )
        # Avoid duplicate mock devices on refresh
        if not any(d.dev_path == "/dev/sdb" for d in safe_devices):
            safe_devices.append(mock_safe_usb)
        if not any(d.dev_path == "/dev/sdc" for d in safe_devices):
            safe_devices.append(mock_safe_hdd)

    return safe_devices, blocked_devices
