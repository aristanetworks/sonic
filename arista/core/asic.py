
import os
import time

from ..libs.pci import pciRescan
from ..libs.wait import waitFor

from .component import DEFAULT_WAIT_TIMEOUT
from .component.pci import PciComponent
from .driver.kernel.pci import PciKernelDriver
from .log import getLogger
from .utils import klog, inSimulation

logging = getLogger(__name__)

ASIC_YIELD_TIME = os.getenv( 'ASIC_YIELD_TIME', 2 )

class SwitchChipDriver(PciKernelDriver):
   PASSIVE = True

class SwitchChip(PciComponent):

   DRIVER = SwitchChipDriver

   def __init__(self, addr, rescan=False, pcieResetDelay=500,
                powerGpios=None, powerGoodGpios=None,
                coreResets=None, pcieResets=None, **kwargs):
      super(SwitchChip, self).__init__(addr=addr, **kwargs)
      self.rescan = rescan
      self.pcieResetDelay = pcieResetDelay
      self.powerGpios = powerGpios or []
      self.powerGoodGpios = powerGoodGpios or []
      self.coreResets = coreResets or []
      self.pcieResets = pcieResets or []

   def __str__(self):
      return '%s(addr=%s)' % (self.__class__.__name__, self.addr)

   def pciRescan(self):
      pciRescan()

   def isPowerGood(self):
      for gpio in self.powerGoodGpios:
         if not gpio.isActive():
            return False
      return True

   def isPowerDown(self):
      for gpio in self.powerGoodGpios:
         if gpio.isActive():
            return False
      return True

   def powerOn(self, wait=True):
      if self.powerGoodGpios and self.isPowerGood():
         logging.debug('%s: power already on', self)
         return

      logging.debug('%s: turning power on', self)
      for gpio in self.powerGpios:
         gpio.setActive(True)

      if wait and self.powerGoodGpios:
         logging.debug('%s: waiting for power good', self)
         waitFor(self.isPowerGood, interval=50,
                 description='waiting for power good')
         logging.debug('%s: power is on', self)

   def powerOff(self, wait=True):
      if self.powerGoodGpios and not self.isPowerGood():
         logging.debug('%s: power already off', self)
         return

      logging.debug('%s: turning power off', self)
      for gpio in self.powerGpios:
         gpio.setActive(False)

      if wait and self.powerGoodGpios:
         logging.debug('%s: waiting for power down', self)
         waitFor(self.isPowerDown, interval=50,
                 description='waiting for power down')
         logging.debug('%s: power is off', self)

   def isInReset(self):
      for reset in self.coreResets + self.pcieResets:
         if reset.read():
            return True
      return False

   def isOutOfReset(self):
      for reset in self.coreResets + self.pcieResets:
         if reset.read():
            return False
      return True

   def _resetOut(self, wait=True):
      if self.isOutOfReset():
         logging.debug('%s: already out of reset', self)
         return

      logging.debug('%s: taking core out of reset', self)
      for reset in self.coreResets:
         reset.resetOut()

      time.sleep(self.pcieResetDelay / 1000.)

      logging.debug('%s: taking pcie out of reset', self)
      for reset in self.pcieResets:
         reset.resetOut()

      self.applyQuirks()

      if wait:
         self.waitForIt()

   def _resetIn(self, wait=True):
      if not self.isOutOfReset():
         logging.debug('%s: already in reset', self)
         return

      logging.debug('%s: putting in reset', self)
      for reset in self.pcieResets + self.coreResets:
         reset.resetIn()

   def resetOut(self):
      if not self.coreResets:
         logging.debug('%s: skipping new reset strategy', self)
         return
      self.powerOn()
      # NOTE: setup calls waitForIt at a later time of the initialization
      # process. This allow other devices to be reset while asic is coming up.
      self._resetOut(wait=False)

   def resetIn(self):
      if not self.coreResets:
         logging.debug('%s: skipping new reset strategy', self)
         return
      self._resetIn()
      self.powerOff()

   def waitForIt(self, timeout=DEFAULT_WAIT_TIMEOUT):
      begin = time.time()
      end = begin + timeout
      rescanTime = begin + 1 # rescan is only enable by platform request

      logging.debug('%s: waiting for switch chip', self)
      if inSimulation():
         return True

      klog('waiting for switch chip')
      while True:
         now = time.time()
         if now > end:
            break
         devPath = self.addr.getSysfsPath()
         if os.path.exists(devPath):
            logging.debug('switch chip is ready')
            klog('switch chip is ready')
            time.sleep(ASIC_YIELD_TIME)
            klog('yielding...')
            return True
         if self.rescan and now > rescanTime:
            self.pciRescan()
            rescanTime = end
         time.sleep(0.1)

      logging.error('%s: timed out waiting for the switch chip', self)
      return False
