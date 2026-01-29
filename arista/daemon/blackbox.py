from ..core.config import Config
from ..core.daemon import OneShotFeature, registerDaemonFeature
from ..core.log import getLogger

logging = getLogger(__name__)

@registerDaemonFeature()
class BlackBoxFeature(OneShotFeature):
   NAME = 'blackbox'

   def run(self):
      enable = Config().blackbox_enable
      logging.info('Blackbox config is %r', enable)
      for blackbox in self.daemon.platform.getInventory().getBlackBox():
         blackbox.setEnabled(enable)
