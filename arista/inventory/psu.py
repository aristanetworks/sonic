
from . import InventoryInterface, diagcls, diagmethod

@diagcls
class PsuSlot(InventoryInterface):
   @diagmethod('slotId')
   def getId(self):
      raise NotImplementedError

   @diagmethod('name')
   def getName(self):
      raise NotImplementedError

   @diagmethod('present', io=True)
   def getPresence(self):
      raise NotImplementedError

   @diagmethod('status', io=True)
   def getStatus(self):
      raise NotImplementedError

   @diagmethod('psu', diag=True)
   def getPsu(self):
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
