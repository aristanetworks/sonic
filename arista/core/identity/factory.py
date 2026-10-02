from ..utils import getCmdlineDict, isBmcEnvironment

from .bmc import PlatformIdentityBmc
from .dmi import PlatformIdentityDmi
from .non_dmi import PlatformIdentityNonDmi


def createPlatformIdentity(cmdline=None):
   if cmdline is None:
      cmdline = getCmdlineDict()
   if isBmcEnvironment():
      return PlatformIdentityBmc(cmdline=cmdline)
   if cmdline.get('arista.identify_dmi') == '1':
      return PlatformIdentityDmi(cmdline=cmdline)
   return PlatformIdentityNonDmi(cmdline=cmdline)
