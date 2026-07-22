import json
import os

from .. import registerAction
from ...args.platform.nic import nicParser
from ....components.bmc_mgmt_nic import BmcMgmtNic
from ....components.nic import Nic
from ....components.bmc_usb_host_nic import BmcUsbHostNic
from ....components.bmc_usb_device_nic import BmcUsbDeviceNic
from ....core.log import getLogger

logging = getLogger(__name__)

BMC_JSON_PATH = '/etc/sonic/bmc.json'

def maskToCidr(mask):
   return sum(bin(int(x)).count('1') for x in mask.split('.'))

def readBmcJson():
   with open(BMC_JSON_PATH, encoding='utf-8') as f:
      return json.load(f)

def loadNicConfig(nic):
   if isinstance(nic, BmcMgmtNic):
      return {'ifName': nic.interface}
   if isinstance(nic, BmcUsbHostNic):
      if os.path.exists('/etc/sonic'):
         cfg = readBmcJson()
         return {'ifName': cfg['bmc_if_name'],
                 'addr': cfg['bmc_if_addr'],
                 'prefixLen': maskToCidr(cfg['bmc_net_mask'])}
   elif isinstance(nic, BmcUsbDeviceNic):
      if os.path.exists('/etc/sonic'):
         cfg = readBmcJson()
         return {'ifName': cfg['bmc_if_name'],
                 'addr': cfg['bmc_addr'],
                 'prefixLen': maskToCidr(cfg['bmc_net_mask'])}
   return None

@registerAction(nicParser)
def doNic(ctx, args):
   failed = False
   for nic in ctx.platform.iterComponents(filters=None, recursive=True):
      if not isinstance(nic, Nic):
         continue
      try:
         if args.config:
            config = loadNicConfig(nic)
            if config:
               nic.configure(**config)
         elif args.clean:
            config = loadNicConfig(nic)
            if config:
               nic.unconfigure(config['ifName'])
      except Exception as e: # pylint: disable=broad-exception-caught
         logging.error('Failed to %s %s: %s',
            'configure' if args.config else 'clean', nic, e)
         failed = True
   if failed:
      return 1
   return 0
