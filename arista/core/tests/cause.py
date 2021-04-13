
import contextlib
import datetime
import json
import os
import tempfile

from ...libs.fs import touch, rmfile
from ...libs.date import datetimeToStr, strToDatetime
from ...tests.testing import unittest

from ..cause import (
   ReloadCauseDataStore,
   ReloadCauseEntry,
   ReloadCauseManager,
   ReloadCauseProviderHelper,
   ReloadCauseScore,
)
from ..config import Config
from ..inventory import Inventory

class MockReloadCauseProvider(ReloadCauseProviderHelper):
   def __init__(self, name, causes, extra=None):
      super(MockReloadCauseProvider, self).__init__(name=name, causes=causes,
                                                    extra=extra or {})
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
            },
            "providers": [
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
   ]

   def setUp(self):
      path = tempfile.mktemp(prefix='unittest-arista-rcm-', suffix='.json')
      self.rcm = ReloadCauseManager(name='switch reload cause', path=path)

   def tearDown(self):
      if os.path.exists(self.rcm.path):
         os.remove(self.rcm.path)

   def _getReloadCauseInventory(self, providers=None):
      inventory = Inventory()
      inventory.addReloadCauseProviders(providers or self.PROVIDERS_SIMPLE)
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
               ) for cause, score, desc in causes
            ]
         ) for name, causes in data.items()
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

   def assertReloadCauseEquals(self, rc, cause=None, description=None, score=None,
                               time=None):
      self.assertIsInstance(rc, ReloadCauseEntry)
      if cause is not None:
         self.assertEqual(rc.getCause(), cause)
      if description is not None:
         self.assertEqual(rc.getDescription(), description)
      if time is not None:
         self.assertEqual(rc.getTime(), time)
      if score is not None:
         self.assertEqual(rc.getScore(), score)

   def testReloadCauseAlgorithm(self):
      self._loadReloadCauses({
         'primary': [
            ('under-voltage', ReloadCauseScore.EVENT, 'Rail X'),
         ],
         'secondary': [
            ('under-voltage', ReloadCauseScore.EVENT, 'Rail Y'),
            ('powerloss', ReloadCauseScore.LOGGED, 'user triggered'),
         ],
      })
      self.assertReloadCauseEquals(self.rcm.lastReport().cause, cause='powerloss')
      self._loadReloadCauses({
         'primary': [
            ('under-voltage', ReloadCauseScore.EVENT, 'Rail X'),
         ],
         'secondary': [
            ('under-voltage', ReloadCauseScore.EVENT, 'Rail Y'),
         ],
      })
      self.assertReloadCauseEquals(self.rcm.lastReport().cause,
                                   cause='under-voltage')
      self.assertEqual(len(self.rcm.reports), 2)

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
      ]
      self.assertEqual(len(cause.__dict__), len(expectedKeys))
      self.assertEqual(set(cause.__dict__), set(expectedKeys))

if __name__ == '__main__':
   unittest.main()
