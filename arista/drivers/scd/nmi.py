
from ..pci import PciConfig

from ...core.utils import FileResource, inSimulation, writeConfig
from ...libs.pci import findPciDevice

class ScdNmiConfig:
   def setup(self, scd):
      if inSimulation():
         return
      self._configureNmi(scd)

   def _configureNmi(self, scd): # pylint: disable=unused-argument
      raise NotImplementedError

   @staticmethod
   def _writeNmiAttrs(scd, *, portIo, ctrlReg, ctrlMask, stsReg, stsMask,
                      gpioStsReg=0, gpioStsMask=0):
      writeConfig(scd.addr.getSysfsPath(), {
         'nmi_port_io_p':            '1' if portIo else '0',
         'nmi_control_reg_addr':     str(ctrlReg),
         'nmi_control_mask':         str(ctrlMask),
         'nmi_status_reg_addr':      str(stsReg),
         'nmi_status_mask':          str(stsMask),
         'nmi_gpio_status_reg_addr': str(gpioStsReg),
         'nmi_gpio_status_mask':     str(gpioStsMask),
      })

class ScdNmiPchConfig(ScdNmiConfig):
   def __init__(self, pciVendorId, pciDeviceId, gpioBaseOffset, gpioBaseMask,
                gpioBit, gpiNmiEn, gpiNmiSts):
      self.pciVendorId = pciVendorId
      self.pciDeviceId = pciDeviceId
      self.gpioBaseOffset = gpioBaseOffset
      self.gpioBaseMask = gpioBaseMask
      self.gpioBit = gpioBit
      self.gpiNmiEn = gpiNmiEn
      self.gpiNmiSts = gpiNmiSts

   def _configureNmi(self, scd):
      pchAddr = findPciDevice(self.pciVendorId, self.pciDeviceId)
      reg = PciConfig(pchAddr).read16(self.gpioBaseOffset)
      gpioBase = reg & self.gpioBaseMask
      ctrlMask = 0x1 << self.gpioBit
      self._writeNmiAttrs(scd,
         portIo=True,
         ctrlReg=gpioBase + self.gpiNmiEn,
         ctrlMask=ctrlMask,
         stsReg=gpioBase + self.gpiNmiSts,
         stsMask=ctrlMask,
      )

class ScdNmiCedarForkPchConfig(ScdNmiConfig):
   def __init__(self, p2SBBase, portId, gpioBit, nmiControl, nmiStatus, gpioBase):
      self.p2SBBase = p2SBBase
      self.portId = portId
      self.gpioBit = gpioBit
      self.nmiControl = nmiControl
      self.nmiStatus = nmiStatus
      self.gpioBase = gpioBase

   def _configureNmi(self, scd):
      portBase = self.p2SBBase | (self.portId << 16)
      ctrlMask = 0x1 << self.gpioBit
      gpioStatusRegAddr = portBase | (self.gpioBase + (0x10 * self.gpioBit))
      self._writeNmiAttrs(scd,
         portIo=False,
         ctrlReg=portBase | self.nmiControl,
         ctrlMask=ctrlMask,
         stsReg=portBase | self.nmiStatus,
         stsMask=ctrlMask,
         gpioStsReg=gpioStatusRegAddr,
         gpioStsMask=0x1 << 1,
      )

