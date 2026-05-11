from ...core.cpu import Cpu
from ...core.fan import FanSlot
from ...core.pci import PciPortDesc, PciRoot
from ...core.utils import incrange

from ...components.cpu.amd.k10temp import K10Temp
from ...components.cpu.amd.piix import PiixI2cBus
from ...components.cpu.crow import (
   CrowCpldRegisters,
   CrowFanCpld,
   CrowSysCpld,
)
from ...components.dpm.ucd import Ucd90120A, UcdGpi
from ...components.max6658 import Max6658

from ...descs.fan import FanDesc, FanPosition
from ...descs.led import LedDesc, LedColor
from ...descs.sensor import Position, SensorDesc
from ...core.filters.ratelimit import RateLimitFilter

class CrowCpu(Cpu):

   PLATFORM = 'crow'

   PCI_PORT_ASIC0 = PciPortDesc(0x02, 1)
   PCI_PORT_SCD0 = PciPortDesc(0x02, 2)

   def __init__(self, registerCls=CrowCpldRegisters, sysCpldCls=CrowSysCpld,
                **kwargs):
      super(CrowCpu, self).__init__(**kwargs)

      self.pciRoot = self.newComponent(PciRoot)

      port = self.pciRoot.rootPort(device=0x18, func=3)
      port.newComponent(K10Temp, addr=port.addr, sensors=[
         SensorDesc(diode=0, name='Cpu temp sensor',
                    position=Position.OTHER, target=60, overheat=90, critical=95,
                    readFilter=RateLimitFilter(9.5)),
      ])

      bus = PiixI2cBus(1, 0x0b20)
      self.syscpld = self.newComponent(sysCpldCls, addr=bus.i2cAddr(0x23),
                                       registerCls=registerCls)
      self.syscpld.addPowerCycle()

   def addScdComponents(self, scd, hwmonBus=0):
      scd.newComponent(Max6658, addr=scd.i2cAddr(hwmonBus, 0x4c), sensors=[
         SensorDesc(diode=0, name='Cpu board temp sensor',
                    position=Position.OTHER, target=55, overheat=75, critical=80),
         SensorDesc(diode=1, name='Back-panel temp sensor',
                    position=Position.OUTLET, target=50, overheat=75, critical=85),
      ])

      cpld = scd.newComponent(CrowFanCpld, addr=scd.i2cAddr(hwmonBus, 0x60))
      for slotId in incrange(1, 4):
         fanDesc = FanDesc(fanId=slotId, position=FanPosition.INLET)
         ledDesc = LedDesc(name='fan%d' % slotId,
                           colors=[LedColor.RED, LedColor.GREEN, LedColor.OFF])
         self.newComponent(
            FanSlot,
            slotId=slotId,
            led=cpld.addFanLed(ledDesc),
            fans=[
               cpld.addFan(fanDesc),
            ]
         )

   def addCpuDpm(self, scd, i2cBus):
      scd.newComponent(Ucd90120A, addr=scd.i2cAddr(i2cBus, 0x4e, t=3), causes={
         'cpu-s5': UcdGpi(1),
         'cpu-s3': UcdGpi(2),
      })
