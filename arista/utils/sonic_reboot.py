"""
This file provides the functionality to perform a powercycle on a platform.

Each platform has possibly different places we need to write to in order to perform
a powercycle, so the exact operations are abstracted by the other files, this simply
calls the function to perform the powercycle.
"""

from __future__ import print_function

import traceback

from arista.core.card import Card
from arista.core.config import Config
from arista.core.linecard import LCpuCtx
from arista.core.platform import getPlatform
from arista.core.supervisor import Supervisor
from arista.core.utils import klog
from .sonic_utils import getInventory

def powerOffLinecards(chassis):
   for linecard in chassis.iterLinecards():
      try:
         print('Power off linecard %s...' % linecard, end='')
         if linecard.slot.getPresence():
            linecard.powerOnIs(False)
            print('SUCCESS')
         else:
            print('(not present)')
      except:
         print('FAILED')
         klog('Failed to power off linecard %s' % linecard, level=0)
         klog(traceback.format_exc(), level=0)

def powerOffFabrics(chassis):
   for fabric in chassis.iterFabrics():
      try:
         print('Power off fabric card %s...' % fabric, end='')
         if fabric.slot.getPresence():
            fabric.powerOnIs(False)
            print('SUCCESS')
         else:
            print('(not present)')
      except:
         print('FAILED')
         klog('Failed to power off fabric %s' % fabric, level=0)
         klog(traceback.format_exc(), level=0)

def powerOffCards(platform):
   """Power off linecards and fabric cards before rebooting supervisor.

   This ensures linecards are not running with inconsistent state, e.g., if ARP requests
   come in while the supervisor is down."""
   if not isinstance(platform, Supervisor):
      return

   chassis = platform.getChassis()
   chassis.loadAll()
   if Config().power_off_linecard_on_reboot:
      powerOffLinecards(chassis)
   if Config().power_off_fabric_on_reboot:
      powerOffFabrics(chassis)

def reboot(platform=None):
   print("Running powercycle script")
   platform = platform or getPlatform()
   inventory = platform.getInventory()

   powerOffCards(platform)

   powerCycles = inventory.getPowerCycles()
   if not powerCycles:
      print("No objects to perform powercycle with on this platform")
      return
   klog("Restarting system", level=0)
   for powerCycle in powerCycles:
      try:
         powerCycle.powerCycle()
      except:
         klog("Failed to power cycle using %s" % powerCycle, level=0)
         klog(traceback.format_exc(), level=0)
