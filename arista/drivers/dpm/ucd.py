
from ...core.log import getLogger
from ...core.utils import inSimulation

from .pmbus import PmbusUserDriver

logging = getLogger(__name__)

class UcdUserDriver(PmbusUserDriver):
   def _decodeVoutModeExponent(self, value):
      exponent = value & 0x1f
      if exponent & 0x10:
         exponent -= 0x20
      return exponent

   def getVoutExponent(self, page):
      if inSimulation():
         return None
      oldPage = self.read_byte_data(self.registers.PAGE)
      try:
         self.write_byte_data(self.registers.PAGE, page - 1)
         return self._decodeVoutModeExponent(
            self.read_byte_data(self.registers.VOUT_MODE))
      finally:
         self.write_byte_data(self.registers.PAGE, oldPage)

   def dumpReg(self, name, data):
      logging.debug('%s reg: %s', name, ' '.join('%02x' % s for s in data))

   def getVersion(self):
      if inSimulation():
         return "SERIAL UCDSIM 2.3.4.0005 241218"
      data = self.getBlock(self.registers.MFR_SERIAL)
      serial = ''.join(chr(c) for c in data)
      data = self.getBlock(self.registers.DEVICE_ID)
      devid = ''.join(chr(c) for c in data if c).replace('|', ' ')
      return '%s %s' % (serial, devid)

   def readFaults(self):
      if inSimulation():
         return [ 0 ] * self.registers.LOGGED_FAULTS_COUNT
      res = self.getBlock(self.registers.LOGGED_FAULTS)
      self.dumpReg('faults', res)
      return res

   def clearFaults(self):
      if inSimulation():
         return
      reg = self.registers.LOGGED_FAULTS
      size = self.bus.read_byte_data(self.addr.address, reg)
      data = [ 0 ] * size
      self.setBlock(reg, data)

   def getFaultCount(self):
      if inSimulation():
         return 0
      reg = self.registers.LOGGED_FAULT_DETAIL_INDEX
      res = self.bus.read_word_data(self.addr.address, reg)
      return res >> 8

   def getFaultNum(self, num):
      if inSimulation():
         return [ 0 ] * self.registers.LOGGED_FAULT_DETAIL_COUNT
      self.bus.write_word_data(self.addr.address,
                               self.registers.LOGGED_FAULT_DETAIL_INDEX, num)
      res = self.getBlock(self.registers.LOGGED_FAULT_DETAIL)
      self.dumpReg('fault %d' % num, res)
      return res
