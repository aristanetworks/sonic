
import subprocess

from ..core.component.component import Component
from ..core.log import getLogger
from ..libs.wait import waitForPath

logging = getLogger(__name__)

class Nic(Component):
   """Base NIC component. Subclass for specific NIC types."""

   WAIT_TIMEOUT = 10

   def configure(self, ifName, addr, prefixLen):
      raise NotImplementedError

   def unconfigure(self, ifName):
      raise NotImplementedError

   def waitForInterface(self, ifName):
      waitForPath('/sys/class/net/%s' % ifName, timeout=self.WAIT_TIMEOUT,
                  interval=500)

   def renameInterface(self, oldName, newName):
      subprocess.check_call(['ip', 'link', 'set', oldName, 'down'])
      subprocess.check_call(['ip', 'link', 'set', oldName, 'name', newName])

   def assignAddr(self, ifName, addr, prefixLen):
      subprocess.check_call(['ip', 'address', 'flush', 'dev', ifName])
      subprocess.check_call(['ip', 'link', 'set', ifName, 'up'])
      subprocess.check_call(
         ['ip', 'address', 'add', f'{addr}/{prefixLen:d}', 'dev', ifName])

   def getConfiguredMac(self, ifName):
      with open(f'/sys/class/net/{ifName}/address', encoding='utf-8') as f:
         return f.read().strip()

   def isAdminUp(self, ifName):
      with open(f'/sys/class/net/{ifName}/flags', encoding='utf-8') as f:
         flags = int(f.read().strip(), 16)
      return bool(flags & 0x1)  # IFF_UP

   def setMACAddress(self, ifName, mac):
      adminUp = self.isAdminUp(ifName)
      if adminUp:
         subprocess.check_call(['ip', 'link', 'set', 'dev', ifName, 'down'])

      try:
         subprocess.check_call(['ip', 'link', 'set', 'dev', ifName, 'address', mac])
      finally:
         if adminUp:
            subprocess.check_call(['ip', 'link', 'set', 'dev', ifName, 'up'])
