from ...core.cpu import Cpu
from ...core.pci import PciRoot

from ...components.cpu.amd.k10temp import K10Temp
from ...components.cpld import (
   SysCpld,
   SysCpldCommonRegistersV2,
)
from ...components.lm75 import Tmp75
from ...components.scd import Scd, ScdCause, ScdReloadCauseRegisters

from ...descs.sensor import Position, SensorDesc

class SkylarkSysCpld(SysCpld):
   REGISTER_CLS = SysCpldCommonRegistersV2

class SkylarkCpu(Cpu):

   PLATFORM = 'skylark'

   def __init__(self, registerCls=SysCpldCommonRegistersV2, **kwargs):
      super().__init__(**kwargs)

      self.pciRoot = self.newComponent(PciRoot)

      port = self.pciRoot.rootPort(device=0x18, func=3)
      port.newComponent(K10Temp, addr=port.addr, sensors=[
         SensorDesc(diode=0, name='Cpu temp sensor',
                    position=Position.OTHER, target=70, overheat=95, critical=115),
      ])

      bridge = self.pciRoot.pciBridge(device=0x02, func=1)
      port = bridge.downstreamPort(port=0)
      #port = self.pciRoot.rootPort(bus=0x4, device=0, func=0)
      cpld = port.newComponent(Scd, addr=port.addr)
      self.cpld = cpld

      cpld.createPowerCycle()
      cpld.addSmbusMasterRange(0x8000, 1, 0x80, 4)
      cpld.createInterrupt(addr=0x3000, num=0)

      #cpld.addLeds([
      #   (0x4000, 'beacon'),
      #   (0x4010, 'system_status'),
      #   (0x4020, 'fan_status'),
      #   (0x4030, 'psu1'),
      #   (0x4040, 'psu2'),
      #])

      cpld.newComponent(Tmp75, addr=cpld.i2cAddr(0, 0x48), sensors=[
         SensorDesc(diode=0, name='Cpu board temp sensor',
                    position=Position.OTHER, target=55, overheat=75, critical=85),
         #SensorDesc(diode=1, name='Back-panel temp sensor',
         #           position=Position.OUTLET, target=55, overheat=75, critical=85),
      ])

      cpld.addReloadCauseProvider(causes=[
         ScdCause(0x01, ScdCause.OVERTEMP),
         ScdCause(0x08, ScdCause.REBOOT, 'Software Reboot'),
         ScdCause(0x0a, ScdCause.POWERLOSS, 'PSU DC to CPU'),
         ScdCause(0x0b, ScdCause.NOFANS),
         ScdCause(0x0c, ScdCause.CPU),
         ScdCause(0x0d, ScdCause.CPU_S3),
         ScdCause(0x0e, ScdCause.CPU_S5),
         ScdCause(0x20, ScdCause.RAIL, 'VR_VDDCR'),
         ScdCause(0x21, ScdCause.RAIL, 'VR_VDDSOC'),
         ScdCause(0x22, ScdCause.RAIL, 'DDR5_UDIMM2'),
         ScdCause(0x23, ScdCause.RAIL, 'DDR5_UDIMM1'),
         ScdCause(0x24, ScdCause.RAIL, 'P1V8_CPU'),
         ScdCause(0x28, ScdCause.RAIL, 'P3V3_CPU'),
         ScdCause(0x29, ScdCause.RAIL, 'P3V3_REGMII'),
         ScdCause(0x2a, ScdCause.RAIL, 'POS1V1_MEM'),
         ScdCause(0x2b, ScdCause.RAIL, 'POS0V78_MEM'),
         ScdCause(0x2c, ScdCause.RAIL, 'POSSV_ALW'),
         ScdCause(0x2d, ScdCause.RAIL, 'POS1V8_BMC'),
         ScdCause(0x2e, ScdCause.RAIL, 'POS1V0_BMC'),
         ScdCause(0x31, ScdCause.RAIL, 'POS1V2_BMC'),
         ScdCause(0x32, ScdCause.RAIL, 'POS2V5_BMC'),
         ScdCause(0x33, ScdCause.RAIL, 'POS0V75_CPU'),
         ScdCause(0x34, ScdCause.RAIL, 'POS1V8_ALW'),
         ScdCause(0x35, ScdCause.RAIL, 'POS1V0_MSW'),
         ScdCause(0x36, ScdCause.RAIL, 'POS1V2'),
         ScdCause(0x37, ScdCause.RAIL, 'POS2V5_CPLD'),
         ScdCause(0x38, ScdCause.RAIL, 'POS0V75_ALW'),
         ScdCause(0x39, ScdCause.RAIL, 'POS0V96_I226'),
         ScdCause(0x3a, ScdCause.RAIL, 'APU_PWROK'),
         ScdCause(0x3b, ScdCause.RAIL, 'POS3V3_ALW'),
         ScdCause(0x3c, ScdCause.RAIL, 'CPUError'),
         ScdCause(0x3d, ScdCause.RAIL, 'BMC pgood'),
      ], regmap=ScdReloadCauseRegisters,
         priority=ScdCause.Priority.SECONDARY)

      self.addFanGroup(self.parent.CHASSIS.FAN_SLOTS, self.parent.CHASSIS.FAN_COUNT)

      self.syscpld = self.newComponent(SkylarkSysCpld,
                                       addr=cpld.i2cAddr(4, 0x23),
                                       registerCls=registerCls)
      self.syscpld.addPowerCycle()

   def addScdComponents(self, scd, hwmonBus=0):
      pass

   def getPciPort(self, num):
      device, func = {
         0: (0x02, 4),
         2: (0x01, 1),
      }[num]
      bridge = self.pciRoot.pciBridge(device=device, func=func)
      return bridge.downstreamPort(port=0)

   def addFanGroup(self, slots=3, count=2):
      self.cpld.addFanGroup(0x9000, 3, slots, count)
      self.cpld.addFanSlotBlock(slotCount=slots, fanCount=count)
