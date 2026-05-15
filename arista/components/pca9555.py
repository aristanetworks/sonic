
from ..core.component import Priority
from ..core.component.i2c import I2cComponent
from ..core.register import Register, RegBitField, RegisterMap

from ..drivers.pca9555 import Pca9555I2cDevDriver

from ..inventory.seu import SeuReporter

class Pca9555(I2cComponent):

   DRIVER = Pca9555I2cDevDriver
   PRIORITY = Priority.DEFAULT

   def resetConfig(self):
      self.driver.reset()

   def addGpio(self, name):
      return self.inventory.addGpio(self.driver.getGpio(name))

   def addGpioLed(self, name, **kwargs):
      return self.inventory.addLed(self.driver.getGpioLed(name, **kwargs))

   def addRedGreenGpioLed(self, name, rname, gname, **kwargs):
      return self.inventory.addLed(
                   self.driver.getRedGreenGpioLed(name, rname, gname, **kwargs))

   def __getattr__(self, key):
      return getattr(self.driver.regs, key)

class Pca9539RegisterMap(RegisterMap):
   INPUT_PORT0 = Register(0x00,
      RegBitField(0, 'io0_0'),
      RegBitField(1, 'io0_1'),
      RegBitField(2, 'io0_2'),
      RegBitField(3, 'io0_3'),
      RegBitField(4, 'io0_4'),
      RegBitField(5, 'io0_5'),
      RegBitField(6, 'io0_6'),
      RegBitField(7, 'io0_7'),
   )
   INPUT_PORT1 = Register(0x01,
      RegBitField(0, 'io1_0'),
      RegBitField(1, 'io1_1'),
      RegBitField(2, 'io1_2'),
      RegBitField(3, 'io1_3'),
      RegBitField(4, 'io1_4'),
      RegBitField(5, 'io1_5'),
      RegBitField(6, 'io1_6'),
      RegBitField(7, 'io1_7'),
   )

class Pca9539Pin:
   def __init__(self, name):
      self.name = name

   def __str__(self):
      return self.name

class Pca9539SeuReporter(SeuReporter):
   def __init__(self, field, name):
      self.pin = Pca9539Pin(name)
      self.field = field

   def getComponent(self):
      return self.pin

   def hasSeuError(self):
      return bool(self.field())

   def powerCycleOnSeu(self, on=None):
      return False

class Pca9539IoExpander(Pca9555):
   REGISTER_CLS = Pca9539RegisterMap

   def __init__(self, *args, seuPins=None, **kwargs):
      super().__init__(*args, **kwargs)
      for pin, name in (seuPins or []):
         self.inventory.addSeuReporter(
            Pca9539SeuReporter(getattr(self.driver.regs, pin), name))
