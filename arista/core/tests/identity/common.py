
from unittest.mock import MagicMock

from ...identity.base import Prefdls
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

def makePrefdl(data):
   return Prefdl.fromDict(data)

def makeManager(cpus=None):
   mgr = MagicMock()
   mgr.cpus = cpus or []
   return mgr

def makeIdentity(switchData=None, cpuData=None, cmdline=None):
   identity = PlatformIdentityNonDmi(makeManager(), cmdline=cmdline or {})
   switchPrefdl = makePrefdl(switchData or {})
   cpuPrefdl = makePrefdl(cpuData) if cpuData else None
   identity._prefdls = Prefdls(switchPrefdl, cpuPrefdl)  # pylint: disable=protected-access
   return identity
