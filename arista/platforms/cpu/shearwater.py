from ...components.cpu.amd.k10temp import K10Temp
from ...components.cpu.shearwater import (
    ShearwaterReloadCauseRegisters,
    ShearwaterSysCpld,
)
from ...components.lm75 import Tmp75
from ...components.scd import Scd, ScdCause

from ...core.cpu import Cpu
from ...core.pci import PciRoot

from ...descs.sensor import Position, SensorDesc

class ShearwaterCpu(Cpu):

   PLATFORM = 'shearwater'
   SID = ['ShearwaterMk2', 'ShearwaterMk2N']
   SKU = ['DCS-7001-SUP-A', 'DCS-7001-SUP-A-N']

   def __init__(self, **kwargs):
      super(ShearwaterCpu, self).__init__(**kwargs)

      self.pciRoot = self.newComponent(PciRoot)

      port = self.pciRoot.rootPort(device=0x18, func=3)
      port.newComponent(K10Temp, addr=port.addr, sensors=[
         SensorDesc(diode=0, name='Cpu temp sensor',
                    position=Position.OTHER, target=70, overheat=95, critical=115),
      ])

      port = self.pciRoot.rootPort(device=0x18, func=7)
      cpld = port.newComponent(Scd, addr=port.addr)
      self.cpld = cpld

      cpld.createPowerCycle()
      cpld.addSmbusMasterRange(0x8000, 1, 0x80, 4)
      cpld.newComponent(Tmp75, addr=cpld.i2cAddr(0, 0x48), sensors=[
         SensorDesc(diode=0, name='Ambient',
                    position=Position.OUTLET, target=55, overheat=75, critical=85),
      ])

      self.fanboard = self.parent.CHASSIS.addFanboard(cpld, cpld.getSmbus(7))

      # TODO: cleanup syscpld declaration accross platforms
      self.syscpld = self.newComponent(ShearwaterSysCpld, addr=cpld.i2cAddr(4, 0x23))
      self.syscpld.addPowerCycle()

      cpld.addReloadCauseProvider(causes=[
         ScdCause(0x01, ScdCause.OVERTEMP),
         ScdCause(0x08, ScdCause.REBOOT, 'Software Reboot'),
         ScdCause(0x0a, ScdCause.POWERLOSS, 'PSU DC to CPU'),
         ScdCause(0x0c, ScdCause.CPU),
         ScdCause(0x0d, ScdCause.CPU_S3),
         ScdCause(0x0e, ScdCause.CPU_S5),
         ScdCause(0x11, ScdCause.CPU, 'Unexpected PCIe reset'),
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
      ], regmap=ShearwaterReloadCauseRegisters,
         priority=ScdCause.Priority.SECONDARY)

   def getPciPort(self, num):
      device, func = {
         0: (0x3, 5),
         2: (0x1, 3),
      }[num]
      bridge = self.pciRoot.pciBridge(device=device, func=func)
      return bridge.downstreamPort(port=0)
