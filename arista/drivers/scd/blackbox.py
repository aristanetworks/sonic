import os
import subprocess

from ...core.config import Config
from ...core.log import getLogger
from ...inventory.blackbox import BlackBoxImpl
from ...drivers.spi import SpidevDriver

logging = getLogger(__name__)

class ScdBlackBoxImpl(BlackBoxImpl):
   def __init__(self, component):
      self.component = component

   def __str__(self):
      return self.__class__.__name__

   def getComponent(self):
      return self.component

   @property
   def regs(self):
      return self.component.regs()

   def version(self):
      return self.component.version()

   def enabled(self):
      return self.component.enabled()

   def setEnabled(self, enabled):
      return self.component.setEnabled(enabled)

   def dump(self, outputPath):
      return self.component.driver.dump(outputPath)

class ScdBlackBoxDriver(SpidevDriver):
   def getBlackBox(self, component):
      return ScdBlackBoxImpl(component)

   def dump(self, outputPath):
      return self._runFlashromCmd(op='-r', outputPath=outputPath)

   def _runFlashromCmd(self, op, outputPath=None):
      devPath = self.getDevPath()
      if not os.path.exists(devPath):
         logging.error('%s: spidev not found: %s', self, devPath)
         return False

      flashromPath = Config().blackbox_flashrom_path
      if not os.path.exists(flashromPath):
         logging.error('%s: flashrom-arista not found at %s', self, flashromPath)
         return False

      cmd = [flashromPath, '-p', f'linux_spi:dev={devPath}']
      cmd.append(op)
      if op == '-r':
         cmd.append(outputPath)

      try:
         logging.debug('%s: Executing %s', self, ' '.join(cmd))
         result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False
         )

         if result.returncode:
            logging.error('%s: flashrom cmd failed. rc:%d', self, result.returncode)
            return False

      except subprocess.TimeoutExpired:
         logging.error('%s: flashrom cmd %s timed out', self, op)
         return False
      except (OSError, ValueError) as e:
         logging.error('%s: Error executing flashrom command: %s', self, e)
         return False
      return True
