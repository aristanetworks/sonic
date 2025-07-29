import os
import re

from ...log import getLogger

from ...utils import inSimulation

from ....core.driver.user.gpio import GpioFuncImpl
from ....core.utils import FileWaiter, inSimulation


logging = getLogger(__name__)

class GpioController:
   SYSFS_INTERFACE = "/sys/class/gpio"

   def __init__(self, driver):
      self.driver = driver
      self.gpios = []

   def set(self, pin, bit):
      globalOffset = self._getGpioOffset()
      pinPath = f"{self.SYSFS_INTERFACE}/gpio{globalOffset + pin}"
      self._writeSysfs(f"{pinPath}/direction", "out")
      self._writeSysfs(f"{pinPath}/value", bit)

   def get(self, pin):
      globalOffset = self._getGpioOffset()
      pinPath = f"{self.SYSFS_INTERFACE}/gpio{globalOffset + pin}"
      return self._readSysfs(pinPath)

   def addGpio(self, desc):
      self.gpios.append(desc.addr)
      return GpioFuncImpl(
         self,
         self._getHandleGpioFunc(desc.addr),
         desc=desc,
         hwActiveLow=desc.activeLow
      )

   def acquirePin(self, pin):
      globalOffset = self._getGpioOffset()
      if os.path.exists(f"{self.SYSFS_INTERFACE}/gpio{globalOffset + pin}"):
         return
      exportPath = f"{self.SYSFS_INTERFACE}/export"
      self._writeSysfs(exportPath, globalOffset + pin)

   def releasePin(self, pin):
      globalOffset = self._getGpioOffset()
      unexport_path = f"{self.SYSFS_INTERFACE}/unexport"
      self._writeSysfs(unexport_path, globalOffset + pin)

   def acquireAllPins(self):
      for gpio in self.gpios:
         self.acquirePin(gpio)

   def releaseAllPins(self):
      for gpio in self.gpios:
         self.releasePin(gpio)

   def _getHandleGpioFunc(self, pin):
      def handleGpio(bit=None):
         if bit is not None:
            return self.set(pin, bit)
         return self.get(pin)
      return handleGpio

   def _getGpioOffset(self):
      if inSimulation():
         return -1

      path = os.path.join(self.driver.getSysfsPath(), 'gpio')
      if FileWaiter(path, 5).waitFileReady():
         for entry in os.listdir(path):
            match = re.match(r'gpiochip(\d+)', entry)
            if match:
               return int(match.group(1))
         logging.error("Missing %s driver", self.driver.NAME)
      else:
         logging.error("Path %s doesn't exist", path)
      return -1

   def _writeSysfs(self, path, value):
      if inSimulation():
         return
      try:
         with open(path, "w", encoding='utf-8') as f:
            f.write(str(value))
      except (OSError, IOError, PermissionError) as e:
         logging.error("Error writing %s to %s: %s", value, path, e.strerror)

   def _readSysfs(self, path):
      if inSimulation():
         return None
      try:
         with open(path, "r", encoding='utf-8') as f:
            value = f.read().strip()
      except (FileNotFoundError, PermissionError, OSError) as e:
         logging.error("Error reading %s: %s", path, e.strerror)
      return value
