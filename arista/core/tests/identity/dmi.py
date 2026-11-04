# pylint: disable=protected-access

from ....tests.testing import unittest, patch

from ...exception import UnknownPlatformError
from ...identity.dmi import _Prefdls, PlatformIdentityDmi

from .common import (
   DummyLoader,
   PREFDL_DATA,
   CPU_PREFDL_DATA,
   SWITCH_PREFDL_DATA,
   makePrefdl,
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

   def _makeIdentity(self, cpus=()):
      _loader = DummyLoader()
      for cpu in cpus:
         _loader.cpus.add(cpu)

      identity = PlatformIdentityDmi(cmdline={})
      identity._loader = _loader
      return identity

   def testLazyInit(self):
      for firstProperty in ('syseeprom', 'cpueeprom'):
         identity = PlatformIdentityDmi(cmdline={})
         switch = makePrefdl(PREFDL_DATA)
         cpu = makePrefdl(CPU_PREFDL_DATA)
         def doRead(identity=identity, switch=switch, cpu=cpu):
            identity._prefdls = _Prefdls(switch, cpu)  # pylint: disable=protected-access
         with patch.object(identity, '_readPrefdl', side_effect=doRead) as read:
            getattr(identity, firstProperty)
            self.assertIs(identity.syseeprom, switch)
            self.assertIs(identity.cpueeprom, cpu)
            self.assertEqual(identity.sid, 'CpuBoardTestProduct')
         read.assert_called_once()

   def testCpuMatchBySid(self):
      switchPrefdl = makePrefdl(SWITCH_PREFDL_DATA)
      fakeCpu = makeFakeCpu(sids=['CpuBoard'], switchPrefdl=switchPrefdl)
      identity = self._makeIdentity(cpus=[fakeCpu])
      with patch.object(identity, '_readCachedPrefdls', return_value=None), \
           patch.object(identity, '_writePrefdlCacheFile') as mockWrite:
         identity._readPrefdl()
      self.assertIs(identity.syseeprom, switchPrefdl)
      self.assertIs(identity.cpueeprom, self.cpuPrefdl)
      self.assertEqual(mockWrite.call_count, 2)
      mockWrite.assert_any_call(switchPrefdl)
      mockWrite.assert_any_call(self.cpuPrefdl,
                                identity._CPU_PREFDL_CACHE_PATH)

   def testCacheHit(self):
      cachedSwitchPrefdl = makePrefdl(SWITCH_PREFDL_DATA)
      cachedCpuPrefdl = makePrefdl(CPU_PREFDL_DATA)
      cached = _Prefdls(cachedSwitchPrefdl, cachedCpuPrefdl)
      identity = self._makeIdentity()
      with patch.object(identity, '_readCachedPrefdls',
                        return_value=cached), \
           patch.object(identity, '_writePrefdlCacheFile') as mockWrite:
         identity._readPrefdl()
      self.assertIs(identity.syseeprom, cachedSwitchPrefdl)
      self.assertIs(identity.cpueeprom, cachedCpuPrefdl)
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
      self.assertIs(identity.syseeprom, switchPrefdl)
      self.assertIs(identity.cpueeprom, self.cpuPrefdl)
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
      self.assertIs(identity.syseeprom, prefdl)
      self.assertIsNone(identity.cpueeprom)
      mockWrite.assert_called_once_with(prefdl)
      mockCreateMarker.assert_called_once_with(identity._CPU_PREFDL_CACHE_PATH)

   def testCacheHitFixedSystem(self):
      cachedPrefdl = makePrefdl(PREFDL_DATA)
      cached = _Prefdls(cachedPrefdl, None)
      identity = self._makeIdentity()
      with patch.object(identity, '_readCachedPrefdls',
                        return_value=cached), \
           patch.object(identity, '_writePrefdlCacheFile') as mockWrite:
         identity._readPrefdl()
      self.assertIs(identity.syseeprom, cachedPrefdl)
      self.assertIsNone(identity.cpueeprom)
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
