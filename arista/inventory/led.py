
from . import InventoryInterface, diagcls, diagmethod

@diagcls
class Led(InventoryInterface):
   @diagmethod('name')
   def getName(self):
      raise NotImplementedError

   @diagmethod('color', io=True)
   def getColor(self):
      raise NotImplementedError

   def setColor(self, color):
      raise NotImplementedError

   @diagmethod('isStatus')
   def isStatusLed(self):
      raise NotImplementedError

class MultiLed(Led):
   def __init__(self, name, leds):
      self.name = name
      self.leds = leds

   def getName(self):
      return self.name

   def getColor(self):
      return self.leds[0].getColor()

   def setColor(self, color):
      for led in self.leds:
         led.setColor(color)
      return True

   def isStatusLed(self):
      return self.leds[0].isStatusLed()
