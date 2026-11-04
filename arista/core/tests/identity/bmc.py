from unittest.mock import Mock, PropertyMock

from ....tests.testing import unittest, patch

from ...exception import UnknownPlatformError
from ...identity.bmc import PlatformIdentityBmc
from ...prefdl import Prefdl

from .common import DummyLoader


class FakeBmc:
   MODEL = ['TestBmc']
   prefdl = None

   @classmethod
   def readChassisEeprom(cls):
      return cls.prefdl


class FakeBmcSubsystem:
   BMC_CLS = FakeBmc
   HOST_SWITCH_CLS = Mock(SID=['TestSid'])


class PlatformIdentityBmcTest(unittest.TestCase):

   def setUp(self):
      FakeBmc.prefdl = Prefdl.fromDict({
         'SID': 'TestSid',
         'SKU': 'DCS-TEST-42',
      })
      _loader = DummyLoader()
      _loader.bmcs.add(FakeBmc)
      _loader.bmc_subsystems.add(FakeBmcSubsystem)

      self._loader = _loader

   def _makeIdentity(self):
      identity = PlatformIdentityBmc(cmdline={})
      identity._loader = self._loader  # pylint: disable=protected-access
      return identity

   def testPlatformLookup(self):
      identity = self._makeIdentity()
      with patch('arista.core.identity.bmc.readBmcDeviceTreeModel',
                 return_value='TestBmc'), \
           patch('arista.core.identity.bmc.loadPrerequisites'):
         self.assertIs(identity.getPlatformCls(), FakeBmcSubsystem)
      self.assertEqual(identity.syseeprom.get('SID'), 'TestSid')
      self.assertTrue(identity.syseeprom.toList())

   def testPlatformLookupWithName(self):
      with self.assertRaisesRegex(UnknownPlatformError, 'does not accept name'):
         self._makeIdentity().getPlatformCls('TestBmc')

   def testIdentificationDoesNotUseSyseeprom(self):
      """Keep chassis-based identification independent of syseeprom so it can
      expose the BMC EEPROM without changing platform selection.
      """
      identity = self._makeIdentity()
      with patch('arista.core.identity.bmc.readBmcDeviceTreeModel',
                 return_value='TestBmc'), \
           patch('arista.core.identity.bmc.loadPrerequisites'), \
           patch.object(PlatformIdentityBmc, 'syseeprom',
                        new_callable=PropertyMock) as systemEeprom, \
           patch.object(FakeBmc, 'readChassisEeprom',
                        return_value=FakeBmc.prefdl) as read:
         self.assertEqual(identity.sid, 'TestSid')
         self.assertIs(identity.getPlatformCls(), FakeBmcSubsystem)
         self.assertEqual(identity.sid, 'TestSid')
      systemEeprom.assert_not_called()
      read.assert_called_once()

   def testReadFailureCanBeRetried(self):
      """A failed chassis read must leave identity uninitialized so a later
      platform lookup retries the read and can succeed.
      """
      identity = self._makeIdentity()
      with patch('arista.core.identity.bmc.readBmcDeviceTreeModel',
                 return_value='TestBmc'), \
           patch('arista.core.identity.bmc.loadPrerequisites'), \
           patch.object(FakeBmc, 'readChassisEeprom',
                        side_effect=[OSError('read failed'), FakeBmc.prefdl]):
         with self.assertRaises(OSError):
            identity.getPlatformCls()
         self.assertIs(identity.getPlatformCls(), FakeBmcSubsystem)

   def testPlatformLookupWithUnknownModel(self):
      with patch('arista.core.identity.bmc.readBmcDeviceTreeModel',
                 return_value='Unknown'):
         with self.assertRaisesRegex(
                  UnknownPlatformError,
                  'Unknown.*supported BMC models: TestBmc'):
            self._makeIdentity().getPlatformCls()

   def testPlatformLookupWithEmptySid(self):
      FakeBmc.prefdl = Prefdl.fromDict({})
      with patch('arista.core.identity.bmc.readBmcDeviceTreeModel',
                 return_value='TestBmc'), \
           patch('arista.core.identity.bmc.loadPrerequisites'):
         with self.assertRaisesRegex(UnknownPlatformError, 'empty SID'):
            self._makeIdentity().getPlatformCls()

   def testPlatformLookupWithUnknownSid(self):
      FakeBmc.prefdl = Prefdl.fromDict({'SID': 'Unknown'})
      with patch('arista.core.identity.bmc.readBmcDeviceTreeModel',
                 return_value='TestBmc'), \
           patch('arista.core.identity.bmc.loadPrerequisites'):
         with self.assertRaisesRegex(
                  UnknownPlatformError,
                  'No BMC subsystem.*TestBmc.*Unknown'):
            self._makeIdentity().getPlatformCls()


if __name__ == '__main__':
   unittest.main()
