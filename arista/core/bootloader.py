
import subprocess

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
      version = getCmdlineDict().get('Aboot')
      if version:
         return version
      try:
         return subprocess.check_output(
            ['dmidecode', '-s', 'bios-version'], text=True).strip()
      except Exception: # pylint: disable=broad-except
         return 'N/A'
