import os
import subprocess

from ...core.config import Config
from ...core.log import getLogger
from ...core.blackbox import BlackBoxDecoder
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
      WAITING_FIRST_MARKER = 0
      WAITING_FIRST_CHAR = 1
      REWAITING_FIRST_MARKER = 2

      result = bytearray()
      buf_len = len(buf)

      if buf_len == 0:
         return result

      i = 0
      first_char_idx = 0
      last_char_idx = 0
      state = WAITING_FIRST_MARKER

      while True:
         if i >= buf_len:
            i = 0
            if state == WAITING_FIRST_MARKER:
               # Check if blackbox has been erased (all zeros)
               while buf[i] == 0:
                  i += 1
                  if i >= buf_len:
                     return result
               return result

         c = buf[i]

         if state == WAITING_FIRST_MARKER:
            if c == 0x9a:
               result.extend(buf[:i])
               return result
            if c == 0x1a:
               state = WAITING_FIRST_CHAR
         elif state == WAITING_FIRST_CHAR:
            if c != 0x1a:
               first_char_idx = i
               state = REWAITING_FIRST_MARKER
         elif state == REWAITING_FIRST_MARKER:
            if c == 0x1a:
               if first_char_idx < i:
                  result.extend(buf[first_char_idx:i])
               else:
                  result.extend(buf[first_char_idx:buf_len])
                  result.extend(buf[:last_char_idx])
               return result
            last_char_idx = i

         i += 1

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

   def decoder(self):
      return ScdBlackBoxDecoder(self.component.bufSplit)

   def erase(self):
      return self.component.driver.erase()

class ScdBlackBoxDriver(SpidevDriver):
   def getBlackBox(self, component):
      return ScdBlackBoxImpl(component)

   def dump(self, outputPath):
      return self._runFlashromCmd(op='-r', outputPath=outputPath)

   def erase(self):
      return self._runFlashromCmd(op='-E')

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
