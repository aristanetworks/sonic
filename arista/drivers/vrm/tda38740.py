
from ...core.driver.kernel.i2c import I2cKernelDriver

class Tda38740KernelDriver(I2cKernelDriver):
   MODULE = 'atda38740'
   NAME = 'atda38740'

class Tda38740aKernelDriver(Tda38740KernelDriver):
   NAME = 'atda38740a'

class Xdpe1a2g5bKernelDriver(Tda38740KernelDriver):
   NAME = 'axdpe1a2g5b'

class Xdpe1b284bKernelDriver(Tda38740KernelDriver):
   NAME = 'axdpe1b284b'

class Xdpe1e496bKernelDriver(Tda38740KernelDriver):
   NAME = 'axdpe1e496b'
