from ..core.driver.kernel.i2c import I2cKernelDriver

class RundleFanCpldKernelDriver(I2cKernelDriver):
   MODULE = 'arista-fan-cpld'
   NAME = 'rundle_cpld'
