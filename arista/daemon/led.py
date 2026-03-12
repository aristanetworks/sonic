
import re

from ..core.daemon import registerDaemonFeature, PollDaemonFeature
from ..core.log import getLogger
from ..core.supervisor import Supervisor

from ..descs.led import LedColor

logging = getLogger(__name__)

@registerDaemonFeature()
class StatusLedFeature(PollDaemonFeature):

   NAME = 'led'
   INTERVAL = 60

   def getActive(self, platform, led):
      return LedColor.GREEN

   def getStatus(self, platform, led):
      return LedColor.GREEN

   def getScmStatus(self, platform, led):
      # TODO: implement logic for SCM leds
      return LedColor.GREEN

   def getAllFansStatus(self, platform, led):
      inv = platform.getInventory()
      fans = []
      for slot in inv.getFanSlots():
         fans.extend(slot.getFans())
      if not fans:
         fans = inv.getFans()

      for fan in fans:
         if not fan.getStatus():
            return LedColor.RED
      return LedColor.GREEN

   def getAllPsusStatus(self, platform, led):
      # RED if any present PSU has a fault OR
      # RED if fewer than MIN_REQUIRED_PSUS are functional
      # GREEN if at least MIN_REQUIRED_PSUS are present and healthy
      if isinstance(platform, Supervisor):
         chassis = platform.getChassis()
         minRequired = chassis.MIN_REQUIRED_PSUS
      else:
         minRequired = platform.CHASSIS.MIN_REQUIRED_PSUS

      goodCount = 0
      for psuSlot in platform.getInventory().getPsuSlots():
         if psuSlot.getPresence():
            if psuSlot.getStatus():
               goodCount += 1
            else:
               return LedColor.RED

      if goodCount < minRequired:
         return LedColor.RED

      return LedColor.GREEN

   def getAllLinecardsStatus(self, platform, led):
      assert isinstance(platform, Supervisor)
      # TODO: implement card fault check
      return LedColor.GREEN

   def getAllFabricsStatus(self, platform, led):
      assert isinstance(platform, Supervisor)
      # TODO: implement card fault check
      return LedColor.GREEN

   def getLedPolicy(self, led):
      name = led.getName()
      ledPolicies = {
         'active': self.getActive,
         'status': None, # SONiC now has a system-health service
         'fan_status': self.getAllFansStatus,
         'psu_status': self.getAllPsusStatus,
         'fabric_status': self.getAllFabricsStatus,
         'linecard_status': self.getAllLinecardsStatus,
         'scm': self.getScmStatus,
      }
      policy = ledPolicies.get(name)
      return policy

   def callback(self, elapsed):
      inventory = self.daemon.platform.getInventory()

      for led in inventory.getLeds().values():
         policy = self.getLedPolicy(led)
         if policy is None:
            continue

         try:
            color = policy(self.daemon.platform, led)
         except Exception: # pylint: disable=broad-except
            logging.error("%s: failed apply policy for led %s", self, led)
            continue

         try:
            led.setColor(color)
         except Exception: # pylint: disable=broad-except
            logging.error("%s: failed to set led color %s for %s", self, color, led)
            continue
