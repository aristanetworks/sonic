#!/usr/bin/env python

from __future__ import print_function

try:
   from sonic_platform_base.thermal_base import ThermalBase
except ImportError as e:
   raise ImportError("%s - required module not found" % e)

class Thermal(ThermalBase):
   """
   Platform-specific class for interfacing with a thermal module
   """

   def __init__(self, temp):
      self._temp = temp

   def get_name(self):
      return self._temp.getName()

   def get_presence(self):
      return self._temp.getPresence()

   def get_interrupt_file(self):
      return None

   def get_temperature(self):
      return self._temp.getTemperature()

   def get_low_threshold(self):
      try:
         return self._temp.getLowThreshold()
      except (IOError, OSError, ValueError):
         # thermalctld expects NotImplementedError
         raise NotImplementedError

   def set_low_threshold(self, temperature):
      try:
         self._temp.setLowThreshold(temperature)
         return True
      except (IOError, OSError, ValueError):
         return False

   def get_high_threshold(self):
      try:
         return self._temp.getHighThreshold()
      except (IOError, OSError, ValueError):
         # thermalctld expects NotImplementedError
         raise NotImplementedError

   def set_high_threshold(self, temperature):
      try:
         self._temp.setHighThreshold(temperature)
         return True
      except (IOError, OSError, ValueError):
         return False

   def get_target_temp(self):
      return self._temp.getTargetTemp()

   def get_overheat_temp(self):
      return self._temp.getOverheatTemp()

   def get_critical_temp(self):
      return self._temp.getCriticalTemp()

   def sensor_overheat(self):
      return self._temp.isSensorOverheat()

   def sensor_critical(self):
      return self._temp.isSensorCritical()
