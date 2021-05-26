import os

from ..core.driver import Driver
from ..core.utils import simulateWith
from ..core.log import getLogger

logging = getLogger(__name__)

class PmbusDriver(Driver):
   def __init__(self, addr=None, hwmonDir=None, sensors=None, **kwargs):
      self.addr = addr
      self.hwmonDir = hwmonDir
      self.sensors = sensors or []
      super(PmbusDriver, self).__init__(**kwargs)

   def sensorPath(self, name):
      return os.path.join(self.hwmonDir, name)

   def readSensor(self, name):
      path = self.sensorPath(name)
      if not os.path.exists(path):
         logging.debug('hwmon sensor %s does not exist', path)
         return 0, False
      logging.debug('hwmon-read %s', path)
      try:
         with open(path, 'r') as f:
            return int(f.read()), True
      except IOError:
         logging.error('failed to read pmbus %s', path)
         return 0, True

   def getStatusSim_(self):
      logging.info('reading psu status from hwmon: %s', self.hwmonDir)
      return True

   @simulateWith(getStatusSim_)
   def getPsuStatus(self, psu):
      # At least one sensor is expected to exist, otherwise treat it as a failure.
      # Check input and output values of current and voltage are in the range.

      # The PMBus PSU will be temporarily used as a generic PSU, so we will fallback
      # to relying on psu presence if the PSU model does not use PMBus
      sensorExists = False

      for sensor in self.sensors:
         nonZero = False
         # The value must be non zero.
         value, exists = self.readSensor('%s_input' % sensor)
         if exists:
            sensorExists = True
         else:
            continue
         if not value:
            continue
         nonZero = True

         # The value must be lower than its critical value.
         valueCrit, exists = self.readSensor('%s_crit' % sensor)
         if exists and valueCrit > 0 and value > valueCrit:
            return False

         # The value must be greater than its lowest allowed value.
         valueLCrit, exists = self.readSensor('%s_lcrit' % sensor)
         if exists and value < valueLCrit:
            return False

         # Not all PSUs will have all the curr/in values, so we just need one
         if nonZero:
            return True

      if sensorExists:
         return False
      return psu.getPresence()
