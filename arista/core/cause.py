
from collections import defaultdict
from datetime import datetime
import json
import os

from .config import Config, flashPath
from .inventory import ReloadCause, ReloadCauseProvider
from .log import getLogger
from .utils import JsonStoredData

from ..descs.cause import ReloadCausePriority, ReloadCauseScore, ReloadCauseAltSource

from ..libs.date import datetimeToStr, strToDatetime, epochToDatetime
from ..libs.procfs import bootDatetime
from ..libs.python import makedirs

logging = getLogger(__name__)

RELOAD_CAUSE_HISTORY_SIZE=128

class ReloadCauseEntry(ReloadCause):
   def __init__(self, cause='unknown', rcTime='unknown', rcDesc='',
                      score=ReloadCauseScore.EVENT,
                      priority=ReloadCausePriority.NORMAL,
                      altSource=None):
      self.cause = cause
      self.time = rcTime
      self.description = rcDesc
      self.score = score
      self.priority = priority
      # The alternative source provider that should be checked if this cause presents
      self.altSource = altSource

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

   def getPriority(self):
      return self.priority

   def getAltSource(self):
      return self.altSource

   def altSourceFromDict(self, data):
      if 'altSource' not in data or not data['altSource']:
         return None
      altSource = None
      try:
         altSource = ReloadCauseAltSource(data['altSource'])
      except ValueError:
         logging.warning(
            "%s:Unknown altSource %s found from json", self, data['altSource'])
      return altSource

   def toDict(self):
      return {
         'cause': self.cause,
         'time': self.time,
         'description': self.description,
         'score': self.score,
         'priority': self.priority,
         'altSource': self.altSource.value if self.altSource else None,
      }

   @classmethod
   def fromDict(cls, data):
      res = cls(
         cause=data['cause'],
         rcTime=data['time'],
         rcDesc=data['description'],
         score=data['score'],
         # If we load a new image onto an old version SONiC switch, its saved
         # reload cause entries might not have priority or altSource
         priority=(ReloadCausePriority.NORMAL if 'priority' not in data
                   else data['priority']),
      )
      res.altSource=res.altSourceFromDict(data)
      return res

class ReloadCauseProviderHelper(ReloadCauseProvider):
   def __init__(self, name='unknown', causes=None, extra=None,
                priority=ReloadCausePriority.PRIMARY,
                altSource=None):
      self.name = name
      self.causes = causes or []
      self.extra = extra or {}
      self.priority = priority
      # The alternative source this provider is serving as
      self.altSource = altSource or []

   def getSourceName(self):
      return self.name

   def getCauses(self):
      return self.causes

   def getExtra(self):
      return self.extra

   def getPriority(self):
      return self.priority

   def getAltSource(self):
      return self.altSource

   def altSourceFromDict(self, data):
      if 'altSource' not in data or not data['altSource']:
         return []
      altSource = []
      for source in data['altSource']:
         try:
            altSource.append(ReloadCauseAltSource(source))
         except ValueError:
            logging.warning(
               "%s:Unknown altSource %s found from json", self, source)
      return altSource

   def process(self):
      raise NotImplementedError

   def poll(self):
      return []

   def toDict(self):
      return {
         'name': self.getSourceName(),
         'causes': [c.toDict() for c in self.getCauses()],
         'extra': self.getExtra(),
         'priority': self.priority,
         'altSource': [altSource.value for altSource in self.altSource],
      }

   @classmethod
   def fromDict(cls, data):
      res = cls(
         name=data['name'],
         causes=[ReloadCauseEntry.fromDict(c) for c in data['causes']],
         extra=data['extra'],
         # If we load a new image onto an old version SONiC switch, its saved
         # reload cause providers might not have priority or altSource
         priority=(ReloadCausePriority.PRIMARY if 'priority' not in data
                   else data['priority']),
      )
      res.altSource=res.altSourceFromDict(data)
      return res

# Following classes are to specify different providers on the priority levels
# To keep the original behaviors unchanged, priority param needs to be set to
# PRIMARY in all child classes. They will eventually be replaced with **kwargs
# after all platforms are adapted to the design changes.
class PreRebootReloadCauseProvider(ReloadCauseProviderHelper):
   def __init__(self, priority=ReloadCausePriority.PREREBOOT, **kwargs):
      super().__init__(priority=priority, **kwargs)

   def process(self):
      raise NotImplementedError

