#!/usr/bin/env python

from __future__ import print_function

try:
   from sonic_platform_base.psu_base import PsuBase
except ImportError as e:
   raise ImportError("%s - required module not found" % e)

class Psu(PsuBase):
   """
   Platform-specific PSU class

   Unimplemented methods:
   - get_model
   - get_serial
   - get_voltage
   - get_current
   - get_power
   """

   def __init__(self, psu):
      self._psu = psu
      super(Psu, self).__init__()

   def get_id(self):
      return self._psu.getId()

   def get_name(self):
      return self._psu.getName()

   def set_status_led(self, color):
      try:
         self._psu.getLed().setColor(color)
      except (IOError, OSError, ValueError):
         return False
      return True

   def get_status_led(self, color=None):
      try:
         c = self._psu.getLed().getColor();
      except (IOError, OSError, ValueError):
         return False
      return c == color if color else c != 'off'

   def get_status(self):
      return self._psu.getStatus()

   def get_presence(self):
      return self._psu.getPresence()

   def get_powergood_status(self):
      return self.get_status()

   def get_interrupt_file(self):
      return None
