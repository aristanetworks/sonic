
import asyncio

from contextlib import asynccontextmanager, contextmanager
from datetime import datetime
from enum import Enum, IntEnum
import errno
import fcntl
import os
import shutil

from .config import Config, provisionPath
from .log import getLogger
from .utils import JsonStoredData

logging = getLogger(__name__)

class ProvisionMode(IntEnum):
   NONE = 0
   STATIC = 1

   def __str__(self):
      return self.name.lower()

class ProvisionState(str, Enum):
   UNPROVISIONED = 'unprovisioned'
   PENDING = 'pending'
   COMPLETE = 'complete'

   @classmethod
   def fromProvisioned(cls, value):
      return cls.COMPLETE if value else cls.UNPROVISIONED

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
         self.manifest = JsonStoredData('manifest.json', lifespan='permanent',
                                        path=pathOverride, append=False)
         self.lockFile = None
      else:
         self.manifest = JsonStoredData('manifest.json', lifespan='permanent',
                                        path=self.PATH, append=False)
         self.lockFile = f'{self.PATH}.lock'
      self.data = {}

   def __str__(self):
      return f'ProvisionManifest({self.PATH})'

   def slotIdToRelative(self, slot):
      from .linecard import Linecard # pylint: disable=import-outside-toplevel,cyclic-import
      return slot - Linecard.ABSOLUTE_CARD_OFFSET

   def read(self, init=False):
      if self.manifest.exist():
         self.data = self.manifest.read()
         if init:
            if self.data.get('version', None) != self.FILE_VERSION:
               logging.warning('%s: Replacing manifest with unsupported version %d',
                               self, self.data.get('version'))
               shutil.move(self.PATH, self.PATH +
                           f'.saved-{datetime.now().strftime("%Y%m%d%H%M")}')
            else:
               # Chassis newly upgraded from 202405 will not have the
               # provision_state field
               for lcData in self.data['linecards'].values():
                  if 'provision_state' not in lcData:
                     lcData['provision_state'] = (
                        ProvisionState.fromProvisioned(lcData['provisioned'])
                     )
               return
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
                  'provisioned': True,
                  'provision_state': ProvisionState.COMPLETE
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

   def serialChanged(self, lc, eepromData=None):
      if not eepromData:
         eepromData = lc.slot.getEeprom()

      cardName = f'LINE-CARD{lc.getRelativeSlotId()}'
      entry = self.data['linecards'].get(cardName)
      prev = entry.get('serial') if entry else None
      cur = self.getLinecardSerial(eepromData)

      return prev != cur

   def _getUnprovisionedLinecardEntry(self, eepromData):
      cur = self.getLinecardSerial(eepromData)

      return {
         'serial': cur,
         'provisioned': False,
         'provision_state': ProvisionState.UNPROVISIONED
      }

   def setLinecardUnprovisioned(self, lc, eepromData=None):
      if not eepromData:
         eepromData = lc.slot.getEeprom()

      cardName = f'LINE-CARD{lc.getRelativeSlotId()}'
      newLcData = self._getUnprovisionedLinecardEntry(eepromData)
      with self.lock():
         if self.manifest.exist():
            self.data = self.manifest.read()
         self.data['linecards'].setdefault(cardName, {}).update(newLcData)
         self._write()

   async def setLinecardProvisionStarted(self, slot):
      async with self.asyncLock():
         # init=False is important here to prevent recursive locking
         self.read(init=False)

         relSlot = self.slotIdToRelative(slot)
         cardName = f'LINE-CARD{relSlot}'
         entry = self.data['linecards'].get(cardName)
         if not entry:
            logging.warning('%s: entry missing for linecard in slot %d', self, slot)
         else:
            entry['provisioned'] = False
            entry['provision_state'] = ProvisionState.PENDING
            self._write()

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
         if entry['provision_state'] == ProvisionState.COMPLETE:
            return
         if entry['provision_state'] != ProvisionState.PENDING:
            logging.warning('%s: %s provisioning status was %s, not pending\n',
                            self, lc, entry['provision_state'])
         entry['provisioned'] = True
         entry['provision_state'] = ProvisionState.COMPLETE
         self._write()

   async def getLinecardProvisionStatus(self, slot):
      async with self.asyncLock():
         # init=False is important here to prevent recursive locking
         self.read(init=False)

         relSlot = self.slotIdToRelative(slot)
         cardName = f'LINE-CARD{relSlot}'
         entry = self.data['linecards'].get(cardName)
         if not entry:
            return None
         return entry['provision_state']
