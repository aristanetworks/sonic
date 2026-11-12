import os
from typing import Optional

from ..config import etcPath, flashPath
from ..exception import UnknownPlatformError
from ..inventory import Inventory
from ..log import getLogger
from ..prefdl import Prefdl
from ..prerequisites import loadPrerequisites
from ..types import I2cBus
from ..utils import inSimulation

from .base import PlatformIdentityBase

logging = getLogger(__name__)

def _readPrefdlFromStaticEepromAddress(busName: str,
                                       i2cAddress: int) -> Optional[Prefdl]:
   # pylint: disable=import-outside-toplevel
   from ...components.eeprom import I2cEeprom
   loadPrerequisites()
   prefdl = None
   try:
      eeprom = I2cEeprom(addr=I2cBus(busName).i2cAddr(i2cAddress),
                        inventoryCls=Inventory)
      eeprom.setup()
      logging.debug('reading system eeprom from %s',
                    eeprom.driver.eepromPath())
      prefdl = eeprom.readPrefdl()
   except Exception: # pylint: disable=broad-except
      logging.exception('could not read eeprom from %s', busName)
   return prefdl

class PlatformIdentityNonDmi(PlatformIdentityBase):
   _HOST_PREFDL_PATH = flashPath('.system-prefdl')
   _HOST_PREFDL_BINPATH = flashPath('.system-prefdl-bin')
   _PREFDL_CACHE_PATH = etcPath('.syseeprom')

   def __init__(self, *args, **kwargs):
      super().__init__(*args, **kwargs)
      self._prefdl = None

   @property
   def syseeprom(self) -> Prefdl:
      if self._prefdl is None:
         self._readPrefdl()
      return self._prefdl

   def _readHostPrefdl(self) -> Optional[Prefdl]:
      lp = f'{self.__class__.__name__}'
      if os.path.exists(self._HOST_PREFDL_BINPATH):
         logging.debug('%s: reading bin system eeprom from %s',
                       lp, self._HOST_PREFDL_BINPATH)
         return Prefdl.fromBinFile(self._HOST_PREFDL_BINPATH)
      if os.path.exists(self._HOST_PREFDL_PATH):
         logging.debug('%s: reading system eeprom from %s',
                       lp, self._HOST_PREFDL_PATH)
         return Prefdl.fromTextFile(self._HOST_PREFDL_PATH)
      return None

   def _readUpperlakeI2cPrefdl(self) -> Optional[Prefdl]:
      return _readPrefdlFromStaticEepromAddress(
            busName='SMBus PIIX4 adapter port 1 at 0b20',
            i2cAddress=0x52)

   def _readPrefdl(self):
      if inSimulation():
         self._prefdl = Prefdl.fromDict({
            'SKU': 'simulation',
            'HwApi': '42',
         })
         return

      prefdl = self._readCachedPrefdl()
      if prefdl:
         self._prefdl = prefdl
         return

      prefdl = self._readHostPrefdl()
      if not prefdl and (self.sid or '').startswith('Upperlake'):
         # Upperlake platforms can tolerate a missing prefdl file in /host;
         # read the prefdl from the EEPROM instead.
         prefdl = self._readUpperlakeI2cPrefdl()

      if not prefdl:
         lp = f'{self.__class__.__name__}'
         raise UnknownPlatformError(f'{lp}: Could not identify current platform')

      self._writePrefdlCacheFile(prefdl)
      self._prefdl = prefdl

   @property
   def sid(self) -> Optional[str]:
      return self._cmdline.get('sid')

   @property
   def sku(self) -> Optional[str]:
      return self.syseeprom.get('SKU')

   @property
   def platform(self) -> Optional[str]:
      return self._cmdline.get('platform')
