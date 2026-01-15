import datetime

from ..core.config import Config, flashPath
from ..core.daemon import OneShotFeature, registerDaemonFeature
from ..core.log import getLogger
from ..core.utils import StoredData
from ..libs.date import datetimeToFileName
from ..libs.fs import RotatedLogFile

logging = getLogger(__name__)

@registerDaemonFeature()
class BlackBoxFeature(OneShotFeature):
   NAME = 'blackbox'

   def _dumpBlackBox(self, blackbox):
      lf = RotatedLogFile(
         name='blackbox',
         path=flashPath('blackbox'),
         keep=Config().blackbox_max_logs,
      )
      with lf.newLog(datetimeToFileName(datetime.datetime.now())) as f:
         blackbox.dump(f.name)

   def run(self):
      enable = Config().blackbox_enable
      logging.info('%s: Blackbox config is %r', self, enable)
      for blackbox in self.daemon.platform.getInventory().getBlackBox():
         dumped = StoredData('blackbox_dumped')
         if not dumped.exist():
            blackbox.setEnabled(False)
            self._dumpBlackBox(blackbox)
            dumped.write('1')
         if enable:
            blackbox.setEnabled(True)
