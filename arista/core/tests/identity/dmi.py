# pylint: disable=protected-access

from ....tests.testing import unittest, patch

from ...exception import UnknownPlatformError
from ...identity.base import Prefdls
from ...identity.dmi import PlatformIdentityDmi

from .common import (
   PREFDL_DATA,
   CPU_PREFDL_DATA,
   SWITCH_PREFDL_DATA,
   makePrefdl,
   makeManager,
   makeFakeCpu,
   makeDmiIdentity,
)


class ReadPrefdlDmiTest(unittest.TestCase):

   def setUp(self):
      self._patchDmiRead = patch(
         'arista.core.identity.dmi.readSystemPrefdlViaDmi')
      self._patchNames = patch(
         'arista.core.identity.dmi._readCpuPlatformNamesViaDmi',
         return_value=[])
      self.mockDmiRead = self._patchDmiRead.start()
      self.mockNames = self._patchNames.start()
      self.cpuPrefdl = makePrefdl(CPU_PREFDL_DATA)
      self.mockDmiRead.return_value = self.cpuPrefdl

   def tearDown(self):
      self._patchDmiRead.stop()
      self._patchNames.stop()

   def _makeIdentity(self, cpus=None):
      return PlatformIdentityDmi(makeManager(cpus=cpus), cmdline={})

   def testCpuMatchBySid(self):
      switchPrefdl = makePrefdl(SWITCH_PREFDL_DATA)
      fakeCpu = makeFakeCpu(sids=['CpuBoard'], switchPrefdl=switchPrefdl)
      identity = self._makeIdentity(cpus=[fakeCpu])
      with patch.object(identity, '_readCachedPrefdls', return_value=None), \
           patch.object(identity, '_writePrefdlCacheFile') as mockWrite:
         identity._readPrefdl()
      self.assertIs(identity._prefdls.switch, switchPrefdl)
      self.assertIs(identity._prefdls.cpu, self.cpuPrefdl)
      self.assertEqual(mockWrite.call_count, 2)
      mockWrite.assert_any_call(switchPrefdl)
      mockWrite.assert_any_call(self.cpuPrefdl,
                                identity._CPU_PREFDL_CACHE_PATH)

   def testCacheHit(self):
      cachedSwitchPrefdl = makePrefdl(SWITCH_PREFDL_DATA)
      cachedCpuPrefdl = makePrefdl(CPU_PREFDL_DATA)
      cached = Prefdls(cachedSwitchPrefdl, cachedCpuPrefdl)
      identity = self._makeIdentity()
      with patch.object(identity, '_readCachedPrefdls',
                        return_value=cached), \
           patch.object(identity, '_writePrefdlCacheFile') as mockWrite:
         identity._readPrefdl()
      self.assertIs(identity._prefdls.switch, cachedSwitchPrefdl)
      self.assertIs(identity._prefdls.cpu, cachedCpuPrefdl)
      self.mockDmiRead.assert_not_called()
      self.mockNames.assert_not_called()
      mockWrite.assert_not_called()

   def testCpuMatchByPlatformName(self):
      switchPrefdl = makePrefdl(SWITCH_PREFDL_DATA)
      self.mockNames.return_value = ['thrasher']
      fakeCpu = makeFakeCpu(sids=[], platform='thrasher',
                            switchPrefdl=switchPrefdl)
      identity = self._makeIdentity(cpus=[fakeCpu])
      with patch.object(identity, '_readCachedPrefdls', return_value=None), \
           patch.object(identity, '_writePrefdlCacheFile') as mockWrite:
         identity._readPrefdl()
      self.assertIs(identity._prefdls.switch, switchPrefdl)
      self.assertIs(identity._prefdls.cpu, self.cpuPrefdl)
      self.assertEqual(mockWrite.call_count, 2)
      mockWrite.assert_any_call(switchPrefdl)
      mockWrite.assert_any_call(self.cpuPrefdl,
                                identity._CPU_PREFDL_CACHE_PATH)

   def testFixedSystem(self):
      prefdl = makePrefdl(PREFDL_DATA)
      self.mockDmiRead.return_value = prefdl
      identity = self._makeIdentity()
      with patch.object(identity, '_readCachedPrefdls', return_value=None), \
           patch.object(identity, '_writePrefdlCacheFile') as mockWrite, \
           patch.object(identity, '_createEmptyMarkerFile') as mockCreateMarker:
         identity._readPrefdl()
      self.assertIs(identity._prefdls.switch, prefdl)
      self.assertIsNone(identity._prefdls.cpu)
      mockWrite.assert_called_once_with(prefdl)
      mockCreateMarker.assert_called_once_with(identity._CPU_PREFDL_CACHE_PATH)

   def testCacheHitFixedSystem(self):
      cachedPrefdl = makePrefdl(PREFDL_DATA)
      cached = Prefdls(cachedPrefdl, None)
      identity = self._makeIdentity()
      with patch.object(identity, '_readCachedPrefdls',
                        return_value=cached), \
           patch.object(identity, '_writePrefdlCacheFile') as mockWrite:
         identity._readPrefdl()
      self.assertIs(identity._prefdls.switch, cachedPrefdl)
      self.assertIsNone(identity._prefdls.cpu)
      self.mockDmiRead.assert_not_called()
      self.mockNames.assert_not_called()
      mockWrite.assert_not_called()

   def testDmiPermissionError(self):
      self.mockDmiRead.side_effect = PermissionError('access denied')
      identity = self._makeIdentity()
      with patch.object(identity, '_readCachedPrefdls', return_value=None), \
           self.assertRaises(PermissionError) as ctx:
         identity._readPrefdl()
      self.assertIn('root privileges', str(ctx.exception))

   def testDmiPrefdlUnavailable(self):
      self.mockDmiRead.return_value = None
      identity = self._makeIdentity()
      with patch.object(identity, '_readCachedPrefdls', return_value=None), \
           self.assertRaises(UnknownPlatformError):
         identity._readPrefdl()

   def testSwitchEepromNoneRaises(self):
      fakeCpu = makeFakeCpu(sids=['CpuBoard'], switchPrefdl=None)
      identity = self._makeIdentity(cpus=[fakeCpu])
      with patch.object(identity, '_readCachedPrefdls', return_value=None), \
           self.assertRaises(UnknownPlatformError):
         identity._readPrefdl()


class DmiSidTest(unittest.TestCase):

   def testSidConcat(self):
      identity = makeDmiIdentity(
         switchData=SWITCH_PREFDL_DATA, cpuData=CPU_PREFDL_DATA)
      self.assertEqual(identity.sid, 'CpuBoardSwitchBoard')

   def testSidFixedSystem(self):
      identity = makeDmiIdentity(switchData=SWITCH_PREFDL_DATA)
      self.assertEqual(identity.sid, 'SwitchBoard')


if __name__ == '__main__':
   unittest.main()
