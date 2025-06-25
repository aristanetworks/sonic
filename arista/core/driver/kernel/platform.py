from . import KernelDriver

class PlatformDriver(KernelDriver):
   NAME = None
   SYSFS_PATH = "/sys/devices/platform"
