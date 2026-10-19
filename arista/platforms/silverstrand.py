from ..core.fixed import FixedSystem
from ..core.hwapi import HwApi
from ..core.utils import incrange
from ..core.port import PortLayout
from ..core.psu import PsuSlot
from ..core.platform import registerPlatform

from ..components.psu.delta import DPS1500AB
from ..components.max6581 import Max6581
from ..components.psu.liteon import PS2242
from ..components.scd import Scd
from ..components.tmp464 import Tmp464
from ..components.asic.xgs.tomahawk4 import Tomahawk4
from ..components.dpm.ucd import Ucd90320, UcdGpi

from ..descs.gpio import GpioDesc
from ..descs.sensor import Position, SensorDesc
from ..descs.reset import ResetDesc
from ..descs.xcvr import Osfp, QsfpDD, Sfp

from .chassis.yuba import Yuba

from .cpu.lorikeet import LorikeetCpu

@registerPlatform()
class SilverstrandP(FixedSystem):

   SID = ['SilverstrandP']
   SKU = ['DCS-7060PX5-64']

   TMP464_UPDATE_HW_API_VERSION = 3

   CHASSIS = Yuba

   PORTS = PortLayout(
      (Osfp(i) for i in incrange(1, 32)),
      (Sfp(i) for i in incrange(33, 34)),
   )

   def __init__(self):
      super(SilverstrandP, self).__init__()

      self.cpu = self.newComponent(LorikeetCpu)
      self.cpu.addCpuDpm()
      self.cpu.cpld.newComponent(Ucd90320, addr=self.cpu.switchDpmAddr(0x11),
         causes=[
            UcdGpi(1, 'overtemp'),
            UcdGpi(3, 'powerloss', 'PSU AC'),
            UcdGpi(4, 'powerloss', 'PSU DC'),
            UcdGpi(5, 'watchdog'),
            UcdGpi(6, 'reboot'),
            UcdGpi(7, 'reboot'),
            UcdGpi(8, 'reboot'),
      ])

      port = self.cpu.getPciPort(0)
      scd = port.newComponent(Scd, addr=port.addr)
      self.scd = scd

      scd.createWatchdog()
      scd.setMsiRearmOffset(0x180)
      scd.addSmbusMasterRange(0x8000, 7, 0x80)

      if self.getHwApi() < HwApi(self.TMP464_UPDATE_HW_API_VERSION):
         scd.newComponent(Max6581, addr=scd.i2cAddr(8, 0x4D), sensors=[
            SensorDesc(diode=0, name='Switch Card',
                        position=Position.OTHER,
                        target=85, overheat=95, critical=105),
            SensorDesc(diode=1, name='Air Exit Behind TH4',
                        position=Position.OUTLET,
                        target=85, overheat=95, critical=105),
            SensorDesc(diode=2, name='Left Edge PCB Near Rear of Switch',
                        position=Position.OTHER,
                        target=85, overheat=95, critical=105),
            SensorDesc(diode=3, name='Air Inlet',
                        position=Position.INLET,
                        target=85, overheat=95, critical=105),
            SensorDesc(diode=6, name='TH4 Diode 1',
                        position=Position.OTHER,
                        target=85, overheat=95, critical=105),
            SensorDesc(diode=7, name='TH4 Diode 2',
                        position=Position.OTHER,
                        target=85, overheat=95, critical=105),
         ])
      else:
         scd.newComponent(Tmp464, addr=scd.i2cAddr(8, 0x48), sensors=[
            SensorDesc(diode=0, name='Switch Card',
                        position=Position.OTHER,
                        target=85, overheat=95, critical=105),
            SensorDesc(diode=1, name='Air Inlet',
                        position=Position.INLET,
                        target=85, overheat=95, critical=105),
            SensorDesc(diode=2, name='PCB Left Exhaust - PSU Inlet',
                        position=Position.OTHER,
                        target=85, overheat=95, critical=105),
            SensorDesc(diode=3, name='TH4 Diode 1',
                        position=Position.OTHER,
                        target=85, overheat=95, critical=105),
            SensorDesc(diode=4, name='TH4 Diode 2',
                        position=Position.OTHER,
                        target=85, overheat=95, critical=105),
         ])

      scd.addResets([
         ResetDesc('switch_chip_reset', addr=0x4000, bit=2, auto=False),
         ResetDesc('switch_chip_pcie_reset', addr=0x4000, bit=3, auto=False),
         ResetDesc('security_asic_reset', addr=0x4000, bit=4),
      ])

      scd.addGpios([
         GpioDesc("psu2_present", 0x5000, 0, ro=True),
         GpioDesc("psu1_present", 0x5000, 1, ro=True),
         GpioDesc("psu2_status", 0x5000, 8, ro=True),
         GpioDesc("psu1_status", 0x5000, 9, ro=True),
         GpioDesc("psu2_ac_status", 0x5000, 10, ro=True),
         GpioDesc("psu1_ac_status", 0x5000, 11, ro=True),
      ])

      intrRegs = [
         scd.createInterrupt(addr=0x3000, num=0),
         scd.createInterrupt(addr=0x3030, num=1),
         scd.createInterrupt(addr=0x3060, num=2),
      ]

      scd.addXcvrSlots(
         ports=self.PORTS.getOsfps(),
         addr=0xA000,
         addrOffset=0x10,
         bus=24,
         ledAddr=0x6100,
         ledAddrOffsetFn=lambda x: 0x10,
         intrRegs=intrRegs,
         intrRegIdxFn=lambda x: 1,
         intrBitFn=lambda xcvrId: xcvrId - 1,
      )

      scd.addXcvrSlots(
         ports=self.PORTS.getSfps(),
         addr=0xA200,
         addrOffset=0x10,
         bus=56,
         ledAddr=0x6900,
         ledAddrOffsetFn=lambda x: 0x40,
         intrRegs=intrRegs,
         intrRegIdxFn=lambda x: 2,
         intrBitFn=lambda xcvrId: xcvrId - 33,
      )

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
            led=self.cpu.cpld.inventory.getLed('%s' % name),
            psus=[
               DPS1500AB,
               PS2242,
            ],
         )

      port = self.cpu.getPciPort(1)
      port.newComponent(Tomahawk4, addr=port.addr,
         coreResets=[
            scd.inventory.getReset('switch_chip_reset'),
         ],
         pcieResets=[
            scd.inventory.getReset('switch_chip_pcie_reset'),
         ],
      )

@registerPlatform()
class SilverstrandDd(SilverstrandP):
   SID = ['SilverstrandDd']
   SKU = ['DCS-7060DX5-64']

   TMP464_UPDATE_HW_API_VERSION = 2

   PORTS = PortLayout(
      (QsfpDD(i) for i in incrange(1, 32)),
      (Sfp(i) for i in incrange(33, 34)),
   )
