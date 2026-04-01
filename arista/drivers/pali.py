from ..core.driver.kernel.i2c import I2cKernelDriver

class Pali2FanCpldKernelDriver(I2cKernelDriver):
   MODULE = 'arista-fan-cpld'
   NAME = 'pali2_cpld'
