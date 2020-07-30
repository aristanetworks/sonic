
from . import InventoryInterface

class Xcvr(InventoryInterface):

   SFP = 0
   QSFP = 1
   OSFP = 2

   ADDR = 0x50

   @classmethod
   def typeStr(cls, typeIndex):
      return ['sfp', 'qsfp', 'osfp'][typeIndex]

   def getType(self):
      raise NotImplementedError()

   def getName(self):
      raise NotImplementedError()

   def getPresence(self):
      raise NotImplementedError()

   def getLowPowerMode(self):
      raise NotImplementedError()

   def setLowPowerMode(self, value):
      raise NotImplementedError()

   def getInterruptLine(self):
      raise NotImplementedError()

   def getReset(self):
      raise NotImplementedError()

   def __diag__(self, ctx):
      intr = self.getInterruptLine()
      reset = self.getReset()
      return {
         "name": self.getName(),
         "presence": self.getPresence() if ctx.performIo else None,
         "lpmode": self.getLowPowerMode() if ctx.performIo else None,
         "intr": intr.__diag__(ctx) if intr else None,
         "reset": reset.__diag__(ctx) if reset else None,
      }
