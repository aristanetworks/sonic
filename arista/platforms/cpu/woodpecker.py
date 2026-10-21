from ...core.cpu import Cpu
from ...core.pci import PciPortDesc, PciRoot

from ...components.cpu.amd.k10temp import K10Temp
from ...components.dpm.ucd import Ucd90160, UcdGpi, UcdPriority
from ...components.max6658 import Max6658
from ...components.scd import (
   BlackBoxRegisterMap,
   Scd,
   ScdBlackBox,
   ScdSpiController,
)

from ...descs.sensor import Position, SensorDesc
from ...descs.cause import ReloadCauseDesc, ReloadCauseAltSource
from ...descs.rail import RailDesc

class WoodpeckerCpu(Cpu):

   PLATFORM = 'woodpecker'

   PCI_PORT_ASIC0 = PciPortDesc(0x03, 1)
   PCI_PORT_ASIC1 = PciPortDesc(0x03, 2)
   PCI_PORT_SCD0 = PciPortDesc(0x02, 3)
   PCI_PORT_SCD1 = PciPortDesc(0x02, 2)

   def __init__(self, **kwargs):
      super().__init__(**kwargs)

      self.pciRoot = self.newComponent(PciRoot)

      port = self.pciRoot.rootPort(device=0x18, func=3)
      port.newComponent(K10Temp, addr=port.addr, sensors=[
         SensorDesc(diode=0, name='Cpu temp sensor',
                    position=Position.OTHER, target=70, overheat=95, critical=115),
      ])

      port = self.pciRoot.rootPort(device=0x09)
      cpld = port.newComponent(Scd, addr=port.addr)
      self.cpld = cpld

      self.addFanGroup(self.parent.CHASSIS.FAN_SLOTS, self.parent.CHASSIS.FAN_COUNT)

      cpld.addSmbusMasterRange(0x8000, 2, 0x80, 4)
      cpld.newComponent(Max6658, addr=cpld.i2cAddr(0, 0x4c), sensors=[
         SensorDesc(diode=0, name='CPU board temp sensor',
                    position=Position.OTHER, target=55, overheat=75, critical=85),
         SensorDesc(diode=1, name='Back-panel temp sensor',
                    position=Position.OUTLET, target=55, overheat=75, critical=85),
      ])

      cpld.createPowerCycle()

      bbCtrl = cpld.newComponent(
         ScdSpiController,
         addr=0x1100,
         stride=0x100,
         numCs=2,
      )

      bbCtrl.newComponent(
         ScdBlackBox,
         addr=bbCtrl.spiAddr(cs=1),
         ctrl=BlackBoxRegisterMap(cpld.driver, cmd=0x1100),
      )

   def addCpuDpm(self, addr=None, causes=None, rails=None):
      addr = addr or self.cpuDpmAddr()
      if rails is None:
         rails = [
            RailDesc(railId=1, name='12V', expectedVoltage=12),
            RailDesc(railId=2, name='5V ALW', expectedVoltage=5),
            RailDesc(railId=3, name='3.3V ALW', expectedVoltage=3.3),
            RailDesc(railId=4, name='1.8V ALW', expectedVoltage=1.8),
            RailDesc(railId=5, name='1.5V ALW', expectedVoltage=1.5),
            RailDesc(railId=6, name='1.2V ALW', expectedVoltage=1.2),
            RailDesc(railId=7, name='1.05V VDDP ALW', expectedVoltage=1.05),
            RailDesc(railId=8, name='0.775V VDDFCH ALW', expectedVoltage=0.775),
            RailDesc(railId=9, name='1.2V TPS51716', expectedVoltage=1.2),
            RailDesc(railId=10, name='2.5V TPS82130', expectedVoltage=2.5),
            RailDesc(railId=11, name='0.6V TPS51716', expectedVoltage=0.6),
            RailDesc(railId=12, name='1.05V TPS543B20', expectedVoltage=1.05),
            RailDesc(railId=13, name='1.2V LAN', expectedVoltage=1.2),
            RailDesc(railId=14, name='1.65V APU VDD CORE', expectedVoltage=1.65),
            RailDesc(railId=15, name='1.65V APU VDD NB', expectedVoltage=1.65),
            RailDesc(railId=16, name='1.65V APU VDD GFX', expectedVoltage=1.65),
         ]
      return self.cpld.newComponent(Ucd90160, addr=addr, causes=causes or [
         UcdGpi(5, ReloadCauseDesc.NO_FANS),
         UcdGpi(6, ReloadCauseDesc.OVERTEMP),
         UcdGpi(7, ReloadCauseDesc.CPU, priority=UcdPriority.LOW),
      ], rails=rails,
         causePriority=UcdPriority.HARDWARE_SECONDARY,
         altSource=[ReloadCauseAltSource.CPU])

   def cpuDpmAddr(self, addr=0x4e, t=3, **kwargs):
      return self.cpld.i2cAddr(1, addr, t=t, **kwargs)

   def switchDpmAddr(self, addr=0x11, t=3, **kwargs):
      return self.cpld.i2cAddr(5, addr, t=t, **kwargs)

   def addFanGroup(self, slots=3, count=2):
      self.cpld.addFanGroup(0x9000, 3, slots, count)
      self.cpld.addFanSlotBlock(slotCount=slots, fanCount=count,
                                skip=self.parent.CHASSIS.IGNORE_FAN_SLOTS)
