import os
import tempfile
from dataclasses import dataclass
from typing import Optional

from ..log import getLogger
from ..prefdl import Prefdl
from ..utils import getCmdlineDict

logging = getLogger(__name__)

@dataclass
class Prefdls:
   switch: Prefdl
   cpu: Optional[Prefdl]

class PlatformIdentityBase:
   _PREFDL_CACHE_PATH: Optional[str] = None
   def __init__(self, manager: 'PlatformManager',
                cmdline: Optional[dict[str, Optional[str]]] = None):
      self._manager = manager
      self._cmdline = getCmdlineDict() if cmdline is None else cmdline
      self._prefdls = None

   @property
   def _initialized(self):
      return self._prefdls is not None

   def _readCachedPrefdl(self,
                         cachePath: Optional[str] = None) -> Optional[Prefdl]:
      cacheFilePath = cachePath or self._PREFDL_CACHE_PATH
      assert cacheFilePath
      if (os.path.isfile(cacheFilePath) and
          os.path.getsize(cacheFilePath) > 0):
         logging.debug('reading cached system eeprom from %s', cacheFilePath)
         return Prefdl.fromTextFile(cacheFilePath)
      return None

   def _writePrefdlCacheFile(self, prefdl: Prefdl,
                             cachePath: Optional[str] = None) -> None:
      cacheFilePath = cachePath or self._PREFDL_CACHE_PATH
      assert cacheFilePath
      parentDir = os.path.dirname(cacheFilePath)
      os.makedirs(parentDir, exist_ok=True)
      fd, tmpFilePath = tempfile.mkstemp(
            dir=parentDir)
      os.close(fd)
      prefdl.writeToFile(tmpFilePath)
      os.chmod(tmpFilePath, 0o644)
      os.replace(tmpFilePath, cacheFilePath)

   def _readPrefdl(self):
      raise NotImplementedError

   @property
   def syseeprom(self) -> Prefdl:
      if not self._initialized:
         self._readPrefdl()
      return self._prefdls.switch

   @property
   def cpueeprom(self) -> Optional[Prefdl]:
      if not self._initialized:
         self._readPrefdl()
      return self._prefdls.cpu

   @property
   def sid(self) -> Optional[str]:
      raise NotImplementedError

   @property
   def sku(self) -> Optional[str]:
      raise NotImplementedError

   @property
   def platform(self) -> Optional[str]:
      raise NotImplementedError

   @property
   def hwApi(self) -> Optional[tuple[int, int]]:
      return self.syseeprom.get('HwApi')
