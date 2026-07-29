
import contextlib
import datetime
import json
import os
import tempfile
from unittest.mock import patch

from ...libs.fs import touch, rmfile
from ...libs.date import datetimeToStr, strToDatetime
from ...tests.testing import unittest
from ...descs.cause import ReloadCauseAltSource, ReloadCauseDesc
from ...drivers.scd.cause import SimpleScdReloadCauseProvider, ScdCause

from ...components.cookie import BertReloadCauseProvider
from ..cause import (
   ReloadCauseDataStore,
   ReloadCauseEntry,
   ReloadCauseManager,
   ReloadCauseProviderHelper,
   ReloadCausePriority,
   ReloadCauseScore,
)
from ..config import Config
from ..inventory import Inventory

class MockReloadCauseProvider(ReloadCauseProviderHelper):
   def __init__(self, name, causes, extra=None, **kwargs):
      super().__init__(name=name, causes=causes, extra=extra or {}, **kwargs)
      self.causesRead = False

   def process(self):
      self.causesRead = True

class ReloadCauseManagerTest(unittest.TestCase):
   EXPECTED_DATE = datetimeToStr(datetime.datetime.now())
   EXPECTED_SIMPLE = {
      "version": 3,
      "name": "switch reload cause",
      "reports": [
         {
            "date": EXPECTED_DATE,
            "cause": {
               'cause': 'powerloss',
               'time': EXPECTED_DATE,
               'description': 'user triggered',
               'score': ReloadCauseScore.LOGGED,
               'priority': ReloadCausePriority.NORMAL,
               'altSource': None,
            },
            "providers": [
               {
                  "name": "bert",
                  "causes": [],
                  "extra": {},
                  'priority': ReloadCausePriority.BERT,
                  'altSource': [],
               },
               {
                  "name": "primary provider",
                  "causes": [
                  ],
                  "extra": {},
                  'priority': ReloadCausePriority.HARDWARE_SECONDARY,
                  'altSource': [],
               },
               {
                  "name": "secondary provider",
                  "causes": [
                     {
                        'cause': 'powerloss',
                        'time': EXPECTED_DATE,
                        'description': 'user triggered',
                        'score': ReloadCauseScore.LOGGED,
                        'priority': ReloadCausePriority.NORMAL,
                        'altSource': None,
                     }
                  ],
                  "extra": {},
                  'priority': ReloadCausePriority.HARDWARE_SECONDARY,
                  'altSource': [],
               },
            ],
         },
      ],
   }
   STORED_SIMPLE_OLD_VERSION = {
      "version": 3,
      "name": "switch reload cause",
      "reports": [
         {
            "date": EXPECTED_DATE,
            "cause": {
               'cause': 'powerloss',
               'time': EXPECTED_DATE,
               'description': 'user triggered',
               'score': ReloadCauseScore.LOGGED,
            },
            "providers": [
               {
                  "name": "bert",
                  "causes": [],
                  "extra": {},
               },
               {
                  "name": "primary provider",
                  "causes": [
                  ],
                  "extra": {},
               },
               {
                  "name": "secondary provider",
                  "causes": [
                     {
                        'cause': 'powerloss',
                        'time': EXPECTED_DATE,
                        'description': 'user triggered',
                        'score': ReloadCauseScore.LOGGED,
                     }
                  ],
                  "extra": {},
               },
            ],
         },
      ],
   }
   PROVIDERS_SIMPLE = [
      MockReloadCauseProvider(
         name='primary provider',
         causes=[
         ],
      ),
      MockReloadCauseProvider(
         name='secondary provider',
         causes=[
            ReloadCauseEntry(
               cause='powerloss',
               rcTime=EXPECTED_DATE,
               rcDesc='user triggered',
               score=ReloadCauseScore.LOGGED,
            ),
         ],
      ),
      MockReloadCauseProvider(
         name='bert',
         causes=[],
         priority=ReloadCausePriority.BERT,
      ),
   ]

   def setUp(self):
      path = tempfile.mktemp(prefix='unittest-arista-rcm-', suffix='.json')
      self.rcm = ReloadCauseManager(name='switch reload cause', path=path)

   def tearDown(self):
      if os.path.exists(self.rcm.path):
         os.remove(self.rcm.path)

   def _getReloadCauseInventory(self, providers=None):
      if providers is None:
         providers = self.PROVIDERS_SIMPLE
      inventory = Inventory()
      inventory.addReloadCauseProviders(providers)
      return inventory

   def _loadReloadCauses(self, data):
      inv = self._getReloadCauseInventory([
         MockReloadCauseProvider(
            name=name,
            causes=[
               ReloadCauseEntry(
                  cause=cause,
                  rcTime=self.EXPECTED_DATE,
                  rcDesc=desc,
                  score=score,
                  priority=priority,
                  altSource=altSource,
               ) for cause, score, desc, priority, altSource in provider['causes']
            ],
            priority = (provider['priority'] if 'priority' in provider
                        else ReloadCausePriority.HARDWARE_SECONDARY),
            altSource = provider['altSource'] if 'altSource' in provider else []
         ) for name, provider in data.items()
      ])
      self.rcm.loaded = False
      self.rcm.readCauses(inv, date=strToDatetime(self.EXPECTED_DATE))

   def storeJson(self, data):
      with open(self.rcm.path, 'w') as f:
         json.dump(data, f)

   def assertCauseStoreEqual(self, expected):
      with open(self.rcm.path) as f:
         data = json.load(f)
      self.maxDiff = None
      self.assertDictEqual(data, expected)

   def testReloadCauseManager(self):
      inv = self._getReloadCauseInventory()
      self.rcm.readCauses(inv)

      for provider in inv.getReloadCauseProviders():
         self.assertTrue(provider.causesRead)

   def testToFromDict(self):
      self.rcm.fromDict(self.EXPECTED_SIMPLE)
      result = self.rcm.toDict()
      self.assertDictEqual(self.EXPECTED_SIMPLE, result,
         msg='Serialization/Deserialization of reload cause failed')

   def testLoadOldVersionStore(self):
      # This is for special cases if there are mismatches between reload cause
      # versions running on the switch and the stored reload causes from an older
      # image
      self.storeJson(self.STORED_SIMPLE_OLD_VERSION)
      self.rcm.loadCauses()
      self.assertReloadCauseEquals(self.rcm.lastReport().cause, cause='powerloss',
                                   priority=ReloadCausePriority.NORMAL)
      self.rcm.storeCauses()
      self.assertCauseStoreEqual(self.EXPECTED_SIMPLE)

   def testLoadStore(self):
      self.storeJson(self.EXPECTED_SIMPLE)
      self.rcm.loadCauses()
      self.rcm.storeCauses()
      self.assertCauseStoreEqual(self.EXPECTED_SIMPLE)

   def testLoadEmptyFile(self):
      touch(self.rcm.path)
      self.rcm.loadCauses()

   def testLoadMissingFile(self):
      self.rcm.loadCauses()
      self.rcm.storeCauses()
      self.assertCauseStoreEqual({
         "name": 'switch reload cause',
         "reports": [],
         "version": 3,
      })

   def testLoadReadStore(self):
      inv = self._getReloadCauseInventory()
      self.rcm.readCauses(inv, date=strToDatetime(self.EXPECTED_DATE))
      self.rcm.storeCauses()
      self.assertCauseStoreEqual(self.EXPECTED_SIMPLE)

   BERT_LINES = [
      'Processor Generic error, severity: Fatal',
      'Memory error, severity: Corrected, FRU: DIMM_A1',
   ]

   def _runBertProvider(self, bertLines):
      provider = BertReloadCauseProvider()
      with patch('arista.components.cookie.getBertDetail', return_value=bertLines):
         provider.process()
      return provider

   def testBertNoBertData(self):
      provider = self._runBertProvider(None)
      self.assertEqual(provider.getCauses(), [])

   def testBertDataProducesEntry(self):
      provider = self._runBertProvider(self.BERT_LINES)
      causes = provider.getCauses()
      self.assertEqual(len(causes), 1)
      cause = causes[0]
      self.assertEqual(cause.getCause(), 'cpu')
      self.assertEqual(cause.getDescription(), ' | '.join(self.BERT_LINES))
      self.assertEqual(cause.getScore(),
                       ReloadCauseScore.LOGGED | ReloadCauseScore.DETAILED)
      self.assertEqual(cause.getPriority(), ReloadCausePriority.BERT)

   def assertReloadCauseEquals(self, rc, cause=None, description=None, score=None,
                               time=None, priority=None, altSource=None):
      self.assertIsInstance(rc, ReloadCauseEntry)
      if cause is not None:
         self.assertEqual(rc.getCause(), cause)
      if description is not None:
         self.assertEqual(rc.getDescription(), description)
      if time is not None:
         self.assertEqual(rc.getTime(), time)
      if score is not None:
         self.assertEqual(rc.getScore(), score)
      if priority is not None:
         self.assertEqual(rc.getPriority(), priority)
      if altSource is not None:
         self.assertEqual(rc.getAltSource(), altSource)

   def testReloadCauseAlgorithmNew(self):
      # 1) insert 1 secondary hardware with 2 causes, see prioritized cause selected
      self._loadReloadCauses({
         'secondary' : {
            'priority' : ReloadCausePriority.HARDWARE_SECONDARY,
            'causes' : [
               # set score to unknown to make sure priority is the real order factor
               ('under-voltage', ReloadCauseScore.UNKNOWN, 'Rail X',
                ReloadCausePriority.NORMAL, None),
               ('unknown', ReloadCauseScore.EVENT, 'Rail Y',
                ReloadCausePriority.NONE, None),
            ]
         }
      })
      self.assertReloadCauseEquals(self.rcm.lastReport().cause,
                                   cause='under-voltage')
      # 2) insert 2 secondary hardware and see any cause selected
      self._loadReloadCauses({
         'secondary1' : {
            'priority' : ReloadCausePriority.HARDWARE_SECONDARY,
            'causes' : [
               ('under-voltage', ReloadCauseScore.EVENT, 'Rail X',
                ReloadCausePriority.NORMAL, None),
            ]
         },
         'secondary2' : {
            'priority' : ReloadCausePriority.HARDWARE_SECONDARY,
            'causes' : [
               ('unknown', ReloadCauseScore.EVENT, 'Rail Y',
                ReloadCausePriority.NORMAL, None),
            ]
         }
      })
      self.assertReloadCauseEquals(self.rcm.lastReport().cause,
                                   cause='under-voltage')
      # 3) insert 1 main hardware and 1 secondary
      self._loadReloadCauses({
         'main' : {
            'priority' : ReloadCausePriority.HARDWARE_MAIN,
            'causes' : [
               # set score to unknown to make sure main controller prioritized
               ('powerloss', ReloadCauseScore.UNKNOWN, 'user triggered',
                ReloadCausePriority.NORMAL, None),
            ]
         },
         'secondary' : {
            'priority' : ReloadCausePriority.HARDWARE_SECONDARY,
            'causes' : [
               ('under-voltage', ReloadCauseScore.EVENT, 'Rail Y',
                ReloadCausePriority.NORMAL, None),
            ]
         }
      })
      self.assertReloadCauseEquals(self.rcm.lastReport().cause, cause='powerloss')
      # 4) insert 1 main hardware but altSource is 1 secondary
      self._loadReloadCauses({
         'main' : {
            'priority' : ReloadCausePriority.HARDWARE_MAIN,
            'causes' : [
               ('cpu', ReloadCauseScore.EVENT, 'secondary reported',
                ReloadCausePriority.NORMAL, ReloadCauseAltSource.CPU),
            ]
         },
         'secondary-CPU' : {
            'priority' : ReloadCausePriority.HARDWARE_SECONDARY,
            'causes' : [
               ('under-voltage', ReloadCauseScore.EVENT, 'Rail Y',
                ReloadCausePriority.NORMAL, None),
            ],
            'altSource' : [ReloadCauseAltSource.CPU]
         }
      })
      self.assertReloadCauseEquals(self.rcm.lastReport().cause,
                                   cause='under-voltage')
      # 5) insert 1 prereboot, 1 main hardware, and 1 secondary
      self._loadReloadCauses({
         'cookies' : {
            'priority' : ReloadCausePriority.PREREBOOT,
            'causes' : [
               ('reboot', ReloadCauseScore.UNKNOWN, 'User issued reboot command',
                ReloadCausePriority.NORMAL, None),
            ]
         },
         'main' : {
            'priority' : ReloadCausePriority.HARDWARE_MAIN,
            'causes' : [
               ('cpu', ReloadCauseScore.EVENT, 'secondary reported',
                ReloadCausePriority.NORMAL, ReloadCauseAltSource.CPU),
            ]
         },
         'secondary-CPU' : {
            'priority' : ReloadCausePriority.HARDWARE_SECONDARY,
            'causes' : [
               ('under-voltage', ReloadCauseScore.EVENT, 'Rail Y',
                ReloadCausePriority.NORMAL, None),
            ],
            'altSource' : [ReloadCauseAltSource.CPU]
         }
      })
      self.assertReloadCauseEquals(self.rcm.lastReport().cause, cause='reboot')
      # 6) test unknown cause
      self._loadReloadCauses({})
      self.assertReloadCauseEquals(self.rcm.lastReport().cause, cause='unknown')
      # 7) bert present alongside a prereboot cause: prereboot wins
      self._loadReloadCauses({
         'cookies' : {
            'priority' : ReloadCausePriority.PREREBOOT,
            'causes' : [
               ('reboot', ReloadCauseScore.EVENT, 'User issued reboot command',
                ReloadCausePriority.NORMAL, None),
            ]
         },
         'bert' : {
            'priority' : ReloadCausePriority.BERT,
            'causes' : [
               ('cpu', ReloadCauseScore.LOGGED | ReloadCauseScore.DETAILED,
                'Processor Generic error, severity: Fatal',
                ReloadCausePriority.BERT, None),
            ]
         },
      })
      self.assertReloadCauseEquals(self.rcm.lastReport().cause, cause='reboot')
      self.assertEqual(len(self.rcm.reports), 7)

   @contextlib.contextmanager
   def _processLegacyReloadCauses(self, causes):
      path = tempfile.mktemp(prefix='unittest-arista-reload-cause-')
      oldPath = Config().reboot_cause_file
      try:
         Config().reboot_cause_file = path
         with open(path, 'w') as f:
            json.dump(causes, f)
         yield path
         self.assertFalse(os.path.exists(path))
      finally:
         Config().reboot_cause_file = oldPath
         if os.path.exists(path):
            os.remove(path)

   def testScdDescsStableAfterProcess(self):
      class MockScd:
         def __str__(self):
            return 'MockScd'

      causes = [
         ScdCause(0x01, ReloadCauseDesc.POWERLOSS),
         ScdCause(0x02, ReloadCauseDesc.WATCHDOG),
      ]
      provider = SimpleScdReloadCauseProvider(MockScd(), 0x5010, causes)
      self.assertEqual(len(provider.getReloadCauseDescs()), 2)

      # Simulate process() overwriting self.causes (the runtime result field)
      provider.causes = []

      descs = provider.getReloadCauseDescs()
      self.assertEqual(len(descs), 2)
      self.assertEqual(descs[0].typ, 'powerloss')
      self.assertEqual(descs[1].typ, 'watchdog')

   def testLegacyV1ToCurrent(self):
      causes = [{
            'reloadReason': 'powerloss',
            'time': '1970-01-01 00:01:11 UTC',
         }, {
            'reloadReason': 'reboot',
            'time': 'unknown',
      }]
      with self._processLegacyReloadCauses(causes):
         self.rcm.loadCauses()
         self.assertEqual(len(self.rcm.allReports()), 1)
         report = self.rcm.lastReport()
         reportCauses = report.providers[0].getCauses()
         self.assertEqual(len(reportCauses), len(causes))
         for cause, reportCause in zip(causes, reportCauses):
            self.assertEqual(cause['reloadReason'], reportCause.getCause())
            self.assertEqual(cause['time'], reportCause.getTime())

