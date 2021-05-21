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

   def __init__(self, index, temp):
      ThermalBase.__init__(self)
      self._index = index
      self._temp = temp
      self._minimum = None
      self._maximum = None

   def get_name(self):
      return self._temp.getName()

   def get_presence(self):
      return self._temp.getPresence()

   def get_model(self):
      return self._temp.getModel()

   def get_serial(self):
      return "N/A"

   def get_status(self):
      return True

   def get_position_in_parent(self):
      return self._index

   def is_replaceable(self):
      return False

   def get_interrupt_file(self):
      return None

   def get_temperature(self):
      value = self._temp.getTemperature()
      if self._minimum is None or self._minimum > value:
         self._minimum = value
      if self._maximum is None or self._maximum < value:
         self._maximum = value
      return value

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

   def get_low_critical_threshold(self):
      return self._temp.getLowCriticalThreshold()

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

   def get_high_critical_threshold(self):
      return self._temp.getHighCriticalThreshold()

   def get_minimum_recorded(self):
      if self._minimum is None:
         self.get_temperature()
      return self._minimum

   def get_maximum_recorded(self):
      if self._maximum is None:
         self.get_temperature()
      return self._maximum

   def get_inventory_object(self):
      return self._temp
