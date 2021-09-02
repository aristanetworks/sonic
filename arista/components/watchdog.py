
from ..inventory.watchdog import Watchdog

class FakeWatchdog(Watchdog):
   def __init__(self):
      self.armed = False
      self.timeout = -1

   def arm(self, timeout):
      self.armed = True
      self.timeout = timeout
      return True

   def stop(self):
      self.armed = False
      self.timeout = -1
      return True

   def status(self):
      return {
         'enabled': self.armed,
         'timeout': self.timeout,
         'remainingTime': self.timeout,
      }
