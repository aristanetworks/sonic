
import enum
import os

from .config import flashPath

class ProvisionMode(enum.IntEnum):
   NONE = 0
   STATIC = 1

   def __str__(self):
      return self.name.lower()

class ProvisionConfig(object):

   CONFIG_PATH = flashPath('provision/%d/.provision')

   def __init__(self, slotId):
      self.configPath_ = self.CONFIG_PATH % slotId

   def loadMode(self):
      if os.path.exists(self.configPath_):
         return ProvisionMode.STATIC
      return ProvisionMode.NONE

   def writeMode(self, mode):
      if mode == ProvisionMode.STATIC:
         try:
            with open(self.configPath_, 'w'):
               pass
         except IOError:
            pass
         return

      try:
         os.remove(self.configPath_)
      except OSError:
         pass
