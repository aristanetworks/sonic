
# pylint: disable=protected-access

import os
import shutil
import tempfile

from ....tests.testing import unittest, patch

from ...exception import UnknownPlatformError
from ...identity.non_dmi import PlatformIdentityNonDmi
from ...prefdl import Prefdl

from .common import (
   PREFDL_DATA,
   makePrefdl,
   makeManager,
   makeNonDmiIdentity,
)


class ReadPrefdlNonDmiTest(unittest.TestCase):

   def _makeIdentity(self):
      return PlatformIdentityNonDmi(makeManager(), cmdline={})

   def _patchSimulation(self):
      return patch('arista.core.identity.non_dmi.inSimulation', return_value=False)

   def testCacheHit(self):
      prefdl = makePrefdl(PREFDL_DATA)
      identity = self._makeIdentity()
      with self._patchSimulation(), \
           patch.object(identity, '_readCachedPrefdl', return_value=prefdl), \
           patch.object(identity, '_writePrefdlCacheFile') as mockWrite:
         identity._readPrefdl()
      self.assertIs(identity._prefdls.switch, prefdl)
      self.assertIsNone(identity._prefdls.cpu)
      mockWrite.assert_not_called()

   def testHostPrefdl(self):
      prefdl = makePrefdl(PREFDL_DATA)
      identity = self._makeIdentity()
      with self._patchSimulation(), \
           patch.object(identity, '_readCachedPrefdl', return_value=None), \
           patch.object(identity, '_readHostPrefdl', return_value=prefdl), \
           patch.object(identity, '_writePrefdlCacheFile') as mockWrite:
         identity._readPrefdl()
      self.assertIs(identity._prefdls.switch, prefdl)
      mockWrite.assert_called_once_with(prefdl)

   def testNoPrefdlSources(self):
      identity = self._makeIdentity()
      with self._patchSimulation(), \
           patch.object(identity, '_readCachedPrefdl', return_value=None), \
           patch.object(identity, '_readHostPrefdl', return_value=None), \
           patch.object(identity, '_writePrefdlCacheFile'):
         with self.assertRaises(UnknownPlatformError):
            identity._readPrefdl()


class ReadCachedPrefdlTest(unittest.TestCase):

   def setUp(self):
      self.tmpdir = tempfile.mkdtemp()
      self.cachePath = os.path.join(self.tmpdir, '.syseeprom')

   def tearDown(self):
      shutil.rmtree(self.tmpdir)

   def _makeIdentity(self):
      identity = PlatformIdentityNonDmi(makeManager(), cmdline={})
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
      identity = PlatformIdentityNonDmi(makeManager(), cmdline={})
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
