
from . import InventoryInterface, diagcls, diagmethod

@diagcls
class RealTimeClock(InventoryInterface):
   @diagmethod('name')
   def getName(self):
      raise NotImplementedError

   @diagmethod('time', io=True)
   def getTime(self):
      raise NotImplementedError

   def setTime(self, dt):
      raise NotImplementedError
