from ...core.cpu import Cpu
from ...core.pci import PciRoot

from ...components.cpu.amd.k10temp import K10Temp
from ...components.cpu.lorikeet import (
    LorikeetCpldRegisters,
    LorikeetPrimeScdReloadCauseRegisters,
    LorikeetSysCpld,
)
from ...components.dpm.adm1266 import Adm1266, AdmCause, AdmPriority
from ...components.max6658 import Max6658
from ...components.scd import Scd, ScdCause

from ...descs.sensor import Position, SensorDesc

class LorikeetCpu(Cpu):

   PLATFORM = 'lorikeet'

   def __init__(self, cpldRegisterCls=LorikeetCpldRegisters, **kwargs):
      super(LorikeetCpu, self).__init__(**kwargs)

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

      cpld.addLeds([
         (0x4000, 'beacon'),
         (0x4010, 'status'),
         (0x4020, 'fan_status'),
         (0x4030, 'psu1'),
         (0x4040, 'psu2'),
      ])

      cpld.createPowerCycle()
      cpld.addSmbusMasterRange(0x8000, 2, 0x80, 4)

      cpld.newComponent(Max6658, addr=cpld.i2cAddr(0, 0x4c), sensors=[
         SensorDesc(diode=0, name='CPU board temp sensor',
                    position=Position.OTHER, target=55, overheat=75, critical=85),
         SensorDesc(diode=1, name='Back-panel temp sensor',
                    position=Position.OUTLET, target=55, overheat=75, critical=85),
      ])

      self.addFanGroup(self.parent.CHASSIS.FAN_SLOTS, self.parent.CHASSIS.FAN_COUNT)

      cpld.addFanSlotBlock(
         slotCount=self.parent.CHASSIS.FAN_SLOTS,
         fanCount=self.parent.CHASSIS.FAN_COUNT,
      )

      self.syscpld = self.newComponent(LorikeetSysCpld, addr=cpld.i2cAddr(4, 0x23),
                                       registerCls=cpldRegisterCls)

      # TODO: Add ISL69247 temp sensors

   def addCpuDpm(self, addr=None, causes=None):
      addr = addr or self.cpuDpmAddr()
      return self.cpld.newComponent(Adm1266, addr=addr, causes=causes or [
         AdmCause(1 << 2, AdmCause.CPU_S5, priority=AdmPriority.LOW),
         AdmCause(1 << 3, AdmCause.CPU_S3, priority=AdmPriority.LOW),
         AdmCause(1 << 4, AdmCause.NOFANS),
         AdmCause(1 << 5, AdmCause.OVERTEMP),
         AdmCause(1 << 6, AdmCause.CPU, priority=AdmPriority.LOW)
      ])

   def cpuDpmAddr(self, addr=0x4f, t=3, **kwargs):
      return self.cpld.i2cAddr(1, addr, t=t, **kwargs)

   def switchDpmAddr(self, addr=0x4f, t=3, **kwargs):
      return self.cpld.i2cAddr(5, addr, t=t, **kwargs)

   def addFanGroup(self, slots=3, count=2):
      self.cpld.addFanGroup(0x9000, 3, slots, count)

   def getPciPort(self, num):
      device, func = {
         0: (0x01, 1),
         1: (0x03, 1),
      }[num]
      bridge = self.pciRoot.pciBridge(device=device, func=func)
      return bridge.downstreamPort(port=0)

class LorikeetPrimeCpu(LorikeetCpu):
   def addCpuDpm(self, addr=None, causes=None):
      self.cpld.addReloadCauseProvider(causes=[
         ScdCause(0x01, ScdCause.OVERTEMP),
         ScdCause(0x08, ScdCause.REBOOT, 'Software Reboot'),
         ScdCause(0x0a, ScdCause.POWERLOSS, 'PSU DC to CPU'),
         ScdCause(0x0b, ScdCause.NOFANS),
         ScdCause(0x0c, ScdCause.CPU),
         ScdCause(0x0d, ScdCause.CPU_S3),
         ScdCause(0x0e, ScdCause.CPU_S5),
         ScdCause(0x20, ScdCause.RAIL, 'CPU_PWROK_3V3'),
         ScdCause(0x21, ScdCause.RAIL, 'POSVDD_CPU_S0'),
         ScdCause(0x22, ScdCause.RAIL, 'POSVDD_SOC_S0'),
         ScdCause(0x23, ScdCause.RAIL, 'POS1V8_S0,POS3V3_S0'),
         ScdCause(0x24, ScdCause.RAIL, 'POS0V6_VTT_MEM'),
         ScdCause(0x25, ScdCause.RAIL, 'POS1V2_VDD_MEM'),
         ScdCause(0x26, ScdCause.RAIL, 'POS2V5_VPP_MEM'),
         ScdCause(0x27, ScdCause.RAIL, 'POS1V8'),
         ScdCause(0x28, ScdCause.RAIL, 'POS0V9'),
         ScdCause(0x29, ScdCause.RAIL, 'ALW_ON_PGOOD'),
         ScdCause(0x2a, ScdCause.RAIL, 'ISL0_CAT_FAULT'),
      ], regmap=LorikeetPrimeScdReloadCauseRegisters,
         priority=ScdCause.Priority.SECONDARY)
