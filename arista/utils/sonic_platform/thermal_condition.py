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
      thermals = thermal_info_dict['thermal_info'].thermals.values()
      return any(t.in_critical_condition for t in thermals)

@thermal_json_object("thermal.any.overheat")
class ThermalAnyOverheatCondition(ThermalPolicyCondition):
   def is_match(self, thermal_info_dict):
      thermals = thermal_info_dict['thermal_info'].thermals.values()
      return any(t.in_overheat_condition for t in thermals)

@thermal_json_object("thermal.all.normal")
class ThermalAllNormalCondition(ThermalPolicyCondition):
   def is_match(self, thermal_info_dict):
      thermals = thermal_info_dict['thermal_info'].thermals.values()
      return all(t.in_normal_condition for t in thermals)

@thermal_json_object("fan.any.absence")
class FanAnyAbsentCondition(ThermalPolicyCondition):
   def is_match(self, thermal_info_dict):
      fans = thermal_info_dict['fan_info'].fans.values()
      return not all(f.presence for f in fans)

@thermal_json_object("fan.all.presence")
class FanAllPresentCondition(ThermalPolicyCondition):
   def is_match(self, thermal_info_dict):
      fans = thermal_info_dict['fan_info'].fans.values()
      return all(f.presence for f in fans)

@thermal_json_object("fan.any.fault")
class FanAnyFaultCondition(ThermalPolicyCondition):
   def is_match(self, thermal_info_dict):
      fans = thermal_info_dict['fan_info'].fans.values()
      return not all(f.status for f in fans)

@thermal_json_object("fan.all.normal")
class FanAllNormalCondition(ThermalPolicyCondition):
   def is_match(self, thermal_info_dict):
      fans = thermal_info_dict['fan_info'].fans.values()
      return all(f.status for f in fans)

@thermal_json_object("psu.any.absence")
class PsuAnyAbsentCondition(ThermalPolicyCondition):
   def is_match(self, thermal_info_dict):
      psus = thermal_info_dict['psu_info'].psus.values()
      return not all(p.presence for p in psus)

@thermal_json_object("psu.all.presence")
class PsuAllPresenceCondition(ThermalPolicyCondition):
   def is_match(self, thermal_info_dict):
      psus = thermal_info_dict['psu_info'].psus.values()
      return all(p.presence for p in psus)

@thermal_json_object("psu.any.fault")
class PsuAnyFaultCondition(ThermalPolicyCondition):
   def is_match(self, thermal_info_dict):
      psus = thermal_info_dict['psu_info'].psus.values()
      return not all(p.status for p in psus)

@thermal_json_object("normal")
class NormalCondition(ThermalPolicyCondition):
   def is_match(self, thermal_info_dict):
      return True
