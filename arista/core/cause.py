
from collections import defaultdict
import json
import os

from .config import Config, flashPath
from .inventory import ReloadCause, ReloadCauseProvider
from .log import getLogger
from .utils import JsonStoredData

from ..descs.cause import ReloadCausePriority, ReloadCauseScore

from ..libs.date import datetimeToStr, strToDatetime, epochToDatetime
from ..libs.procfs import bootDatetime
from ..libs.python import makedirs

logging = getLogger(__name__)

RELOAD_CAUSE_HISTORY_SIZE=128

class ReloadCauseEntry(ReloadCause):
   def __init__(self, cause='unknown', rcTime='unknown', rcDesc='',
                      score=ReloadCauseScore.EVENT):
      self.cause = cause
      self.time = rcTime
      self.description = rcDesc
      self.score = score

   def __str__(self):
      items = [self.cause]
      if self.description:
         items.append('description: %s' % self.description)
      if self.time != "unknown":
         items.append('time: %s' % self.time)
      return ', '.join(items)

   def getCause(self):
      return self.cause

   def getDescription(self):
      return self.description

   def getTime(self):
      return self.time

   def getScore(self):
      return self.score

   def toDict(self):
      return {
         'cause': self.cause,
         'time': self.time,
         'description': self.description,
         'score': self.score,
      }

   @classmethod
   def fromDict(cls, data):
      return cls(
         cause=data['cause'],
         rcTime=data['time'],
         rcDesc=data['description'],
         score=data['score'],
      )

class ReloadCauseProviderHelper(ReloadCauseProvider):
   def __init__(self, name='unknown', causes=None, extra=None,
                priority=ReloadCausePriority.PRIMARY):
      self.name = name
      self.causes = causes or []
      self.extra = extra or {}
      self.priority = priority

   def getSourceName(self):
      return self.name

   def getCauses(self):
      return self.causes

   def getExtra(self):
      return self.extra

   def getPriority(self):
      return self.priority

   def process(self):
      raise NotImplementedError

   def poll(self):
      return []

   def toDict(self):
      return {
         'name': self.getSourceName(),
         'causes': [c.toDict() for c in self.getCauses()],
         'extra': self.getExtra(),
      }

   @classmethod
   def fromDict(cls, data):
      return cls(
         name=data['name'],
         causes=[ReloadCauseEntry.fromDict(c) for c in data['causes']],
         extra=data['extra'],
      )

class ReloadCauseDataStore(JsonStoredData):
   # NOTE: legacy class, do not use
   def __init__(self, name=None, **kwargs):
      name = name or Config().reboot_cause_file
      super(ReloadCauseDataStore, self).__init__(name, **kwargs)
      self.dataType = ReloadCauseEntry

   def convertFormatV1(self, data):
      for item in data:
         item['cause'] = item['reloadReason']
         del item['reloadReason']
      return data

   def maybeConvertReloadCauseFormat(self, data):
      assert isinstance(data, list) # TODO: use a dict to store data in the future
      if data and data[0].get('reloadReason'):
         data = self.convertFormatV1(data)
      for item in data:
         if 'description' not in item:
            item['description'] = ''
         if 'score' not in item:
            item['score'] = ReloadCauseScore.UNKNOWN
      return data

   def readCauses(self):
      data = self.maybeConvertReloadCauseFormat(self.read())
      return [self._createObj(item, self.dataType) for item in data]

   def writeCauses(self, causes):
      return self.writeList(causes)

   def readCausesV3(self, name):
      causes = self.maybeConvertReloadCauseFormat(self.read())
      date = epochToDatetime(os.stat(self.path).st_mtime)
      return {
         'version': 3,
         'name': name,
         'reports': [{
            'date': datetimeToStr(date),
            'cause': causes[0],
            'providers': [{
               'name': 'Legacy reboot causes',
               'causes': causes,
               'extra': {},
            }],
         }],
      }

