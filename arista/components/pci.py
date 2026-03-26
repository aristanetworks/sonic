
from ..core.quirk import Quirk
from ..core.utils import inSimulation

from ..drivers.pci import PciConfig

class EcrcPciQuirk(Quirk):
   description = "Enable ECRC"
   when = Quirk.When.AFTER
   def run(self, component):
      if inSimulation():
         return
      config = PciConfig(component.addr)
      aer = config.aerCapability()
      aer.ecrcGene(True)
      aer.ecrcChke(True)

class CompletionTimeoutPciQuirk(Quirk):
   description = "Set Completion Timeout setting"
   when = Quirk.When.AFTER

   def __init__(self, completionTimeoutValue=0x5):
      self.completionTimeoutValue = completionTimeoutValue

   def run(self, component):
      if inSimulation():
         return
      config = PciConfig(component.addr)
      pcieCaps = config.pcieCapability()
      pcieCaps.completionTimeoutValue(self.completionTimeoutValue)
