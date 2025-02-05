from ..core.fixed import FixedSystem
from ..core.platform import registerPlatform
from ..core.port import PortLayout
from ..core.psu import PsuSlot
from ..core.utils import incrange

from ..components.asic.xgs.trident4 import Trident4
from ..components.dpm.adm1266 import Adm1266, AdmCause
from ..components.psu.delta import DPS1500AB, DPS1600AB, DPS1600CB
from ..components.scd import Scd
from ..components.tmp468 import Tmp468

from ..descs.gpio import GpioDesc
from ..descs.reset import ResetDesc
from ..descs.sensor import Position, SensorDesc
from ..descs.xcvr import Osfp, QsfpDD, Sfp

from .chassis.yuba import Yuba
from .cpu.lorikeet import LorikeetCpu

@registerPlatform()
class BlackhawkTD4(FixedSystem):

   SID = ['BlackhawkT4O']
   SKU = ['DCS-7050PX4-32S']

   CHASSIS = Yuba

   PORTS = PortLayout(
      (Osfp(i) for i in incrange(1, 32)),
      (Sfp(i) for i in incrange(33, 34)),
   )

   def __init__(self):
      super(BlackhawkTD4, self).__init__()

      self.cpu = self.newComponent(LorikeetCpu)
      self.cpu.addCpuDpm()
      self.cpu.cpld.newComponent(Adm1266, addr=self.cpu.switchDpmAddr(), causes=[
         AdmCause(1, AdmCause.OVERTEMP),
         AdmCause(1 << 2, AdmCause.WATCHDOG),
         AdmCause(1 << 3, AdmCause.POWERLOSS, "Both PSUs lost input power"),
         AdmCause(1 << 4, AdmCause.POWERLOSS, "Both PSUs lost DC output power"),
         AdmCause(1 << 5, AdmCause.REBOOT)
      ])

      port = self.cpu.getPciPort(0)
      scd = port.newComponent(Scd, addr=port.addr)
      self.scd = scd

      scd.createWatchdog()

      scd.newComponent(Tmp468, addr=scd.i2cAddr(8, 0x48), sensors=[
         SensorDesc(diode=0, name='Center Rear',
                    position=Position.OTHER, target=69, overheat=75, critical=85),
         SensorDesc(diode=1, name='Switch board middle sensor',
                    position=Position.OTHER, target=55, overheat=65, critical=75),
         SensorDesc(diode=2, name='Switch board left sensor',
                    position=Position.OTHER, target=55, overheat=65, critical=75),
         SensorDesc(diode=3, name='Front-panel temp sensor',
                    position=Position.INLET, target=55, overheat=65, critical=70),
         SensorDesc(diode=6, name='Switch chip diode 1 sensor',
                    position=Position.OTHER, target=95, overheat=101, critical=105),
         SensorDesc(diode=7, name='Switch chip diode 2 sensor',
                    position=Position.OTHER, target=95, overheat=101, critical=105),
      ])

      scd.addSmbusMasterRange(0x8000, 7, 0x80)

      scd.addResets([
         ResetDesc('switch_chip_reset', addr=0x4000, bit=2, auto=False),
         ResetDesc('switch_chip_pcie_reset', addr=0x4000, bit=1, auto=False),
         ResetDesc('security_asic_reset', addr=0x4000, bit=0),
      ])

      scd.addGpios([
         GpioDesc("psu1_present", addr=0x5000, bit=1, ro=True),
         GpioDesc("psu2_present", addr=0x5000, bit=0, ro=True),
         GpioDesc("psu1_status", addr=0x5000, bit=9, ro=True),
         GpioDesc("psu2_status", addr=0x5000, bit=8, ro=True),
         GpioDesc("psu1_ac_status", addr=0x5000, bit=11, ro=True),
         GpioDesc("psu2_ac_status", addr=0x5000, bit=10, ro=True),
      ])

      intrRegs = [
         scd.createInterrupt(addr=0x3000, num=0),
         scd.createInterrupt(addr=0x3030, num=1),
         scd.createInterrupt(addr=0x3060, num=2),
      ]

      scd.addXcvrSlots(
         ports=self.PORTS.getOsfps(),
         addr=0xA010,
         bus=16,
         ledAddr=0x6100,
         ledAddrOffsetFn=lambda x: 0x40,
         intrRegs=intrRegs,
         intrRegIdxFn=lambda xcvrId: 1,
         intrBitFn=lambda xcvrId: xcvrId - 1,
      )

      scd.addXcvrSlots(
         ports=self.PORTS.getSfps(),
         addr=0xA210,
         bus=48,
         ledAddr=0x6900,
         ledAddrOffsetFn=lambda x: 0x40,
      )

      # TODO: Lorikeet DPM component

      for psuId, bus in [(1, 11), (2, 12)]:
         addrFunc=lambda addr, bus=bus: \
                  scd.i2cAddr(bus, addr, t=3, datr=2, datw=3)
         name = "psu%d" % psuId
         scd.newComponent(
            PsuSlot,
            slotId=psuId,
            addrFunc=addrFunc,
            presentGpio=scd.inventory.getGpio("%s_present" % name),
            inputOkGpio=scd.inventory.getGpio("%s_ac_status" % name),
            outputOkGpio=scd.inventory.getGpio("%s_status" % name),
            led=self.cpu.cpld.inventory.getLed("%s" % name),
            psus=[
               DPS1500AB,
               DPS1600AB,
               DPS1600CB,
            ],
         )

      port = self.cpu.getPciPort(1)
      port.newComponent(Trident4, addr=port.addr,
         coreResets=[
            scd.inventory.getReset('switch_chip_reset'),
         ],
         pcieResets=[
            scd.inventory.getReset('switch_chip_pcie_reset'),
         ],
      )

@registerPlatform()
class BlackhawkTD4DD(BlackhawkTD4):
   SID = ['BlackhawkT4DD']
   SKU = ['DCS-7050DX4-32S']

   PORTS = PortLayout(
      (QsfpDD(i) for i in incrange(1, 32)),
      (Sfp(i) for i in incrange(33, 34)),
   )
