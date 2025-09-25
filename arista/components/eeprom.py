
from ..core.component import Priority
from ..core.component.i2c import I2cComponent
from ..core.log import getLogger
from ..core.prefdl import Prefdl
from ..core.utils import JsonStoredData

from ..drivers.eeprom import (
   At24C32KernelDriver,
   At24C64KernelDriver,
   At24C512KernelDriver,
   EepromKernelDriver,
)

logging = getLogger(__name__)

def maybeCached(name, func, cls=JsonStoredData):
   name += '.json'
   try:
      cache = cls(name)
      if cache.exist():
         return cache.read()
   except Exception: # pylint: disable=broad-except
      logging.debug('Failed to read cache for %s', name)

   data = func()

   if cache:
      try:
         cache.write(data, mode='w')
      except Exception: # pylint: disable=broad-except
         logging.debug('Failed to cache value for %s', name)

   return data

def isCached(name, cls=JsonStoredData):
   name += '.json'
   try:
      cache = cls(name)
      return cache.exist()
   except Exception: # pylint: disable=broad-except
      logging.debug('Failed to read cache for %s', name)
      return False

def maybeClearCache(name):
   name += '.json'
   try:
      cache = JsonStoredData(name)
      cache.clear()
   except Exception: # pylint: disable=broad-except
      logging.debug("Failed to clear cache %s", name)

class I2cEeprom(I2cComponent):
   DRIVER = EepromKernelDriver
   PRIORITY = Priority.DEFAULT

   def eepromName(self):
      return self.label or 'eeprom_%s' % self.addr

   def prefdlCached(self):
      return isCached(self.eepromName())

   def clearPrefdlCache(self):
      maybeClearCache(self.eepromName())

   def prefdl(self):
      return maybeCached(self.eepromName(), lambda: self.readPrefdl().data())

   def readPrefdl(self):
      return Prefdl.fromBinFile(self.driver.eepromPath())

   def readPrefdlRaw(self):
      return self.readPrefdl().getRaw()

   def read(self):
      return self.driver.read()

   def clean(self):
      super(I2cEeprom, self).clean()
      self.clearPrefdlCache()

class I2cSeeprom(I2cEeprom):
   def __init__(self, *args, hdrSz=8, **kwargs):
      super().__init__(*args, **kwargs)
      self.hdrSz = hdrSz

   def readPrefdl(self):
      return Prefdl.fromBinFile(self.driver.eepromPath(), skip=self.hdrSz)

   def readPrefdlRaw(self):
      header = self.driver.read(self.hdrSz)
      return header + self.readPrefdl().getRaw()

class At24C32(I2cEeprom):
   DRIVER = At24C32KernelDriver

class At24C64(I2cSeeprom):
   DRIVER = At24C64KernelDriver

class At24C512(I2cSeeprom):
   DRIVER = At24C512KernelDriver
