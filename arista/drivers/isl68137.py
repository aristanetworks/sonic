from ..core.driver.kernel.i2c import I2cKernelDriver

class Isl68137KernelDriver(I2cKernelDriver):
   MODULE = 'isl68137'
   NAME = 'isl68137'

class Isl68226KernelDriver(Isl68137KernelDriver):
   NAME = 'isl68226'

class Isl68223KernelDriver(Isl68137KernelDriver):
   NAME = 'isl68223'

class Raa228228KernelDriver(Isl68137KernelDriver):
   NAME = 'raa228228'
