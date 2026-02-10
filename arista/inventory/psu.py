
from . import InventoryInterface, diagcls, diagmethod

@diagcls
class PsuSlot(InventoryInterface):
   @diagmethod('slotId')
   def getId(self):
      raise NotImplementedError

   def getGenId(self):
      raise NotImplementedError

   @diagmethod('name')
   def getName(self):
      raise NotImplementedError

   @diagmethod('present', io=True)
   def getPresence(self):
      raise NotImplementedError

   @diagmethod('presentCached')
   def getPresenceCached(self):
      raise NotImplementedError

   @diagmethod('status', io=True)
   def getStatus(self):
      raise NotImplementedError

   @diagmethod('psu', diag=True)
   def getPsu(self):
      raise NotImplementedError

   def getLoadedPsu(self):
      raise NotImplementedError

   def reloadPsu(self):
      raise NotImplementedError

   @diagmethod('led', diag=True)
   def getLed(self):
      raise NotImplementedError

@diagcls
class Psu(InventoryInterface):
   @diagmethod('name')
   def getName(self):
      raise NotImplementedError

   @diagmethod('model')
   def getModel(self):
      raise NotImplementedError

   @diagmethod('revision')
   def getRevision(self):
      raise NotImplementedError

   @diagmethod('serial')
   def getSerial(self):
      raise NotImplementedError

   @diagmethod('status', io=True)
   def getStatus(self):
      raise NotImplementedError

   @diagmethod('capacity')
   def getCapacity(self):
      raise NotImplementedError

   @diagmethod('mfr')
   def getMfr(self):
      raise NotImplementedError

   @diagmethod('fans', diag=True)
   def getFans(self):
      raise NotImplementedError

   @diagmethod('temps', diag=True)
   def getTemps(self):
      raise NotImplementedError

   @diagmethod('rails', diag=True)
   def getRails(self):
      raise NotImplementedError
