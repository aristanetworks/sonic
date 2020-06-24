from ..core.log import getLogger
from ..inventory.fan import Fan

logging = getLogger(__name__)

class FanImpl(Fan):
   MIN_FAN_SPEED = 30
   MAX_FAN_SPEED = 100

   def __init__(self, fanId=1, driver=None, led=None, **kwargs):
      self.fanId = fanId
      self.driver = driver
      self.led = led
      self.customSpeed = None
      self.__dict__.update(kwargs)

   def getId(self):
      return self.fanId

   def getName(self):
      return 'fan%s' % self.fanId

   def getSpeed(self):
      return self.driver.getFanSpeed(self)

   def setSpeed(self, speed):
      if self.customSpeed == self.MAX_FAN_SPEED and speed != self.MAX_FAN_SPEED:
         logging.debug("%s fan speed reduced from max", self.getName())
      elif self.customSpeed != self.MAX_FAN_SPEED and speed == self.MAX_FAN_SPEED:
         logging.warn("%s fan speed set to max", self.getName())
      self.customSpeed = speed
      return self.driver.setFanSpeed(self, speed)

   def getPresence(self):
      return self.driver.getFanPresence(self)

   def getStatus(self):
      return self.driver.getFanStatus(self)

   def getDirection(self):
      return self.driver.getFanDirection(self)

   def getLed(self):
      return self.led
