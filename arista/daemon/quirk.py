
from ..core.asic import SwitchChip
from ..core.daemon import registerDaemonFeature, OneShotFeature
from ..core.log import getLogger

logging = getLogger(__name__)

@registerDaemonFeature()
class QuirkOneShotFeature(OneShotFeature):

   NAME = 'quirk'

   def run(self):
      for component in self.daemon.platform.iterComponents(filters=None):
         if isinstance(component, SwitchChip):
            logging.info('%s: applying quirks on %s', self, component)
            component.applyQuirks(delayed=True)
