import os.path

from ..core.log import getLogger
from ..core.utils import inSimulation
from ..inventory.gpio import Gpio

logging = getLogger(__name__)

class GpioImpl(Gpio):
   def __init__(self, name, addr=0, bit=0, ro=False, activeLow=False,
                hwActiveLow=False, **kwargs):
      self.name = name
      self.addr = addr
      self.bit = bit
      self.ro = ro
      self.activeLow = activeLow
      self.hwActiveLow = hwActiveLow
      self.__dict__.update(kwargs)

   def getName(self):
      return self.name

   def getAddr(self):
      return self.addr

   def getPath(self):
      return None

   def getBit(self):
      return self.bit

   def isRo(self):
      return self.ro

   def isActiveLow(self):
      return False if self.hwActiveLow else self.activeLow

   def getRawValue(self):
      raise NotImplementedError

   def setRawValue(self, value):
      raise NotImplementedError

   def _activeValue(self):
      return 0 if self.isActiveLow() else 1

   def isActive(self):
      if inSimulation():
         return True
      return self.getRawValue() == self._activeValue()

   def setActive(self, value):
      self.setRawValue(not value if self.isActiveLow() else value)

class FileGpioImpl(GpioImpl):
   def __init__(self, path, name, *args, **kwargs):
      super(FileGpioImpl, self).__init__(name, *args, **kwargs)
      self.path = os.path.join(path, name)

   def getPath(self):
      return self.path

   def getRawValue(self):
      try:
         with open(self.path, 'r') as f:
            return int(f.read())
      except IOError:
         logging.error('file gpio read failed on %s', self.path)
         return None

   def setRawValue(self, value):
      with open(self.path, 'w') as f:
         f.write(int(value))

class FuncGpioImpl(GpioImpl):
   def __init__(self, func, name):
      super(FuncGpioImpl, self).__init__(name)
      self.func = func

   def getRawValue(self):
      return self.func()

   def setRawValue(self, value):
      return self.func(value)
