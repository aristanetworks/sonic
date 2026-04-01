from ..core.driver.kernel.i2c import I2cKernelDriver

class MinkeFanCpldKernelDriver(I2cKernelDriver):
   MODULE = 'arista-fan-cpld'
   NAME = 'minke_cpld'
