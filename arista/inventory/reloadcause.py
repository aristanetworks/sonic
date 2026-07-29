
from . import InventoryInterface, diagcls, diagmethod

@diagcls
class ReloadCause(InventoryInterface):
   @diagmethod('time')
   def getTime(self):
      raise NotImplementedError

   @diagmethod('cause')
   def getCause(self):
      raise NotImplementedError

   @diagmethod('score')
   def getScore(self):
      raise NotImplementedError

   @diagmethod('priority')
   def getPriority(self):
      raise NotImplementedError

   @diagmethod('altSource')
   def getAltSource(self):
      raise NotImplementedError

@diagcls
class ReloadCauseProvider(InventoryInterface):
   @diagmethod('source')
   def getSourceName(self):
      raise NotImplementedError

   @diagmethod('causes', diag=True)
   def getCauses(self):
      raise NotImplementedError

   @diagmethod('extra')
   def getExtra(self):
      raise NotImplementedError

   @diagmethod('priority')
   def getPriority(self):
      raise NotImplementedError

   @diagmethod('altSource')
   def getAltSource(self):
      raise NotImplementedError

   @diagmethod('providers', diag=True)
   def getRemoteProviders(self):
      return []
