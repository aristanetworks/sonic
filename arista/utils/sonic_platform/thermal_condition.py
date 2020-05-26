#!/usr/bin/env python

from __future__ import print_function

try:
   from sonic_platform_base.sonic_thermal_control.thermal_condition_base \
      import ThermalPolicyConditionBase
   from sonic_platform_base.sonic_thermal_control.thermal_json_object \
      import thermal_json_object
except ImportError as e:
   raise ImportError("%s - required module not found" % e)

class ThermalPolicyCondition(ThermalPolicyConditionBase):
   """
   Policy conditions to be matched by chassis info
   """
   pass

@thermal_json_object("thermal.any.critical")
class ThermalAnyCriticalCondition(ThermalPolicyCondition):
   def is_match(self, thermal_info_dict):
      return any(thermal_info_dict['thermal_info'].thermals_critical.values())

@thermal_json_object("thermal.any.overheat")
class ThermalAnyOverheatCondition(ThermalPolicyCondition):
   def is_match(self, thermal_info_dict):
      return any(thermal_info_dict['thermal_info'].thermals_overheat.values())

@thermal_json_object("fan.any.absent")
class FanAnyAbsentCondition(ThermalPolicyCondition):
   def is_match(self, thermal_info_dict):
      return not all(thermal_info_dict['fan_info'].fans_presence.values())

@thermal_json_object("fan.any.fault")
class FanAnyFaultCondition(ThermalPolicyCondition):
   def is_match(self, thermal_info_dict):
      return not all(thermal_info_dict['fan_info'].fans_status.values())

@thermal_json_object("normal")
class NormalCondition(ThermalPolicyCondition):
   def is_match(self, thermal_info_dict):
      return True
