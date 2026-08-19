from ..core.cooling import CoolingConfig, CoolingLogicIncPid
from ..core.fixed import FixedSystem
from ..core.platform import registerPlatform
from ..core.port import PortLayout
from ..core.utils import incrange

from ..components.asic.xgs.tomahawk6 import Tomahawk6
from ..components.dpm.ucd import Ucd90320, UcdGpi, UcdMon
from ..components.scd import Scd
from ..components.tmp401 import Tmp431

from ..descs.cause import ReloadCauseDesc
from ..descs.led import LedDesc, LedKind
from ..descs.reset import ResetDesc
from ..descs.sensor import Position, SensorDesc
from ..descs.xcvr import Osfp1600, Qsfp28

from .cpu.marconi import MarconiCpu

OSFP_TRICOLOR_LED = {'defaultLed': '%s:rgb:1', 'leds': [
   LedDesc(addr=0, name='%s:rgb:1', **LedKind.desc(LedKind.RGB_8_F)),
   LedDesc(addr=16, name='%s:rgb:2', **LedKind.desc(LedKind.RGB_8_F)),
]}
QSFP_TRICOLOR_LED = {'defaultLed': '%s:rgb:1', 'leds': [
   LedDesc(addr=0, name='%s:rgb:1', **LedKind.desc(LedKind.RGB_8_F)),
]}

class SteamerLaneBase(FixedSystem):

   PORTS = PortLayout(
      (Osfp1600(i, **OSFP_TRICOLOR_LED) for i in incrange(1, 64)),
      (Qsfp28(65, **QSFP_TRICOLOR_LED),),
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

      self.cpu.cpld.newComponent(
         Ucd90320, addr=bus.i2cAddr(0x11),
         causes=[
            UcdMon(1, ReloadCauseDesc.POWERLOSS, "Busbar"),
            UcdMon(2, ReloadCauseDesc.POWERLOSS, "ECB output"),
            UcdGpi(12, ReloadCauseDesc.CPU),
            UcdGpi(13, ReloadCauseDesc.OVERTEMP),
            UcdGpi(14, ReloadCauseDesc.OVERTEMP),
            UcdGpi(15, ReloadCauseDesc.OVERTEMP),
            UcdGpi(17, ReloadCauseDesc.WATCHDOG),
            UcdGpi(22, ReloadCauseDesc.LEAK_DETECTED, "Rope 2"),
            UcdGpi(23, ReloadCauseDesc.LEAK_DETECTED, "Rope 1"),
            UcdGpi(24, ReloadCauseDesc.RAIL, "CPU"),
            UcdGpi(27, ReloadCauseDesc.RAIL, "TH6"),
            UcdGpi(32, ReloadCauseDesc.POWERLOSS, "ECB enable"),
      ])
      self.cpu.cpld.newComponent(Ucd90320,addr=bus.i2cAddr(0x13))

      port = self.cpu.getPciPort(self.cpu.PCI_PORT_SCD0)
      self.scd = scd = port.newComponent(Scd, addr=port.addr)
      scd.setMsiRearmOffset(0x180)
      scd.addSmbusMasterRange(0x8000, 11, 0x80, 8)

      scd.newComponent(Tmp431, addr=scd.i2cAddr(0, 0x4c), sensors=[
         SensorDesc(diode=0, name='Back center PCB sensor',
                    position=Position.INLET, target=75, overheat=80, critical=90),
         SensorDesc(diode=1, name='TH6 diode 0',
                    position=Position.INLET, target=100, overheat=105, critical=110),
      ])
      scd.newComponent(Tmp431, addr=scd.i2cAddr(1, 0x4c), sensors=[
         SensorDesc(diode=0, name='Front left PCB sensor',
                    position=Position.INLET, target=75, overheat=80, critical=90),
         SensorDesc(diode=1, name='TH6 diode 1',
                    position=Position.INLET, target=100, overheat=105, critical=110),
      ])
      scd.newComponent(Tmp431, addr=scd.i2cAddr(2, 0x4c), sensors=[
         SensorDesc(diode=0, name='Back left PCB sensor',
                    position=Position.INLET, target=75, overheat=80, critical=90),
         SensorDesc(diode=1, name='TH6 diode 2',
                    position=Position.INLET, target=100, overheat=105, critical=110),
      ])

      # TODO: add Psus and ECBs

      # TODO: add VRMs

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

      # TODO: Add windsurf board

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
