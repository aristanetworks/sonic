from ..core.cooling import CoolingConfig, CoolingLogicIncPid
from ..core.fixed import FixedSystem
from ..core.platform import registerPlatform
from ..core.port import PortLayout
from ..core.utils import incrange

from ..components.asic.xgs.tomahawk6 import Tomahawk6
from ..components.dpm.ucd import Ucd90320
from ..components.scd import Scd
from ..components.tmp401 import Tmp431

from ..descs.led import LedDesc, LedKind
from ..descs.reset import ResetDesc
from ..descs.xcvr import Osfp1600, Qsfp28

from .cpu.marconi import MarconiCpu

SFP_TRICOLOR_LED = {'defaultLed': '%s:rgb:1', 'leds': [
   LedDesc(addr=0, name='%s:rgb:1', **LedKind.desc(LedKind.RGB_8_F)),
   LedDesc(addr=16, name='%s:rgb:2', **LedKind.desc(LedKind.RGB_8_F)),
]}

class SteamerLaneBase(FixedSystem):

   PORTS = PortLayout(
      (Osfp1600(i, **SFP_TRICOLOR_LED) for i in incrange(1, 64)),
      (Qsfp28(65, **SFP_TRICOLOR_LED),),
   )

   COOLING = CoolingConfig(
      logic=CoolingLogicIncPid,
      kp=9,
      ki=0.75,
      kd=0,
      negHyst=0,
      posHyst=0,
   )

   def __init__(self, **kwargs):
      super().__init__(**kwargs)

      self.cpu = self.newComponent(MarconiCpu)

      # NOTE: should all the devices that hangs off the CPU i2c bus be declared
      # in a dedicated method. If the BMC takes ownership of those it would
      # make things easier to not load them from the CPU

      bus = self.cpu.getSmbus(self.cpu.SMBUS_FC)
      # TODO: add necessary components
      # 0x23 SYSCPLD
      # 0x08 POWER_CYCLER
      # 0x50 CPU_IDPROM
      # 0x74 IO EXPANDER

      bus = self.cpu.getSmbus(self.cpu.SMBUS_POL)
      self.cpu.cpld.newComponent(Ucd90320, addr=bus.i2cAddr(0x11))
      self.cpu.cpld.newComponent(Ucd90320, addr=bus.i2cAddr(0x13))
      # TODO: reboot causes?

      port = self.cpu.getPciPort(self.cpu.PCI_PORT_SCD0)
      self.scd = scd = port.newComponent(Scd, addr=port.addr)
      scd.setMsiRearmOffset(0x180)
      scd.addSmbusMasterRange(0x8000, 11, 0x80, 8)

      # TODO: add SensorDescs
      scd.newComponent(Tmp431, addr=scd.i2cAddr(0, 0x4c))
      scd.newComponent(Tmp431, addr=scd.i2cAddr(1, 0x4c))
      scd.newComponent(Tmp431, addr=scd.i2cAddr(2, 0x4c))

      # TODO: add Psus

      intrRegs = [
         scd.createInterrupt(addr=0x3000, num=0),
         scd.createInterrupt(addr=0x3030, num=1),
         scd.createInterrupt(addr=0x3060, num=2),
      ]

      scd.createWatchdog(intr=scd.getInterrupt(0), bit=20)

      scd.addXcvrSlots(
         ports=self.PORTS.getOsfps(),
         addr=0xA010,
         bus=8,
         ledAddr=0x6100,
         ledAddrOffsetFn=lambda x: 0x10,
         intrRegs=intrRegs,
         intrRegIdxFn=lambda xcvrId: xcvrId // 33 + 1,
         intrBitFn=lambda xcvrId: (xcvrId - 1) % 32,
      )

      scd.addXcvrSlots(
         ports=self.PORTS.getQsfps(),
         addr=0xA410,
         bus=6,
         ledAddr=0x6900,
         ledAddrOffsetFn=lambda x: 0x40,
         intrRegs=intrRegs,
         intrRegIdxFn=lambda _: 0,
         intrBitFn=lambda xcvrId: xcvrId - 65 + 9,
      )

      scd.addResets([
         ResetDesc('switch_chip_pcie_reset', addr=0x4000, bit=1, auto=False),
         ResetDesc('switch_chip_reset', addr=0x4000, bit=0, auto=False),
      ])

      # TODO: add system/status LEDs (on the management card)

      port = self.cpu.getPciPort(self.cpu.PCI_PORT_ASIC1)
      self.asic = port.newComponent(Tomahawk6, addr=port.addr,
         coreResets=[
            scd.inventory.getReset('switch_chip_reset'),
         ],
         pcieResets=[
            scd.inventory.getReset('switch_chip_pcie_reset'),
         ],
      )

@registerPlatform()
class SteamerLaneMv3(SteamerLaneBase):
   SID = ['SteamerLaneMv3']
   SKU = ['7060XE7-64PRS-MV3-L', 'DCS-7060XE7-64PRS-MV3-L']
