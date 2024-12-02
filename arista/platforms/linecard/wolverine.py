
from ...core.component.i2c import I2cByteQuirk, I2cBlockQuirk
from ...core.hwapi import HwApi
from ...core.platform import registerPlatform
from ...core.port import PortLayout
from ...core.utils import incrange

from ...components.asic.dnx.jericho2c import Jericho2cPlus
from ...components.denali.desc import DenaliAsicDesc
from ...components.denali.linecard import (
   DenaliLinecard,
   GpioRegisterMap,
   StandbyScdRegisterMap,
)
from ...components.dpm.ucd import Ucd90320, UcdGpi
from ...components.eeprom import At24C512
from ...components.pca9555 import Pca9555
from ...components.plx import PlxPortDesc
from ...components.scd import I2cScd
from ...components.tmp464 import Tmp464
from ...components.vrm.mp8796b import Mp8796B

from ...descs.cause import ReloadCauseDesc
from ...descs.sensor import Position, SensorDesc
from ...descs.xcvr import Osfp, QsfpDD

from ..cpu.hedgehog import HedgehogCpu

class WolverineStandbyRegMap(StandbyScdRegisterMap):
   pass

class Wolverine(DenaliLinecard):
   CPU_CLS = HedgehogCpu
   ASICS = [
      DenaliAsicDesc(cls=Jericho2cPlus, asicId=0),
      DenaliAsicDesc(cls=Jericho2cPlus, asicId=1),
   ]
   XCVR_BUS_OFFSET = 24
   PLX_PORTS = [
      PlxPortDesc(port=0, name='sup1', upstream=True),
      PlxPortDesc(port=1, name='lcpu', vs=PlxPortDesc.VS1, upstream=True),
      PlxPortDesc(port=2, name='sup2', upstream=True),
      PlxPortDesc(port=3, name='je0', vs=PlxPortDesc.VS1),
      PlxPortDesc(port=4, name='je1', vs=PlxPortDesc.VS1),
      PlxPortDesc(port=5, name='scd', vs=PlxPortDesc.VS1),
      PlxPortDesc(port=13, name='gmac'),
   ]

   PORTS = PortLayout(
      (Osfp(i) for i in incrange(1, 36)),
   )

   def createPorts(self):
      intrRegs = [self.scd.getInterrupt(intId) for intId in incrange(0, 6)]
      # IRQ2 -> port 32:1 (bit 31:0)
      # IRQ3 -> port 36:33 (bit 3:0)
      self.scd.addXcvrSlots(
         ports=self.PORTS.getOsfps(),
         addr=0xA010,
         bus=self.XCVR_BUS_OFFSET,
         ledAddr=0x6100,
         intrRegs=intrRegs,
         intrRegIdxFn=lambda xcvrId: xcvrId // 32 + 2,
         intrBitFn=lambda xcvrId: (xcvrId - 1) % 32,
         isHwModSelAvail=False,
      )

      for riserId in incrange(1, 18):
         bus = 64 + riserId - 1
         self.scd.newComponent(At24C512, addr=self.scd.i2cAddr(bus, 0x50),
                               label='card%d_riser%s' % (self.slot.slotId, riserId))
         if self.getHwApi().majorOnly() == HwApi(43):
            # Increase UVP Tolerance
            self.scd.newComponent(
               Mp8796B,
               addr=self.scd.i2cAddr(bus, 0x32),
               quirks=[
                  I2cByteQuirk(0xd9, 0x00, description="lower xcvr uv threshold")
               ]
            )

   def mainDomain(self):
      self.scd.addSmbusMasterRange(0x8000, 10, spacing=0x80)

      for intId in incrange(0, 6):
         addr = 0x3000 + intId * 0x30
         self.scd.createInterrupt(addr=addr, num=intId)

      # At the moment there is no unique name for objects added to the kernel such
      # as leds, mdios, ... As a result, the kernel does some renaming, which is
      # not handled by the platform library. Until we have support for something
      # like slot prefixes for kernel objects, we only create the ports in LCPU
      # mode.
      if self.cpu:
         self.createPorts()
         self.cpu.addScdComponents(self.scd)

   def controlDomain(self):
      super(Wolverine, self).controlDomain()
      assert self.control, "Control plane power domain not initialized"
      self.CPU_CLS.addCpuDpm(bus=self.control, addr=self.pca.i2cAddr(0x4f))

   def createGpio1(self):
      self.gpio1 = self.pca.newComponent(Pca9555, addr=self.pca.i2cAddr(0x74),
                                         registerCls=GpioRegisterMap)

   def createStandbyDpm(self):
      quirks = [
         # GPI_CONFIG that disables faults on various GPIs due to
         # spurious failures
         I2cBlockQuirk(0xf9, [
            0x2e, 0xb5, 0x53, 0x02, 0x25, 0x51, 0x0d, 0x45, 0x10, 0x51, 0x65,
            0x50, 0x41, 0x15, 0x51, 0x0e, 0xf5, 0x50, 0x15, 0x61, 0x11, 0x50,
            0xa1, 0x13, 0x40, 0x95, 0x54, 0x2f, 0x21, 0x55, 0x13, 0x45, 0x51,
            0x39, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0xf2, 0x30, 0x02, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00,
         ], description='GPI_CONFIG'),
         # GPO_CONFIG_INDEX = 11 (GPO12 DPM_JE_DISCONNECT)
         I2cByteQuirk(0xf7, 0x0b, description='GPO_CONFIG_INDEX'),
         # GPO_CONFIG to be an actively driven output with no logic
         # Pin index 0x46 maps to LGPO15
         I2cBlockQuirk(0xf8, [
            0x46, 0x06, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
         ], description='GPO_CONFIG'),
         # GPIO_SELECT = 0x46 (LGPO15)
         I2cByteQuirk(0xfa, 0x46, description='GPIO_SELECT'),
         # GPIO_CONFIG the pin to be driven low
         I2cByteQuirk(0xfb, 0x03, description='GPIO_CONFIG'),
      ] if self.getHwApi() > HwApi(41) else []

      self.control.newComponent(Ucd90320, addr=self.pca.i2cAddr(0x11), causes=[
         UcdGpi(1, 'powerloss'),
         UcdGpi(5, 'asic-overtemp', 'asic'),
         UcdGpi(6, 'reboot'),
         UcdGpi(7, 'hotswap', 'lc eject'),
         UcdGpi(11, 'powerloss'),
         UcdGpi(12, 'powerloss'),
         UcdGpi(13, 'overtemp', 'asic memory'),
         UcdGpi(14, 'overtemp', 'asic memory'),
      ], quirks=quirks)

   def standbyDomain(self):
      super(Wolverine, self).standbyDomain()
      self.syscpld = self.pca.newComponent(I2cScd, addr=self.pca.i2cAddr(0x23),
                                           registerCls=WolverineStandbyRegMap)

      slot_prefix = f'LINE-CARD{self.getRelativeSlotId()} '
      self.pca.newComponent(Tmp464, addr=self.pca.i2cAddr(0x48),
                            sensors=[
         SensorDesc(diode=0, name=slot_prefix + 'Right', position=Position.OTHER,
                    target=70, overheat=80, critical=90),
         SensorDesc(diode=1, name=slot_prefix + 'Inlet', position=Position.INLET,
                    target=70, overheat=100, critical=105),
         SensorDesc(diode=2, name=slot_prefix + 'Outlet', position=Position.OUTLET,
                    target=70, overheat=100, critical=105),
         SensorDesc(diode=3, name=slot_prefix + 'Fap0 Back',
                    position=Position.OUTLET,
                    target=75, overheat=90, critical=100),
         SensorDesc(diode=4, name=slot_prefix + 'Fap1 Back',
                    position=Position.OUTLET,
                    target=75, overheat=90, critical=100),
      ])
      for fapId, addr in enumerate((0x49, 0x4a)):
         prefix = slot_prefix + f'Fap{fapId} '
         self.pca.newComponent(Tmp464, addr=self.pca.i2cAddr(addr),
                               sensors=[
            SensorDesc(diode=0, name=prefix + 'Front', position=Position.OTHER,
                       target=70, overheat=80, critical=90),
            SensorDesc(diode=1, name=prefix + 'C', position=Position.OTHER,
                       target=75, overheat=100, critical=105),
            SensorDesc(diode=2, name=prefix + 'AVS', position=Position.OTHER,
                       target=75, overheat=100, critical=105),
            SensorDesc(diode=3, name=prefix + 'FAB', position=Position.OTHER,
                       target=75, overheat=100, critical=105),
            SensorDesc(diode=4, name=prefix + 'NIF', position=Position.OTHER,
                       target=75, overheat=100, critical=105),
         ])

      self.cookies.register(ReloadCauseDesc.WATCHDOG,
                            self.syscpld.lcScdWatchdogInterrupt)

