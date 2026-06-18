from ..utils import getCmdlineDict, isBmcEnvironment

from .bmc import PlatformIdentityBmc
from .non_dmi import PlatformIdentityNonDmi


def createPlatformIdentity(manager, cmdline=None):
   if cmdline is None:
      cmdline = getCmdlineDict()
   if isBmcEnvironment():
      return PlatformIdentityBmc(manager, cmdline=cmdline)
   return PlatformIdentityNonDmi(manager, cmdline=cmdline)
