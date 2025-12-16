
from .component import Component
from ..quirk import Quirk
from ..driver.user.i2c import I2cDevDriver

class I2cRegisterQuirk(Quirk): # pylint: disable=abstract-method
   def __init__(self, addr, data, description=None):
      self.addr = addr
      self.data = data
      self.description = description

   def __str__(self):
      return self.description or f'{self.__class__.__name__}({self.addr})'

class I2cByteQuirk(I2cRegisterQuirk):
   def run(self, component):
      component.getUserDriver().write_byte_data(self.addr, self.data)

class I2cBlockQuirk(I2cRegisterQuirk):
   def run(self, component):
      component.getUserDriver().write_bytes([self.addr, len(self.data)] + self.data)

class I2cComponent(Component):
   def getUserDriver(self):
      if isinstance(self.driver, I2cDevDriver):
         return self.driver
      return I2cDevDriver(parent=self, addr=self.addr)
