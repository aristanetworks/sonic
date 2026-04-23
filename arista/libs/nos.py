import os.path

from .docker import runningInContainer
from .onie import getPlatformName

def getSonicPlatformPath():
   if runningInContainer():
      return "/usr/share/sonic/platform"

   platform = getPlatformName()
   if platform is not None:
      return os.path.join("/usr/share/sonic/device/", platform)

   return None

def getPlatformPath():
   return getSonicPlatformPath()
