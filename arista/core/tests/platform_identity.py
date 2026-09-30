
from ...tests.testing import unittest, patch

from ..platform import (
   readSid,
   readSku,
   readPlatformName,
   readHwApi,
   SysEeprom,
)

from .identity.common import makeNonDmiIdentity


class ReadHelpersDelegationTest(unittest.TestCase):

   @patch('arista.core.platform.getPlatformIdentity')
   def testReadSid(self, mockGetIdentity):
      mockGetIdentity.return_value = makeNonDmiIdentity(cmdline={'sid': 'test-sid'})
      self.assertEqual(readSid(), 'test-sid')

   @patch('arista.core.platform.getPlatformIdentity')
   def testReadSku(self, mockGetIdentity):
      mockGetIdentity.return_value = makeNonDmiIdentity(
         switchData={'SKU': 'DCS-TEST-42'})
      self.assertEqual(readSku(), 'DCS-TEST-42')

   @patch('arista.core.platform.getPlatformIdentity')
   def testReadPlatformName(self, mockGetIdentity):
      mockGetIdentity.return_value = makeNonDmiIdentity(
         cmdline={'platform': 'raven'})
      self.assertEqual(readPlatformName(), 'raven')

   @patch('arista.core.platform.getPlatformIdentity')
   def testReadPlatformNameNone(self, mockGetIdentity):
      mockGetIdentity.return_value = makeNonDmiIdentity()
      self.assertIsNone(readPlatformName())

   @patch('arista.core.platform.getPlatformIdentity')
   def testReadHwApi(self, mockGetIdentity):
      mockGetIdentity.return_value = makeNonDmiIdentity(
         switchData={'SKU': 'X', 'HwApi': '03.00'})
      self.assertEqual(readHwApi(), (3, 0))


class SysEepromReadPrefdlTest(unittest.TestCase):

   @patch('arista.core.platform.getPlatformIdentity')
   def testReadPrefdlDelegatesToIdentity(self, mockGetIdentity):
      mockGetIdentity.return_value = makeNonDmiIdentity(
         switchData={'SKU': 'DCS-TEST', 'SID': 'Test'})
      eeprom = SysEeprom()
      result = eeprom.readPrefdl()
      self.assertEqual(result.get('SKU'), 'DCS-TEST')
      self.assertEqual(result.get('SID'), 'Test')


if __name__ == '__main__':
   unittest.main()
