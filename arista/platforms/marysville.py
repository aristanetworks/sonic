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

from ..components.asic.xgs.trident3 import Trident3
from ..components.cpld import SysCpldCause, SysCpldReloadCauseRegistersV2
from ..components.dpm.ucd import Ucd90320, UcdGpi
from ..components.max6658 import Max6658
from ..components.psu.delta import DPS500AB
from ..components.psu.artesyn import CSU500DP
from ..components.scd import Scd
from ..components.tmp464 import Tmp464

from ..descs.cause import ReloadCauseDesc
from ..descs.gpio import GpioDesc
from ..descs.reset import ResetDesc
from ..descs.sensor import Position, SensorDesc
from ..descs.xcvr import Qsfp28, Sfp, Sfp28

from .chassis.yuba import Yuba
from .cpu.puffin import PuffinPrimeCpu
from .cpu.woodpecker import WoodpeckerCpu


class MarysvilleBase(FixedSystem):
   CHASSIS = Yuba
   SYSCPLD_REGMAP_CLS = None
   PORTS = PortLayout(
      (Sfp28(i) for i in incrange(1, 48)),
      (Qsfp28(i, leds=4) for i in incrange(49, 56)),
   )

   def __init__(self):
      super().__init__()
      if self.SYSCPLD_REGMAP_CLS is not None:
         self.cpu = self.newComponent(self.CPU_CLS,
                                      registerCls=self.SYSCPLD_REGMAP_CLS)
      else:
         self.cpu = self.newComponent(self.CPU_CLS)
      port = self.cpu.getPciPort(self.cpu.PCI_PORT_SCD0)
      self.scd = port.newComponent(Scd, addr=port.addr)
      scd = self.scd

      scd.createWatchdog()
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

      port = self.cpu.getPciPort(self.cpu.PCI_PORT_ASIC0)
      port.newComponent(Trident3, addr=port.addr,
         coreResets=[
            scd.inventory.getReset('switch_chip_reset'),
         ],
         pcieResets=[
            scd.inventory.getReset('switch_chip_pcie_reset'),
         ],
      )

@registerPlatform()
class Marysville(MarysvilleBase):

   SID = ['Marysville']
   SKU = ['DCS-7050SX3-48YC8']
   CPU_CLS = WoodpeckerCpu

   def __init__(self):
      super().__init__()

      self.cpu.addCpuDpm()
      self.cpu.cpld.newComponent(Ucd90320, addr=self.cpu.switchDpmAddr(),
         causes=[
            UcdGpi(1, ReloadCauseDesc.POWERLOSS),
            UcdGpi(3, ReloadCauseDesc.REBOOT),
            UcdGpi(4, ReloadCauseDesc.WATCHDOG),
            UcdGpi(6, ReloadCauseDesc.OVERTEMP),
            UcdGpi(7, ReloadCauseDesc.CPU),
      ])

      self.scd.newComponent(Tmp464, addr=self.scd.i2cAddr(2, 0x48), sensors=[
         SensorDesc(diode=0, name='Switch Card temp sensor', position=Position.OTHER,
                    target=85, overheat=100, critical=110),
         SensorDesc(diode=1, name='Front-panel temp sensor', position=Position.INLET,
                    target=60, overheat=65, critical=75),
         SensorDesc(diode=2, name='Front PCB temp sensor', position=Position.OTHER,
                    target=70, overheat=75, critical=80),
      ])

@registerPlatform()
class Marysville10(Marysville):
   SID = ['Marysville10']
   SKU = ['DCS-7050SX3-48C8']

   PORTS = PortLayout(
      (Sfp(i) for i in incrange(1, 48)),
      (Qsfp28(i, leds=4) for i in incrange(49, 56)),
   )

