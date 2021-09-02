from ...core.cpu import Cpu
from ...core.register import Register, RegisterMap
from ...core.types import PciAddr

from ...components.cpu.amd.k10temp import K10Temp
from ...components.scd import Scd
from ...components.watchdog import FakeWatchdog

from ...descs.sensor import SensorDesc, Position

class HedgehogCpuCpld(RegisterMap):
   REVISION = Register(0x10, name='revision')
   SCRATCHPAD = Register(0x20, name='scratchpad', ro=False)
   SLOT_ID = Register(0x30, name='slotId')
   PROVISION = Register(0x50, name='provision')

class HedgehogCpu(Cpu):

   PLATFORM = 'hedgehog'

   def __init__(self, slot, **kwargs):
      super(HedgehogCpu, self).__init__(**kwargs)
      self.slot = slot
      self.syscpld = self.newComponent(Scd, addr=PciAddr(device=0x18, func=7),
                                       registerCls=HedgehogCpuCpld)
      self.newComponent(K10Temp, addr=PciAddr(device=0x18, func=3), sensors=[
         SensorDesc(diode=0, name='Cpu temp sensor',
                    position=Position.OTHER, target=60, overheat=90, critical=95),
      ])

      self.inventory.addWatchdog(FakeWatchdog())
