from ....core.component.component import Component

from ....drivers.cpu.amd import AmdGpioDriver

from ....inventory.powercycle import PowerCycle


class AmdGpioController(Component):
   DRIVER = AmdGpioDriver

   def addPowerCycle(self, desc, **kwargs):
      gpio = self.addGpio(desc, **kwargs)
      return self.inventory.addPowerCycle(GpioPowerCycle(gpio))

class GpioPowerCycle(PowerCycle):
   def __init__(self, gpio):
      self.gpio = gpio

   def powerCycle(self):
      self.gpio.setActive(1)
