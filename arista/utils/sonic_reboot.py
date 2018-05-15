"""
This file provides the functionality to perform a powercycle on a platform.

Each platform has possibly different places we need to write to in order to perform
a powercycle, so the exact operations are abstracted by the other files, this simply
calls the function to perform the powercycle.
"""

from __future__ import print_function

from arista.core.platform import getPlatform

def reboot(platform=None):
   print("Running powercycle script")
   if not platform:
      platform = getPlatform()
   print("Powercycle for platform %s" % platform)
   for powerCycle in platform.getInventory().getPowerCycles():
      powerCycle.powerCycle()
