from ..core.fixed import FixedSystem
from ..core.platform import registerPlatform
from ..core.port import PortLayout
from ..core.psu import PsuSlot
from ..core.utils import incrange

from ..components.asic.xgs.tomahawk5 import Tomahawk5
from ..components.cpld import SysCpldReloadCauseRegistersV2, SysCpldCause
from ..components.psu.delta import ECD1502008
from ..components.scd import Scd
from ..components.lm75 import Tmp75

from ..descs.gpio import GpioDesc
from ..descs.reset import ResetDesc
from ..descs.sensor import Position, SensorDesc
from ..descs.xcvr import Osfp, Sfp

from .chassis.yuba import Yuba
from .cpu.skylark import SkylarkCpu

class MorandaBase(FixedSystem):

   CHASSIS = Yuba
   CPU_CLS = SkylarkCpu

   def __init__(self):
      super().__init__()

      self.cpu = self.newComponent(self.CPU_CLS)
      self.syscpld = self.cpu.syscpld

      port = self.cpu.getPciPort(0)
      scd = port.newComponent(Scd, addr=port.addr)
      self.scd = scd
      #scd.setMsiRearmOffset(0x180)
      scd.createWatchdog()
      # Moranda SCD has 0-5 SMBus master
      scd.addSmbusMasterRange(0x8000, 6, 0x80)

      scd.newComponent(Tmp75, addr=scd.i2cAddr(0, 0x48), sensors=[
         SensorDesc(diode=0, name='Inlet Ambient Air',
                    position=Position.INLET, target=55, overheat=65, critical=70),
         #SensorDesc(diode=1, name='ASIC',
         #           position=Position.INLET, target=95, overheat=105, critical=115),
      ])

      scd.addLeds([
         (0x6050, 'status'),
         (0x6060, 'fan_status'),
         (0x6070, 'psu1'),
         (0x6080, 'psu2'),
         (0x6090, 'beacon'),
      ])

      scd.addResets([
         ResetDesc('switch_chip_pcie_reset', addr=0x4000, bit=1, auto=False),
         ResetDesc('switch_chip_reset', addr=0x4000, bit=0, auto=False),
      ])

      intrRegs = [
         scd.createInterrupt(addr=0x3000, num=0),
         scd.createInterrupt(addr=0x3030, num=1),
         scd.createInterrupt(addr=0x3060, num=2),
         scd.createInterrupt(addr=0x3090, num=3),
      ]

      scd.addXcvrSlots(
         ports=self.PORTS.getOsfps(),
         addr=0xA000,
         bus=24,
         ledAddr=0x6100,
         intrRegs=intrRegs,
         intrRegIdxFn=lambda xcvrId: 1,
         intrBitFn=lambda xcvrId: xcvrId - 1,
      )

      scd.addXcvrSlots(
         ports=self.PORTS.getSfps(),
         addr=0xA200,
         bus=24,
         ledAddr=0x6300,
         intrRegs=intrRegs,
         intrRegIdxFn=lambda xcvrId: 2,
         intrBitFn=lambda xcvrId: (xcvrId - 1) % 32,
      )

      scd.addGpios([
         GpioDesc("psu1_present", 0x5000, 0, ro=True),
         GpioDesc("psu2_present", 0x5000, 1, ro=True),
         GpioDesc("psu1_status", 0x5000, 8, ro=True),
         GpioDesc("psu2_status", 0x5000, 9, ro=True),
         GpioDesc("psu1_ac_status", 0x5000, 10, ro=True),
         GpioDesc("psu2_ac_status", 0x5000, 11, ro=True),
      ])

      for psuId in incrange(1, 2):
         addrFunc=lambda addr, i=psuId: \
                  self.scd.i2cAddr(2+(i-1), addr, t=3, datr=2, datw=3)
         name = "psu%d" % psuId
         self.scd.newComponent(
            PsuSlot,
            slotId=psuId,
            addrFunc=addrFunc,
            presentGpio=self.scd.inventory.getGpio("%s_present" % name),
            inputOkGpio=self.scd.inventory.getGpio("%s_ac_status" % name),
            outputOkGpio=self.scd.inventory.getGpio("%s_status" % name),
            led=self.scd.inventory.getLed("%s" % name),
            psus=[ ECD1502008 ],
         )

      port = self.cpu.getPciPort(2)
      port.newComponent(Tomahawk5, addr=port.addr,
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
      ], regmap=SysCpldReloadCauseRegistersV2)

@registerPlatform()
class MorandaP(MorandaBase):
   SID = ['MorandaP']
   SKU = ['DCS-7060X6-32PE']

   PORTS = PortLayout(
      (Osfp(i) for i in incrange(1, 32)),
      (Sfp(i) for i in incrange(33, 34)),
   )

@registerPlatform()
class MorandaDd(MorandaBase):
   SID = ['MorandaDD']
   SKU = ['DCS-7060X6-32DE']
