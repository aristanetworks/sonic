from ..core.cause import ReloadCausePriority
from ..core.hwapi import HwApi
from ..core.fixed import FixedSystem
from ..core.platform import registerPlatform
from ..core.port import PortLayout
from ..core.psu import PsuSlot
from ..core.quirk import PciConfigQuirk
from ..core.utils import incrange

from ..components.asic.xgs.tomahawk import Tomahawk
from ..components.cpld import SysCpldCause
from ..components.cpu.crow import KoiCpldRegisters, KoiSysCpld
from ..components.dpm.ucd import Ucd90120A, UcdGpi, UcdPriority
from ..components.max6697 import Max6697
from ..components.psu.delta import DPS495CB, DPS750AB
from ..components.psu.artesyn import DS495SPE
from ..components.scd import Scd

from ..descs.cause import ReloadCauseDesc
from ..descs.gpio import GpioDesc
from ..descs.rail import RailDesc
from ..descs.reset import ResetDesc
from ..descs.sensor import Position, SensorDesc
from ..descs.xcvr import Qsfp28, Sfp

from .cpu.crow import CrowCpu

@registerPlatform()
class Upperlake(FixedSystem):

   SID = ['Upperlake', 'UpperlakeES', 'UpperlakeSsd']
   SKU = ['DCS-7060CX-32S', 'DCS-7060CX-32S-ES', 'DCS-7060CX-32S-SSD']

   PORTS = PortLayout(
      (Qsfp28(i, leds=4) for i in incrange(1, 32)),
      (Sfp(i) for i in incrange(33, 34)),
   )

   def __init__(self):
      super(Upperlake, self).__init__()

      cpu = self.newComponent(CrowCpu, registerCls=KoiCpldRegisters,
                              sysCpldCls=KoiSysCpld)
      self.cpu = cpu
      self.syscpld = cpu.syscpld

      port = cpu.getPciPort(self.cpu.PCI_PORT_SCD0)
      scd = port.newComponent(Scd, addr=port.addr)
      self.scd = scd

      scd.addSmbusMasterRange(0x8000, 5, 0x80)

      self.cpu.addScdComponents(scd, hwmonBus=1)

      scd.createWatchdog()

      scd.newComponent(Max6697, addr=scd.i2cAddr(0, 0x1a), sensors=[
         SensorDesc(diode=0, name='Board sensor',
                    position=Position.OTHER, target=55, overheat=65, critical=75),
         SensorDesc(diode=1, name='Switch chip left sensor',
                    position=Position.OTHER, target=55, overheat=95, critical=105),
         SensorDesc(diode=5, name='Switch chip right sensor',
                    position=Position.OTHER, target=55, overheat=95, critical=105),
         SensorDesc(diode=6, name='Front-panel temp sensor',
                    position=Position.INLET, target=55, overheat=65, critical=75),
      ])

      self.configureCpuDpm()
      self.configureSwitchDpm()

      scd.addLeds([
         (0x6050, 'status'),
         (0x6060, 'fan_status'),
         (0x6070, 'psu1'),
         (0x6080, 'psu2'),
         (0x6090, 'beacon'),
      ])

      scd.addResets([
         ResetDesc('switch_chip_reset', addr=0x4000, bit=1, auto=False),
         ResetDesc('switch_chip_pcie_reset', addr=0x4000, bit=2, auto=False)
      ])

      scd.addGpios([
         GpioDesc("psu1_present", 0x5000, 1, ro=True),
         GpioDesc("psu2_present", 0x5000, 0, ro=True),
      ])

      self.syscpld.addGpios([
         ('psu1DcOk', 'psu1_status'),
         ('psu2DcOk', 'psu2_status'),
         ('psu1AcOk', 'psu1_ac_status'),
         ('psu2AcOk', 'psu2_ac_status'),
      ])

      for psuId, bus in [(1, 4), (2, 3)]:
         addrFunc=lambda addr, bus=bus: \
                  scd.i2cAddr(bus, addr, t=3, datr=2, datw=3)
         name = "psu%d" % psuId
         scd.newComponent(
            PsuSlot,
            slotId=psuId,
            addrFunc=addrFunc,
            presentGpio=scd.inventory.getGpio("%s_present" % name),
            inputOkGpio=self.syscpld.inventory.getGpio("%s_ac_status" % name),
            outputOkGpio=self.syscpld.inventory.getGpio("%s_status" % name),
            led=scd.inventory.getLed(name),
            psus=[
               DPS495CB,
               DPS750AB,
               DS495SPE,
            ],
         )

      intrRegs = [
         scd.createInterrupt(addr=0x3000, num=0),
         scd.createInterrupt(addr=0x3030, num=1),
      ]

      scd.addXcvrSlots(
         ports=self.PORTS.getSfps(),
         addr=0x5010,
         bus=8,
         ledAddr=0x6100,
      )

      scd.addXcvrSlots(
         ports=self.PORTS.getQsfps(),
         addr=0x5050,
         bus=16,
         ledAddr=0x6140,
         intrRegs=intrRegs,
         intrRegIdxFn=lambda xcvrId: 1,
         intrBitFn=lambda xcvrId: xcvrId - 1,
         isHwLpModeAvail=False,
      )

      port = cpu.getPciPort(self.cpu.PCI_PORT_ASIC0)
      port.newComponent(Tomahawk, addr=port.addr,
         coreResets=[
            scd.inventory.getReset('switch_chip_reset'),
         ],
         pcieResets=[
            scd.inventory.getReset('switch_chip_pcie_reset'),
         ],
         quirks=[
            PciConfigQuirk(port.pciAddr(func=0), 'CAP_EXP+0x28.B=6',
                           'Set max pcie timeout to 210ms'),
            PciConfigQuirk(port.pciAddr(func=1), 'CAP_EXP+0x28.B=6',
                           'Set max pcie timeout to 210ms'),
         ],
      )

   def configureCpuDpm(self):
      self.cpu.addCpuDpm(self.scd, 1)

   def configureSwitchDpm(self):
      self.scd.newComponent(Ucd90120A, addr=self.scd.i2cAddr(5, 0x4e, t=3), causes=[
         UcdGpi(1, ReloadCauseDesc.REBOOT),
         UcdGpi(2, ReloadCauseDesc.WATCHDOG),
         UcdGpi(3, ReloadCauseDesc.SEU, 'SCD SEU ERROR'),
         UcdGpi(4, ReloadCauseDesc.OVERTEMP),
         UcdGpi(5, ReloadCauseDesc.POWERLOSS),
         UcdGpi(8, ReloadCauseDesc.SEU, 'CPLD SEU ERROR'),
      ], rails=[
         RailDesc(railId=1, name='12V System rail'),
         RailDesc(railId=2, name='12V Standby'),
         RailDesc(railId=3, name='5V Stanbdy'),
         RailDesc(railId=4, name='3.3V Standby'),
         RailDesc(railId=5, name='3.3V'),
         RailDesc(railId=6, name='3.3V Ports'),
         RailDesc(railId=7, name='2.5V'),
         RailDesc(railId=8, name='1.8V'),
         RailDesc(railId=9, name='1.25V'),
         RailDesc(railId=10, name='1.2V'),
         RailDesc(railId=11, name='1V Tomahawk core'),
         RailDesc(railId=12, name='1V Tomahawk analog'),
      ], causePriority=UcdPriority.HARDWARE_MAIN)

