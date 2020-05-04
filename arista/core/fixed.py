from .cause import ReloadCauseEntry
from .component import Component, Priority
from .config import Config
from .driver import KernelDriver
from .inventory import Inventory
from .utils import inSimulation, JsonStoredData

class FixedSystem(Component):

   PLATFORM = None
   SID = None
   SKU = None
   HWAPI = None

   def __init__(self, drivers=None, inventory=None, **kwargs):
      drivers = drivers or [KernelDriver(module='eeprom'),
                            KernelDriver(module='i2c-dev')]
      inventory = inventory or Inventory()
      super(FixedSystem, self).__init__(drivers=drivers, inventory=inventory,
                                        **kwargs)

   def setup(self, filters=Priority.defaultFilter):
      super(FixedSystem, self).setup()
      super(FixedSystem, self).finish(filters)

   def __str__(self):
      return '%s()' % self.__class__.__name__

   def getReloadCauses(self, clear=False):
      if inSimulation():
         return []
      rebootCauses = JsonStoredData('%s' % Config().reboot_cause_file)
      if not rebootCauses.exist():
         causes = super(FixedSystem, self).getReloadCauses(clear=clear)
         rebootCauses.writeList(causes)
      return rebootCauses.readList(ReloadCauseEntry)