class ScdNmiCedarForkWestBankPchConfig(ScdNmiConfig):
   def __init__(self, p2SBBase, portId, gpioBit, nmiControl, nmiStatus, gpioBase,
                hostSwOwnReg, padCfgDw0Mask, padCfgDw0Setting):
      self.p2SBBase = p2SBBase
      self.portId = portId
      self.gpioBit = gpioBit
      self.nmiControl = nmiControl
      self.nmiStatus = nmiStatus
      self.gpioBase = gpioBase
      self.hostSwOwnReg = hostSwOwnReg
      self.padCfgDw0Mask = padCfgDw0Mask
      self.padCfgDw0Setting = padCfgDw0Setting

   def _configureNmi(self, scd):
      portBase = self.p2SBBase | (self.portId << 16)
      ctrlMask = 0x1 << self.gpioBit
      gpioStatusRegOffset = self.gpioBase + (0x10 * self.gpioBit)

      with FileResource('/dev/mem') as mem:
         hostSwOwnAddr = portBase + self.hostSwOwnReg
         mem.write32(hostSwOwnAddr,
                     mem.read32(hostSwOwnAddr) & ~(0x1 << self.gpioBit))
         val = mem.read32(portBase + gpioStatusRegOffset) & ~self.padCfgDw0Mask
         val |= self.padCfgDw0Setting
         mem.write32(portBase + gpioStatusRegOffset, val)
         mem.write32(portBase + self.nmiControl,
                     mem.read32(portBase + self.nmiControl) | ctrlMask)

      self._writeNmiAttrs(scd,
         portIo=False,
         ctrlReg=portBase | self.nmiControl,
         ctrlMask=ctrlMask,
         stsReg=portBase | self.nmiStatus,
         stsMask=ctrlMask,
         gpioStsReg=portBase | gpioStatusRegOffset,
         gpioStsMask=0x1 << 1,
      )

class ScdNmiKabiniConfig(ScdNmiConfig):
   SMI_BASE_OFFSET = 0x200

   def __init__(self, gpioBit, base=0xfed80000):
      self.gpioBit = gpioBit
      self.base = base

   def _configureNmi(self, scd):
      ctrlReg  = self.base + self.SMI_BASE_OFFSET + 0xa0
      ctrlMask = 0x3 << (2 * self.gpioBit)
      stsReg   = self.base + self.SMI_BASE_OFFSET + 0x80
      stsMask  = 0x1 << self.gpioBit
      trigReg  = self.base + self.SMI_BASE_OFFSET + 0x98

      with FileResource('/dev/mem') as mem:
         mem.write32(trigReg, mem.read32(trigReg) & ~stsMask)
         val = mem.read32(ctrlReg) & ~ctrlMask
         val |= 0x2 << (2 * self.gpioBit)
         mem.write32(ctrlReg, val)

      self._writeNmiAttrs(scd,
         portIo=False,
         ctrlReg=ctrlReg,
         ctrlMask=ctrlMask,
         stsReg=stsReg,
         stsMask=stsMask,
      )

class ScdNmiSb800Config(ScdNmiConfig):
   def __init__(self, base, smiControl7, smiStatus3, nmiIrq, gpioBit,
                gpioBase, pciIntrIndex, pciIntrData):
      self.base = base
      self.smiControl7 = smiControl7
      self.smiStatus3 = smiStatus3
      self.nmiIrq = nmiIrq
      self.gpioBit = gpioBit
      self.gpioBase = gpioBase
      self.pciIntrIndex = pciIntrIndex
      self.pciIntrData = pciIntrData

   def _configureNmi(self, scd):
      ctrlReg           = self.base + self.smiControl7
      ctrlMask          = 0x3 << (2 * (self.nmiIrq - 16))
      stsReg            = self.base + self.smiStatus3
      stsMask           = 0x1 << self.nmiIrq
      gpioStatusRegAddr = self.gpioBase + 28 + self.gpioBit
      gpioStatusMask    = 0x1 << 7

      with FileResource('/dev/port') as port:
         port.write8(self.pciIntrIndex, self.gpioBit | (1 << 7))
         port.write8(self.pciIntrData, self.nmiIrq)

      with FileResource('/dev/mem') as mem:
         val = mem.read32(ctrlReg) & ~ctrlMask
         val |= 0x2 << (2 * (self.nmiIrq - 16))
         mem.write32(ctrlReg, val)

      self._writeNmiAttrs(scd,
         portIo=False,
         ctrlReg=ctrlReg,
         ctrlMask=ctrlMask,
         stsReg=stsReg,
         stsMask=stsMask,
         gpioStsReg=gpioStatusRegAddr,
         gpioStsMask=gpioStatusMask,
      )
