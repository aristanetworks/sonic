
# pylint: disable=protected-access

import os
import shutil
import tempfile

from ....tests.testing import unittest, patch

from ...exception import UnknownPlatformError
from ...identity.non_dmi import PlatformIdentityNonDmi
from ...prefdl import Prefdl
from ....components.eeprom import I2cEeprom

from .common import (
   PREFDL_DATA,
   makePrefdl,
   makeNonDmiIdentity,
)


class ReadPrefdlNonDmiTest(unittest.TestCase):

   def _makeIdentity(self):
      return PlatformIdentityNonDmi(cmdline={})

   def _patchSimulation(self):
      return patch('arista.core.identity.non_dmi.inSimulation', return_value=False)

   def testLazyInit(self):
      identity = PlatformIdentityNonDmi(cmdline={})
      prefdl = makePrefdl(PREFDL_DATA)
      with patch('arista.core.identity.non_dmi.inSimulation', return_value=False), \
           patch.object(identity, '_readCachedPrefdl', return_value=prefdl) as read:
         self.assertIsNone(identity.cpueeprom)
         read.assert_not_called()
         self.assertIs(identity.syseeprom, prefdl)
         self.assertEqual(identity.sku, 'DCS-TEST-42')
         self.assertIs(identity.syseeprom, prefdl)
      read.assert_called_once()

   def testCacheHit(self):
      prefdl = makePrefdl(PREFDL_DATA)
      identity = self._makeIdentity()
      with self._patchSimulation(), \
           patch.object(identity, '_readCachedPrefdl', return_value=prefdl), \
           patch.object(identity, '_writePrefdlCacheFile') as mockWrite:
         identity._readPrefdl()
      self.assertIs(identity.syseeprom, prefdl)
      self.assertIsNone(identity.cpueeprom)
      mockWrite.assert_not_called()

   def testHostPrefdl(self):
      prefdl = makePrefdl(PREFDL_DATA)
      identity = self._makeIdentity()
      with self._patchSimulation(), \
           patch.object(identity, '_readCachedPrefdl', return_value=None), \
           patch.object(identity, '_readHostPrefdl', return_value=prefdl), \
           patch.object(identity, '_readUpperlakeI2cPrefdl') as mockI2c, \
           patch.object(identity, '_writePrefdlCacheFile') as mockWrite:
         identity._readPrefdl()
      self.assertIs(identity.syseeprom, prefdl)
      mockWrite.assert_called_once_with(prefdl)
      mockI2c.assert_not_called()

   def testUpperlakeI2cFallback(self):
      prefdl = makePrefdl(PREFDL_DATA)
      identity = PlatformIdentityNonDmi(cmdline={'sid': 'Upperlake-Test'})
      with self._patchSimulation(), \
           patch.object(identity, '_readCachedPrefdl', return_value=None), \
           patch.object(identity, '_readHostPrefdl', return_value=None), \
           patch.object(identity, '_readUpperlakeI2cPrefdl',
                        return_value=prefdl) as mockI2c, \
           patch.object(identity, '_writePrefdlCacheFile') as mockWrite:
         self.assertIs(identity.syseeprom, prefdl)
         self.assertIs(identity.syseeprom, prefdl)
      mockI2c.assert_called_once_with()
      mockWrite.assert_called_once_with(prefdl)

   def testI2cFallbackSkippedForOtherSids(self):
      for sid in (None, '', 'OtherPlatform'):
         with self.subTest(sid=sid):
            identity = PlatformIdentityNonDmi(cmdline={'sid': sid})
            with self._patchSimulation(), \
                 patch.object(identity, '_readCachedPrefdl', return_value=None), \
                 patch.object(identity, '_readHostPrefdl', return_value=None), \
                 patch.object(identity, '_readUpperlakeI2cPrefdl') as mockI2c, \
                 patch.object(identity, '_writePrefdlCacheFile') as mockWrite:
               with self.assertRaises(UnknownPlatformError):
                  _ = identity.syseeprom
            mockI2c.assert_not_called()
            mockWrite.assert_not_called()

   def testI2cPrefdlSetup(self):
      """Exercise real component setup with hardware operations mocked."""
      prefdl = makePrefdl(PREFDL_DATA)
      identity = self._makeIdentity()
      with patch('arista.core.identity.non_dmi.loadPrerequisites'), \
           patch('arista.core.identity.non_dmi.I2cBus'), \
           patch.object(I2cEeprom, 'DRIVER') as driverCls, \
           patch.object(I2cEeprom, 'readPrefdl', return_value=prefdl):
         self.assertIs(identity._readUpperlakeI2cPrefdl(), prefdl)
      driverCls.return_value.setup.assert_called_once_with()
      driverCls.return_value.finish.assert_called_once_with()

   def testNoPrefdlSources(self):
      identity = PlatformIdentityNonDmi(cmdline={'sid': 'Upperlake'})
      with self._patchSimulation(), \
           patch.object(identity, '_readCachedPrefdl', return_value=None), \
           patch.object(identity, '_readHostPrefdl', return_value=None), \
           patch.object(identity, '_readUpperlakeI2cPrefdl', return_value=None), \
           patch.object(identity, '_writePrefdlCacheFile'):
         with self.assertRaises(UnknownPlatformError):
            identity._readPrefdl()

   def testReadFailureCanBeRetried(self):
      """A failed host PreFDL read must not prevent a later EEPROM access
      from retrying the read and initializing identity successfully.
      """
      identity = self._makeIdentity()
      prefdl = makePrefdl(PREFDL_DATA)
      with self._patchSimulation(), \
           patch.object(identity, '_readCachedPrefdl', return_value=None), \
           patch.object(identity, '_readHostPrefdl',
                        side_effect=[OSError('read failed'), prefdl]), \
           patch.object(identity, '_writePrefdlCacheFile'):
         with self.assertRaises(OSError):
            _ = identity.syseeprom
         self.assertIs(identity.syseeprom, prefdl)


