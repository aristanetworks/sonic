#!/usr/bin/env python

from __future__ import print_function

try:
   from sonic_platform_base.psu_base import PsuBase
except ImportError as e:
   raise ImportError("%s - required module not found" % e)

from .fan import Fan
from .thermal import Thermal

class Psu(PsuBase):
   """
   Platform-specific PSU class
   """

   def __init__(self, slot):
      PsuBase.__init__(self)
      self._slot = slot
      self._psu = None
      self._compute_psu()

   def _compute_psu(self):
      old = self._psu
      if self._psu is None:
         self._psu = self._slot.getPsu()
      else:
         # TODO: handle PSU hotswap
         pass
      if self._psu != old:
         self._fan_list = [Fan(self, f) for f in self._psu.getFans()]
         self._thermal_list = [Thermal(i + 1, t) for i, t in enumerate(self._psu.getTemps())]

   @property
   def psu(self):
      self._compute_psu()
      return self._psu

   @property
   def rail(self):
      if self.psu is None:
         return None
      rails = self.psu.psu.getInventory().getRails()
      return rails[1] if rails else None

   @property
   def input_rail(self):
      if self.psu is None:
         return None
      rails = self.psu.psu.getInventory().getRails()
      return rails[0] if rails else None

   def get_id(self):
      return self._slot.getId()

   def get_name(self):
      return self._slot.getName()

   def get_model(self):
      psu = self.psu
      return psu.getModel() if psu else "N/A"

   def get_revision(self):
      psu = self.psu
      return psu.getRevision().replace('\x00', '') if psu else "N/A"

   def get_serial(self):
      psu = self.psu
      return psu.getSerial().replace('\x00', '') if psu else "N/A"

   def get_status(self):
      # TODO: check status of power supply itself
      return self._slot.getStatus()

   def get_presence(self):
      return self._slot.getPresence()

   def get_position_in_parent(self):
      return self._slot.getId()

   def is_replaceable(self):
      return True

   def get_voltage(self):
      rail = self.rail
      return round(rail.getVoltage(), 3) if rail else None

   def get_current(self):
      rail = self.rail
      if not rail:
         return None
      power = self.get_power()
      current = rail.getCurrent()
      # Zero power means zero current (filters leakage and sensor noise)
      if power is None or abs(power) < 1.0:  # Less than 1Watt
         return 0.0
      return round(current, 3)

   def get_power(self):
      rail = self.rail
      return round(rail.getPower(), 3) if rail else None

   def get_input_voltage(self):
      rail = self.input_rail
      return round(rail.getVoltage(), 3) if rail else None

   def get_input_current(self):
      rail = self.input_rail
      return round(rail.getCurrent(), 3) if rail else None

   # TODO: thresholds

   def get_powergood_status(self):
      return self.get_status()

   def set_status_led(self, color):
      led = self._slot.getLed()
      if led is None:
         return True
      try:
         led.setColor(color)
      except Exception: # pylint: disable=broad-except
         return False
      return True

   def get_status_led(self, color=None):
      # TODO: remove color= argument
      led = self._slot.getLed()
      if led is None:
         if self.get_status():
            return self.STATUS_LED_COLOR_GREEN
         return self.STATUS_LED_COLOR_RED
      try:
         return led.getColor()
      except Exception: # pylint: disable=broad-except
         return self.STATUS_LED_COLOR_OFF

   # NOTE the methods below should be deprecated by the of use get_all_thermals()
   #      in the sonic daemons but it's not the case today.
   #      use a dumb policy of taking the first sensor
   def get_temperature(self):
      if not self.get_num_thermals():
         return 'N/A'
      return self.get_thermal(0).get_temperature()

   def get_temperature_high_threshold(self):
      if not self.get_num_thermals():
         return 'N/A'
      return self.get_thermal(0).get_high_threshold()

   def get_voltage_high_threshold(self):
      rail = self.rail
      return rail.voltage.getHighThreshold() if rail else None

   def get_voltage_low_threshold(self):
      rail = self.rail
      return rail.voltage.getLowThreshold() if rail else None

   def get_interrupt_file(self):
      return None

   def get_maximum_supplied_power(self):
      psu = self._slot.getPsu()
      return float(psu.getCapacity()) if psu else 0.
