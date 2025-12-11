
from ..core.driver.kernel.i2c import I2cKernelDriver

class Tmp401KernelDriver(I2cKernelDriver):
   MODULE = 'tmp401'
   NAME = 'tmp401'

class Tmp431KernelDriver(Tmp401KernelDriver):
   NAME = 'tmp431'
