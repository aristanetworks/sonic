
from ...core.component import Priority
from ...core.component.i2c import I2cComponent
from ...core.log import getLogger

logging = getLogger(__name__)

class PmbusComponent(I2cComponent):

   PRIORITY = Priority.DEFAULT

   class Registers(object):
      CLEAR_FAULTS = 0x03

      PMBUS_REVISION = 0x98

      MFR_ID = 0x99
      MFR_MODEL = 0x9a
      MFR_REVISION = 0x9b
      MFR_LOCATION = 0x9c
      MFR_DATE = 0x9d
      MFR_SERIAL = 0x9e

   def __init__(self, **kwargs):
      super(PmbusComponent, self).__init__(registers=self.Registers, **kwargs)

   def getVersion(self):
      return 'N/A'

   def getRealTimeClock(self):
      return None

   def setRealTimeClock(self, dt):
      pass

   def setup(self):
      try:
         serial = self.getVersion()
         logging.info('%s version: %s', self, serial)
      except Exception: # pylint: disable=broad-except
         logging.error('%s: failed to version information', self)

   def __diag__(self, ctx):
      return {
         "name": str(self),
         "version": self.getVersion() if ctx.performIo else "N/A",
      }

class PmbusDpm(PmbusComponent):
   pass
