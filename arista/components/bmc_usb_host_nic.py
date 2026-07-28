
import os
import subprocess

from ..core.log import getLogger
from ..core.utils import inSimulation

from .nic import Nic

logging = getLogger(__name__)

class BmcUsbHostNic(Nic):
   """CPU side — USB host NIC.

   The USB host interface appears automatically when the BMC gadget enumerates.
   setup() is a no-op; configure() waits for the interface, renames it and
   assigns an IP address.
   """

   KERNEL_IFACE = 'usb0'
   WAIT_TIMEOUT = 20

   def configure(self, ifName, addr, prefixLen):
      if inSimulation():
         logging.debug('%s: simulation, skipping configure', self)
         return

      if os.path.exists('/sys/class/net/%s' % ifName):
         logging.debug('%s: %s already exists, re-assigning address', self, ifName)
         self.assignAddr(ifName, addr, prefixLen)
         return

      self.waitForInterface(self.KERNEL_IFACE)

      if ifName != self.KERNEL_IFACE:
         self.renameInterface(self.KERNEL_IFACE, ifName)

      self.assignAddr(ifName, addr, prefixLen)
      logging.info('%s: configured %s with %s/%d', self, ifName, addr, prefixLen)

   def unconfigure(self, ifName):
      if inSimulation():
         logging.debug('%s: simulation, skipping unconfigure', self)
         return

      if not os.path.exists('/sys/class/net/%s' % ifName):
         logging.debug('%s: %s not found, nothing to unconfigure', self, ifName)
         return

      subprocess.check_call(['ip', 'address', 'flush', 'dev', ifName])
      subprocess.check_call(['ip', 'link', 'set', ifName, 'down'])
      if ifName != self.KERNEL_IFACE:
         self.renameInterface(ifName, self.KERNEL_IFACE)
      logging.info('%s: unconfigured %s', self, ifName)
