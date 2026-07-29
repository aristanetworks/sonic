from ...core.cpu import Cpu
from ...core.pci import PciPortDesc, PciRoot

from ...components.cpu.amd.designware import DesignWareI2cBus
from ...components.cpu.amd.k10temp import K10Temp
from ...components.lm75 import Tmp75

from ...descs.sensor import Position, SensorDesc

class PrairieCpu(Cpu):

   PLATFORM = 'prairie'

   PCI_PORT_ASIC0 = PciPortDesc(0x01, 1)
   PCI_PORT_SCD0 = PciPortDesc(0x18, 7, root=True)

   def __init__(self, tempBus=1, **kwargs):
      super().__init__(**kwargs)

      self.pciRoot = self.newComponent(PciRoot)

      bus = DesignWareI2cBus(tempBus)

      port = self.pciRoot.rootPort(device=0x18, func=3)
      port.newComponent(K10Temp, addr=port.addr, sensors=[
         SensorDesc(diode=0, name='Cpu temp sensor',
                    position=Position.OTHER, target=70, overheat=95, critical=115),
      ])

      self.newComponent(Tmp75, addr=bus.i2cAddr(0x4A), sensors=[
         SensorDesc(diode=0, name='Psu temp sensor',
                    position=Position.INLET, overheat=75, critical=80),
      ])

      self.newComponent(Tmp75, addr=bus.i2cAddr(0x4B), sensors=[
         SensorDesc(diode=0, name='SFP+ connector temp sensor',
                    position=Position.OTHER, overheat=75, critical=80),
      ])

      self.newComponent(Tmp75, addr=bus.i2cAddr(0x4C), sensors=[
         SensorDesc(diode=0, name='MAC external temp sensor',
                    position=Position.OTHER, overheat=75, critical=80),
      ])
