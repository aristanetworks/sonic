
from unittest.mock import MagicMock

from ...identity.dmi import _Prefdls, PlatformIdentityDmi
from ...identity.non_dmi import PlatformIdentityNonDmi
from ...platform_loader import _Loader
from ...prefdl import Prefdl

PREFDL_DATA = {
   'SID': 'TestProduct',
   'SKU': 'DCS-TEST-42',
   'HwApi': '02.00',
}

CPU_PREFDL_DATA = {
   'SID': 'CpuBoard',
   'SKU': 'CPU-TEST',
}

SWITCH_PREFDL_DATA = {
   'SID': 'SwitchBoard',
   'SKU': 'DCS-SWITCH-42',
}

class DummyLoader(_Loader):
   def __init__(self):
      super().__init__()
      for index in self._indexes():
         index._descriptors = {}  # setting descriptors prevents registry loading

   def _discover_all(self):
      pass

def makePrefdl(data):
   return Prefdl.fromDict(data)

def makeFakeCpu(sids, platform='fakecpu', switchPrefdl=None):
   cpu = MagicMock()
   cpu.SID = sids
   cpu.PLATFORM = platform
   cpu.readSwitchEeprom.return_value = switchPrefdl
   return cpu

def makeNonDmiIdentity(switchData=None, cmdline=None):
   identity = PlatformIdentityNonDmi(cmdline=cmdline or {})
   identity._prefdl = makePrefdl(switchData or {})  # pylint: disable=protected-access
   return identity

def makeDmiIdentity(switchData=None, cpuData=None):
   identity = PlatformIdentityDmi(cmdline={})
   switchPrefdl = makePrefdl(switchData or {})
   cpuPrefdl = makePrefdl(cpuData) if cpuData else None
   identity._prefdls = _Prefdls(switchPrefdl, cpuPrefdl)  # pylint: disable=protected-access
   return identity
