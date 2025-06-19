
from .bootloader import Aboot
from .sku import Sku

from ..components.cookie import PlatformCookieComponent

class Cpu(Sku):
   def __init__(self, *args, **kwargs):
      super(Cpu, self).__init__(*args, **kwargs)
      self.bootloader = self.newComponent(Aboot)
      self.cookies = self.newComponent(PlatformCookieComponent)

   def getPciPort(self, desc):
      if desc.root:
         return self.pciRoot.rootPort(device=desc.device, func=desc.func)
      bridge = self.pciRoot.pciBridge(device=desc.device, func=desc.func)
      desc.maybeAddQuirks(bridge.upstream)
      return bridge.downstreamPort(port=desc.port)
