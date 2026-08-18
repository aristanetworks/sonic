
import struct

from ..core.driver.user.i2c import I2cDevDriver
from ..core.log import getLogger

logging = getLogger(__name__)

class BcmAsicQspi(I2cDevDriver):
   BSPI_MMAP_BASE = 0x04000000
   FW_HEADER_OFFSET = 0x2c00
   PCIE_FW_LDR_VER_OFFSET = 0x04

   def _readIprocReg(self, iprocAddr):
      cmd = [
         (iprocAddr >> 24) & 0xff,
         (iprocAddr >> 16) & 0xff,
         (iprocAddr >>  8) & 0xff,
         iprocAddr        & 0xff,
      ]
      wire = self.read_bytes(cmd, 4)
      return bytes(reversed(wire))

   def getVersion(self):
      iprocAddr = (self.BSPI_MMAP_BASE
                   + self.FW_HEADER_OFFSET
                   + self.PCIE_FW_LDR_VER_OFFSET)
      try:
         data = self._readIprocReg(iprocAddr)
      except OSError as e:
         logging.debug('%s: iproc read failed: %s', self, e)
         return 'N/A'
      if data == b'\xff\xff\xff\xff':
         logging.debug('%s: version register reads all-ones', self)
         return 'N/A'
      minor, major = struct.unpack('<HH', data)
      version = '%d.%d' % (major, minor)
      logging.debug('%s: firmware version = %s', self, version)
      return version
