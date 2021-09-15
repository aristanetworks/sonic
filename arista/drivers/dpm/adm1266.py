
import datetime
import struct
import time

from ...core.log import getLogger
from ...core.utils import incrange

from ...libs.date import epochToDatetime
from ...libs.retry import retryGet

from .pmbus import PmbusUserDriver

logging = getLogger(__name__)

def cyclicRange(start, size):
   if start > size:
      return
   for i in range(start, size):
      yield i
   for i in range(0, start):
      yield i

def bitOffsets(integer):
   idx = 0
   res = []
   while integer:
      if integer & 0x1:
         res.append(idx)
      integer >>=1
      idx += 1
   return res

def bitOffsetsStr(integer, off=1, sep=',', bmax=None):
   bits = bitOffsets(integer)
   return sep.join('%s' % (b + off) for b in bits if bmax is None or b < bmax)

def bitMapStr(integer, mapping, sep=','):
   bits = bitOffsets(integer)
   return sep.join(str(mapping[b]) for b in bits if mapping[b] is not None)

def admToDatetime(data):
   current = 0
   for i, x in enumerate(data[2:]):
      current |= (x & 0xff) << (8 * i)
   usecs = 0
   for i, x in enumerate(data[:2]):
      usecs |= (x & 0xff) << (8 * i)
   return epochToDatetime(current) + datetime.timedelta(seconds=usecs / 2**16)

class Adm1266Fault(object):
   VHX_MAP = ['VH%d_OV' % i for i in incrange(1, 4)] + \
             ['VH%d_UV' % i for i in incrange(1, 4)]
   GPIO_MAP = [1, 2, 3, None, None, None, 8, 9, 4, 5, 6, 7, None, None, None, None]

   def __init__(self, raw, uid, empty, action, rule, vhx, current, last, vp_ov,
                vp_uv, gpio_in, gpio_out, pdio_in, pdio_out, powerup, timestamp,
                crc):
      self.raw = raw
      self.uid = uid
      self.empty = empty
      self.action = action
      self.rule = rule
      self.vhx = vhx
      self.current = current
      self.last = last
      self.vp_ov = vp_ov
      self.vp_uv = vp_uv
      self.gpio_in = gpio_in
      self.gpio_out = gpio_out
      self.pdio_in = pdio_in
      self.pdio_out = pdio_out
      self.powerup = powerup
      self.timestamp = timestamp
      self.crc = crc

   def isValid(self):
      return self.empty & 0x1 == 0

   def isGpio(self, gpio):
      bit = self.GPIO_MAP.index(gpio)
      return bool(self.gpio_in & (1 << bit))

   def getTime(self):
      return admToDatetime(self.timestamp)

   def data(self):
      return {
         'uid': self.uid,
         'empty': self.empty,
         'vhx': bitMapStr(self.vhx, self.VHX_MAP),
         'current': self.current,
         'last': self.last,
         'vp_ov': bitOffsetsStr(self.vp_ov, bmax=13),
         'vp_uv': bitOffsetsStr(self.vp_uv, bmax=13),
         'gpio_in': bitMapStr(self.gpio_in, mapping=self.GPIO_MAP),
         'gpio_out': bitMapStr(self.gpio_out, mapping=self.GPIO_MAP),
         'pdio_in': bitOffsetsStr(self.pdio_in),
         'pdio_out': bitOffsetsStr(self.pdio_out),
         'powerup': self.powerup,
         'timestamp': self.getTime(),
      }

   def summary(self):
      return ' '.join('%s=%s' % (k, v) for k, v in self.data().items() if v)

class Adm1266UserDriver(PmbusUserDriver):

   def getBlackboxInfo(self):
      data = self.read_block_data(self.registers.BLACKBOX_INFORMATION)
      bbid, index, count = struct.unpack('<HBB', bytearray(data))
      return bbid, index, count

   def getPowerupCounter(self):
      data = self.read_i2c_block_data(self.registers.POWERUP_COUNTER, 3)[1:]
      return struct.unpack('<H', bytearray(data))

   def getUserData(self, idx=0, length=32):
      cmd = [self.registers.USER_DATA, 3, length, idx & 0xff, (idx >> 8) & 0xff]
      return self.read_bytes(cmd, length + 1)[1:]

   def getUserDataStr(self, idx=0, length=32):
      return self._bytesToStr(self.getUserData(idx, length))

   def _readMfrStr(self, reg):
      return self.read_bytes_str([reg, 32], 33).strip()

   def getVersion(self):
      model = self._readMfrStr(self.registers.MFR_MODEL)
      version = self._readMfrStr(self.registers.MFR_REVISION)
      date = self._readMfrStr(self.registers.MFR_DATE)
      serial = self._readMfrStr(self.registers.MFR_SERIAL)
      fw = self.getUserDataStr()
      return "%s %s %s %s %s" % (model, version, date, serial, fw)

   def getBlackboxFault(self, index):
      data = self.read_bytes([self.registers.READ_BLACKBOX, 1, index], 65)[1:]
      logging.debug('%s: fault %d: %s', self, index,
                    ' '.join('%02x' % s for s in data))

      fmt = '<HBBBBHHHHHHHHH'
      attrs = struct.unpack(fmt, bytearray(data[:24]))
      timestamp = data[24:32]
      crc = data[-1]
      return Adm1266Fault(data, *tuple(list(attrs) + [timestamp, crc]))

   def getBlackboxFaults(self):
      _, index, count = self.getBlackboxInfo()
      logging.debug('%s: fault info: index=%d count=%d', self, index, count)
      faults = []
      for i in reversed(list(cyclicRange(index + 1, count))):
         fault = self.getBlackboxFault(i)
         if fault.isValid():
            faults.append(fault)
      return faults

   def getRunTimeClock(self):
      data = self.read_block_data(self.registers.RUN_TIME_CLOCK)
      return admToDatetime(data)

   def setRunTimeClock(self):
      now = time.time()
      secs = int(now)
      usecs = int((now - secs) * 2**16)
      data = [0] * 6
      for i in range(4):
         data[i + 2] = (secs >> (i * 8)) & 0xff
      for i in range(2):
         data[i] = (usecs >> (i * 8)) & 0xff

      def writeRunTimeClock():
         # Use retry for this function
         self.write_block_data(self.registers.RUN_TIME_CLOCK, data)
      retryGet(writeRunTimeClock, retries=5)

   def clearBlackboxFaults(self):
      self.write_block_data(self.registers.READ_BLACKBOX, [0xfe, 0])
