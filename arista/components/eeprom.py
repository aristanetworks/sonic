
from ..core.component import Priority
from ..core.component.i2c import I2cComponent
from ..core.log import getLogger
from ..core.prefdl import Prefdl
from ..core.utils import JsonStoredData

from ..drivers.eeprom import SeepromI2cDevDriver, EepromKernelDriver

logging = getLogger(__name__)

class I2cEeprom(I2cComponent):
   DRIVER = EepromKernelDriver
   PRIORITY = Priority.DEFAULT

   def read(self):
      return self.driver.read()

class I2cSeeprom(I2cComponent):
   DRIVER = SeepromI2cDevDriver
   PRIORITY = Priority.DEFAULT

   def read(self):
      return self.driver.read()

class PrefdlBase(object):
   def prefdl(self):
      cachedPrefdl = None
      try:
         cachedPrefdl = JsonStoredData(self.cacheFile())
         if cachedPrefdl.exist():
            return cachedPrefdl.read()
      except:
         logging.debug('Failed to read cached prefdl for device %s' %
               self.prefdlAddr())

      data = self.decode()

      if cachedPrefdl:
         try:
            cachedPrefdl.write(data, mode='w')
         except:
            logging.debug('Failed to cache prefdl for device %s' % self.prefdlAddr())

      return data

   def clean(self):
      cachedPrefdl = JsonStoredData(self.cacheFile())
      cachedPrefdl.clear()

   def cacheFile(self):
      return 'prefdl_%s' % self.prefdlAddr()

   def decode(self):
      raise NotImplementedError

   def prefdlAddr(self):
      raise NotImplementedError

class PrefdlEeprom(I2cEeprom, PrefdlBase):
   def decode(self):
      return Prefdl.fromBytes(self.read()).data()

   def prefdlAddr(self):
      return str(self.addr)

   def clean(self):
      I2cEeprom.clean(self)
      PrefdlBase.clean(self)

class PrefdlSeeprom(I2cSeeprom, PrefdlBase):
   def decode(self):
      return Prefdl.fromBytes(self.read()[8:]).data()

   def prefdlAddr(self):
      return str(self.addr)

   def clean(self):
      I2cSeeprom.clean(self)
      PrefdlBase.clean(self)
