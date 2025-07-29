from ....core.component.component import Component

from ....drivers.cpu.amd import AmdGpioDriver

from ....inventory.powercycle import PowerCycle


class AmdGpioController(Component):
   DRIVER = AmdGpioDriver

   def addPowerCycle(self, desc, **kwargs):
      gpio = self.addGpio(desc, **kwargs)
      return self.inventory.addPowerCycle(GpioPowerCycle(gpio, self.driver))

class GpioPowerCycle(PowerCycle):
   def __init__(self, gpio, driver):
      self.gpio = gpio
      self.driver = driver

   def ensureAvailable(self):
      self.driver.setup()

   def powerCycle(self):
      self.gpio.setActive(1)
