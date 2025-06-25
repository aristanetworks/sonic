import os

from ...core.driver.kernel.gpio import GpioController
from ...core.driver.kernel.platform import PlatformDriver
from ...core.log import getLogger


logging = getLogger(__name__)

class AmdGpioDriver(PlatformDriver):
   NAME = "AMDI0030:00"

   def __init__(self, **kwargs):
      super().__init__(**kwargs)
      self.controller = GpioController(self)

   def setup(self):
      self.controller.acquireAllPins()

   def clean(self):
      self.controller.releaseAllPins()

   def getSysfsPath(self):
      return os.path.join(PlatformDriver.SYSFS_PATH, self.NAME)

   def getGpio(self, desc, **kwargs):
      return self.controller.addGpio(desc)
