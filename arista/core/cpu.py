from typing import Optional

from .bootloader import Aboot
from .driver.kernel import KernelDriver
from .log import getLogger
from .platform import getPlatformIdentity
from .prefdl import Prefdl
from .prerequisites import loadPrerequisites
from .sku import Sku

from ..components.cookie import (
   PlatformCookieComponent,
   SonicReloadCauseCookieComponent
)
from ..components.eeprom import RawI2cPrefdlEeprom

logging = getLogger(__name__)

PREREQUISITES = [
   KernelDriver(module='i2c-dev'),
]

class Cpu(Sku):

   PREFDL_EEPROM_BUS = None
   PREFDL_EEPROM_ADDR = 0x50

   def __init__(self, *args, **kwargs):
      super(Cpu, self).__init__(*args, **kwargs)
      self.bootloader = self.newComponent(Aboot)
      self.cookies = self.newComponent(PlatformCookieComponent)
      self.sonicOsCookie = self.newComponent(SonicReloadCauseCookieComponent)

   def getEeprom(self):
      prefdl = getPlatformIdentity().cpueeprom
      if prefdl is not None:
         return prefdl.data()

      if self.PREFDL_EEPROM_BUS is None:
         return {}
      loadPrerequisites()
      try:
         eeprom = RawI2cPrefdlEeprom(self.PREFDL_EEPROM_BUS,
                                     self.PREFDL_EEPROM_ADDR)
         return eeprom.prefdl()
      except Exception: # pylint: disable=broad-except
         logging.debug('%s: failed to read cpu prefdl', self)
         return {}

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

   @classmethod
   def readSwitchEeprom(cls) -> Optional[Prefdl]:
      return None
