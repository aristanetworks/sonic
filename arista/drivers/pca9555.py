
from ..core.register import Register
from ..core.utils import inSimulation
from ..descs.led import LedColor
from ..inventory.led import Led

from .i2c import I2cDevDriver

class LedGpioImpl(Led):
   def __init__(self, driver, name, gpio, colorActive=LedColor.RED,
                colorInactive=LedColor.OFF, **kwargs):
      self.name = name
      self.driver = driver
      self.gpio = gpio
      self.colorActive = colorActive
      self.colorInactive = colorInactive
      self.__dict__.update(kwargs)

   def getName(self):
      return self.name

   def getColor(self):
      if self.gpio.isActive():
         return self.colorActive
      return self.colorInactive

   def setColor(self, color):
      if color == self.colorActive:
         self.gpio.setActive(True)
      else:
         self.gpio.setActive(False)
      return True

   def isStatusLed(self):
      return True

PCA9555_INPUT_REG = 0x0
PCA9555_OUTPUT_REG = 0x2
PCA9555_CONFIG_REG = 0x6

class GpioRegister(Register):
   '''Register's addr is more like offset in GpioRegister, which is 0x0 or 0x1.
   '''
   def readBit(self, bitpos):
      if inSimulation():
         return 0

      # Always read bits from input registers
      assert 0x0 <= self.addr <= 0x1
      regval = self.parent.read(PCA9555_INPUT_REG + self.addr)
      return (regval >> bitpos) & 1

   def writeBit(self, bitpos, value):
      if inSimulation():
         return

      # Read output registers, update bit, and write back
      # Doing the same for configuration registers,
      # in case they are modified unexpectedly.
      assert 0x0 <= self.addr <= 0x1
      def _writeBit(addr, value):
         regval = self.parent.read(addr)
         if value:
            regval |= (1 << bitpos)
         else:
            regval &= ~(1 << bitpos)
         self.parent.write(addr, regval)
      _writeBit(PCA9555_OUTPUT_REG + self.addr, value)
      _writeBit(PCA9555_CONFIG_REG + self.addr, False) # False for output

class Pca9555I2cDevDriver(I2cDevDriver):
   def reset(self):
      # Set all bits in config reg to have pins in input mode
      data = 0xff
      self.write(PCA9555_CONFIG_REG, data)
      self.write(PCA9555_CONFIG_REG + 1, data)

   def getGpioLed(self, name, **kwargs):
      return LedGpioImpl(self, name, self.getGpio(name), **kwargs)

   def __diag__(self, ctx):
      return {
         'name': self.name,
         'regs': self.regs.__diag__(ctx),
         'status': { reg : self.read(reg) if ctx.performIo else None for reg in range(8) },
      }