class MarysvillPrimeSysCpldRegisters(RegisterMap):
   MINOR = Register(0x00, name='revisionMinor')
   REVISION = Register(0x01, name='revision')
   SCRATCHPAD = Register(0x02, name='scratchpad', ro=False)

   PWR_CTRL_STATUS = Register(0x05,
      RegBitField(7, 'dpPower', ro=False),
      RegBitField(1, 'cpPowerGood'),
      RegBitField(0, 'switchCardPowerGood'),
   )

   SCD_CTRL_STS = Register(0x0A,
      RegBitField(6, 'scdInitDone'),
      RegBitField(5, 'scdReset', ro=False),
      RegBitField(4, 'scdHold', ro=False),
      RegBitField(0, 'scdConfDone'),
   )

   PWR_CYC_EN = Register(0x11,
      RegBitField(2, 'powerCycleOnCrc', ro=False),
   )

@registerPlatform()
class MarsvillePrime(MarysvilleBase):
   SID = ['MarsvillePrime']
   SKU = ['DCS-7050SX3-48YC8C']
   CPU_CLS = PuffinPrimeCpu
   SYSCPLD_REGMAP_CLS = MarysvillPrimeSysCpldRegisters

   def __init__(self):
      super().__init__()

      self.scd.newComponent(Max6658, addr=self.scd.i2cAddr(2, 0x4c), sensors=[
         SensorDesc(diode=0, name='Switch Card temp sensor', position=Position.OTHER,
                    target=85, overheat=100, critical=110),
      ])

      syscpld = self.cpu.syscpld
      syscpld.addReloadCauseProvider(causes=[
         SysCpldCause(0x00, SysCpldCause.UNKNOWN),
         SysCpldCause(0x01, SysCpldCause.OVERTEMP),
         SysCpldCause(0x02, SysCpldCause.SEU),
         SysCpldCause(0x03, SysCpldCause.WATCHDOG,
                      priority=SysCpldCause.Priority.HIGH),
         SysCpldCause(0x04, SysCpldCause.CPU,
                      priority=SysCpldCause.Priority.LOW),
         SysCpldCause(0x05, SysCpldCause.RAIL, "PWR_OK_SW_CP Fault"),
         SysCpldCause(0x08, SysCpldCause.REBOOT, "Software Reboot"),
         SysCpldCause(0x09, SysCpldCause.POWERLOSS, "PSU AC"),
         SysCpldCause(0x0a, SysCpldCause.POWERLOSS, "PSU DC"),
         SysCpldCause(0x0b, SysCpldCause.NOFANS),
         SysCpldCause(0x0c, SysCpldCause.CPU, "CPU_CAT_ERR"),
         SysCpldCause(0x0d, SysCpldCause.CPU_S3),
         SysCpldCause(0x0e, SysCpldCause.CPU_S5),
         SysCpldCause(0x0f, SysCpldCause.SEU, "BitShadow RX parity Error"),
         SysCpldCause(0x20, SysCpldCause.RAIL, "POS1V0 FAULT"),
         SysCpldCause(0x21, SysCpldCause.RAIL, "POS1V2 FAULT"),
         SysCpldCause(0x22, SysCpldCause.RAIL, "POS1V8 FAULT"),
         SysCpldCause(0x23, SysCpldCause.RAIL, "POS3V3 FAULT"),
         SysCpldCause(0x24, SysCpldCause.RAIL, "POS5V0 FAULT"),
         SysCpldCause(0x25, SysCpldCause.RAIL, "POS0V9_C FAULT"),
         SysCpldCause(0x26, SysCpldCause.RAIL, "POS1V2_TD FAULT"),
         SysCpldCause(0x27, SysCpldCause.RAIL, "POS1V8_TD FAULT"),
         SysCpldCause(0x28, SysCpldCause.RAIL, "POS0V8_A FAULT"),
         SysCpldCause(0x28, SysCpldCause.RAIL, "POS3V3_OPTICS FAULT"),
      ], regmap=SysCpldReloadCauseRegistersV2)