class ReloadCauseReport(object):
   def __init__(self, date=None, cause=None, providers=None):
      self.date = date
      self.cause = cause
      self.providers = providers or []

   def processProviders(self, providers):
      for provider in sorted(providers, key=lambda p: p.getPriority()):
         provider.process()
         remotes = provider.getRemoteProviders()
         if remotes:
            self.providers.extend(remotes)
         else:
            self.providers.append(provider)

   def analyzeCauses(self):
      causes = defaultdict(list)
      for provider in self.providers:
         for cause in provider.getCauses():
            causes[cause.getScore()].append(cause)

      for _, causes in reversed(sorted(causes.items())):
         for cause in causes:
            # TODO: maybe sort causes by getTime but not that reliable
            self.cause = cause
            return

      self.cause = ReloadCauseEntry(
         cause='unknown',
         rcTime=datetimeToStr(self.date),
         rcDesc='could not find a valid reboot cause',
         score=ReloadCauseScore.UNKNOWN,
      )

   def toDict(self):
      return {
         'date': datetimeToStr(self.date),
         'cause': self.cause.toDict() if self.cause else None,
         'providers': [p.toDict() for p in self.providers],
      }

   @classmethod
   def fromDict(cls, data):
      return cls(
         date=strToDatetime(data['date']),
         cause=ReloadCauseEntry.fromDict(data['cause']),
         providers=[ReloadCauseProviderHelper.fromDict(p) for p in data['providers']]
      )

class ReloadCauseManager(object):

   VERSION = 3

   def __init__(self, name=None, path=None):
      self.name = name
      self.path = path or flashPath('reboot-cause/platform/causes.json')
      self.loaded = False
      self.reports = []

   @classmethod
   def processReportCause(cls, report):
      return report

   def readCauses(self, inventory, date=None):
      '''Read reload causes from hardware'''
      try:
         self.loadCauses()
      except Exception: # pylint: disable=broad-except
         logging.exception("Failed to read previous reboot causes")
      report = ReloadCauseReport(date=date or bootDatetime())
      report.processProviders(inventory.getReloadCauseProviders())
      report.analyzeCauses()
      # TODO: only add report if there is none for current boot
      #       probably a tempfile under /run/platform_cache/
      self.reports.insert(0, report)

   def fromDict(self, data):
      if data["version"] != self.VERSION:
         raise ValueError("Expected reload cause version to be %d" % self.VERSION)
      if data["name"] != self.name:
         raise ValueError("Expected reload cause name to match %s" % self.name)
      self.reports.extend(ReloadCauseReport.fromDict(d) for d in data['reports'])

   def loadLegacyCauseFile(self):
      rcds = ReloadCauseDataStore(lifespan='persistent')
      if not rcds.exist():
         return

      logging.info("Loading legacy reboot cause information")
      self.fromDict(rcds.readCausesV3(self.name))
      rcds.clear()

   def loadCauseFile(self, path):
      if not os.path.exists(path):
         logging.debug("No prior reboot cause information from %s", path)
         return None

      with open(path) as f:
         try:
            return json.load(f)
         except (ValueError, KeyError):
            logging.exception("Failed to parse reboot cause from %s", self.path)

      return None

   def loadCauses(self):
      '''Load reload causes from file'''
      assert not self.loaded
      try:
         self.loadLegacyCauseFile()
      except Exception: # pylint: disable=broad-except
         logging.exception("Failed to load legacy reload causes")
      data = self.loadCauseFile(self.path)
      if data:
         self.fromDict(data)
      self.loaded = True

   def lastReport(self):
      if not self.reports:
         return None
      return self.reports[0]

   def allReports(self):
      return self.reports

   def toDict(self, latestOnly=False):
      if latestOnly:
         reports = [self.reports[0].toDict()]
      else:
         reports = [r.toDict() for r in self.reports]
      return {
         'name': self.name,
         'reports': reports,
         'version': self.VERSION,
      }

   def storeCauses(self):
      '''Store reload causes into a file'''
      if not self.loaded:
         raise RuntimeError("Storing reboot cause without loading them first")

      folder = os.path.dirname(self.path)
      if not os.path.isdir(folder):
         makedirs(folder, mode=0o755, exist_ok=True)

      with open(self.path, 'w') as f:
         json.dump(self.toDict(), f, indent=3, separators=(',', ': '))

def getReloadCauseManager(platform, read=False):
   rcm = ReloadCauseManager(name=platform.getEeprom().get('SerialNumber'))
   if read:
      rcm.readCauses(platform.getInventory())
      rcm.storeCauses()
      platform.handleUngracefulReboot(reloadCauseReport=rcm.lastReport())
   else:
      rcm.loadCauses()
   return rcm

def getLinecardReloadCauseManager(linecard, read=False):
   slotId = linecard.getSlotId()
   rcm = ReloadCauseManager(
      name=linecard.getEeprom().get('SerialNumber'),
      path=flashPath(f'reboot-cause/platform/card{slotId}.json'))
   if read:
      rcm.readCauses(linecard.getInventory())
      rcm.storeCauses()
   else:
      rcm.loadCauses()
   return rcm
