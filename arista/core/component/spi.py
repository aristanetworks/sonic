
from .unmanaged import Component, UnmanagedComponent

class SpiComponent(Component):
   pass

class SpiController(UnmanagedComponent):

   def iterSpiComponents(self):
      return [c for c in self.components if isinstance(c, SpiComponent)]
