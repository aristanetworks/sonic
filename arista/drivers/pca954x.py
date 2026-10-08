from .i2c_mux import I2cMuxKernelDriver

class Pca954xKernelDriver(I2cMuxKernelDriver):
   MODULE = 'i2c-mux-pca954x'
   NUM_CHANNELS = 0

class Pca9548KernelDriver(Pca954xKernelDriver):
   NAME = 'pca9548'
   NUM_CHANNELS = 8
   SMBUS_BLOCK = False
