from unittest.mock import Mock, PropertyMock

from ....tests.testing import unittest, patch

from ...exception import UnknownPlatformError
from ...identity.bmc import PlatformIdentityBmc
from ...prefdl import Prefdl
from ...platform import SysEeprom

from .common import DummyLoader


class FakeBmc:
   MODEL = ['TestBmc']
   chassisPrefdl = None
   bmcPrefdl = None

   @classmethod
   def readBmcEeprom(cls):
      return cls.bmcPrefdl

   @classmethod
   def readChassisEeprom(cls):
      return cls.chassisPrefdl


class FakeBmcSubsystem:
   BMC_CLS = FakeBmc
   HOST_SWITCH_CLS = Mock(SID=['TestSid'])


class PlatformIdentityBmcTest(unittest.TestCase):

   def setUp(self):
      FakeBmc.bmcPrefdl = Prefdl.fromDict({
         'SID': 'BmcSid',
         'SKU': 'BMC-TEST',
         'SerialNumber': 'BMC-SERIAL',
      })
      FakeBmc.chassisPrefdl = Prefdl.fromDict({
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
         self.assertEqual(identity.syseeprom.get('SID'), 'BmcSid')
         self.assertEqual(identity.sid, 'TestSid')
      self.assertTrue(identity.syseeprom.toList())

   def testSyseepromDoesNotReadChassis(self):
      """System EEPROM consumers must receive BMC data without requiring a
      chassis EEPROM read, and repeated accesses must reuse the BMC data.
      """
      identity = self._makeIdentity()
      with patch('arista.core.identity.bmc.readBmcDeviceTreeModel',
                 return_value='TestBmc'), \
           patch('arista.core.identity.bmc.loadPrerequisites'), \
           patch.object(FakeBmc, 'readChassisEeprom',
                        side_effect=OSError('chassis unavailable')) as chassis, \
           patch.object(FakeBmc, 'readBmcEeprom',
                        return_value=FakeBmc.bmcPrefdl) as bmc, \
           patch('arista.core.platform.getPlatformIdentity',
                 return_value=identity):
         self.assertIs(SysEeprom().readPrefdl(), FakeBmc.bmcPrefdl)
         self.assertIs(identity.syseeprom, FakeBmc.bmcPrefdl)
         self.assertIsNone(identity.cpueeprom)
      chassis.assert_not_called()
      bmc.assert_called_once()

   def testIdentificationDoesNotReadBmc(self):
      """An unavailable BMC EEPROM must not prevent chassis-based lookup."""
      identity = self._makeIdentity()
      with patch('arista.core.identity.bmc.readBmcDeviceTreeModel',
                 return_value='TestBmc'), \
           patch('arista.core.identity.bmc.loadPrerequisites'), \
           patch.object(FakeBmc, 'readBmcEeprom',
                        side_effect=OSError('BMC unavailable')) as bmc:
         self.assertIs(identity.getPlatformCls(), FakeBmcSubsystem)
         self.assertEqual(identity.sid, 'TestSid')
      bmc.assert_not_called()

   def testBmcReadFailureCanBeRetried(self):
      """A failed BMC read must not cache incomplete system EEPROM data."""
      identity = self._makeIdentity()
      with patch('arista.core.identity.bmc.readBmcDeviceTreeModel',
                 return_value='TestBmc'), \
           patch('arista.core.identity.bmc.loadPrerequisites'), \
           patch.object(FakeBmc, 'readBmcEeprom',
                        side_effect=[OSError('read failed'), FakeBmc.bmcPrefdl]):
         with self.assertRaises(OSError):
            _ = identity.syseeprom
         self.assertIs(identity.syseeprom, FakeBmc.bmcPrefdl)

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
                        return_value=FakeBmc.chassisPrefdl) as read:
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
                        side_effect=[OSError('read failed'), FakeBmc.chassisPrefdl]):
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
      FakeBmc.chassisPrefdl = Prefdl.fromDict({})
      with patch('arista.core.identity.bmc.readBmcDeviceTreeModel',
                 return_value='TestBmc'), \
           patch('arista.core.identity.bmc.loadPrerequisites'):
         with self.assertRaisesRegex(UnknownPlatformError, 'empty SID'):
            self._makeIdentity().getPlatformCls()

   def testPlatformLookupWithUnknownSid(self):
      FakeBmc.chassisPrefdl = Prefdl.fromDict({'SID': 'Unknown'})
      with patch('arista.core.identity.bmc.readBmcDeviceTreeModel',
                 return_value='TestBmc'), \
           patch('arista.core.identity.bmc.loadPrerequisites'):
         with self.assertRaisesRegex(
                  UnknownPlatformError,
                  'No BMC subsystem.*TestBmc.*Unknown'):
            self._makeIdentity().getPlatformCls()


if __name__ == '__main__':
   unittest.main()
