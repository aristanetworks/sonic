
from unittest.mock import MagicMock

from ...identity.base import PlatformIdentityBase, Prefdls
from ...identity.dmi import PlatformIdentityDmi
from ...identity.non_dmi import PlatformIdentityNonDmi
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

def makePrefdl(data):
   return Prefdl.fromDict(data)

def makeManager(cpus=None):
   mgr = MagicMock()
   mgr.cpus = cpus or []
   return mgr

def makeFakeCpu(sids, platform='fakecpu', switchPrefdl=None):
   cpu = MagicMock()
   cpu.SID = sids
   cpu.PLATFORM = platform
   cpu.readSwitchEeprom.return_value = switchPrefdl
   return cpu

def _makeIdentity(cls, switchData=None, cpuData=None, cmdline=None):
   identity = cls(makeManager(), cmdline=cmdline or {})
   switchPrefdl = makePrefdl(switchData or {})
   cpuPrefdl = makePrefdl(cpuData) if cpuData else None
   identity._prefdls = Prefdls(switchPrefdl, cpuPrefdl)  # pylint: disable=protected-access
   return identity

def makeBaseIdentity(switchData=None, cpuData=None):
   return _makeIdentity(PlatformIdentityBase, switchData, cpuData)

def makeNonDmiIdentity(switchData=None, cpuData=None, cmdline=None):
   return _makeIdentity(PlatformIdentityNonDmi, switchData, cpuData, cmdline)

def makeDmiIdentity(switchData=None, cpuData=None):
   return _makeIdentity(PlatformIdentityDmi, switchData, cpuData)
