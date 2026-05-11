
from . import InventoryInterface, diagcls, diagmethod

@diagcls
class BlackBoxImpl(InventoryInterface):
   @diagmethod('component', fmt=str)
   def getComponent(self):
      raise NotImplementedError

   @diagmethod('version', io=True)
   def version(self):
      raise NotImplementedError

   @diagmethod('enabled', io=True)
   def enabled(self):
      raise NotImplementedError

   @diagmethod('model', io=True)
   def getModel(self):
      raise NotImplementedError

   def setEnabled(self, enabled):
      raise NotImplementedError

   def decoder(self):
      raise NotImplementedError

   def dump(self, outputPath):
      raise NotImplementedError

   def erase(self):
      raise NotImplementedError
