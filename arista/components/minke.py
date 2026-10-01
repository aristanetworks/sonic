from ..core.component.i2c import I2cComponent
from ..core.component import Priority

from ..drivers.minke import MinkeFanCpldKernelDriver

from .fanboard import FanBoardBase

class MinkeFanCpld(I2cComponent):
   DRIVER = MinkeFanCpldKernelDriver
   PRIORITY = Priority.COOLING

class Minke(FanBoardBase):

   FAN_SLOTS = 3
   FAN_COUNT = 6

   FAN_CPLD_CLS = MinkeFanCpld
