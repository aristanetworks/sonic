
from .component.component import Component

from ..libs.procfs import getCmdlineDict
from ..inventory.programmable import Programmable

class AbootProgrammable(Programmable):
   def __init__(self, aboot):
      self.aboot = aboot

   def getComponent(self):
      return self.aboot

   def getDescription(self):
      return 'Bootloader'

   def getVersion(self):
      return self.aboot.getVersion()

class Aboot(Component):
   def __init__(self, *args, **kwargs):
      super(Aboot, self).__init__(*args, **kwargs)
      self.inventory.addProgrammable(AbootProgrammable(self))

   def getVersion(self):
      return getCmdlineDict().get('Aboot', 'N/A')

class UbootProgrammable(Programmable):
   def __init__(self, uboot):
      self.uboot = uboot

   def getComponent(self):
      return self.uboot

   def getDescription(self):
      return 'U-Boot'

   def getVersion(self):
      return self.uboot.getVersion()

class Uboot(Component):
   def __init__(self, *args, **kwargs):
      super(Uboot, self).__init__(*args, **kwargs)
      self.inventory.addProgrammable(UbootProgrammable(self))

   def getVersion(self):
      try:
         with open('/proc/device-tree/chosen/u-boot,version', encoding='utf-8') as f:
            return f.read().strip().rstrip('\x00')
      except (FileNotFoundError, OSError):
         return 'N/A'
