
from ....inventory.rtc import RealTimeClock

class RealTimeClockImpl(RealTimeClock):
   def __init__(self, component):
      self.component = component

   def getName(self):
      return str(self.component)

   def getTime(self):
      return self.component.getRealTimeClock()

   def setTime(self, dt):
      self.component.setRealTimeClock(dt)
