
import struct

from ..core.component import Priority
from ..core.component.i2c import I2cComponent
from ..core.i2c_utils import I2cMsg
from ..core.log import getLogger
from ..core.prefdl import Prefdl
from ..core.utils import JsonStoredData

from ..drivers.eeprom import (
   At24C32KernelDriver,
   At24C64KernelDriver,
   At24C512KernelDriver,
   At24KernelDriver,
)

logging = getLogger(__name__)

def maybeCached(name, func, cls=JsonStoredData):
   name += '.json'
   try:
      cache = JsonStoredData(name)
      if cache.exist():
         return cache.read()
   except Exception: # pylint: disable=broad-except
      logging.debug('Failed to read cache for %s' % name)

   data = func()

   if cache:
      try:
         cache.write(data, mode='w')
      except Exception: # pylint: disable=broad-except
         logging.debug('Failed to cache value for %s' % name)

   return data

def maybeClearCache(name):
   name += '.json'
   try:
      cache = JsonStoredData(name)
      cache.clear()
   except Exception: # pylint: disable=broad-except
      logging.debug("Failed to clear cache %s" % name)

class I2cEeprom(I2cComponent):
   DRIVER = At24KernelDriver
   PRIORITY = Priority.DEFAULT

   def eepromName(self):
      return self.label or 'eeprom_%s' % self.addr

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
      maybeClearCache(self.eepromName())

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

class RawI2cPrefdlEeprom():
   """Read PreFDL from EEPROM via raw I2C (no kernel driver).

   For use before kernel EEPROM drivers are available, e.g. at
   firmware update time before SCD setup.
   """

   HDR_SIZE = 8
   TYPE_PREFDL = 3

   def __init__(self, bus, addr, label=None):
      self.bus = bus
      self.addr = addr
      self.label = label

   def eepromName(self):
      return self.label or 'cpu_prefdl'

   def prefdl(self):
      return maybeCached(self.eepromName(),
                         lambda: self.readPrefdl().data())

   def readPrefdl(self):
      i2cAddr = self.bus.i2cAddr(self.addr)
      with I2cMsg(i2cAddr) as msg:
         # PREFDL EEPROM uses 2-byte addressing; 8-byte header
         # (type + length) precedes the PreFDL payload
         hdr = msg.read_bytes(i2cAddr.address,
                              [0x00, 0x00], self.HDR_SIZE)
         eepromType, length = struct.unpack('>LL', bytes(hdr))
         if eepromType != self.TYPE_PREFDL:
            raise ValueError('unexpected eeprom type %d' % eepromType)
         data = msg.read_bytes(i2cAddr.address,
                               [0x00, self.HDR_SIZE], length)
         return Prefdl.fromBytes(bytes(data))

   def clean(self):
      maybeClearCache(self.eepromName())
