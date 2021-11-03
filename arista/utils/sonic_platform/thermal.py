#!/usr/bin/env python

from __future__ import print_function

try:
   from arista.libs.python import monotonicRaw
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

   def get_revision(self):
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
      self.get_temperature()
      return self._minimum

   def get_maximum_recorded(self):
      self.get_temperature()
      return self._maximum

   def get_inventory_object(self):
      return self._temp

class SfpThermal(ThermalBase):
   THRESH_DELAY = 1 # 1 second

   def __init__(self, sfp):
      ThermalBase.__init__(self)
      self._sfp = sfp
      self._minimum = None
      self._maximum = None
      self._cachedThreshInfo = None
      self._cachedThreshInfoTime = 0

   def get_name(self):
      return "%s %s temp sensor" % (self._sfp.sfp_type, self._sfp.get_id())

   def get_presence(self):
      return self._sfp.get_presence()

   def get_model(self):
      return "N/A"

   def get_serial(self):
      return "N/A"

   def get_status(self):
      return self.get_temperature() is not None

   def get_position_in_parent(self):
      return 1

   def is_replaceable(self):
      return False

   def get_temperature(self):
      value = self._sfp.get_temperature()
      if value == 'N/A':
         raise NotImplementedError
      if self._minimum is None or self._minimum > value:
         self._minimum = value
      if self._maximum is None or self._maximum < value:
         self._maximum = value
      return value

   def _get_threshold_info(self):
      currTime = monotonicRaw()
      if currTime - self._cachedThreshInfoTime > self.THRESH_DELAY:
         self._cachedThreshInfoTime = currTime
         self._cachedThreshInfo = self._sfp.get_transceiver_threshold_info()
      return self._cachedThreshInfo

   def get_low_threshold(self):
      threshInfo = self._get_threshold_info()
      if threshInfo:
         lowThreshold = threshInfo.get("templowwarning")
      if not threshInfo or lowThreshold == "N/A":
         raise NotImplementedError
      return lowThreshold

   def set_low_threshold(self, temperature):
      return False

   def get_low_critical_threshold(self):
      threshInfo = self._get_threshold_info()
      if threshInfo:
         lowCritThreshold = threshInfo.get("templowalarm")
      if not threshInfo or lowCritThreshold == "N/A":
         raise NotImplementedError
      return lowCritThreshold

   def get_high_threshold(self):
      threshInfo = self._get_threshold_info()
      if threshInfo:
         highThreshold = threshInfo.get("temphighwarning")
      if not threshInfo or highThreshold == "N/A":
         raise NotImplementedError
      return highThreshold

   def set_high_threshold(self, temperature):
      return False

   def get_high_critical_threshold(self):
      threshInfo = self._get_threshold_info()
      if threshInfo:
         highCritThreshold = threshInfo.get("temphighalarm")
      if not threshInfo or highCritThreshold == "N/A":
         raise NotImplementedError
      return highCritThreshold

   def get_minimum_recorded(self):
      self.get_temperature()
      return self._minimum

   def get_maximum_recorded(self):
      self.get_temperature()
      return self._maximum