@registerPlatform()
class UpperlakePlus(Upperlake):
   SID = ['UpperlakePlus']
   SKU = ['DCS-7060CX2-32S']

@registerPlatform()
class UpperlakeElite(Upperlake):
   SID = ['UpperlakeElite']
   SKU = ['DCS-7060CX-32C']

   def configureCpuDpm(self):
      if self.getHwApi() < HwApi(2):
         super().configureCpuDpm()

   def configureSwitchDpm(self):
      causes = [
         SysCpldCause(0x00, ReloadCauseDesc.UNKNOWN),
         SysCpldCause(0x01, ReloadCauseDesc.REBOOT),
         SysCpldCause(0x02, ReloadCauseDesc.WATCHDOG),
         SysCpldCause(0x03, ReloadCauseDesc.POWERLOSS, 'PSU AC'),
         SysCpldCause(0x04, ReloadCauseDesc.OVERTEMP),
         SysCpldCause(0x05, ReloadCauseDesc.SEU, 'SCD SEU ERROR'),
         SysCpldCause(0x06, ReloadCauseDesc.POWERLOSS, 'PSU DC'),
         SysCpldCause(0x07, ReloadCauseDesc.SEU, 'CPLD SEU ERROR'),
         SysCpldCause(0x08, ReloadCauseDesc.RAIL, 'POS5V_STANDBY'),
         SysCpldCause(0x09, ReloadCauseDesc.RAIL, 'POS3V3'),
         SysCpldCause(0x0a, ReloadCauseDesc.RAIL, 'POS1V8'),
         SysCpldCause(0x0b, ReloadCauseDesc.RAIL, 'POS1V25'),
         SysCpldCause(0x0c, ReloadCauseDesc.RAIL, 'POS1V0_CORE'),
         SysCpldCause(0x0d, ReloadCauseDesc.RAIL, 'POS3V3_QSFP'),
         SysCpldCause(0x0e, ReloadCauseDesc.RAIL, 'POS1V0A'),
         SysCpldCause(0x0f, ReloadCauseDesc.RAIL, 'POS1V2'),
         SysCpldCause(0x10, ReloadCauseDesc.RAIL, 'POS2V5'),
      ]
      if self.getHwApi() >= HwApi(2):
         causes.append(SysCpldCause(0x11, ReloadCauseDesc.POWERLOSS, 'CPU'))
      self.syscpld.addReloadCauseProvider(
         causes=causes,
         priority=ReloadCausePriority.HARDWARE_MAIN,
      )
