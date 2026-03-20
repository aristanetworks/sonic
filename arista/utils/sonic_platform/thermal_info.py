#!/usr/bin/env python

try:
   from sonic_platform_base.sonic_thermal_control.thermal_info_base \
      import ThermalPolicyInfoBase
   from sonic_platform_base.sonic_thermal_control.thermal_json_object \
      import thermal_json_object
   from arista.core.cooling import CoolingAlgorithm
   from .thermal_helper import CoolingEntityManager
except ImportError as e:
   raise ImportError("%s - required module not found" % e)

class ThermalPolicyInfo(ThermalPolicyInfoBase):
   """
   Class for collecting chassis info to be fed to thermal policy
   """
   def collect(self, chassis):
      pass

@thermal_json_object("fan_info")
class FanInfo(ThermalPolicyInfo):
   def __init__(self):
      super().__init__()
      self.fans = {}

   def collect(self, chassis):
      self.fans = CoolingEntityManager.get(chassis).get_all_fans()
      for fan in self.fans.values():
         fan.update()

@thermal_json_object("thermal_info")
class ThermalInfo(ThermalPolicyInfo):
   def __init__(self):
      super().__init__()
      self.thermals = {}

   def collect(self, chassis):
      self.thermals = CoolingEntityManager.get(chassis).get_all_thermals()
      for thermal in self.thermals.values():
         thermal.update()

@thermal_json_object("psu_info")
class PsuInfo(ThermalPolicyInfo):
   def __init__(self):
      super().__init__()
      self.psus = None

   def collect(self, chassis):
      self.psus = CoolingEntityManager.get(chassis).get_all_psus()
      for psu in self.psus.values():
         psu.update()

@thermal_json_object("control_info")
class ControlInfo(ThermalPolicyInfo):
   def __init__(self):
      super().__init__()
      self.algo = None

   def collect(self, chassis):
      if self.algo is None:
         self.algo = CoolingAlgorithm(chassis.getPlatform())
      CoolingEntityManager.get(chassis).gc()

@thermal_json_object("chassis_info")
class ChassisInfo(ControlInfo):
   pass
