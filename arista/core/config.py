import os
import yaml

from .log import getLogger
from ..libs.procfs import getCmdlineDict

logging = getLogger(__name__)

CONFIG_PATH = "/etc/sonic/arista.config"

class Config(object):
   instance_ = None

   def __new__(cls):
      if cls.instance_ is None:
         cls.instance_ = object.__new__(cls)
         cls.instance_.plugin_xcvr = 'native'
         cls.instance_.plugin_led = 'native'
         cls.instance_.plugin_psu = 'native'
         cls.instance_.lock_scd_conf = True
         cls.instance_.init_irq = True
         cls.instance_.reboot_cause_file = 'last_reboot_cause'
         cls.instance_.persistent_presence_check = True
         cls.instance_.lock_file = '/var/lock/arista.lock'
         cls.instance_.linecard_standby_only = True
         cls.instance_.linecard_cpu_enable = False
         cls.instance_.power_off_linecard_on_reboot = True
         cls.instance_.power_off_fabric_on_reboot = False
         cls.instance_.use_metainventory = True
         cls.instance_.write_hw_thresholds = True
         cls.instance_.report_hw_thresholds = False
         cls.instance_.api_use_sfpoptoe = False
         cls.instance_.flash_path = '/host'
         cls.instance_.tmpfs_path = '/var/run/platform_cache/arista'
         cls.instance_.etc_path = '/etc/sonic'
         cls.instance_._parseConfig()
         cls.instance_._parseCmdline()
      return cls.instance_

   def _getKeys(self):
      return self.__dict__.keys()

   @staticmethod
   def _parseVal(val):
      if not isinstance(val, str):
         return val
      yes = ['yes', 'y', 'true']
      no = ['no', 'n', 'false']
      vl = val.lower()
      if vl in yes:
         return True
      if vl in no:
         return False
      return val

   def setAttr(self, key, val):
      v = getattr(self, key, None)
      if type(v) != type(val):
         logging.warning('%s attr type changed: old %s, new %s',
                         key, type(v), type(val))
      setattr(self, key, self._parseVal(val))

   def _parseCmdline(self):
      cmdline = getCmdlineDict()

      for key in self._getKeys():
         k = 'arista.%s' % key
         if k in cmdline:
            self.setAttr(key, cmdline[k])

   def _parseConfig(self):
      if not os.path.exists(CONFIG_PATH):
         return

      try:
         with open(CONFIG_PATH, 'r') as f:
            data = yaml.safe_load(f)
      except IOError as e:
         logging.warning('cannot open file %s: %s', CONFIG_PATH, e)
         return
      except yaml.YAMLError as e:
         logging.warning('invalid %s format: %s', CONFIG_PATH, e)
         return

      for key in self._getKeys():
         if key in data:
            self.setAttr(key, data[key])

   def get(self, confName):
      return getattr(self, confName, None)

def flashPath(*args):
   return os.path.join(Config().flash_path, *args)

def tmpfsPath(*args):
   return os.path.join(Config().tmpfs_path, *args)

def etcPath(*args):
   return os.path.join(Config().etc_path, *args)
