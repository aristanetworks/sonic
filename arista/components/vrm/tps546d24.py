from ...core.component import Priority
from ...core.component.i2c import I2cComponent

from ...drivers.vrm.tps546d24 import Tps546D24KernelDriver

class Tps546D24(I2cComponent):
   DRIVER = Tps546D24KernelDriver
   PRIORITY = Priority.THERMAL
