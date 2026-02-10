from ...core.cpu import Cpu
from ...core.pci import PciPortDesc, PciRoot

from ...components.cpu.amd.k10temp import K10Temp
from ...components.cpld import (
   SysCpld,
   SysCpldCommonRegistersV2,
)
from ...components.max6658 import Max6658
from ...components.scd import Scd, ScdCause, ScdReloadCauseRegisters

from ...descs.sensor import Position, SensorDesc

class PuffinPrimeSysCpld(SysCpld):
   REGISTER_CLS = SysCpldCommonRegistersV2

class PuffinPrimeCpu(Cpu):

   PLATFORM = 'puffin'

   PCI_PORT_ASIC0 = PciPortDesc(0x01, 3)
   PCI_PORT_SCD0 = PciPortDesc(0x01, 2)

   def __init__(self, registerCls=SysCpldCommonRegistersV2, **kwargs):
      super().__init__(**kwargs)

      self.pciRoot = self.newComponent(PciRoot)

      port = self.pciRoot.rootPort(device=0x18, func=3)
      port.newComponent(K10Temp, addr=port.addr, sensors=[
         SensorDesc(diode=0, name='Cpu temp sensor',
                    position=Position.OTHER, target=70, overheat=95, critical=115),
      ])

      port = self.pciRoot.rootPort(device=0x18, func=7)
      cpld = port.newComponent(Scd, addr=port.addr)
      self.cpld = cpld

      cpld.createInterrupt(addr=0x3000, num=0)

      cpld.createPowerCycle()
      cpld.addSmbusMasterRange(0x8000, 1, 0x80, 4)

      cpld.newComponent(Max6658, addr=cpld.i2cAddr(0, 0x4c), sensors=[
         SensorDesc(diode=0, name='Cpu board temp sensor',
                    position=Position.OTHER, target=55, overheat=75, critical=85),
         SensorDesc(diode=1, name='Back-panel temp sensor',
                    position=Position.OUTLET, target=55, overheat=75, critical=85),
      ])

      cpld.addReloadCauseProvider(causes=[
         ScdCause(0x01, ScdCause.OVERTEMP),
         ScdCause(0x08, ScdCause.REBOOT, 'Software Reboot'),
         ScdCause(0x0a, ScdCause.POWERLOSS, 'PSU DC to CPU'),
         ScdCause(0x0b, ScdCause.NOFANS),
         ScdCause(0x0c, ScdCause.CPU),
         ScdCause(0x0d, ScdCause.CPU_S3),
         ScdCause(0x0e, ScdCause.CPU_S5),
         ScdCause(0x20, ScdCause.RAIL, 'PSU_FAULT'),
         ScdCause(0x21, ScdCause.RAIL, 'apu_pwrok_3v3'),
         ScdCause(0x22, ScdCause.RAIL, 'apu_vddcr_soc'),
         ScdCause(0x23, ScdCause.RAIL, 'apu_vddcr'),
         ScdCause(0x24, ScdCause.RAIL, 'p0v9_vddp'),
         ScdCause(0x25, ScdCause.RAIL, 'p0v6_vtt'),
         ScdCause(0x26, ScdCause.RAIL, 'p1v2_vdd_mem'),
         ScdCause(0x27, ScdCause.RAIL, 'p2v6_vpp_mem'),
         ScdCause(0x28, ScdCause.RAIL, 'pos3v3'),
      ], regmap=ScdReloadCauseRegisters,
         priority=ScdCause.Priority.SECONDARY)

      self.addFanGroup(self.parent.CHASSIS.FAN_SLOTS, self.parent.CHASSIS.FAN_COUNT)

      self.syscpld = cpld.newComponent(PuffinPrimeSysCpld,
                                       addr=cpld.i2cAddr(4, 0x23),
                                       registerCls=registerCls)
      self.syscpld.addPowerCycle()

   def addScdComponents(self, scd, hwmonBus=0):
      pass

   def addFanGroup(self, slots=3, count=2):
      self.cpld.addFanGroup(0x9000, 3, slots, count)
      self.cpld.addFanSlotBlock(slotCount=slots, fanCount=count,
                                skip=self.parent.CHASSIS.IGNORE_FAN_SLOTS)
