from functools import cached_property
from typing import Optional

from ..exception import UnknownPlatformError
from ..prerequisites import loadPrerequisites
from ..prefdl import Prefdl
from ..utils import readBmcDeviceTreeModel

from .base import PlatformIdentityBase


class PlatformIdentityBmc(PlatformIdentityBase):
   # BMC identity does not expose a CPU EEPROM yet. Existing BMC consumers
   # fetch it directly through BmcSubsystem.cpuEeprom. Identification does
   # not need it because the chassis EEPROM is directly accessible.
   def __init__(self, *args, **kwargs):
      super().__init__(*args, **kwargs)
      self._model = None

   # readChassisEeprom() owns the tmpfs cache; identity retains its result
   # in memory and reads the EEPROM only when requested.
   @cached_property
   def _chassisPrefdl(self) -> Prefdl:
      return self._bmcCls.readChassisEeprom()

   @property
   def syseeprom(self) -> Prefdl:
      return self._chassisPrefdl

   @cached_property
   def _bmcCls(self):
      model = readBmcDeviceTreeModel()
      bmcCls = self._loader.bmcs.get(model)
      if bmcCls is None:
         supportedModels = ', '.join(sorted(self._loader.bmcs.keys()))
         raise UnknownPlatformError(
            f'BMC model {model!r} is not registered; supported BMC models: '
            f'{supportedModels}')

      loadPrerequisites()
      self._model = model
      return bmcCls

   def getPlatformCls(self, name=None):
      if name is not None:
         raise UnknownPlatformError(
            f'BMC platform identification does not accept name={name!r}')

      sid = self.sid
      if not sid:
         raise UnknownPlatformError(
            f'BMC model {self._model!r} has an empty SID in its chassis EEPROM')

      platformCls = self._loader.bmc_subsystems.get((self._model, sid))
      if platformCls is None:
         raise UnknownPlatformError(
            f'No BMC subsystem is registered for model {self._model!r} '
            f'and SID {sid!r}')
      return platformCls

   @property
   def sid(self) -> Optional[str]:
      return self._chassisPrefdl.get('SID')

   @property
   def sku(self) -> Optional[str]:
      raise NotImplementedError('sku is not supported in BMC identification path')

   @property
   def platform(self) -> Optional[str]:
      raise NotImplementedError(
         'platform is not supported in BMC identification path')
