
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

         if present:
            self.manifest.checkLinecardSerial(lc, clearCache=False)

      super().init()

   def handleLinecardChanged(self, lc):
      present = lc.getPresence()
      logging.info('%s: presence changed from %s to %s',
                   lc, self.curPresence[lc.getSlotId()],
                   present)
      if not present:
         return False

      return self.manifest.checkLinecardSerial(lc)

   def callback(self, elapsed): # pylint: disable=unused-argument
      for lc in self.daemon.platform.chassis.iterLinecards(presentOnly=False):
         if lc.slot.getPresenceChanged():
            self.handleLinecardChanged(lc)
