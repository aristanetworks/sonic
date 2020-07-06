
import json
import tempfile

from ...tests.testing import unittest
from ...libs.fs import touch, rmfile

from ..cause import ReloadCauseDataStore, ReloadCauseEntry
from ..config import Config

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
         "time",
      ]
      self.assertEqual(len(cause.__dict__), len(expectedKeys))
      self.assertEqual(set(cause.__dict__), set(expectedKeys))

if __name__ == '__main__':
   unittest.main()
