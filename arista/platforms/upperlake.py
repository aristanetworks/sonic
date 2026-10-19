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
from ..components.dpm.ucd import Ucd90120A, UcdGpi
from ..components.max6697 import Max6697
from ..components.psu.delta import DPS495CB, DPS750AB
from ..components.psu.artesyn import DS495SPE
from ..components.scd import Scd

from ..descs.gpio import GpioDesc
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

      port = cpu.getPciPort(1)
      scd = port.newComponent(Scd, addr=port.addr)
      self.scd = scd

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

      scd.addSmbusMasterRange(0x8000, 5, 0x80)

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
         GpioDesc("psu1_present", 0x5000, 0, ro=True),
         GpioDesc("psu2_present", 0x5000, 1, ro=True),
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

      port = cpu.getPciPort(0)
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
      self.scd.newComponent(Ucd90120A, addr=self.scd.i2cAddr(1, 0x4e, t=3))

   def configureSwitchDpm(self):
      self.scd.newComponent(Ucd90120A, addr=self.scd.i2cAddr(5, 0x4e, t=3), causes={
         'reboot': UcdGpi(1),
         'watchdog': UcdGpi(2),
         'overtemp': UcdGpi(4),
         'powerloss': UcdGpi(5),
      })

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
      self.syscpld.addReloadCauseProvider(causes=[
         SysCpldCause(0x00, 'unknown'),
         SysCpldCause(0x01, 'reboot'),
         SysCpldCause(0x02, 'watchdog'),
         SysCpldCause(0x03, 'powerloss', 'PSU AC'),
         SysCpldCause(0x04, 'overtemp'),
         SysCpldCause(0x06, 'powerloss', 'PSU DC'),
         SysCpldCause(0x08, 'rail', 'POS5V_STANDBY'),
         SysCpldCause(0x09, 'rail', 'POS3V3'),
         SysCpldCause(0x0a, 'rail', 'POS1V8'),
         SysCpldCause(0x0b, 'rail', 'POS1V25'),
         SysCpldCause(0x0c, 'rail', 'POS1V0_CORE'),
         SysCpldCause(0x0d, 'rail', 'POS3V3_QSFP'),
         SysCpldCause(0x0e, 'rail', 'POS1V0A'),
         SysCpldCause(0x0f, 'rail', 'POS1V2'),
         SysCpldCause(0x10, 'rail', 'POS2V5'),
      ])
