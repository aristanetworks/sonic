
from ..core.daemon import registerDaemonFeature, PollDaemonFeature
from ..core.log import getLogger
from ..core.supervisor import Supervisor

logging = getLogger(__name__)

@registerDaemonFeature()
class CookiesFeature(PollDaemonFeature):

   NAME = 'cookies'
   INTERVAL = 3

   @classmethod
   def runnable(cls, daemon):
      return isinstance(daemon.platform, Supervisor)

   def checkProviders(self, unit):
      causes = {}
      for p in unit.getInventory().getReloadCauseProviders():
         slotCauses = p.poll()
         assert p.getSourceName() not in causes
         causes[p.getSourceName()] = slotCauses
      return causes

   def init(self):
      platform = self.daemon.platform
      cookies = platform.getCookies()
      cookies.loadCookieFile()
      super().init()

   async def callback(self, elapsed):
      platform = self.daemon.platform
      cookies = platform.getCookies()

      cookies.poll()
      cookies.storeCauses()
