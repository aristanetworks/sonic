from ..core.component.i2c import I2cComponent
from ..core.component import Priority

from ..drivers.rundle import RundleFanCpldKernelDriver
from .minke import FanBoardBase

class RundleFanCpld(I2cComponent):
   DRIVER = RundleFanCpldKernelDriver
   PRIORITY = Priority.COOLING

class Rundle(FanBoardBase):
   FAN_COUNT = 8
   FAN_SLOTS = 8

   FAN_CPLD_CLS = RundleFanCpld

   def create_temp(self):
      pass

   def create_eeprom(self):
      pass
