from ...core.component.i2c import I2cComponent
from ...core.driver.user.i2c import I2cDevDriver

class Mp8796B(I2cComponent):
   DRIVER = I2cDevDriver

   def setup(self):
      self.applyQuirks()
