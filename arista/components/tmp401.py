
from ..core.component import Priority
from ..core.component.i2c import I2cComponent

from ..drivers.tmp401 import Tmp431KernelDriver

class Tmp431(I2cComponent):
   DRIVER = Tmp431KernelDriver
   PRIORITY = Priority.THERMAL
