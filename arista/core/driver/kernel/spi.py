
import os

from . import KernelDriver

class SpiKernelDriver(KernelDriver):

   def getDriverPath(self):
      return os.path.join('/sys/bus/spi/drivers', self.MODULE)

   def getSysfsPath(self):
      return self.addr.getSysfsPath()
