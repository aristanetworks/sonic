import enum
import os

from ..core.driver import Driver, KernelDriver
from ..core.register import RegBitField, RegisterMap
from ..core.utils import FileResource, FileWaiter, MmapResource

from ..components.pci import PciRegister8, PciRegister16

from ..libs.wait import waitFor

class PciCapability(enum.IntEnum):
   PCI_EXPRESS = 0x10

class PciHeader(RegisterMap):
   STATUS = PciRegister16(0x6,
      RegBitField(4, 'capabilityList')
   )
   CAPABILITY_PTR = PciRegister8(0x34, name='capabilityPtr')

class PcieCapability(RegisterMap):
   LINK_CONTROL = PciRegister16(0x10,
      RegBitField(4, 'disabled', ro=False)
   )
   LINK_STATUS = PciRegister16(0x12)

class PciConfig(object):
   def __init__(self, addr=None):
      self.addr = addr
      self.hdrRegs = PciHeader(self)
      self.config_ = None

   def __str__(self):
      return '%s(addr=%s)' % (self.__class__.__name__, self.addr)

   @property
   def config(self):
      if self.config_ is None:
         path = os.path.join(self.addr.getSysfsPath(), "config")
         if not FileWaiter(path, 5).waitFileReady():
            raise IOError('mmap failed because file %s doesn\'t exist' % path)
         self.config_ = FileResource(path)
         if not self.config_.openResource():
            raise IOError('Failed to open file %s' % path)
      return self.config_

   def write8(self, addr, value):
      self.config.write8(addr, value)

   def read8(self, addr):
      return self.config.read8(addr)

   def write16(self, addr, value):
      self.config.write16(addr, value)

   def read16(self, addr):
      return self.config.read16(addr)

   def write(self, addr, value):
      self.config.write32(addr, value)

   def read(self, addr):
      return self.config.read32(addr)

   def findCapabilityHeader(self, capId):
      '''
      Walk the capability list to search for the capability capId.

      If found, the start offset of this capability is return.
      If not, None is returned
      '''

      if not self.hdrRegs.capabilityList():
         # Device doesn't support capabilities
         return None

      # Lower 2 bits are reserved & should be masked
      curCapOffset = self.hdrRegs.capabilityPtr() & 0xFC

      while curCapOffset != 0x0:
         # First byte is capability ID
         curCapId = self.config.read8(curCapOffset)
         if curCapId == capId:
            return curCapOffset

         # Second byte is the pointer to the next capability
         curCapOffset = self.config.read8(curCapOffset + 0x1)

      return None

   def pcieCapability(self):
      registerOffset = self.findCapabilityHeader(PciCapability.PCI_EXPRESS)
      assert registerOffset, "Device doesn't support PCIe capability"
      return PcieCapability(self, offset=registerOffset)

   def disabled(self):
      return self.pcieCapability().disabled()

   def enable(self):
      if self.disabled():
         self.pcieCapability().disabled(False)

   def disable(self):
      if not self.disabled():
         self.pcieCapability().disabled(True)

class PciSwitchPortDriver(Driver):
   def __init__(self, addr=None, upstreamAddr=None, **kwargs):
      super(PciSwitchPortDriver, self).__init__(**kwargs)
      self.addr = addr
      self.upstreamAddr = upstreamAddr
      self.config = PciConfig(addr)

   def upstreamPortExists(self):
      uStreamPath = os.path.join(self.addr.getSysfsPath(), str(self.upstreamAddr))
      return os.path.exists(uStreamPath)

   def disabled(self):
      return self.config.disabled()

   def enable(self):
      self.config.enable()

   def disable(self):
      self.config.disable()
      # We need to wait for the port to disapear. If we don't and the kernel is not
      # done processing the link down event, proceeding with things like turning off
      # power, may generate PCI error.
      waitFor(lambda: not self.upstreamPortExists())

class PciKernelDriver(KernelDriver):
   def __init__(self, addr=None, registerCls=None, **kwargs):
      self.addr = addr
      self.regs = registerCls(self) if registerCls is not None else None
      self.mmap_ = None
      self.hwmonPath = None
      super(PciKernelDriver, self).__init__(**kwargs)

   @property
   def mmap(self):
      if self.mmap_ is None:
         path = os.path.join(self.addr.getSysfsPath(), "resource0")
         if not FileWaiter(path, 5).waitFileReady():
            raise IOError('Mmap failed because file %s doesn\'t exist' % path)
         self.mmap_ = MmapResource(path)
         if not self.mmap_.map():
            raise IOError('Failed to mmap file %s' % path)
      return self.mmap_

   def write(self, addr, value):
      self.mmap.write32(addr, value)

   def read(self, addr):
      return self.mmap.read32(addr)

   def getSysfsPath(self):
      return self.addr.getSysfsPath()
