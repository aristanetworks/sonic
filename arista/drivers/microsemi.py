
import contextlib
import os

from ..core.config import tmpfsPath
from ..core.driver import Driver
from ..core.utils import FileLock, MmapResource

from ..libs.wait import waitFor

class MicrosemiConsts(object):
   GAS_DONE = 2
   GAS_INPROGRESS = 1
   SWITCHTEC_MAX_PORTS = 48
   MICROSEMI_VENDOR_ID = 0x11f8
   MICROSEMI_DEVICE_IDS = [ 0x8533, 0x8534, 0x8532 ]
   MICROSEMI_BUS = 5
   MICROSEMI_FUNC = 1

class MicrosemiGAS(object):
   GAS_INPUT_DATA = 0
   GAS_OUTPUT_DATA = 0x400
   GAS_COMMAND = 0x800
   GAS_STATUS = 0x804
   GAS_RETURNVALUE = 0x808

class MCRPC_P2PSubcommand(object):
   MRPC_P2P_BIND = 0
   MRPC_P2P_UNBIND = 1
   MRPC_P2P_INFO = 3

class MicrosemiMRPC(MCRPC_P2PSubcommand):
   MRPC_PORTLN = 8
   MRPC_PORTPARTP2P = 12
   MRPC_LNKSTAT = 28

class MicrosemiDriver(MicrosemiConsts, MicrosemiMRPC, MicrosemiGAS, Driver):
   def __init__(self, addr=None, **kwargs):
      # TODO: refactor this driver to share map/pci primitives with others
      #       something like PciUserDriver or PciDevDriver as base instead of Driver
      super(MicrosemiDriver, self).__init__(**kwargs)
      self.addr = addr
      self.microsemiBar = 0
      self.resource_ = None

   @property
   def lockName(self):
      return '%s_%s.lock' % (self.__class__.__name__, str(self.addr))

   @contextlib.contextmanager
   def lock(self):
      path = tmpfsPath(self.lockName)
      with FileLock(path):
         yield

   @property
   def resource(self):
      if self.resource_ is None:
         self.mapResource()
      return self.resource_

   def mapResource(self):
      p = os.path.join(self.addr.getSysfsPath(), "resource%d" % self.microsemiBar)
      self.resource_ = MmapResource(p)
      self.resource_.map()

   def write32(self, offset, value):
      return self.resource.write32(offset, value)

   def read32(self, offset):
      return self.resource.read32(offset)

   def gasWait(self):
      def status():
         return self.read32(self.GAS_STATUS)
      waitFor(lambda: (status() == self.GAS_DONE))
      return self.read32(self.GAS_RETURNVALUE)

   def doGas(self, cmd, dataIn):
      dataIn = [dataIn] if not isinstance(dataIn, list) else dataIn
      for i, data in enumerate(dataIn):
         self.write32(self.GAS_INPUT_DATA + i * 0x4, data)
      self.write32(self.GAS_COMMAND, cmd)
      return self.gasWait()

   def doGasLocked(self, cmd, dataIn):
      with self.lock():
         return self.doGas(cmd, dataIn)

   def bind(self, port, dsp=1, partition=0):
      data = self.MRPC_P2P_BIND | int(partition) << 8 | \
             int(dsp) << 16 | int(port) << 24
      return self.doGasLocked(self.MRPC_PORTPARTP2P, data)

   def unbind(self, dsp, partition=0, flags=0x2):
      data = self.MRPC_P2P_UNBIND | int(partition) << 8 | \
             int(dsp) << 16 | int(flags) << 24
      return self.doGasLocked(self.MRPC_PORTPARTP2P, data)
