#!/usr/bin/env python

from __future__ import print_function

try:
   from sonic_platform_base.platform_base import PlatformBase
   import arista.platforms
   from arista.core.platform import getPlatform
   from arista.utils.sonic_platform.chassis import Chassis
except ImportError as e:
   raise ImportError("%s - required module not found" % e)

class Platform(PlatformBase):
   def __init__(self):
      self._platform = getPlatform()
      self._chassis = Chassis(self._platform)
