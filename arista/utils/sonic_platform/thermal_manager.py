#!/usr/bin/env python

try:
   from arista.core.config import Config
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
   # override default interval of 60 by 10
   _interval = Config().cooling_loop_interval
