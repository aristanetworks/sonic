#!/usr/bin/env python

from __future__ import print_function

try:
   from sonic_platform_base.sonic_thermal_control.thermal_action_base \
      import ThermalPolicyActionBase
   from sonic_platform_base.sonic_thermal_control.thermal_json_object \
      import thermal_json_object
except ImportError as e:
   raise ImportError("%s - required module not found" % e)

class ThermalPolicyAction(ThermalPolicyActionBase):
   """
   A thermal policy action to execute
   """
   pass

class SetFanSpeedAction(ThermalPolicyAction):
   JSON_FIELD_SPEED = "speed"

   def __init__(self):
      self.speed = None

   def load_from_json(self, json_obj):
      if self.JSON_FIELD_SPEED in json_obj:
         self.speed = float(json_obj[self.JSON_FIELD_SPEED])
      else:
         raise ValueError("SetFanSpeedAction missing field in json file")

@thermal_json_object("fan.all.set_speed")
class SetFanSpeedAllAction(SetFanSpeedAction):
   def execute(self, thermal_info_dict):
      for fan in thermal_info_dict['fan_info'].fans.values():
         fan.set_speed(self.speed)

@thermal_json_object("thermal_control.control")
class ThermalControlAction(ThermalPolicyAction):
   def execute(self, thermal_info_dict):
      sensorsToFanSpeed = thermal_info_dict['control_info'].sensorsToFanSpeed
      fanSpeed = sensorsToFanSpeed(
            thermal_info_dict['thermal_info'].thermals.values())
      for fan in thermal_info_dict['fan_info'].fans.values():
         fan.set_speed(fanSpeed)