@registerPlatform()
class WolverineO(Wolverine):
   SID = ['WolverineO']
   SKU = ['7800R3A-36P-LC']

   MAX_POWER_DRAW = 749
   TYP_POWER_DRAW = 533

@registerPlatform()
class WolverineOMs(Wolverine):
   SID = ['WolverineOMs']
   SKU = ['7800R3A-36PM-LC']

   MAX_POWER_DRAW = 764
   TYP_POWER_DRAW = 548

@registerPlatform()
class WolverineOBkMs(Wolverine):
   SID = ['WolverineOBkMs']
   SKU = ['7800R3AK-36PM-LC']

   MAX_POWER_DRAW = 794
   TYP_POWER_DRAW = 578

@registerPlatform()
class WolverineQ(Wolverine):
   SID = ['WolverineQ']
   SKU = ['7800R3A-36D-LC']

   MAX_POWER_DRAW = 749
   TYP_POWER_DRAW = 533

   PORTS = PortLayout(
      (QsfpDD(i) for i in incrange(1, 36)),
   )

@registerPlatform()
class WolverineQMs(WolverineQ):
   SID = ['WolverineQMs']
   SKU = ['7800R3A-36DM-LC']

   MAX_POWER_DRAW = 764
   TYP_POWER_DRAW = 548

@registerPlatform()
class WolverineQBkMs(WolverineQ):
   SID = ['WolverineQBkMs']
   SKU = ['7800R3AK-36DM-LC']

   MAX_POWER_DRAW = 794
   TYP_POWER_DRAW = 578

@registerPlatform()
class WolverineQCpu(WolverineQ):
   SID = ['WolverineQCpu']
   SKU = ['7800R3A-36D2-LC']

   MAX_POWER_DRAW = 779
   TYP_POWER_DRAW = 563

@registerPlatform()
class WolverineQCpuMs(WolverineQ):
   SID = ['WolverineQCpuMs']
   SKU = ['7800R3A-36DM2-LC']

   MAX_POWER_DRAW = 794
   TYP_POWER_DRAW = 578

@registerPlatform()
class WolverineQCpuBkMs(WolverineQ):
   SID = ['WolverineQCpuBkMs']
   SKU = ['7800R3AK-36DM2-LC']

   MAX_POWER_DRAW = 824
   TYP_POWER_DRAW = 608
