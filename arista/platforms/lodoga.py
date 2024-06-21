from ..core.fixed import FixedSystem
from ..core.platform import registerPlatform
from ..core.port import PortLayout
from ..core.psu import PsuSlot
from ..core.register import Register, RegBitField
from ..core.utils import incrange

from ..components.asic.xgs.trident3 import Trident3
from ..components.cpld import (
   SysCpldCause,
   SysCpldCommonRegistersV2,
   SysCpldReloadCauseRegistersV2,
)
from ..components.dpm.ucd import Ucd90120A, UcdGpi
from ..components.max6658 import Max6658
from ..components.psu.delta import DPS495CB, DPS500AB
from ..components.psu.artesyn import DS495SPE
from ..components.scd import Scd

from ..descs.gpio import GpioDesc
from ..descs.reset import ResetDesc
from ..descs.sensor import Position, SensorDesc
from ..descs.xcvr import Qsfp28, Sfp

from .chassis.yuba import Yuba

from .cpu.crow import CrowCpu, CrowCpldRegisters
from .cpu.puffin import PuffinPrimeCpu

class LodogaCpldRegisters(CrowCpldRegisters):
   FAULT_CTRL = Register(0x17,
       RegBitField(2, 'powerCycleOnCrc', ro=False),
   )
   FAULT_STATUS = Register(0x19,
       RegBitField(6, 'scdSeuError'),
   )

class LodogaPrimeChassis(Yuba):
   FAN_SLOTS = 2

class LodogaPrimeCpldRegisters(SysCpldCommonRegistersV2):
   pass

class LodogaBase(FixedSystem):

   PORTS = PortLayout(
      (Qsfp28(i, leds=4) for i in incrange(1, 32)),
      (Sfp(i) for i in incrange(33, 34)),
   )

   def __init__(self, cpuCls, syscpldRegisters):
      super().__init__()

      cpu = self.newComponent(cpuCls, registerCls=syscpldRegisters)
      self.cpu = cpu
      self.syscpld = cpu.syscpld

      port = cpu.getPciPort(self.SCD_PCI_PORT_IDX)
      scd = port.newComponent(Scd, addr=port.addr)
      self.scd = scd

      self.cpu.addScdComponents(scd)

      scd.createWatchdog()

      addrs = self.SmBusAddresses
      scd.newComponent(Max6658,
                    addr=scd.i2cAddr(addrs.TS, 0x4c), sensors=[
         SensorDesc(diode=0, name='Board temp sensor',
                    position=Position.OTHER, target=65, overheat=75, critical=85),
         SensorDesc(diode=1, name='Front-panel temp sensor',
                    position=Position.INLET, target=50, overheat=60, critical=65),
      ])

      scd.addSmbusMasterRange(0x8000, 6, 0x80)

      self.addPlatformComponents()

      scd.addResets([
         ResetDesc('switch_chip_reset', addr=0x4000, bit=1, auto=False),
         ResetDesc('switch_chip_pcie_reset', addr=0x4000, bit=2, auto=False)
      ])

      scd.addGpios([
         GpioDesc("psu1_present", 0x5000, addrs.PSU1_PRSNT, ro=True),
         GpioDesc("psu2_present", 0x5000, addrs.PSU2_PRSNT, ro=True),
         GpioDesc("psu1_status", 0x5000, addrs.PSU1_OK, ro=True),
         GpioDesc("psu2_status", 0x5000, addrs.PSU2_OK, ro=True),
         GpioDesc("psu1_ac_status", 0x5000, addrs.PSU1_ACOK, ro=True),
         GpioDesc("psu2_ac_status", 0x5000, addrs.PSU2_ACOK, ro=True),
      ])

      psuLedDev = scd if isinstance(self.cpu, CrowCpu) else self.cpu.cpld
      for psuId in incrange(1, 2):
         addrFunc=lambda addr, i=psuId: \
                  scd.i2cAddr(addrs.PSU + i, addr, t=3, datr=2, datw=3)
         name = "psu%d" % psuId
         scd.newComponent(
            PsuSlot,
            slotId=psuId,
            addrFunc=addrFunc,
            presentGpio=scd.inventory.getGpio("%s_present" % name),
            inputOkGpio=scd.inventory.getGpio("%s_ac_status" % name),
            outputOkGpio=scd.inventory.getGpio("%s_status" % name),
            led=psuLedDev.inventory.getLed(name),
            psus=self.PSU_CLS,
         )

      intrRegs = [
         scd.createInterrupt(addr=0x3000, num=0),
         scd.createInterrupt(addr=0x3030, num=1),
      ]

      scd.addXcvrSlots(
         ports=self.PORTS.getSfps(),
         addr=0xA010,
         bus=addrs.SFP,
         ledAddr=0x6120,
         intrRegs=intrRegs,
         intrRegIdxFn=lambda xcvrId: 0,
         intrBitFn=lambda xcvrId: 28 + xcvrId - 33
      )

      scd.addXcvrSlots(
         ports=self.PORTS.getQsfps(),
         addr=0xA050,
         bus=addrs.QSFP,
         ledAddr=0x6140,
         intrRegs=intrRegs,
         intrRegIdxFn=lambda xcvrId: 1,
         intrBitFn=lambda xcvrId: xcvrId - 1,
         isHwLpModeAvail=False
      )

      port = cpu.getPciPort(self.SWITCH_CHIPSET_PCI_PORT_IDX)
      port.newComponent(Trident3, addr=port.addr,
         coreResets=[
            scd.inventory.getReset('switch_chip_reset'),
         ],
         pcieResets=[
            scd.inventory.getReset('switch_chip_pcie_reset'),
         ],
      )

   def addPlatformComponents(self):
      pass

