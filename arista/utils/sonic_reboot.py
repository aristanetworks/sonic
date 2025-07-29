"""
This file provides the functionality to perform a powercycle on a platform.

Each platform has possibly different places we need to write to in order to perform
a powercycle, so the exact operations are abstracted by the other files, this simply
calls the function to perform the powercycle.
"""

from __future__ import print_function

import traceback

from arista.core.log import LoggerError, getLogger, setupLogging
from arista.core.config import Config
from arista.core.platform import getPlatform
from arista.core.supervisor import Supervisor
from arista.core.utils import klog
from arista.libs.procfs import inKdump

logging = getLogger(__name__)

def powerOffCards(platform):
   """Power off linecards and fabric cards before rebooting supervisor.

   This ensures linecards are not running with inconsistent state, e.g., if ARP requests
   come in while the supervisor is down."""
   if not isinstance(platform, Supervisor):
      return
   if inKdump():
      print('Not shutting down linecards on kdump kernel')
      return

   chassis = platform.getChassis()
   chassis.loadAll()
   if Config().power_off_linecard_on_reboot:
      chassis.powerOffLinecards()
   if Config().power_off_fabric_on_reboot:
      chassis.powerOffFabrics()

def do_reboot(platform=None):
   logging.info("Running powercycle script")
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
         powerCycle.ensureAvailable()
         powerCycle.powerCycle()
      except:
         klog("Failed to power cycle using %s" % powerCycle, level=0)
         klog(traceback.format_exc(), level=0)


def reboot(platform=None):
   try:
      setupLogging()
   except LoggerError as e:
      print(e.msg)

   do_reboot(platform)