class ReloadCauseTest(unittest.TestCase):
   EXPECTED = [
      ReloadCauseEntry(cause='powerloss', rcTime='1970-01-01 00:01:11 UTC'),
      ReloadCauseEntry(cause='reboot', rcTime='unknown'),
   ]

   def setUp(self):
      self.tempfile = tempfile.mktemp(prefix='unittest-arista-reload-cause-')
      Config().reboot_cause_file = self.tempfile
      self.rcds = ReloadCauseDataStore(name=self.tempfile, path=self.tempfile)

   def tearDown(self):
      rmfile(self.tempfile)

   def _writeJsonReloadCause(self, data):
      with open(self.tempfile, 'w') as f:
         json.dump(data, f)

   def _assertReloadCauseEqual(self, value, expected):
      self.assertEqual(value.cause, expected.cause)
      self.assertEqual(value.time, expected.time)
      self.assertEqual(value.description, expected.description)

   def _assertReloadCauseListEqual(self, value, expected):
      self.assertEqual(len(value), len(expected),
                       msg='Reload cause count invalid')
      for v, e in zip(value, expected):
         self._assertReloadCauseEqual(v, e)

   def testEmptyReloadCauseFile(self):
      touch(self.tempfile)
      self._assertReloadCauseListEqual(self.rcds.readCauses(), [])

   def testCompatibilityFormatV1(self):
      '''Verify that the parser can import reload cause with V1 format'''
      self._writeJsonReloadCause([
         {
            'reloadReason': 'powerloss',
            'time': '1970-01-01 00:01:11 UTC',
         }, {
            'reloadReason': 'reboot',
            'time': 'unknown',
         },
      ])
      self._assertReloadCauseListEqual(self.rcds.readCauses(), self.EXPECTED)

   def testRebootCauseDataStore(self):
      self.rcds.writeCauses(self.EXPECTED)
      causes = self.rcds.readCauses()
      self._assertReloadCauseListEqual(causes, self.EXPECTED)

   def testToPreventCompatibilityBreakage(self):
      cause = ReloadCauseEntry()
      expectedKeys = [
         "cause",
         "description",
         "score",
         "time",
         "priority",
         "altSource",
         "debugInfo",
      ]
      self.assertEqual(len(cause.__dict__), len(expectedKeys))
      self.assertEqual(set(cause.__dict__), set(expectedKeys))

   def testDebugInfoRoundTrip(self):
      entry = ReloadCauseEntry(cause='fault', debugInfo='ab cd')
      self.assertEqual(ReloadCauseEntry.fromDict(entry.toDict()).debugInfo, 'ab cd')

   def testDebugInfoDefaultsToNoneFromOldJson(self):
      # Json written before debugInfo existed must deserialize with debugInfo=None.
      entry = ReloadCauseEntry.fromDict(ReloadCauseEntry(cause='fault').toDict())
      self.assertIsNone(entry.debugInfo)

if __name__ == '__main__':
   unittest.main()
