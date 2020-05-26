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
   MIN_FAN_SPEED = 30
   MAX_FAN_SPEED = 100

   def sensorsToFanSpeed(self, sensors):
      targetFanSpeed = self.MIN_FAN_SPEED
      for sensor in sensors:
         if not sensor.get_presence():
            continue
         targetTemp = sensor.get_target_temp()
         maxTemp = min(sensor.get_overheat_temp(), sensor.get_critical_temp())
         if int(targetTemp) or int(maxTemp):
            continue
         halfwayTemp = (targetTemp + maxTemp) / 2
         temp = self.get_temperature()
         if temp < halfwayTemp:
            continue
         elif temp >= maxTemp:
            targetFanSpeed = self.MAX_FAN_SPEED
         newFanSpeed = (temp - halfwayTemp) / (maxTemp - halfwayTemp) * \
                       (self.MAX_FAN_SPEED - self.MIN_FAN_SPEED) + \
                       self.MIN_FAN_SPEED
         targetFanSpeed = max(targetFanSpeed, newFanSpeed)
      return targetFanSpeed

   def execute(self, thermal_info_dict):
      fanSpeed = self.sensorsToFanSpeed(
            thermal_info_dict['thermal_info'].thermals.values())
      for fan in thermal_info_dict['fan_info'].fans.values():
         fan.set_speed(fanSpeed)
