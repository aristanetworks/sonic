
import os

from ..core.utils import inSimulation
from ..libs.wait import waitFor

from ..core.driver.kernel.i2c import I2cKernelDriver

class At24KernelDriver(I2cKernelDriver):
   MODULE = 'at24'
   NAME = '24c02'

   def eepromPath(self):
      return os.path.join(self.getSysfsPath(), 'eeprom')

   def read(self, size=-1):
      with open(self.eepromPath(), 'rb') as f:
         return bytearray(f.read(size))

   def setup(self):
      super(At24KernelDriver, self).setup()
      if not inSimulation():
         waitFor(lambda: os.path.exists(self.eepromPath()),
                 timeout=30, description="eeprom sysfs entry")

class At24C32KernelDriver(At24KernelDriver):
   NAME = '24c32'

class At24C64KernelDriver(At24KernelDriver):
   NAME = '24c64'

class At24C512KernelDriver(At24KernelDriver):
   NAME = '24c512'
