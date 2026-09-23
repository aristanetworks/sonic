from ...core.cpu import Cpu
from ...core.fan import FanSlot
from ...core.pci import PciPortDesc, PciRoot
from ...core.utils import incrange

from ...components.cpu.intel.coretemp import Coretemp
from ...components.cpu.intel.pch import PchTemp
from ...components.cpu.rook import (
   LaFanCpld,
   RookCpldPowerCycleOnScFaultQuirk,
   RookCpldRegisters,
   RookStatusLeds,
   RookSysCpld,
   RookSysCpldRegisters,
)
from ...components.dpm.ucd import Ucd90160, UcdGpi, UcdPriority
from ...components.lm73 import Lm73
from ...components.max6658 import Max6658
from ...components.scd import Scd

from ...descs.fan import FanDesc, FanPosition
from ...descs.led import LedDesc, LedColor
from ...descs.rail import RailDesc
from ...descs.sensor import Position, SensorDesc
from ...descs.cause import ReloadCauseDesc

class RookCpu(Cpu):

   PLATFORM = 'rook'

   PCI_PORT_ASIC0 = PciPortDesc(0x1c, 4)
   PCI_PORT_SCD0 = PciPortDesc(0x1c, 0)

   def __init__(self, mgmtBus=15, fanCpldCls=LaFanCpld, hasLmSensor=True,
                hasCpuLeds=True, cpldRegisterCls=RookSysCpldRegisters,
                sysCpldQuirks=None, **kwargs):
      super().__init__(**kwargs)

      self.pciRoot = self.newComponent(PciRoot)

      port = self.pciRoot.rootPort(device=0x1f, func=6)
      port.newComponent(PchTemp, addr=port.addr, sensors=[
         SensorDesc(diode=0, name='PCH temp sensor',
                    position=Position.OTHER, target=65, overheat=75, critical=85),
      ])

      self.newComponent(Coretemp, sensors=[
         SensorDesc(diode=0, name='Physical id 0',
                    position=Position.OTHER, target=82, overheat=95, critical=105),
         SensorDesc(diode=1, name='CPU core0 temp sensor',
                    position=Position.OTHER, target=82, overheat=95, critical=105),
         SensorDesc(diode=2, name='CPU core1 temp sensor',
                    position=Position.OTHER, target=82, overheat=95, critical=105),
      ])

      port = self.pciRoot.rootPort(bus=0xff, device=0x0b, func=3)
      cpld = port.newComponent(Scd, addr=port.addr, registerCls=RookCpldRegisters,
                               quirks=[RookCpldPowerCycleOnScFaultQuirk()])
      self.cpld = cpld

      cpld.addSmbusMasterRange(0x8000, 4, 0x80, 4)
      cpld.newComponent(Max6658, addr=cpld.i2cAddr(0, 0x4c), sensors=[
         SensorDesc(diode=0, name='CPU board temp sensor',
                    position=Position.OTHER, target=70, overheat=80, critical=85),
         SensorDesc(diode=1, name='Back-panel temp sensor',
                    position=Position.OUTLET, target=55, overheat=65, critical=75),
      ])

      fanCpld = cpld.newComponent(fanCpldCls, addr=cpld.i2cAddr(12, 0x60))
      for slotId in incrange(1, fanCpld.FAN_COUNT):
         fanDesc = FanDesc(fanId=slotId, position=FanPosition.INLET)
         ledDesc = LedDesc(name='fan%d' % slotId,
                           colors=[LedColor.RED, LedColor.GREEN, LedColor.OFF])
         self.newComponent(
            FanSlot,
            slotId=slotId,
            led=fanCpld.addFanLed(ledDesc),
            fans=[
               fanCpld.addFan(fanDesc),
            ]
         )

      if hasLmSensor:
         cpld.newComponent(Lm73, addr=cpld.i2cAddr(mgmtBus, 0x48), sensors=[
            SensorDesc(diode=0, name='Front-panel temp sensor',
                       position=Position.OTHER, target=55, overheat=75, critical=85),
         ])

      self.leds = None
      if hasCpuLeds:
         self.leds = cpld.newComponent(RookStatusLeds,
                                       addr=cpld.i2cAddr(mgmtBus, 0x20), leds=[
            LedDesc(name='beacon', colors=['blue']),
            LedDesc(name='fan_status', colors=['green', 'red']),
            LedDesc(name='psu1_status', colors=['green', 'red']),
            LedDesc(name='psu2_status', colors=['green', 'red']),
            LedDesc(name='status', colors=['green', 'red']),
         ])

      cpld.createPowerCycle()

      self.syscpld = cpld.newComponent(RookSysCpld, addr=cpld.i2cAddr(8, 0x23),
                                       registerCls=cpldRegisterCls,
                                       quirks=sysCpldQuirks or [])

   def addCpuDpm(self, addr=None, causes=None, rails=None):
      addr = addr or self.cpuDpmAddr()
      return self.cpld.newComponent(Ucd90160, addr=addr, causes=causes or [
         UcdGpi(2, ReloadCauseDesc.CPU_S3),
         UcdGpi(3, ReloadCauseDesc.OVERTEMP),
         UcdGpi(4, ReloadCauseDesc.CPU_CATERR, priority=UcdPriority.LOW),
         UcdGpi(5, ReloadCauseDesc.NO_FANS),
      ], rails=rails if rails is not None else [
         RailDesc(railId=1, name='1.7V VCCIN', expectedVoltage=1.5),
         RailDesc(railId=2, name='0.6V VTT', expectedVoltage=0.6),
         RailDesc(railId=3, name='1.2V VDDQ', expectedVoltage=1.2),
         RailDesc(railId=4, name='2.5V VPP', expectedVoltage=2.5),
         RailDesc(railId=5, name='1.5V PCH', expectedVoltage=1.5),
         RailDesc(railId=6, name='1.05V COM', expectedVoltage=1.05),
         RailDesc(railId=7, name='1.3V KRHV', expectedVoltage=1.3),
         RailDesc(railId=8, name='1.7V SCFUSE', expectedVoltage=1.7),
         RailDesc(railId=9, name='3.3V TPS54821', expectedVoltage=3.3),
         RailDesc(railId=10, name='5V TPS54821', expectedVoltage=5),
         RailDesc(railId=11, name='1.2V ALW', expectedVoltage=1.2),
         RailDesc(railId=12, name='3.3V ALW', expectedVoltage=3.3),
         RailDesc(railId=13, name='12V Power Cable', expectedVoltage=12),
         RailDesc(railId=14, name='1.2V LAN1', expectedVoltage=1.2),
         RailDesc(railId=15, name='1.2V LAN2', expectedVoltage=1.2),
      ],
         causePriority=UcdPriority.HARDWARE_SECONDARY)

   def cpuDpmAddr(self, addr=0x4e, t=3, **kwargs):
      return self.cpld.i2cAddr(1, addr, t=t, **kwargs)

   def switchDpmAddr(self, addr=0x4e, t=3, **kwargs):
      return self.cpld.i2cAddr(10, addr, t=t, **kwargs)
