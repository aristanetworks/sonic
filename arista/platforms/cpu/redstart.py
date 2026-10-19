from ...core.cpu import Cpu
from ...core.pci import PciRoot
from ...core.utils import incranges

from ...components.cpu.amd.k10temp import K10Temp
from ...components.cpu.redstart import (
    RedstartReloadCauseRegisters,
    RedstartSysCpld,
)
from ...components.scd import Scd, ScdCause

from ...descs.sensor import Position, SensorDesc

class RedstartCpu(Cpu):

   PLATFORM = 'redstart'
   SID = ['Redstart8Mk2']
   SKU = ['DCS-7001-SUP-L']

   def __init__(self, **kwargs):
      super().__init__(**kwargs)

      self.pciRoot = self.newComponent(PciRoot)

      port = self.pciRoot.rootPort(device=0x18, func=3)
      port.newComponent(K10Temp, addr=port.addr, sensors=[
         SensorDesc(diode=0, name='Cpu temp sensor',
                    position=Position.OTHER, target=70, overheat=95, critical=115),
      ])

      port = self.pciRoot.pciBridge(device=0x02, func=1).downstreamPort(0)
      cpld = port.newComponent(Scd, addr=port.addr)
      self.cpld = cpld

      cpld.createPowerCycle()
      cpld.addSmbusMasterRange(0x8000, 1, 0x80, 6)

      self.fanboard = self.parent.CHASSIS.addFanboard(cpld, cpld.getSmbus(9))

      self.syscpld = self.newComponent(RedstartSysCpld, addr=cpld.i2cAddr(6, 0x23))
      self.syscpld.addPowerCycle()

      cpld.addReloadCauseProvider(causes=[
         ScdCause(0x01, ScdCause.OVERTEMP),
         ScdCause(0x08, ScdCause.REBOOT, 'Software Reboot'),
         ScdCause(0x0a, ScdCause.POWERLOSS, 'PSU DC to CPU'),
         ScdCause(0x0c, ScdCause.CPU),
         ScdCause(0x0d, ScdCause.CPU_S3, 'CPU Sleep Mode'),
      ] + [
         ScdCause(v, ScdCause.RAIL) for v in incranges(
            (0x20, 0x24),
            (0x28, 0x2e),
            (0x31, 0x3d),
         )
      ], regmap=RedstartReloadCauseRegisters,
         priority=ScdCause.Priority.SECONDARY)

   def getPciPort(self, num):
      device, func = {
         0: (0x1, 2),
         2: (0x2, 5),
      }[num]
      bridge = self.pciRoot.pciBridge(device=device, func=func)
      return bridge.downstreamPort(port=0)
