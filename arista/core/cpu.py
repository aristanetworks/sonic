
from .bootloader import Aboot
from .sku import Sku

from ..components.cookie import (
   PlatformCookieComponent,
   SonicReloadCauseCookieComponent
)
from ..descs.cause import ReloadCausePriority

class Cpu(Sku):
   def __init__(self, *args, cookiesPriority=ReloadCausePriority.PRIMARY, **kwargs):
      super(Cpu, self).__init__(*args, **kwargs)
      self.bootloader = self.newComponent(Aboot)
      self.cookies = self.newComponent(PlatformCookieComponent,
                                       priority=cookiesPriority)
      self.sonicOsCookie = self.newComponent(SonicReloadCauseCookieComponent,
                                             priority=cookiesPriority)

   def getPciPort(self, desc):
      if desc.root:
         port = self.pciRoot.rootPort(domain=desc.domain, bus=desc.bus,
                                      device=desc.device, func=desc.func)
         desc.maybeAddQuirks(port)
         return port
      bridge = self.pciRoot.pciBridge(domain=desc.domain, bus=desc.bus,
                                      device=desc.device, func=desc.func)
      desc.maybeAddQuirks(bridge.upstream)
      return bridge.downstreamPort(port=desc.port)
