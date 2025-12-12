
from . import InventoryInterface, diagcls, diagmethod

@diagcls
class SwitchAsic(InventoryInterface):

   @diagmethod('id')
   def getId(self) -> int:
      raise NotImplementedError

   @diagmethod('name')
   def getName(self) -> str:
      raise NotImplementedError

   @diagmethod('model')
   def getModel(self) -> str:
      raise NotImplementedError
