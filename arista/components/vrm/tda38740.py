from ...core.component import Priority
from ...core.component.i2c import I2cComponent

from ...drivers.vrm.tda38740 import (
   Tda38740aKernelDriver,
   Xdpe1a2g5bKernelDriver,
   Xdpe1b284bKernelDriver,
   Xdpe1e496bKernelDriver,
)

class Tda38740a(I2cComponent):
   DRIVER = Tda38740aKernelDriver
   PRIORITY = Priority.THERMAL

class Xdpe1a2g5b(Tda38740a):
   DRIVER = Xdpe1a2g5bKernelDriver

class Xdpe1b284b(Tda38740a):
   DRIVER = Xdpe1b284bKernelDriver

class Xdpe1e496b(Tda38740a):
   DRIVER = Xdpe1e496bKernelDriver
