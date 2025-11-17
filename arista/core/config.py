import os
import shutil
from types import UnionType
import yaml

from .log import getLogger
from ..libs.procfs import getCmdlineDict

logging = getLogger(__name__)

DEFAULT_FLASH_PATH = '/host'
CONFIG_PATH = "/etc/sonic/arista.config"
FLASH_CONFIG_PATH = os.path.join(DEFAULT_FLASH_PATH, 'arista-platform.config')

class DefaultConfig:
   plugin_xcvr: str = 'native'
   plugin_led: str = 'native'
   plugin_psu: str = 'native'
   lock_scd_conf: bool = True
   init_irq: bool = True
   reboot_cause_file: str = 'last_reboot_cause'
   persistent_presence_check: bool = True
   lock_file: str = '/var/lock/arista.lock'
   linecard_lock_file_pattern: str = \
      '/var/lock/arista.linecard{:d}.lock'
   linecard_standby_only: bool = True
   linecard_cpu_enable: bool = False
   power_off_linecard_on_reboot: bool = True
   power_off_fabric_on_reboot: bool = False
   write_hw_thresholds: bool = True
   report_hw_thresholds: bool = False
   watchdog_state_file: str = 'watchdog.json'
   xcvr_lpmode_out: bool = False
   api_use_sfpoptoe: bool = True
   api_sfp_thermal: bool = False
   api_sfp_reset_lpmode: bool = True
   api_event_use_interrupts: bool = False
   flash_path: str = DEFAULT_FLASH_PATH
   tmpfs_path: str = '/var/run/platform_cache/arista'
   etc_path: str = '/etc/sonic'
   api_rpc_sup: str = '127.100.1.1'
   api_rpc_lcx: str = "127.100.{}.1"
   api_rpc_host: str = '127.0.0.1'
   api_rpc_port: str = '12322'
   api_linecard_reboot_graceful: bool = False
   cooling_data_points: int = 3
   cooling_export_path: str | None = None
   cooling_max_decrease: float = 10.
   cooling_max_increase: float = 25.
   cooling_min_speed: float | None = None
   cooling_loop_interval: int = 10
   cooling_target_offset: float | None = None
   cooling_target_factor: float = 0.8
   cooling_xcvr_target_offset: float = -10.
   cooling_gc_count: int = 15
   cooling_hysteresis_negative: float | None = None
   cooling_hysteresis_positive: float | None = None
   cooling_kp: float | None = None
   cooling_ki: float | None = None
   cooling_kd: float | None = None
   cooling_xcvrs_via_api: bool = False
   cooling_xcvrs_use_dom_temperature: bool = True
   cooling_override_xcvr_target: float | None = None

class Config():
   instance_ = None

   def __new__(cls):
      if cls.instance_ is None:
         cls.instance_ = object.__new__(cls)
         cls.instance_.types = None

         cls.instance_._parseDefaultConfig()
         cls.instance_._parseConfig()
         cls.instance_._parseCmdline()

      return cls.instance_

   def _getKeys(self):
      return self.__dict__.keys()

   @staticmethod
   def _parseBoolVal(val):
      if isinstance(val, bool):
         return val
      if isinstance(val, str):
         yes = ['yes', 'y', 'true']
         no = ['no', 'n', 'false']
         vl = val.lower()
         if vl in yes:
            return True
         if vl in no:
            return False

      raise ValueError(f"Couldn't parse bool, invalid value: {val!r}")

   def setAttr(self, key: str, val):
      if not hasattr(DefaultConfig, key):
         logging.warning("Invalid config option: %s. Skipping...", key)
         return

      try:
         if self.getType(key) is bool:
            val = self._parseBoolVal(val)
         else:
            val = self._convertType(key, val)
      except ValueError as e:
         logging.warning("Type conversion failed: %s", str(e))
         return

      setattr(self, key, val)

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

   def _convertType(self, key: str, value):
      type_ = self.getType(key)

      try:
         return type_(value)
      except ValueError as e:
         raise ValueError(
            f'Cannot convert {key} = {value!r} to type: {type_!r}') from e
      except TypeError as e:
         raise TypeError(
            f"Cannot convert type because attribute {key} does NOT exist") from e

   def getType(self, key: str):
      return self.types.get(key, type(None))

   def _parseDefaultConfig(self):
      for key, value in DefaultConfig.__dict__.items():
         if not key.startswith('__'):
            setattr(self, key, value)

      self.types = DefaultConfig.__annotations__.copy() # pylint: disable=attribute-defined-outside-init
      for key, value in self.types.items():
         type_ = value
         if isinstance(value, UnionType):
            for i in value.__args__:
               if i is not type(None):
                  type_ = i
         self.types[key] = type_


def flashPath(*args):
   return os.path.join(Config().flash_path, *args)

def tmpfsPath(*args):
   return os.path.join(Config().tmpfs_path, *args)

def etcPath(*args):
   return os.path.join(Config().etc_path, *args)
