#!/usr/bin/env python

from __future__ import print_function

try:
   from sonic_platform_base.watchdog_base import WatchdogBase
except ImportError as e:
   raise ImportError("%s - required module not found" % e)

class Watchdog(WatchdogBase):
   """
   Platform-specific watchdog class for interfacing with a hardware watchdog module

   Unimplemented methods:
   - get_name
   - get_presence
   - get_model
   - get_serial
   - get_status
   - get_remaining_time
   """

   def __init__(self, watchdog):
      self._watchdog = watchdog

   def arm(self, seconds):
      if not self._watchdog.arm(seconds * 100):
         return -1
      return seconds

   def disarm(self):
      return self._watchdog.stop()

   def is_armed(self):
      return self._watchdog.status()['enabled']
