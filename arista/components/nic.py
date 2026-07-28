
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
         ['ip', 'address', 'add', '%s/%d' % (addr, prefixLen), 'dev', ifName])
