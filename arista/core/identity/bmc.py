from typing import Optional

from ..exception import UnknownPlatformError
from ..prerequisites import loadPrerequisites
from ..utils import readBmcDeviceTreeModel

from .base import PlatformIdentityBase, Prefdls


class PlatformIdentityBmc(PlatformIdentityBase):
   # BMC identity does not expose a CPU EEPROM yet. Existing BMC consumers
   # fetch it directly through BmcSubsystem.cpuEeprom. Identification does
   # not need it because the chassis EEPROM is directly accessible.
   def __init__(self, *args, **kwargs):
      super().__init__(*args, **kwargs)
      self._model = None

   def _readPrefdl(self):
      model = readBmcDeviceTreeModel()
      bmcCls = self._manager.bmcIndex.get(model)
      if bmcCls is None:
         supportedModels = ', '.join(sorted(self._manager.bmcIndex))
         raise UnknownPlatformError(
            f'BMC model {model!r} is not registered; supported BMC models: '
            f'{supportedModels}')

      loadPrerequisites()
      self._model = model
      # readChassisEeprom() owns caching for BMC chassis EEPROM reads.
      self._prefdls = Prefdls(bmcCls.readChassisEeprom(), None)

   def getPlatformCls(self, name=None):
      if name is not None:
         raise UnknownPlatformError(
            f'BMC platform identification does not accept name={name!r}')

      sid = self.syseeprom.get('SID')
      if not sid:
         raise UnknownPlatformError(
            f'BMC model {self._model!r} has an empty SID in its chassis EEPROM')

      platformCls = self._manager.bmcSubsystemIndex.get((self._model, sid))
      if platformCls is None:
         raise UnknownPlatformError(
            f'No BMC subsystem is registered for model {self._model!r} '
            f'and SID {sid!r}')
      return platformCls

   @property
   def sid(self) -> Optional[str]:
      return self.syseeprom.get('SID')

   @property
   def sku(self) -> Optional[str]:
      raise NotImplementedError('sku is not supported in BMC identification path')

   @property
   def platform(self) -> Optional[str]:
      raise NotImplementedError(
         'platform is not supported in BMC identification path')
