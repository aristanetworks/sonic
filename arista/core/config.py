import logging
import os
import yaml

from .utils import getCmdlineDict

CONFIG_PATH = "/etc/sonic/arista.yml"

class Config(object):
   instance_ = None

   def __new__(cls):
      if cls.instance_ is None:
         cls.instance_ = object.__new__(cls)
      return cls.instance_

   def __init__(self):
      self.plugin_xcvr = 'native'
      self.plugin_led = 'native'
      self.plugin_psu = 'native'
      self._parseCmdline()
      self._parseConfig()

   def _getKeys(self):
      return self.__dict__.keys()

   def _parseCmdline(self):
      cmdline = getCmdlineDict()

      for key in self._getKeys():
         k = 'arista.%s' % key
         if k in cmdline:
            setattr(self, key, cmdline[k])

   def _parseConfig(self):
      if not os.path.exists(CONFIG_PATH):
         return

      try:
         with open(CONFIG_PATH, 'r') as f:
            data = yaml.load(f)
      except IOError as e:
         logging.warning('cannot open file %s: %s', CONFIG_PATH, e)
         return
      except yaml.YAMLError as e:
         logging.warning('invalid %s format: %s', CONFIG_PATH, e)
         return

      for key in self._getKeys():
         if key in data:
            setattr(self, key, data[key])

   def get(self, confName):
      return getattr(self, confName, None)
