from ...inventory.blackbox import BlackBoxImpl
from ...drivers.spi import SpidevDriver

class ScdBlackBoxImpl(BlackBoxImpl):
   def __init__(self, component):
      self.component = component

   def __str__(self):
      return self.__class__.__name__

   def getComponent(self):
      return self.component

   @property
   def regs(self):
      return self.component.regs()

   def version(self):
      return self.component.version()

   def enabled(self):
      return self.component.enabled()

   def setEnabled(self, enabled):
      return self.component.setEnabled(enabled)

class ScdBlackBoxDriver(SpidevDriver):
   def getBlackBox(self, component):
      return ScdBlackBoxImpl(component)
