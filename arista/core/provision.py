
import asyncio
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime
import enum
import errno
import fcntl
import os
import shutil

from .config import Config, provisionPath
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

class LockBusyError(Exception):
   pass

class ProvisionManifest:

   FILE_VERSION = 1
   PATH = provisionPath('manifest.json')

   def __init__(self, platform, pathOverride=None):
      self.platform = platform
      if pathOverride:
         self.manifest = JsonStoredData('manifest.json', lifespan='temporary',
                                        path=pathOverride, append=False)
         self.lockFile = None
      else:
         self.manifest = JsonStoredData('manifest.json', lifespan='permanent',
                                        path=self.PATH, append=False)
         self.lockFile = f'{self.PATH}.lock'
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
         logging.info('Creating initial chassis linecard manifest')
         with self.lock():
            self.data.clear()
            self.data['version'] = self.FILE_VERSION
            self.data['linecards'] = {}
            for lc in self.platform.chassis.iterLinecards(presentOnly=True):
               if not lc.getPresence():
                  logging.warning(
                     '%s: iterated with presentOnly=True but not present',
                     lc)
                  continue
               self.data['linecards'][f'LINE-CARD{lc.getRelativeSlotId()}'] = {
                  'serial': self.getLinecardSerial(lc.slot.getEeprom()),
                  'provisioned': True
               }
            self._write()

   def _write(self):
      self.manifest.write(self.data)

   @asynccontextmanager
   async def asyncLock(self):
      if self.lockFile is None:
         yield None
         return

      for _ in range(Config().provision_max_lock_retries):
         try:
            with open(self.lockFile, 'a', encoding='utf-8') as f:
               fcntl.lockf(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
               yield f
               return
         except OSError as ex:
            if ex.errno in [errno.EAGAIN, errno.EACCES]:
               await asyncio.sleep(1)
            else:
               raise

      logging.warning('Failed to acquire lock for linecard manifest')
      raise LockBusyError()

   @contextmanager
   def lock(self):
      if self.lockFile is None:
         yield None
         return

      with open(self.lockFile, 'a', encoding='utf-8') as f:
         fcntl.lockf(f, fcntl.LOCK_EX)
         yield f

   def getLinecardSerial(self, eepromData):
      return eepromData.get('Serial') or \
         eepromData.get('SerialNumber')

   def checkLinecardSerial(self, lc, clearCache=True):
      cardName = f'LINE-CARD{lc.getRelativeSlotId()}'
      entry = self.data['linecards'].get(cardName)
      prev = entry.get('serial') if entry else None
      if clearCache:
         logging.debug('%s: Clearing prefdl cache', lc)
         lc.eeprom.clearPrefdlCache()

      cur = self.getLinecardSerial(lc.slot.getEeprom())

      if prev != cur:
         newLcData = {'serial': cur, 'provisioned': False}

         with self.lock():
            if self.manifest.exist():
               self.data = self.manifest.read()
            self.data['linecards'].setdefault(cardName, {}).update(newLcData)
            self._write()
         return True
      return False

   async def setLinecardProvisioned(self, lc):
      curSerial = self.getLinecardSerial(lc.getEeprom())

      async with self.asyncLock():
         # init=False is important here to prevent recursive locking
         self.read(init=False)

         cardName = f'LINE-CARD{lc.getRelativeSlotId()}'
         entry = self.data['linecards'].get(cardName)
         if not entry:
            logging.warning('%s: entry missing for %s', self, lc)
            entry = self.data['linecards'].setdefault(cardName, {})
            entry['serial'] = curSerial
         entry['provisioned'] = True
         self._write()
