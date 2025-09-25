
import asyncio

from ..core.daemon import PollDaemonFeature, registerDaemonFeature
from ..core.log import getLogger
from ..core.provision import ProvisionManifest
from ..core.supervisor import Supervisor

logging = getLogger(__name__)

@registerDaemonFeature()
class LinecardMonitor(PollDaemonFeature):

   NAME = 'linecard_monitor'
   INTERVAL = 30

   curPresence = {}
   midplaneUp = {}
   manifest: ProvisionManifest

   @classmethod
   def runnable(cls, daemon):
      return isinstance(daemon.platform, Supervisor)

   def init(self):
      self.manifest = ProvisionManifest(self.daemon.platform)
      self.manifest.read(init=True)

      for lc in self.daemon.platform.chassis.iterLinecards(presentOnly=False):
         present = lc.slot.getPresence()
         changed = lc.slot.getPresenceChanged()
         logging.info('%s: initial present=%s presence_changed=%s',
                      lc, present, changed)
         self.curPresence[lc.getSlotId()] = present

         eepromData = lc.getEeprom()
         if present and self.manifest.serialChanged(lc, eepromData):
            self.manifest.setLinecardUnprovisioned(lc, eepromData)

      super().init()

   async def refreshEepromCache(self, lc):
      p = await asyncio.create_subprocess_exec(
         'arista', 'linecard', '-i', str(lc.getSlotId()),
         'eeprom', '--reset')
      await p.wait()
      return lc.getEeprom()

   async def handleLinecardChanged(self, lc):
      present = lc.getPresence()
      logging.info('%s: presence changed from %s to %s',
                   lc, self.curPresence[lc.getSlotId()],
                   present)
      self.curPresence[lc.getSlotId()] = present
      if not present:
         return

      eepromData = await self.refreshEepromCache(lc)
      if self.manifest.serialChanged(lc, eepromData):
         self.manifest.setLinecardUnprovisioned(lc, eepromData)

   async def callback(self, elapsed): # pylint: disable=unused-argument
      for lc in self.daemon.platform.chassis.iterLinecards(presentOnly=False):
         if lc.slot.getPresenceChanged():
            await self.handleLinecardChanged(lc)
