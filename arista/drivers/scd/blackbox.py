import os
import subprocess

from ...core.config import Config
from ...core.log import getLogger
from ...core.blackbox import BlackBoxDecoder
from ...core.utils import StoredData
from ...inventory.blackbox import BlackBoxImpl
from ...drivers.spi import SpidevDriver

logging = getLogger(__name__)

class ScdBlackBoxDecoder(BlackBoxDecoder):
   def __init__(self, bufSplit=0):
      self.bufSplit = bufSplit

   def decode(self, data):
      s = self.bufSplit or len(data)
      return (self._decode(bytearray(data[:s])) +
              self._decode(bytearray(data[s:]))).decode('ascii')

   def _decode(self, buf):
      if not buf:
         return bytearray()

      if all(c == 0xff for c in buf):
         return bytearray()

      end = buf.find(0x9a)
      if end != -1:
         return bytearray(buf[:end])

      split = buf.find(0x1a)
      if split != -1:
         return bytearray(buf[split + 1:] + buf[:split])

      return bytearray(buf)

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

   def getModel(self):
      driver = self.component.driver
      if self.enabled():
         return driver.cachedFramModel or 'Unknown'
      return driver.framModel

   def enabled(self):
      return self.component.enabled()

   def setEnabled(self, enabled):
      return self.component.setEnabled(enabled)

   def dump(self, outputPath):
      return self.component.driver.dump(outputPath)

   def decoder(self):
      return ScdBlackBoxDecoder(self.component.bufSplit)

   def erase(self):
      return self.component.driver.erase()

class ScdBlackBoxDriver(SpidevDriver):
   def __init__(self, **kwargs):
      super().__init__(**kwargs)
      self._framModel = None

   def getBlackBox(self, component):
      return ScdBlackBoxImpl(component)

   def _framModelStore(self):
      return StoredData(f'blackbox{self.addr.bus}.{self.addr.cs}_fram_model')

   def _cacheFramModel(self, model):
      if model:
         self._framModelStore().write(model)
         self._framModel = model

   @property
   def cachedFramModel(self):
      if self._framModel is None:
         cache = self._framModelStore()
         if cache.exist():
            self._framModel = cache.read()
      return self._framModel

   def _parseFramModel(self, output):
      if output is None:
         return None
      for line in output.splitlines():
         if 'flash chip' in line:
            parts = line.split()
            ## Example: "Found Macronix flash chip "MX25U25645G""
            return f'''{parts[1]} {parts[4].strip('"')}'''
      return None

   @property
   def framModel(self):
      if self.cachedFramModel is None:
         self._cacheFramModel(self._detectFramModel())
      return self._framModel or 'Unknown'

   def dump(self, outputPath):
      output = self._runFlashromCmd(op='-r', outputPath=outputPath)
      self._cacheFramModel(self._parseFramModel(output))
      return output

   def erase(self):
      return self._runFlashromCmd(op='-E')

   def _detectFramModel(self):
      return self._parseFramModel(self._runFlashromCmd(op='-V'))

   def _runFlashromCmd(self, op, outputPath=None):
      devPath = self.getDevPath()
      if not os.path.exists(devPath):
         logging.error('%s: spidev not found: %s', self, devPath)
         return None

      flashromPath = Config().blackbox_flashrom_path
      if not os.path.exists(flashromPath):
         logging.error('%s: flashrom-arista not found at %s', self, flashromPath)
         return None

      cmd = [flashromPath, '-p', f'linux_spi:dev={devPath}']
      cmd.append(op)
      if op == '-r':
         cmd.append(outputPath)

      try:
         logging.debug('%s: Executing %s', self, ' '.join(cmd))
         result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False
         )

         if result.returncode:
            logging.error('%s: flashrom cmd failed. rc:%d', self, result.returncode)
            return None

      except subprocess.TimeoutExpired:
         logging.error('%s: flashrom cmd %s timed out', self, op)
         return None
      except (OSError, ValueError) as e:
         logging.error('%s: Error executing flashrom command: %s', self, e)
         return None

      return result.stdout.decode('ascii')
