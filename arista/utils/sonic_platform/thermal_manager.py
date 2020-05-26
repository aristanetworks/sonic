#!/usr/bin/env python

from __future__ import print_function

try:
   from arista.utils.sonic_platform.thermal_action import *
   from arista.utils.sonic_platform.thermal_condition import *
   from arista.utils.sonic_platform.thermal_info import *
   from sonic_platform_base.sonic_thermal_control.thermal_manager_base \
      import ThermalManagerBase
except ImportError as e:
   raise ImportError("%s - required module not found" % e)

class ThermalManager(ThermalManagerBase):
   """
   Manager for controlling thermal policies.
   """
   pass
