
from datetime import datetime

from ..core.daemon import registerDaemonFeature, PollDaemonFeature
from ..core.log import getLogger

logging = getLogger(__name__)

@registerDaemonFeature()
class RtcSyncFeature(PollDaemonFeature):

   NAME = 'rtc'
   INTERVAL = 10 * 60
   DELAY = 60

   def callback(self, elapsed):
      for rtc in self.daemon.platform.getInventory().getRtcs():
         try:
            logging.debug('%s: updating %s rtc', self, rtc.getName())
            rtc.setTime(datetime.now())
         except Exception: # pylint: disable=broad-except
            logging.error('%s: failed to update %s rtc', self, rtc.getName())
