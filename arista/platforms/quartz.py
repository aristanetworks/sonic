from ..core.fixed import FixedSystem
from ..core.platform import registerPlatform
from ..core.port import PortLayout
from ..core.psu import PsuSlot
from ..core.utils import incrange

from ..components.asic.dnx.jericho2c import Jericho2cPlus
from ..components.dpm.ucd import Ucd90320, UcdGpi
from ..components.psu.liteon import PS2242
from ..components.scd import Scd
from ..components.tmp464 import Tmp464

from ..descs.cause import ReloadCauseDesc
from ..descs.gpio import GpioDesc
from ..descs.reset import ResetDesc
from ..descs.sensor import Position, SensorDesc
from ..descs.xcvr import Osfp, QsfpDD

from .chassis.tuba import Tuba

from .cpu.cormorant import CormorantCpu

@registerPlatform()
class QuartzDd(FixedSystem):
   SID = ["QuartzDd"]
   SKU = ["DCS-7280DR3A-36"]
   CHASSIS = Tuba

   PORTS = PortLayout(
      (QsfpDD(i) for i in incrange(1, 36)),
      (Osfp(i) for i in incrange(37, 38))
   )

   def __init__(self):
      super(QuartzDd, self).__init__()

      self.cpu = self.newComponent(CormorantCpu)
      self.cpu.addCpuDpm()

      self.cpu.cpld.newComponent(Ucd90320, addr=self.cpu.switchDpmAddr(0x11),
         causes=[
            UcdGpi(3, ReloadCauseDesc.POWERLOSS),
            UcdGpi(4, ReloadCauseDesc.REBOOT),
            UcdGpi(5, ReloadCauseDesc.WATCHDOG),
            UcdGpi(6, ReloadCauseDesc.OVERTEMP),
            UcdGpi(8, ReloadCauseDesc.CPU),
      ])

      port = self.cpu.getPciPort(0)
      scd = port.newComponent(Scd, addr=port.addr)

      scd.createWatchdog()
      scd.setMsiRearmOffset(0x180)
      scd.addSmbusMasterRange(0x8000, 6, 0x80)

      scd.newComponent(Tmp464, addr=scd.i2cAddr(7, 0x48), sensors=[
            SensorDesc(diode=0, name='JE0 Front Side', position=Position.OTHER,
                       target=60, overheat=62, critical=65),
            SensorDesc(diode=1, name='Air Inlet', position=Position.INLET,
                       target=60, overheat=62, critical=65),
            SensorDesc(diode=2, name='Board Temp', position=Position.OTHER,
                       target=55, overheat=60, critical=65),
            SensorDesc(diode=3, name='JE1_C Diode', position=Position.OTHER,
                       target=80, overheat=100, critical=105),
            SensorDesc(diode=4, name='JE0_C Diode', position=Position.OTHER,
                       target=80, overheat=100, critical=105),
      ])

      scd.addLeds([
         (0x6050, 'status'),
         (0x6060, 'fan_status'),
         (0x6070, 'psu1'),
         (0x6080, 'psu2'),
         (0x6090, 'beacon'),
      ])

      scd.addResets([
         ResetDesc('switch_chip0_pcie_reset', addr=0x4000, bit=0, auto=False),
         ResetDesc('switch_chip0_reset', addr=0x4000, bit=1, auto=False),
         ResetDesc('switch_chip1_pcie_reset', addr=0x4000, bit=2, auto=False),
         ResetDesc('switch_chip1_reset', addr=0x4000, bit=3, auto=False),
      ])

      scd.addGpios([
         GpioDesc("psu1_present", 0x5000, 0, ro=True),
         GpioDesc("psu2_present", 0x5000, 1, ro=True),
         GpioDesc("psu1_status", 0x5000, 8, ro=True),
         GpioDesc("psu2_status", 0x5000, 9, ro=True),
         GpioDesc("psu1_ac_status", 0x5000, 10, ro=True),
         GpioDesc("psu2_ac_status", 0x5000, 11, ro=True),

         GpioDesc("psu1_present_changed", 0x5000, 16),
         GpioDesc("psu2_present_changed", 0x5000, 17),
         GpioDesc("psu1_status_changed", 0x5000, 18),
         GpioDesc("psu2_status_changed", 0x5000, 19),
         GpioDesc("psu1_ac_status_changed", 0x5000, 20),
         GpioDesc("psu2_ac_status_changed", 0x5000, 21),
      ])

      for psuId in incrange(1, 2):
         addrFunc=lambda addr, i=psuId: \
               scd.i2cAddr(i - 1, addr, t=3, datr=3, datw=3)
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
               PS2242,
            ],
         )

      intrRegs = [
         scd.createInterrupt(addr=0x3000, num=0),
         scd.createInterrupt(addr=0x3030, num=1),
         scd.createInterrupt(addr=0x3060, num=2),
         scd.createInterrupt(addr=0x3090, num=3),
      ]

      scd.addXcvrSlots(
         ports=self.PORTS.getOsfps(),
         addr=0xA010,
         bus=8,
         ledAddr=0x6100,
         intrRegs=intrRegs,
         intrRegIdxFn=lambda xcvrId: 2 + (xcvrId - 1) // 32,
         intrBitFn=lambda xcvrId: (xcvrId - 1) % 32,
      )

      port = self.cpu.getPciPort(1)
      self.je0 = port.newComponent(Jericho2cPlus, addr=port.addr,
         coreResets=[
            scd.inventory.getReset('switch_chip0_reset'),
         ],
         pcieResets=[
            scd.inventory.getReset('switch_chip0_pcie_reset'),
         ],
      )
      port = self.cpu.getPciPort(2)
      self.je1 = port.newComponent(Jericho2cPlus, addr=port.addr,
         coreResets=[
            scd.inventory.getReset('switch_chip1_reset'),
         ],
         pcieResets=[
            scd.inventory.getReset('switch_chip1_pcie_reset'),
         ],
      )

@registerPlatform()
class QuartzDdBK(QuartzDd):
   SID = ['QuartzDdBK']
   SKU = ['DCS-7280DR3AK-36']

@registerPlatform()
class QuartzDdBKS(QuartzDdBK):
   SID = ['QuartzDdBKS']
   SKU = ['DCS-7280DR3AK-36S']

   PORTS = PortLayout(
      (QsfpDD(i) for i in incrange(1, 36))
   )

@registerPlatform()
class QuartzDdMs(QuartzDd):
   SID = ['QuartzDdMs']
   SKU = ['DCS-7280DR3AM-36']
