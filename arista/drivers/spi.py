
import os

from ..core.driver.kernel.spi import SpiKernelDriver
from ..core.log import getLogger
from ..core.utils import inSimulation

logging = getLogger(__name__)

class SpidevDriver(SpiKernelDriver):
   MODULE = 'spidev'

   def setup(self):
      super().setup()

      if inSimulation():
         return

      devPath = self.getDevPath()
      if os.path.exists(devPath):
         logging.debug('%s: %s already exists', self, devPath)
      else:
         logging.debug('%s: binding to %s', self, self.MODULE)
         overridePath = os.path.join(self.getSysfsPath(), 'driver_override')
         with open(overridePath, 'w', encoding='utf-8') as f:
            f.write(self.MODULE)
         bindPath = os.path.join(self.getDriverPath(), 'bind')
         with open(bindPath, 'w', encoding='utf-8') as f:
            f.write(str(self.addr))

   def clean(self):
      if inSimulation():
         return

      if not os.path.exists(self.getDevPath()):
         logging.debug('%s: not bound to %s', self, self.MODULE)
         return

      logging.debug('%s: unbinding from %s', self, self.MODULE)
      path = os.path.join(self.getDriverPath(), 'unbind')
      with open(path, 'w', encoding='utf-8') as f:
         f.write(str(self.addr))

      super().clean()

   def getDevPath(self):
      return f'/dev/spidev{self.addr.bus}.{self.addr.cs}'
