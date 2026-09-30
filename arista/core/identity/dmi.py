import os
from typing import TYPE_CHECKING, Optional

from ..config import tmpfsPath
from ..exception import UnknownPlatformError
from ..log import getLogger
from ..prefdl import Prefdl

from .base import PlatformIdentityBase, Prefdls
from .common import readSystemPrefdlViaDmi

from ...libs.dmi import DmiType

if TYPE_CHECKING:
   from ..cpu import Cpu

logging = getLogger(__name__)

def _readCpuPlatformNamesViaDmi() -> list[str]:
   entries = [
      (DmiType.BASEBOARD, 'Product Name'),
      (DmiType.SYSTEM, 'Product Name'),
   ]
   names = []
   for entry, field in entries:
      try:
         name = entry.decode().get(field)
         if name is not None:
            names.append(name.lower())
      except PermissionError:
         raise
      except Exception: # pylint: disable=broad-except
         logging.exception('failed to extract %s from %s',
               field, entry)
   return names

class PlatformIdentityDmi(PlatformIdentityBase):
   # tmpfs cache so the eeprom is re-read on every boot.
   _PREFDL_CACHE_PATH = tmpfsPath('.syseeprom')
   _CPU_PREFDL_CACHE_PATH = tmpfsPath('.cpueeprom')

   @staticmethod
   def _createEmptyMarkerFile(path):
      os.makedirs(os.path.dirname(path), exist_ok=True)
      with open(path, 'w', encoding='utf-8'):
         pass
      os.chmod(path, 0o644)

   def _readSwitchEeprom(self, cpuCls: 'type[Cpu]', lp: str) -> Prefdl:
      logging.debug('%s: looking for switch eeprom', lp)
      switchPrefdl = cpuCls.readSwitchEeprom()
      if switchPrefdl is None:
         raise UnknownPlatformError(
               f'{lp}: readSwitchEeprom returned None for {cpuCls}')
      logging.debug('%s: found switch eeprom for %s', lp,
                    switchPrefdl.get('SID'))
      return switchPrefdl

   def _readCachedPrefdls(self) -> Optional[Prefdls]:
      switchPrefdl = self._readCachedPrefdl()
      if not switchPrefdl:
         return None
      if not os.path.exists(self._CPU_PREFDL_CACHE_PATH):
         return None
      cpuPrefdl = self._readCachedPrefdl(self._CPU_PREFDL_CACHE_PATH)
      return Prefdls(switchPrefdl, cpuPrefdl)

   def _readPrefdl(self):
      lp = f'{self.__class__.__name__}(Dmi)'

      cached = self._readCachedPrefdls()
      if cached:
         logging.debug('%s: loaded prefdls from cache', lp)
         self._prefdls = cached
         return

      logging.debug('%s: looking for prefdl in DMI tables', lp)
      try:
         dmiPrefdl = readSystemPrefdlViaDmi()
      except PermissionError as e:
         raise PermissionError(
            e.errno,
            f'{lp}: reading DMI requires root privileges; '
            f'ensure a root service (e.g. arista setup) has run first '
            f'to populate the identity cache',
            e.filename) from None
      if not dmiPrefdl:
         raise UnknownPlatformError(f'{lp}: DMI prefdl not available')

      sid = dmiPrefdl.get('SID')
      platformNames = _readCpuPlatformNamesViaDmi()
      logging.debug('%s: looking for cpu matching %s or %s', lp, sid,
                    platformNames)
      found = None
      for cpu in self._manager.cpus:
         if cpu.SID and sid in cpu.SID:
            found = cpu
            break
         if cpu.PLATFORM in platformNames:
            found = cpu
            break

      if found is not None:
         logging.debug('%s: found matching cpu definition %s', lp, found)
         switchPrefdl = self._readSwitchEeprom(found, lp)
         cpuPrefdl = dmiPrefdl
         self._writePrefdlCacheFile(cpuPrefdl, self._CPU_PREFDL_CACHE_PATH)
      else:
         logging.debug('%s: assuming switch eeprom for %s', lp, sid)
         switchPrefdl = dmiPrefdl
         cpuPrefdl = None
         self._createEmptyMarkerFile(self._CPU_PREFDL_CACHE_PATH)

      self._writePrefdlCacheFile(switchPrefdl)
      self._prefdls = Prefdls(switchPrefdl, cpuPrefdl)

   @property
   def concatSid(self) -> Optional[str]:
      cpuSid = self.cpueeprom and self.cpueeprom.get('SID')
      switchSid = self.syseeprom.get('SID')
      if cpuSid and switchSid:
         return cpuSid + switchSid
      return switchSid

   @property
   def sid(self) -> Optional[str]:
      return self.concatSid

   @property
   def sku(self) -> Optional[str]:
      raise NotImplementedError('sku is not supported in DMI identification path')

   @property
   def platform(self) -> Optional[str]:
      raise NotImplementedError(
         'platform is not supported in DMI identification path')
