from ...core.component import Priority
from ...core.component.i2c import I2cComponent

from ...drivers.isl68137 import (
   Isl68137KernelDriver,
   Isl68226KernelDriver,
   Isl68223KernelDriver,
)

class Isl68137(I2cComponent):
   DRIVER = Isl68137KernelDriver
   PRIORITY = Priority.THERMAL

class Isl68226(Isl68137):
   DRIVER = Isl68226KernelDriver

class Isl68223(Isl68137):
   DRIVER = Isl68223KernelDriver
