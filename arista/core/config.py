import os
import shutil
import yaml

from .log import getLogger
from ..libs.procfs import getCmdlineDict

logging = getLogger(__name__)

DEFAULT_FLASH_PATH = '/host'
CONFIG_PATH = "/etc/sonic/arista.config"
FLASH_CONFIG_PATH = os.path.join(DEFAULT_FLASH_PATH, 'arista-platform.config')

class Config():
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
         cls.instance_.linecard_lock_file_pattern = \
            '/var/lock/arista.linecard{:d}.lock'
         cls.instance_.linecard_standby_only = True
         cls.instance_.linecard_cpu_enable = False
         cls.instance_.power_off_linecard_on_reboot = True
         cls.instance_.power_off_fabric_on_reboot = False
         cls.instance_.write_hw_thresholds = True
         cls.instance_.report_hw_thresholds = False
         cls.instance_.watchdog_state_file = 'watchdog.json'
         cls.instance_.xcvr_lpmode_out = False
         cls.instance_.api_use_sfpoptoe = True
         cls.instance_.api_sfp_thermal = False
         cls.instance_.api_sfp_reset_lpmode = True
         cls.instance_.api_event_use_interrupts = False
         cls.instance_.flash_path = DEFAULT_FLASH_PATH
         cls.instance_.tmpfs_path = '/var/run/platform_cache/arista'
         cls.instance_.etc_path = '/etc/sonic'
         cls.instance_.api_rpc_sup = '127.100.1.1'
         cls.instance_.api_rpc_lcx = "127.100.{}.1"
         cls.instance_.api_rpc_host = '127.0.0.1'
         cls.instance_.api_rpc_port = '12322'
         cls.instance_.api_linecard_reboot_graceful = False
         cls.instance_.cooling_data_points = 10
         cls.instance_.cooling_export_path = None
         cls.instance_.cooling_max_decrease = 10
         cls.instance_.cooling_max_increase = 25
         cls.instance_.cooling_min_speed = 30
         cls.instance_.cooling_loop_interval = 20
         cls.instance_.cooling_target_offset = 0
         cls.instance_.cooling_target_factor = 0.8
         cls.instance_.cooling_xcvr_target_offset = -10
         cls.instance_.cooling_adjust_under = -5.
         cls.instance_.cooling_adjust_over = 0.
         cls.instance_.cooling_gc_count = 15
         cls.instance_.cooling_xcvrs_via_api = False
         cls.instance_.cooling_xcvrs_use_dom_temperature = True
         cls.instance_.cooling_override_xcvr_target = None
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
      if os.path.exists(FLASH_CONFIG_PATH):
         try:
            if os.path.exists(CONFIG_PATH):
               logging.warning(
                  'Configuration %s exists, removing migration config %s from flash',
                  CONFIG_PATH, FLASH_CONFIG_PATH)
               os.remove(FLASH_CONFIG_PATH)

            shutil.move(FLASH_CONFIG_PATH, CONFIG_PATH)
         except Exception:  # pylint: disable=broad-except
            logging.exception('could not migrate platform config from flash')

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
