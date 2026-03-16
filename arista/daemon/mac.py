
from ..core.daemon import registerDaemonFeature, OneShotFeature
from ..core.log import getLogger
from ..core.platform import getSysEepromData
from ..core.utils import getCmdlineDict

logging = getLogger(__name__)

@registerDaemonFeature()
class MacOneShotFeature(OneShotFeature):

   NAME = 'mac'

   def readMacAddress(self, intfName):
      path = '/sys/class/net/%s/address' % intfName
      with open(path) as f:
         return f.read().rstrip()

   def run(self):
      intfName = 'eth0'
      currentMac = self.readMacAddress(intfName)
      desiredMac = getSysEepromData().get('MAC', '00:00:00:00:00:00')
      currentMacValue = int(currentMac.replace(':', ''), 16)
      desiredMacValue = int(desiredMac.replace(':', ''), 16)
      if currentMac == desiredMac:
         logging.info('mac address of %s is properly set to %s', intfName,
                      currentMac)
      elif currentMacValue == desiredMacValue + 1:
         logging.warning('mac address of %s is not set properly. is %s should be %s'
                         ' (likely coming from EOS via fast-reboot)',
                         intfName, currentMac, desiredMac)
      else:
         logging.error('mac address of %s is not set properly. is %s should be %s',
                       intfName, currentMac, desiredMac)
         for key, value in getCmdlineDict().items():
            if key.startswith('hwaddr_'):
               logging.info('cmdline: %s=%s', key, value)
