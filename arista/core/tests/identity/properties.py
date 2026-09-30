
# pylint: disable=protected-access

from ....tests.testing import unittest, patch

from ...identity.base import PlatformIdentityBase, Prefdls

from .common import (
   PREFDL_DATA,
   CPU_PREFDL_DATA,
   makePrefdl,
   makeManager,
   makeBaseIdentity,
)


class PlatformIdentityBasePropertiesTest(unittest.TestCase):

   def testSyseeprom(self):
      identity = makeBaseIdentity(switchData=PREFDL_DATA)
      self.assertEqual(identity.syseeprom.get('SID'), 'TestProduct')

   def testSyseepromTriggersLazyInit(self):
      prefdls = Prefdls(makePrefdl(PREFDL_DATA), None)
      identity = PlatformIdentityBase(makeManager(), cmdline={})
      self.assertFalse(identity._initialized)
      def doRead():
         identity._prefdls = prefdls
      with patch.object(identity, '_readPrefdl',
                        side_effect=doRead) as mockRead:
         result = identity.syseeprom
      mockRead.assert_called_once()
      self.assertIs(result, prefdls.switch)

   def testCpueeprom(self):
      identity = makeBaseIdentity(
         switchData=PREFDL_DATA, cpuData=CPU_PREFDL_DATA)
      self.assertEqual(identity.cpueeprom.get('SID'), 'CpuBoard')

   def testCpueepromNone(self):
      identity = makeBaseIdentity(switchData=PREFDL_DATA)
      self.assertIsNone(identity.cpueeprom)

   def testHwApi(self):
      identity = makeBaseIdentity(switchData=PREFDL_DATA)
      self.assertEqual(identity.hwApi, (2, 0))


if __name__ == '__main__':
   unittest.main()
