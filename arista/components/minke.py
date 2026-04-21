from ..components.lm75 import Tmp75

from ..core.component.i2c import I2cComponent
from ..core.component import Priority
from ..core.fan import FanSlot
from ..core.utils import incrange

from ..descs.fan import FanDesc, FanPosition
from ..descs.led import LedDesc, LedColor
from ..descs.sensor import Position, SensorDesc

from ..drivers.minke import MinkeFanCpldKernelDriver

from .eeprom import At24C32

class FanBoardBase:

   FAN_SLOTS = 0
   FAN_COUNT = 0

   FAN_CPLD_CLS = None
   IDPROM_CLS = At24C32

   def __init__(self, parent, bus, fanMaxPowerDraw=0):
      self.parent = parent
      self.bus = bus
      self.eeprom = self.create_eeprom()
      self.cpld = self.create_cpld()
      self.temp = self.create_temp()
      self.slots = self.create_fan_slots(fanMaxPowerDraw)
      self.dpm = self.create_dpm() # pylint: disable=assignment-from-none

   def create_eeprom(self):
      return self.parent.newComponent(self.IDPROM_CLS, addr=self.bus.i2cAddr(0x50))

   def create_cpld(self):
      return self.parent.newComponent(self.FAN_CPLD_CLS, addr=self.bus.i2cAddr(0x60))

   def create_temp(self):
      return self.parent.newComponent(Tmp75, addr=self.bus.i2cAddr(0x48), sensors=[
         SensorDesc(diode=0, name='Outlet', position=Position.OUTLET,
            target=65, overheat=80, critical=95),
      ])

   def create_fan_slots(self, fanMaxPowerDraw=0):
      fansPerSlot = self.FAN_COUNT // self.FAN_SLOTS
      return [
         self.parent.newComponent(
            FanSlot,
            slotId=slotId,
            maxPowerDraw=fanMaxPowerDraw,
            led=self.cpld.addFanLed(LedDesc(
               name='fan_slot%d' % slotId,
               colors=[LedColor.RED, LedColor.AMBER, LedColor.GREEN,
                       LedColor.BLUE, LedColor.OFF],
            )),
            fans=[self.cpld.addFan(FanDesc(
                  fanId=(slotId - 1) * fansPerSlot + relFanId,
                  position=FanPosition.INLET,
               )) for relFanId in incrange(1, fansPerSlot)
            ],
         ) for slotId in incrange(1, self.FAN_SLOTS)
      ]

   def create_dpm(self):
      return None

class MinkeFanCpld(I2cComponent):
   DRIVER = MinkeFanCpldKernelDriver
   PRIORITY = Priority.COOLING

class Minke(FanBoardBase):

   FAN_SLOTS = 3
   FAN_COUNT = 6

   FAN_CPLD_CLS = MinkeFanCpld
   IDPROM_CLS = At24C32