class HardwareReloadCauseProvider(ReloadCauseProviderHelper):
   def __init__(self, priority=ReloadCausePriority.HARDWARE_SECONDARY, **kwargs):
      # if not mentioned, a hardware provider is not the main power controller
      super().__init__(priority=priority, **kwargs)

   def process(self):
      raise NotImplementedError

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
         if 'priority' not in item:
            item['priority'] = ReloadCausePriority.NORMAL
         if 'altSource' not in item:
            item['altSource'] = None
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
         try:
            provider.process()
            remotes = provider.getRemoteProviders()
            if remotes:
               self.providers.extend(remotes)
            else:
               self.providers.append(provider)
         except Exception:  # pylint: disable=broad-except
            sourceName = 'unknown'
            try:
               sourceName = provider.getSourceName()
            finally:
               logging.exception(
                  "Failed to get reload cause from provider %s", sourceName)

   def analyzeCauseFromProviders(self, providers, orderByScore):
      causes = defaultdict(list)
      for provider in providers:
         for cause in provider.getCauses():
            if orderByScore:
               causes[cause.getScore()].append(cause)
            else:
               causes[cause.getPriority()].append(cause)

      for _, causes in reversed(sorted(causes.items())):
         for cause in causes:
            # TODO: maybe sort causes by getTime but not that reliable
            return cause
      return None

   def analyzeCauses(self):
      cause = self.analyzeCauseFromProviders(self.providers, orderByScore=True)
      if cause is not None:
         self.cause = cause
         return

      self.cause = ReloadCauseEntry(
         cause='unknown',
         rcTime=datetimeToStr(self.date),
         rcDesc='could not find a valid reboot cause',
         score=ReloadCauseScore.UNKNOWN,
      )

   # This will be renamed to analyzeCauses after the function above is cleared
   def analyzeCausesNew(self):
      # Reorganizing all providers by their priorities
      # This block will be moved to provider processing when old logics are removed
      providerDict = {}
      for priority in ReloadCauseManager.NEW_VERSION_PRIORITIES:
         providerDict[priority] = []
      for provider in self.providers:
         if provider.getPriority() == ReloadCausePriority.PREREBOOT:
            providerDict[ReloadCausePriority.PREREBOOT].append(provider)
         elif provider.getPriority() == ReloadCausePriority.HARDWARE_MAIN:
            if providerDict[ReloadCausePriority.HARDWARE_MAIN]:
               mainProvider = providerDict[ReloadCausePriority.HARDWARE_MAIN][0]
               logging.warning("%s:Multiple main controllers found: %s already in "
                               "data, but %s is found",self,
                               mainProvider.getSourceName(),
                               provider.getSourceName())
            providerDict[ReloadCausePriority.HARDWARE_MAIN].append(provider)
         elif provider.getPriority() == ReloadCausePriority.HARDWARE_SECONDARY:
            providerDict[ReloadCausePriority.HARDWARE_SECONDARY].append(provider)
         elif provider.getPriority() == ReloadCausePriority.BERT:
            providerDict[ReloadCausePriority.BERT].append(provider)
         else:
            logging.warning("%s:Old version / unknown reload cause provider "
                            "priority %s found", self, provider.getPriority())
      # First check all prereboot providers
      preRebootProviders = providerDict[ReloadCausePriority.PREREBOOT]
      cause = self.analyzeCauseFromProviders(preRebootProviders, orderByScore=False)
      if cause:
         self.cause = cause
         return
      # If no prereboot cause found, check main controller
      mainHardwareProvider = providerDict[ReloadCausePriority.HARDWARE_MAIN]
      # In case multiple main controllers are found, pick the first one
      if len(mainHardwareProvider) > 1:
         mainHardwareProvider = mainHardwareProvider[:1]
      cause = self.analyzeCauseFromProviders(mainHardwareProvider,
                                             orderByScore=False)
      # If an altSource presents, check its reload cause
      checkedSource = []
      while cause and cause.getAltSource():
         if cause.getAltSource() in checkedSource:
            loopStr = ""
            for source in checkedSource:
               loopStr += source
               loopStr += " -> "
            loopStr += cause.getAltSource()
            logging.warning("%s:Alternative source loop %s found in providers. "
                            "Please review platform code", self, loopStr)
            # Use where the loop ends as the root cause as it is the same as picking
            # a random secondary source reload cause
            break
         checkedSource.append(cause.getAltSource())
         nextSourceProvider = None
         for provider in self.providers:
            if cause.getAltSource() in provider.getAltSource():
               nextSourceProvider = provider
         if not nextSourceProvider:
            logging.warning("%s:Alternative source %s is not in the provider list",
                            self, cause.getAltSource())
            break
         cause = self.analyzeCauseFromProviders([nextSourceProvider],
                                                orderByScore=False)
      if cause:
         self.cause = cause
         return
      # Finally, try to randomly pick one from secondary causes
      # This will be fixed to pick the firt available reload cause from the first
      # provider to ensure a stable output trend
      # Note that this is the unexpected behavior
      logging.warning("%s:No exact reload cause found through "
                      "software and main hardware controller. "
                      "Pick the first reload cause from the rest", self)
      hardwareProvider = providerDict[ReloadCausePriority.HARDWARE_SECONDARY]
      cause = self.analyzeCauseFromProviders(hardwareProvider, orderByScore=False)
      if cause:
         self.cause = cause
         return
      bertProvider = providerDict[ReloadCausePriority.BERT]
      cause = self.analyzeCauseFromProviders(bertProvider, orderByScore=False)
      if cause:
         self.cause = cause
         return

      self.cause = ReloadCauseEntry(
         cause='unknown',
         rcTime=datetimeToStr(self.date),
         rcDesc='could not find a valid reboot cause',
         score=ReloadCauseScore.UNKNOWN,
         priority=ReloadCausePriority.UNKNOWN,
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

   NEW_VERSION_PRIORITIES = [ReloadCausePriority.PREREBOOT,
                             ReloadCausePriority.HARDWARE_MAIN,
                             ReloadCausePriority.HARDWARE_SECONDARY,
                             ReloadCausePriority.BERT]

   def __init__(self, name=None, path=None):
      self.name = name
      self.path = path or flashPath('reboot-cause/platform/causes.json')
      self.loaded = False
      self.reports = []

   @classmethod
   def processReportCause(cls, report):
      return report

   def isProviderPriorityVersionNew(self, providers):
      '''Check if the providers are using the new version of priority or not'''
      # This is a temporary function and will be cleared once all platforms
      # get transformed into the new design. If there is necessity to keep
      # some of the platform running in the old design, it should be discussed
      # if this function should be kept
      res = None
      for provider in providers:
         # BERT is injected on all platforms regardless of their priority scheme,
         # so it cannot be used as a version indicator. Remove this skip once all
         # platforms have migrated to the new priority scheme.
         if provider.getPriority() == ReloadCausePriority.BERT:
            continue
         isNewVersion = provider.getPriority() in self.NEW_VERSION_PRIORITIES
         if res is None:
            res = isNewVersion
         else:
            assert res == isNewVersion, (
               "Found reload cause providers at different design versions")
      return res if res is not None else False

   def syncRtcs(self, inventory):
      '''Ensure all component clocks are properly updated'''
      for rtc in inventory.getRtcs():
         try:
            rtc.setTime(datetime.now())
         except Exception: # pylint: disable=broad-except
            logging.exception('failed to sync rtc %s', rtc.getName())

   def readCauses(self, inventory, date=None):
      '''Read reload causes from hardware'''
      try:
         self.loadCauses()
      except Exception: # pylint: disable=broad-except
         logging.exception("Failed to read previous reboot causes")
      self.syncRtcs(inventory)
      report = ReloadCauseReport(date=date or bootDatetime())
      providers = inventory.getReloadCauseProviders()
      report.processProviders(providers)
      if self.isProviderPriorityVersionNew(providers):
         report.analyzeCausesNew()
      else:
         report.analyzeCauses()
      # TODO: only add report if there is none for current boot
      #       probably a tempfile under /run/platform_cache/
      self.reports.insert(0, report)

   def fromDict(self, data):
      if data["version"] != self.VERSION:
         raise ValueError("Expected reload cause version to be %d" % self.VERSION)
      if data["name"] != self.name:
         logging.warning(
            "Expected reload cause name to match %s, existing name is %s",
            self.name, data["name"])
         data["name"] = self.name
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