@registerPlatform()
class Lodoga(LodogaBase):

   SID = ['Lodoga', 'LodogaSsd']
   SKU = ['DCS-7050CX3-32S', 'DCS-7050CX3-32S-SSD']
   PSU_CLS = [DPS495CB, DS495SPE]
   SCD_PCI_PORT_IDX = 1
   SWITCH_CHIPSET_PCI_PORT_IDX = 0

   class SmBusAddresses(object):
      TS  = 9
      PSU = 10
      PSU1_PRSNT = 1
      PSU2_PRSNT = 0
      PSU1_OK = 9
      PSU2_OK = 8
      PSU1_ACOK = 11
      PSU2_ACOK = 10
      SFP = 16
      QSFP = 24

   def __init__(self):
      super().__init__(CrowCpu, LodogaCpldRegisters)

   def addPlatformComponents(self):
      self.scd.newComponent(Ucd90120A, addr=self.scd.i2cAddr(0, 0x4e, t=3))
      self.scd.addLeds([
         (0x6050, 'status'),
         (0x6060, 'fan_status'),
         (0x6070, 'psu1'),
         (0x6080, 'psu2'),
         (0x6090, 'beacon'),
      ])
      self.scd.newComponent(Ucd90120A, addr=self.scd.i2cAddr(13, 0x4e, t=3), causes=[
         UcdGpi(1, 'reboot'),
         UcdGpi(2, 'watchdog'),
         UcdGpi(4, 'overtemp'),
         UcdGpi(5, 'powerloss', 'PSU AC'),
         UcdGpi(6, 'powerloss', 'PSU DC'),
      ])

@registerPlatform()
class LodogaPrime(LodogaBase):

   SID = ['LodogaPrime']
   SKU = ['DCS-7050CX3-32C']

   CHASSIS = LodogaPrimeChassis
   PSU_CLS = [DPS500AB]
   SCD_PCI_PORT_IDX = 0
   SWITCH_CHIPSET_PCI_PORT_IDX = 1

   class SmBusAddresses(object):
      TS  = 0
      PSU = 0
      PSU1_PRSNT = 0
      PSU2_PRSNT = 1
      PSU1_OK = 8
      PSU2_OK = 9
      PSU1_ACOK = 10
      PSU2_ACOK = 11
      SFP = 8
      QSFP = 16

   def __init__(self):
      super().__init__(PuffinPrimeCpu, LodogaPrimeCpldRegisters)

   def addPlatformComponents(self):
      self.syscpld.addReloadCauseProvider(causes=[
         SysCpldCause(0x00, SysCpldCause.UNKNOWN),
         SysCpldCause(0x01, SysCpldCause.OVERTEMP),
         SysCpldCause(0x02, SysCpldCause.SEU),
         SysCpldCause(0x03, SysCpldCause.WATCHDOG,
                      priority=SysCpldCause.Priority.HIGH),
         SysCpldCause(0x04, SysCpldCause.CPU, 'CPU source or CPU PGOOD',
                      priority=SysCpldCause.Priority.LOW),
         SysCpldCause(0x08, SysCpldCause.REBOOT, 'Software Reboot'),
         SysCpldCause(0x09, SysCpldCause.POWERLOSS, 'PSU AC'),
         SysCpldCause(0x0a, SysCpldCause.POWERLOSS, 'PSU DC'),
      ], regmap=SysCpldReloadCauseRegistersV2)
