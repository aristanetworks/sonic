
from . import InventoryInterface

class PowerCycle(InventoryInterface):
   def ensureAvailable(self):
      raise NotImplementedError

   def powerCycle(self):
      raise NotImplementedError
