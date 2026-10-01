
from ..core.component.i2c import I2cComponent
from ..core.component import Priority

from ..drivers.pali import Pali2FanCpldKernelDriver

from .fanboard import FanBoardBase

class Pali2FanCpld(I2cComponent):
   DRIVER = Pali2FanCpldKernelDriver
   PRIORITY = Priority.COOLING

class Pali2(FanBoardBase):

   FAN_COUNT = 4
   FAN_SLOTS = 4

   FAN_CPLD_CLS = Pali2FanCpld
