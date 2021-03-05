from .component import Priority
from .config import Config
from .driver import KernelDriver
from .inventory import Inventory
from .metainventory import MetaInventory
from .platform import getSysEepromData
from .sku import Sku

class FixedSystem(Sku):

   def __init__(self, drivers=None, inventory=None, **kwargs):
      drivers = drivers or [KernelDriver(module='eeprom'),
                            KernelDriver(module='i2c-dev')]
      inventory = inventory or Inventory()
      super(FixedSystem, self).__init__(drivers=drivers, inventory=inventory,
                                        **kwargs)

   def getEeprom(self):
      return getSysEepromData()

   def getInventory(self):
      if Config().use_metainventory:
         return MetaInventory(self.iterInventory())
      return self.inventory

   def setup(self, filters=Priority.defaultFilter):
      super(FixedSystem, self).setup()
      super(FixedSystem, self).finish(filters)

   def __str__(self):
      return '%s()' % self.__class__.__name__
