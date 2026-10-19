from ..core.fixed import FixedSystem
from ..core.platform import registerPlatform
from ..core.port import PortLayout
from ..core.psu import PsuSlot
from ..core.register import (
   Register,
   RegisterMap,
   RegBitField,
)
from ..core.utils import incrange

from ..components.asic.xgs.tomahawk4 import Tomahawk4
from ..components.cpld import SysCpldCause, SysCpldReloadCauseRegistersV2
from ..components.max6581 import Max6581
from ..components.psu.delta import DPS1500AB, DPS1600AB, DPS1600CB
from ..components.scd import Scd

from ..descs.gpio import GpioDesc
from ..descs.reset import ResetDesc
from ..descs.sensor import Position, SensorDesc
from ..descs.xcvr import QsfpDD, Sfp

from .chassis.yuba import Yuba
from .cpu.lorikeet import LorikeetPrimeCpu

class BlackhawkTH4CpldRegisters(RegisterMap):
   MINOR = Register(0x00, name='revisionMinor')
   REVISION = Register(0x01, name='revision')
   SCRATCHPAD = Register(0x02, name='scratchpad', ro=False)

   PWR_CTRL_STS = Register(0x05,
      RegBitField(7, 'dpPower', ro=False),
      RegBitField(0, 'switchCardPowerGood'),
   )
   SCD_CTRL_STS = Register(0x0A,
      RegBitField(5, 'scdReset', ro=False),
      RegBitField(1, 'scdInitDone'),
      RegBitField(0, 'scdConfDone'),
   )
   PWR_CYC_EN = Register(0x11,
      RegBitField(2, 'powerCycleOnCrc', ro=False),
   )
   RT_FAULT_0 = Register(0x46,
      RegBitField(2, 'scdCrcError'),
   )

@registerPlatform()
class BlackhawkTH4DD(FixedSystem):

   SID = ['BlackhawkTH4DD']
   SKU = ['DCS-7060DX5-32']

   CHASSIS = Yuba

   PORTS = PortLayout(
      (QsfpDD(i) for i in incrange(1, 32)),
      (Sfp(i) for i in incrange(33, 33)),
   )

   def __init__(self):
      super(BlackhawkTH4DD, self).__init__()

      self.cpu = self.newComponent(LorikeetPrimeCpu,
                                   cpldRegisterCls=BlackhawkTH4CpldRegisters)
      self.cpu.addCpuDpm()
      self.syscpld = self.cpu.syscpld

      port = self.cpu.getPciPort(0)
      scd = port.newComponent(Scd, addr=port.addr)
      self.scd = scd

      scd.createWatchdog()
      scd.addSmbusMasterRange(0x8000, 6, 0x80)

      scd.newComponent(Max6581, addr=scd.i2cAddr(8, 0x4d), sensors=[
         SensorDesc(diode=0, name='Center Rear',
                    position=Position.OTHER, target=85, overheat=100, critical=105),
         SensorDesc(diode=1, name='Switch board right sensor',
                    position=Position.OUTLET, target=55, overheat=65, critical=75),
         SensorDesc(diode=2, name='Switch board left sensor',
                    position=Position.OUTLET, target=55, overheat=65, critical=75),
         SensorDesc(diode=3, name='Front-panel temp sensor',
                    position=Position.INLET, target=55, overheat=65, critical=70),
         SensorDesc(diode=6, name='Switch chip diode 1 sensor',
                    position=Position.OTHER, target=90, overheat=100, critical=105),
         SensorDesc(diode=7, name='Switch chip diode 2 sensor',
                    position=Position.OTHER, target=90, overheat=100, critical=105),
      ])

      scd.addResets([
         ResetDesc('switch_chip_reset', addr=0x4000, bit=2, auto=False),
         ResetDesc('switch_chip_pcie_reset', addr=0x4000, bit=1, auto=False),
         ResetDesc('security_asic_reset', addr=0x4000, bit=0),
      ])

      scd.addGpios([
         GpioDesc("psu1_present", addr=0x5000, bit=0, ro=True),
         GpioDesc("psu2_present", addr=0x5000, bit=1, ro=True),
         GpioDesc("psu1_status", addr=0x5000, bit=8, ro=True),
         GpioDesc("psu2_status", addr=0x5000, bit=9, ro=True),
         GpioDesc("psu1_ac_status", addr=0x5000, bit=10, ro=True),
         GpioDesc("psu2_ac_status", addr=0x5000, bit=11, ro=True),
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
         bus=50,
         ledAddr=0x6900,
         ledAddrOffsetFn=lambda x: 0x40,
         intrRegs=intrRegs,
         intrRegIdxFn=lambda xcvrId: 2,
         intrBitFn=lambda xcvrId: xcvrId - 33,
      )

      for psuId, bus in [(1, 12), (2, 11)]:
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
      port.newComponent(Tomahawk4, addr=port.addr,
         coreResets=[
            scd.inventory.getReset('switch_chip_reset'),
         ],
         pcieResets=[
            scd.inventory.getReset('switch_chip_pcie_reset'),
         ],
      )

      self.syscpld.addReloadCauseProvider(causes=[
         SysCpldCause(0x00, SysCpldCause.UNKNOWN),
         SysCpldCause(0x01, SysCpldCause.OVERTEMP),
         SysCpldCause(0x02, SysCpldCause.SEU),
         SysCpldCause(0x03, SysCpldCause.WATCHDOG,
                      priority=SysCpldCause.Priority.HIGH),
         SysCpldCause(0x04, SysCpldCause.CPU, 'CPU source or CPU PGOOD',
                      priority=SysCpldCause.Priority.LOW),
         SysCpldCause(0x08, SysCpldCause.REBOOT),
         SysCpldCause(0x09, SysCpldCause.POWERLOSS, 'PSU AC'),
         SysCpldCause(0x0a, SysCpldCause.POWERLOSS, 'PSU DC'),
         SysCpldCause(0x0f, SysCpldCause.SEU, 'bitshadow rx parity error'),
         #TODO rails
      ], regmap=SysCpldReloadCauseRegistersV2)
