from ..core.fixed import FixedSystem
from ..core.platform import registerPlatform
from ..core.port import PortLayout
from ..core.psu import PsuSlot
from ..core.utils import incrange

from ..components.asic.xgs.trident3 import Trident3
from ..components.dpm.ucd import Ucd90320, UcdGpi
from ..components.psu.delta import DPS500AB
from ..components.psu.artesyn import CSU500DP
from ..components.scd import Scd
from ..components.tmp464 import Tmp464

from ..descs.gpio import GpioDesc
from ..descs.reset import ResetDesc
from ..descs.sensor import Position, SensorDesc
from ..descs.xcvr import Qsfp28, Sfp, Sfp28

from .chassis.yuba import Yuba
from .cpu.woodpecker import WoodpeckerCpu

@registerPlatform()
class Marysville(FixedSystem):

   SID = ['Marysville']
   SKU = ['DCS-7050SX3-48YC8']

   CHASSIS = Yuba

   PORTS = PortLayout(
      (Sfp28(i) for i in incrange(1, 48)),
      (Qsfp28(i, leds=4) for i in incrange(49, 56)),
   )

   def __init__(self):
      super(Marysville, self).__init__()

      self.cpu = self.newComponent(WoodpeckerCpu)
      self.cpu.addCpuDpm()
      self.cpu.cpld.newComponent(Ucd90320, addr=self.cpu.switchDpmAddr(), causes={
         'powerloss': UcdGpi(1),
         'reboot': UcdGpi(3),
         'watchdog': UcdGpi(4),
         'overtemp': UcdGpi(6),
         'cpu': UcdGpi(7),
      })

      port = self.cpu.getPciPort(0)
      scd = port.newComponent(Scd, addr=port.addr)

      scd.createWatchdog()

      scd.newComponent(Tmp464, addr=scd.i2cAddr(2, 0x48), sensors=[
         SensorDesc(diode=0, name='Switch Card temp sensor', position=Position.OTHER,
                    target=85, overheat=100, critical=110),
         SensorDesc(diode=1, name='Front-panel temp sensor', position=Position.INLET,
                    target=60, overheat=65, critical=75),
         SensorDesc(diode=2, name='Front PCB temp sensor', position=Position.OTHER,
                    target=70, overheat=75, critical=80),
      ])

      scd.addSmbusMasterRange(0x8000, 7, 0x80)

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
         GpioDesc("psu1_status", 0x5000, 8, ro=True),
         GpioDesc("psu2_status", 0x5000, 9, ro=True),
         GpioDesc("psu1_ac_status", 0x5000, 10, ro=True),
         GpioDesc("psu2_ac_status", 0x5000, 11, ro=True),
      ])

      for psuId in incrange(1, 2):
         addrFunc = lambda addr, i=psuId: \
               scd.i2cAddr(-1 + i, addr, t=3, datr=3, datw=3)
         name = "psu%d" % psuId
         scd.newComponent(
            PsuSlot,
            slotId=psuId,
            addrFunc=addrFunc,
            presentGpio=scd.inventory.getGpio("%s_present" % name),
            inputOkGpio=scd.inventory.getGpio("%s_ac_status" % name),
            outputOkGpio=scd.inventory.getGpio("%s_status" % name),
            led=scd.inventory.getLed('%s' % name),
            psus=[
               DPS500AB,
               CSU500DP,
            ],
         )

      intrRegs = [
         scd.createInterrupt(addr=0x3000, num=0),
         scd.createInterrupt(addr=0x3030, num=1),
         scd.createInterrupt(addr=0x3060, num=2),
      ]

      scd.addXcvrSlots(
         ports=self.PORTS.getSfps(),
         addr=0xA000,
         bus=8,
         ledAddr=0x6100,
         intrRegs=intrRegs,
         intrRegIdxFn=lambda xcvrId: xcvrId // 33 + 1,
         intrBitFn=lambda xcvrId: (xcvrId - 1) % 32,
      )

      scd.addXcvrSlots(
         ports=self.PORTS.getQsfps(),
         addr=0xA300,
         bus=56,
         ledAddr=0x6400,
         intrRegs=intrRegs,
         intrRegIdxFn=lambda xcvrId: 2,
         intrBitFn=lambda xcvrId: xcvrId - 33,
         isHwLpModeAvail=False,
      )

      port = self.cpu.getPciPort(1)
      port.newComponent(Trident3, addr=port.addr,
         coreResets=[
            scd.inventory.getReset('switch_chip_reset'),
         ],
         pcieResets=[
            scd.inventory.getReset('switch_chip_pcie_reset'),
         ],
      )

@registerPlatform()
class Marysville10(Marysville):
   SID = ['Marysville10']
   SKU = ['DCS-7050SX3-48C8']

   PORTS = PortLayout(
      (Sfp(i) for i in incrange(1, 48)),
      (Qsfp28(i, leds=4) for i in incrange(49, 56)),
   )
