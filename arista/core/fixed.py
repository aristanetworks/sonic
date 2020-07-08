from .cause import ReloadCauseDataStore
from .component import Priority
from .driver import KernelDriver
from .inventory import Inventory
from .platform import getSysEeprom
from .sku import Sku
from .utils import inSimulation

class FixedSystem(Sku):

   def __init__(self, drivers=None, inventory=None, **kwargs):
      drivers = drivers or [KernelDriver(module='eeprom'),
                            KernelDriver(module='i2c-dev')]
      inventory = inventory or Inventory()
      super(FixedSystem, self).__init__(drivers=drivers, inventory=inventory,
                                        **kwargs)

   def getEeprom(self):
      return getSysEeprom()

   def setup(self, filters=Priority.defaultFilter):
      super(FixedSystem, self).setup()
      super(FixedSystem, self).finish(filters)

   def __str__(self):
      return '%s()' % self.__class__.__name__

   def getReloadCauses(self, clear=False):
      if inSimulation():
         return []
      rebootCauses = ReloadCauseDataStore()
      if not rebootCauses.exist():
         causes = super(FixedSystem, self).getReloadCauses(clear=clear)
         rebootCauses.writeList(causes)
      return rebootCauses.readCauses()
