import os
import tempfile
from typing import Optional

from arista.core.platform_loader import platform_loader
from ..log import getLogger
from ..prefdl import Prefdl
from ..utils import getCmdlineDict

logging = getLogger(__name__)

class PlatformIdentityBase:
   _PREFDL_CACHE_PATH: Optional[str] = None

   _loader = platform_loader  # overridable in tests

   def __init__(self, cmdline: Optional[dict[str, Optional[str]]] = None):
      self._cmdline = getCmdlineDict() if cmdline is None else cmdline

   def _readCachedPrefdl(self,
                         cachePath: Optional[str] = None) -> Optional[Prefdl]:
      cacheFilePath = cachePath or self._PREFDL_CACHE_PATH
      assert cacheFilePath
      if (os.path.isfile(cacheFilePath) and
          os.path.getsize(cacheFilePath) > 0):
         logging.debug('reading cached prefdl from %s', cacheFilePath)
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

   @property
   def syseeprom(self) -> Prefdl:
      raise NotImplementedError

   @property
   def cpueeprom(self) -> Optional[Prefdl]:
      return None

   @property
   def sid(self) -> Optional[str]:
      raise NotImplementedError

   @property
   def sku(self) -> Optional[str]:
      raise NotImplementedError

   @property
   def platform(self) -> Optional[str]:
      raise NotImplementedError
