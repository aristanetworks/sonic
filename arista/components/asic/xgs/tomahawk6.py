from ....drivers.bcm_qspi import BcmAsicQspi
from ....inventory.programmable import Programmable

from . import XgsSwitchChip

class Tomahawk6Programmable(Programmable):
   def __init__(self, asic):
      self.asic = asic

   def getComponent(self):
      return self.asic

   def getDescription(self):
      return 'Switch ASIC'

   def getVersion(self):
      return self.asic.getVersion()

class Tomahawk6(XgsSwitchChip):
   def __init__(self, *args, qspiAddr=None, **kwargs):
      super().__init__(*args, **kwargs)
      self.qspiDriver = BcmAsicQspi(addr=qspiAddr) if qspiAddr else None
      self.inventory.addProgrammable(Tomahawk6Programmable(self))

   def getVersion(self):
      if self.qspiDriver is None:
         return 'N/A'
      return self.qspiDriver.getVersion()
