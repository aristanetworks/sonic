#!/usr/bin/env python

from __future__ import print_function

try:
   from sonic_platform_base.watchdog_base import WatchdogBase
except ImportError as e:
   raise ImportError("%s - required module not found" % e)

class Watchdog(WatchdogBase):
   """
   Platform-specific watchdog class for interfacing with a hardware watchdog module
   """

   def __init__(self, watchdog):
      self._watchdog = watchdog

   def get_name(self):
      return "watchdog"

   def get_model(self):
      return "N/A"

   def get_presence(self):
      return True

   def get_serial(self):
      return "N/A"

   def get_status(self):
      return True

   def get_position_in_parent(self):
      return -1

   def is_replaceable(self):
      return False

   def arm(self, seconds):
      if not self._watchdog.arm(seconds * 100):
         return -1
      return seconds

   def disarm(self):
      return self._watchdog.stop()

   def get_remaining_time(self):
      remainingTime = self._watchdog.status()['remainingTime']
      if remainingTime != -1:
         remainingTime //= 100
      return remainingTime

   def is_armed(self):
      return self._watchdog.status()['enabled']
