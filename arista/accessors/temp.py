
from ..inventory.temp import Temp

class TempImpl(Temp):
   def __init__(self, sensor, driver=None, **kwargs):
      self.sensor = sensor
      self.name = sensor.name
      self.driver = driver
      self.__dict__.update(kwargs)

   def getName(self):
      return self.name

   def getPresence(self):
      return self.driver.getPresence(self.sensor)

   def getTemperature(self):
      return self.driver.getTemperature(self.sensor)

   def getLowThreshold(self):
      return self.driver.getLowThreshold(self.sensor)

   def setLowThreshold(self, value):
      return self.driver.setLowThreshold(self.sensor, value)

   def getHighThreshold(self):
      return float(self.sensor.critical)

   def setHighThreshold(self, value):
      self.sensor.critical = value
      return self.driver.setHighThreshold(self.sensor, value)

   def getTargetTemp(self):
      return self.sensor.target

   def getOverheatTemp(self):
      return self.sensor.overheat

   def getCriticalTemp(self):
      return self.sensor.critical

   def isSensorOverheat(self):
      if self.getPresence():
         return self.getTemperature() >= self.sensor.overheat
      return False

   def isSensorCritical(self):
      if self.getPresence():
         return self.getTemperature() >= self.sensor.critical
      return False
