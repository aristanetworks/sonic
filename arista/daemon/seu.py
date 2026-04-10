
from __future__ import absolute_import, division, print_function

from ..core.daemon import registerDaemonFeature, PollDaemonFeature
from ..core.log import getLogger

logging = getLogger(__name__)

@registerDaemonFeature()
class SeuDaemonFeature(PollDaemonFeature):

   NAME = 'seu'
   INTERVAL = 60

   def init(self):
      PollDaemonFeature.init(self)
      self.seuDetected = {} # pylint: disable=attribute-defined-outside-init
      for reporter in self.daemon.platform.getInventory().getSeuReporters():
         component = reporter.getComponent()
         self.seuDetected[component] = False
         if reporter.powerCycleOnSeu():
            logging.info('%s: disabling powercycle on SEU', component)
            reporter.powerCycleOnSeu(False)
         else:
            logging.info('%s: powercycle on SEU already disabled', component)

   async def callback(self, elapsed):
      for reporter in self.daemon.platform.getInventory().getSeuReporters():
         component = reporter.getComponent()
         detected = self.seuDetected.get(component)
         if not detected and reporter.hasSeuError():
            logging.error('A SEU error was detected on %s', component)
            logging.info('The impact can vary from nothing and in rare cases '
                         'unexpected behavior')
            logging.info('Power cycling the system would restore it to a '
                         'clean slate')
            self.seuDetected[component] = True
