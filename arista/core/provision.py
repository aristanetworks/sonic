
from datetime import datetime
import enum
import os
import shutil

from .config import provisionPath
from .log import getLogger
from .utils import JsonStoredData

logging = getLogger(__name__)

class ProvisionMode(enum.IntEnum):
   NONE = 0
   STATIC = 1

   def __str__(self):
      return self.name.lower()

class ProvisionConfig(object):

   CONFIG_PATH = provisionPath('%d/.provision')

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

class ProvisionManifest:

   FILE_VERSION = 1
   PATH = provisionPath('manifest.json')

   def __init__(self, platform):
      self.platform = platform
      self.manifest = JsonStoredData('manifest.json', lifespan='permanent',
                                 path=self.PATH, append=False)
      self.data = {}

   def __str__(self):
      return f'ProvisionManifest({self.PATH})'

   def read(self, init=False):
      if self.manifest.exist():
         self.data = self.manifest.read()
         if init and self.data.get('version', None) != self.FILE_VERSION:
            logging.warning('%s: Replacing manifest with unsupported version %d',
               self, self.data.get('version'))
            shutil.move(self.PATH, self.PATH +
               f'.saved-{datetime.now().strftime("%Y%m%d%H%M")}')
         else:
            return

      if init:
         self.data = {}
         self.data['version'] = self.FILE_VERSION
         self.data['linecards'] = {}
         for lc in self.platform.chassis.iterLinecards(presentOnly=True):
            if not lc.getPresence():
               logging.warning('%s: iterated with presentOnly=True but not present',
                               lc)
               continue
            self.data['linecards'][f'LINE-CARD{lc.getRelativeSlotId()}'] = {
               'serial': self.getLinecardSerial(lc),
               'provisioned': True
            }
         self.manifest.write(self.data)

   def write(self):
      self.manifest.write(self.data)

   def getLinecardSerial(self, lc):
      return lc.getEeprom().get('Serial') or \
         lc.getEeprom().get('SerialNumber')

   def checkLinecardSerial(self, lc, clearCache=True):
      update = not lc.eeprom.prefdlCached()

      cardName = f'LINE-CARD{lc.getRelativeSlotId()}'
      entry = self.data['linecards'].get(cardName)
      prev = entry.get('serial') if entry else None
      if clearCache:
         lc.eeprom.clearPrefdlCache()

      cur = self.getLinecardSerial(lc)

      if prev != cur:
         update = True
         self.data['linecards'][cardName]['serial'] = cur
         self.data['linecards'][cardName]['provisioned'] = False

      return update

   def setLinecardProvisioned(self, lc):
      cardName = f'LINE-CARD{lc.getRelativeSlotId()}'
      entry = self.data['linecards'].get(cardName)
      if not entry:
         logging.warning('%s: entry missing for %s', self, lc)
         entry = self.data['linecards'][cardName]
         entry['serial'] = self.getLinecardSerial(lc)
      entry['provisioned'] = True
