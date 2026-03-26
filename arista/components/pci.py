
from ..core.quirk import Quirk
from ..core.utils import inSimulation

from ..drivers.pci import PciConfig

class EcrcPciQuirk(Quirk):
   def __str__(self):
      return "Enable ECRC"

   def run(self, component):
      if inSimulation():
         return
      config = PciConfig(component.addr)
      aer = config.aerCapability()
      aer.ecrcGene(True)
      aer.ecrcChke(True)

class CompletionTimeoutPciQuirk(Quirk):
   def __str__(self):
      return "Set Completion Timeout setting"

   def __init__(self, completionTimeoutValue=0x5):
      self.completionTimeoutValue = completionTimeoutValue

   def run(self, component):
      if inSimulation():
         return
      config = PciConfig(component.addr)
      pcieCaps = config.pcieCapability()
      pcieCaps.completionTimeoutValue(self.completionTimeoutValue)
