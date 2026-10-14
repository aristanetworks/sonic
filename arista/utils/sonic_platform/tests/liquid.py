import importlib
import sys

if 'arista.utils.sonic_platform.liquid' not in sys.modules:
   importlib.import_module('arista.utils.tests.sonic_platform_base').mock()

# sonic_platform_base is provided by SONiC on devices, not by the unit-test
# environment; the mock above installs its module for this import.
# pylint: disable=import-error,wrong-import-position
from sonic_platform_base.liquid_cooling_base import LeakSeverity

from arista.core.liquid import LeakSensorType
from arista.utils.sonic_platform.liquid import (
   AristaLeakageSensorTest,
   LeakageSensor,
   LeakageSensorProfile,
)
from ....tests.testing import unittest


class FakeLeakInterface:
   def __init__(self):
      self.forced = {}
      self.realLeak = {}
      self.broken = {}
      self.failSet = set()
      self.ignoreSet = set()
      self.leakReads = {}

   @staticmethod
   def _key(ropeType, ropeNum):
      return (ropeType, ropeNum)

   def isRopeLeakForced(self, ropeType, ropeNum):
      return self.forced.get(self._key(ropeType, ropeNum), False)

   def setRopeLeakForced(self, ropeType, ropeNum, forced):
      key = self._key(ropeType, ropeNum)
      if (key, bool(forced)) in self.failSet:
         raise RuntimeError('simulated register write failure')
      if (key, bool(forced)) not in self.ignoreSet:
         self.forced[key] = bool(forced)

   def isRopeLeakDetected(self, ropeType, ropeNum):
      key = self._key(ropeType, ropeNum)
      self.leakReads[key] = self.leakReads.get(key, 0) + 1
      # While the force bit is set, the hardware leak status reflects the
      # injected test state and cannot identify an underlying real leak.
      if self.forced.get(key, False):
         return True
      return self.realLeak.get(key, False)

   def isRopeBroken(self, ropeType, ropeNum):
      return self.broken.get(self._key(ropeType, ropeNum), False)

   # The arguments mirror the hardware interface.
   def hasRopeStatusChanged(self, ropeType, ropeNum): # pylint: disable=unused-argument
      return False

   def clearRopeStatusChanged(self, ropeType, ropeNum):
      pass


class TestAristaLeakageSensorTest(unittest.TestCase):
   def setUp(self):
      self.interface = FakeLeakInterface()
      self.profile = LeakageSensorProfile()
      self.smallLeak = LeakageSensor(
         self.interface, LeakSensorType.ROPE_MINOR, 0, self.profile,
         name='smallLeak')
      self.trayLeak = LeakageSensor(
         self.interface, LeakSensorType.ROPE_MAJOR, 0, self.profile,
         name='trayLeak')
      self.mitigationDisabled = True
      self.leakTest = AristaLeakageSensorTest(
         self.interface, [self.smallLeak, self.trayLeak],
         lambda: self.mitigationDisabled)

   def testSupportedAndUnknownSensor(self):
      self.assertTrue(self.leakTest.is_leak_test_supported())
      self.assertFalse(self.leakTest.is_test_leak_enabled('unknown'))
      self.assertFalse(self.leakTest.set_test_leak('unknown', True))

   def testSeverityMustMatchFixedRopeSeverity(self):
      with self.assertRaises(ValueError):
         self.leakTest.set_test_leak('trayLeak', True)
      with self.assertRaises(ValueError):
         self.leakTest.set_test_leak('smallLeak', True,
                                     severity=LeakSeverity.CRITICAL)
      with self.assertRaises(ValueError):
         self.leakTest.set_test_leak('smallLeak', True, severity=object())

      self.assertTrue(self.leakTest.set_test_leak(
         'trayLeak', True, severity=LeakSeverity.CRITICAL))
      self.assertTrue(self.leakTest.set_test_leak(
         'trayLeak', False, severity=None))
      self.assertTrue(self.leakTest.set_test_leak(
         'smallLeak', True, severity=None))
      self.assertTrue(self.leakTest.set_test_leak('smallLeak', False))

   def testForcedLeakStatusIsDistinctAndClearRefreshesHardware(self):
      key = (LeakSensorType.ROPE_MINOR, 0)
      self.interface.realLeak[key] = True

      self.assertTrue(self.leakTest.set_test_leak('smallLeak', True))
      self.assertTrue(self.smallLeak.is_test_leak())
      self.assertTrue(self.smallLeak.is_leak())
      readsBeforeClear = self.interface.leakReads[key]

      self.assertTrue(self.leakTest.set_test_leak('smallLeak', False))
      self.assertFalse(self.smallLeak.is_test_leak())
      # The injected state is indistinguishable from a real leak while forced;
      # after clearing, the sensor is refreshed and the real leak remains.
      self.assertTrue(self.smallLeak.is_leak())
      self.assertGreater(self.interface.leakReads[key], readsBeforeClear)

   def testMitigationGuardRefusesInjection(self):
      self.mitigationDisabled = False

      self.assertFalse(self.leakTest.set_test_leak('smallLeak', True))
      self.assertFalse(self.leakTest.is_test_leak_enabled('smallLeak'))

   def testSetterReadbackFailureReturnsFalse(self):
      key = (LeakSensorType.ROPE_MINOR, 0)
      self.interface.ignoreSet.add((key, True))

      self.assertFalse(self.leakTest.set_test_leak('smallLeak', True))
      self.assertFalse(self.leakTest.is_test_leak_enabled('smallLeak'))

   def testClearAttemptsEverySensorAfterFailure(self):
      minorKey = (LeakSensorType.ROPE_MINOR, 0)
      majorKey = (LeakSensorType.ROPE_MAJOR, 0)
      self.interface.forced[minorKey] = True
      self.interface.forced[majorKey] = True
      self.interface.failSet.add((minorKey, False))

      self.assertFalse(self.leakTest.clear_test_leaks())
      self.assertTrue(self.interface.isRopeLeakForced(*minorKey))
      self.assertFalse(self.interface.isRopeLeakForced(*majorKey))


if __name__ == '__main__':
   unittest.main()