class ReadCachedPrefdlTest(unittest.TestCase):

   def setUp(self):
      self.tmpdir = tempfile.mkdtemp()
      self.cachePath = os.path.join(self.tmpdir, '.syseeprom')

   def tearDown(self):
      shutil.rmtree(self.tmpdir)

   def _makeIdentity(self):
      identity = PlatformIdentityNonDmi(cmdline={})
      identity._PREFDL_CACHE_PATH = self.cachePath
      return identity

   def testCacheExists(self):
      makePrefdl(PREFDL_DATA).writeToFile(self.cachePath)
      identity = self._makeIdentity()
      result = identity._readCachedPrefdl()
      self.assertIsNotNone(result)
      self.assertEqual(result.get('SID'), 'TestProduct')
      self.assertEqual(result.get('SKU'), 'DCS-TEST-42')

   def testCacheDoesNotExist(self):
      identity = self._makeIdentity()
      result = identity._readCachedPrefdl()
      self.assertIsNone(result)

   def testCacheEmpty(self):
      with open(self.cachePath, 'w', encoding='utf-8'):
         pass
      identity = self._makeIdentity()
      result = identity._readCachedPrefdl()
      self.assertIsNone(result)


class ReadHostPrefdlTest(unittest.TestCase):

   def setUp(self):
      self.tmpdir = tempfile.mkdtemp()
      self.textPath = os.path.join(self.tmpdir, '.system-prefdl')
      self.binPath = os.path.join(self.tmpdir, '.system-prefdl-bin')

   def tearDown(self):
      shutil.rmtree(self.tmpdir)

   def _makeIdentity(self):
      identity = PlatformIdentityNonDmi(cmdline={})
      identity._HOST_PREFDL_PATH = self.textPath
      identity._HOST_PREFDL_BINPATH = self.binPath
      return identity

   def testTextPrefdl(self):
      makePrefdl(PREFDL_DATA).writeToFile(self.textPath)
      identity = self._makeIdentity()
      result = identity._readHostPrefdl()
      self.assertIsNotNone(result)
      self.assertEqual(result.get('SID'), 'TestProduct')

   def testNoFiles(self):
      identity = self._makeIdentity()
      result = identity._readHostPrefdl()
      self.assertIsNone(result)

   def testBinPreferredOverText(self):
      makePrefdl(PREFDL_DATA).writeToFile(self.textPath)
      binPrefdl = makePrefdl({'SID': 'BinProduct', 'SKU': 'BIN-SKU'})
      identity = self._makeIdentity()
      with patch.object(Prefdl, 'fromBinFile', return_value=binPrefdl):
         with open(self.binPath, 'wb'):
            pass
         result = identity._readHostPrefdl()
      self.assertEqual(result.get('SID'), 'BinProduct')


class NonDmiPropertiesTest(unittest.TestCase):

   def testSid(self):
      identity = makeNonDmiIdentity(cmdline={'sid': 'cmdline-sid'})
      self.assertEqual(identity.sid, 'cmdline-sid')

   def testSidNone(self):
      identity = makeNonDmiIdentity(cmdline={})
      self.assertIsNone(identity.sid)

   def testSku(self):
      identity = makeNonDmiIdentity(switchData=PREFDL_DATA)
      self.assertEqual(identity.sku, 'DCS-TEST-42')

   def testPlatformFromCmdline(self):
      identity = makeNonDmiIdentity(cmdline={'platform': 'raven'})
      self.assertEqual(identity.platform, 'raven')

   def testPlatformNone(self):
      identity = makeNonDmiIdentity()
      self.assertIsNone(identity.platform)


if __name__ == '__main__':
   unittest.main()
