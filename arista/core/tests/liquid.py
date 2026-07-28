from types import SimpleNamespace

from ...tests.testing import unittest

from ...components.cpld import LeakDetectionCpldRegistersV1
from ...components.scd import LeakDetectionPcieRegistersV1

from ..liquid import LeakDetectionInterfaceV1, LeakSensorType


ROPE_TYPES = (LeakSensorType.ROPE_MINOR, LeakSensorType.ROPE_MAJOR)
ROPE_NUMS = (0, 1, 2, 3)


def _severityPrefix(ropeType):
   return 'minor' if ropeType is LeakSensorType.ROPE_MINOR else 'major'


def _adapter(regs):
   component = SimpleNamespace(driver=SimpleNamespace(regs=regs))
   return LeakDetectionInterfaceV1(component)


class RecordingRegs:
   """
   Fake `regs` that implements the RegisterMap accessor protocol: every
   attribute lookup returns a callable that reads when called with no args and
   writes when called with one. Records all accesses for assertion.
   """
   def __init__(self):
      self.values = {}
      self.reads = []
      self.writes = []

   def __getattr__(self, name):
      def accessor(*args):
         if not args:
            self.reads.append(name)
            return self.values.get(name, 0)
         (value,) = args
         self.writes.append((name, value))
         self.values[name] = value
         return None
      return accessor


class TestAdapterFieldNames(unittest.TestCase):
   """
   Verifies that each adapter method looks up the field name expected by the
   register-map naming convention. Catches typos on the adapter side.
   """

   def setUp(self):
      self.regs = RecordingRegs()
      self.adapter = _adapter(self.regs)

   def _checkRopeAccess(self, regSuffix, getter=None, setter=None):
      for ropeType in ROPE_TYPES:
         severity = _severityPrefix(ropeType)
         for ropeNum in ROPE_NUMS:
            expected = f'{severity}Rope{ropeNum}{regSuffix}'
            with self.subTest(severity=severity, rope=ropeNum):
               if getter is not None:
                  self.regs.reads.clear()
                  getter(self.adapter, ropeType, ropeNum)
                  self.assertIn(expected, self.regs.reads)
               if setter is not None:
                  self.regs.writes.clear()
                  setter(self.adapter, ropeType, ropeNum)
                  self.assertTrue(
                     any(n == expected for n, _ in self.regs.writes),
                     f'expected write to {expected}, got {self.regs.writes}')

   def _checkSeverityAccess(self, regSuffix, getter=None, setter=None):
      for ropeType in ROPE_TYPES:
         severity = _severityPrefix(ropeType)
         expected = f'{severity}{regSuffix}'
         with self.subTest(severity=severity, regSuffix=regSuffix):
            if getter is not None:
               self.regs.reads.clear()
               getter(self.adapter, ropeType)
               self.assertIn(expected, self.regs.reads)
            if setter is not None:
               self.regs.writes.clear()
               setter(self.adapter, ropeType)
               self.assertTrue(
                  any(n == expected for n, _ in self.regs.writes),
                  f'expected write to {expected}, got {self.regs.writes}')

   def testRopePresent(self):
      self._checkRopeAccess('Present',
         getter=lambda a, t, n: a.isRopePresent(t, n))

   def testRopeBroken(self):
      self._checkRopeAccess('Break',
         getter=lambda a, t, n: a.isRopeBroken(t, n))

   def testRopeLeakDetected(self):
      self._checkRopeAccess('Leak',
         getter=lambda a, t, n: a.isRopeLeakDetected(t, n))

   def testRopeStatusChanged(self):
      self._checkRopeAccess('Changed',
         getter=lambda a, t, n: a.hasRopeStatusChanged(t, n),
         setter=lambda a, t, n: a.clearRopeStatusChanged(t, n))

   def testRopeDebounce(self):
      self._checkRopeAccess('DebounceS',
         getter=lambda a, t, n: a.getRopeDebounceS(t, n),
         setter=lambda a, t, n: a.setRopeDebounceS(t, n, 5))

   def testRopeLeakForced(self):
      self._checkRopeAccess('ForceLeak',
         getter=lambda a, t, n: a.isRopeLeakForced(t, n),
         setter=lambda a, t, n: a.setRopeLeakForced(t, n, True))

   def testLiquidDomainPowerDown(self):
      self._checkSeverityAccess('LiquidDomainPowerDownEnable',
         getter=lambda a, t: a.isLiquidDomainPowerDownEnabled(t),
         setter=lambda a, t: a.setLiquidDomainPowerDownEnabled(t, True))

   def testSystemPowerCycle(self):
      self._checkSeverityAccess('SystemPowerCycleEnable',
         getter=lambda a, t: a.isSystemPowerCycleEnabled(t),
         setter=lambda a, t: a.setSystemPowerCycleEnabled(t, True))

   def testLeakActionDelayTime(self):
      self._checkSeverityAccess('LeakActionDelayTimeS',
         getter=lambda a, t: a.getLeakActionDelayTimeS(t),
         setter=lambda a, t: a.setLeakActionDelayTimeS(t, 5))

   def testLeakActionDelayTimeEnabled(self):
      self._checkSeverityAccess('LeakActionDelayTimeEnable',
         getter=lambda a, t: a.isLeakActionDelayEnabled(t),
         setter=lambda a, t: a.setLeakActionDelayTimeEnabled(t, True))

   def testWatchdogLiquidDomainPowerDown(self):
      self._checkSeverityAccess('WatchdogLiquidDomainPowerDownEnable',
         getter=lambda a, t: a.isWatchdogLiquidDomainPowerDownEnabled(t),
         setter=lambda a, t: a.setWatchdogLiquidDomainPowerDownEnabled(t, True))

   def testWatchdogSystemPowerCycle(self):
      self._checkSeverityAccess('WatchdogSystemPowerCycleEnable',
         getter=lambda a, t: a.isWatchdogSystemPowerCycleEnabled(t),
         setter=lambda a, t: a.setWatchdogSystemPowerCycleEnabled(t, True))

   def testWatchdogTime(self):
      self._checkSeverityAccess('WatchdogTimeS',
         getter=lambda a, t: a.getWatchdogTimeS(t),
         setter=lambda a, t: a.setWatchdogTimeS(t, 5))

   def testWatchdogEnabled(self):
      self._checkSeverityAccess('WatchdogEnable',
         getter=lambda a, t: a.isWatchdogEnabled(t),
         setter=lambda a, t: a.setWatchdogEnabled(t, True))

   def testBoolCoercedToInt(self):
      # Adapter must coerce bools to int so register backends that type-check
      # don't see True/False.
      self.adapter.setRopeLeakForced(LeakSensorType.ROPE_MAJOR, 0, True)
      _, value = self.regs.writes[-1]
      self.assertIs(type(value), int)
      self.assertEqual(value, 1)

   def testRangeChecks(self):
      # Multi-bit setters must reject out-of-range values rather than silently
      # truncating via the hardware register's bit mask.
      cases = [
         (lambda v: self.adapter.setRopeDebounceS(
             LeakSensorType.ROPE_MAJOR, 0, v), 0xff, 0x100),
         (lambda v: self.adapter.setLeakActionDelayTimeS(
             LeakSensorType.ROPE_MAJOR, v), 0x3f, 0x40),
         (lambda v: self.adapter.setWatchdogTimeS(
             LeakSensorType.ROPE_MAJOR, v), 0x3f, 0x40),
      ]
      for setter, maxValid, firstInvalid in cases:
         with self.subTest(maxValid=maxValid):
            setter(0)
            setter(maxValid)
            with self.assertRaises(ValueError):
               setter(firstInvalid)
            with self.assertRaises(ValueError):
               setter(-1)


class FakeAddressDriver:
   """Address-keyed dict driver — the 'parent' interface a RegisterMap needs."""
   def __init__(self):
      self.mem = {}

   def read(self, addr):
      return self.mem.get(addr, 0)

   def write(self, addr, value):
      self.mem[addr] = value


class RegisterMapRoundTripMixin:
   """
   Mounts the real register-map class on a fake driver and verifies that each
   per-rope adapter operation round-trips independently. Catches:
     - duplicated bit aliases (two RegBitField defs sharing a name)
     - off-by-one / missing rope fields (polyfill silently no-ops)
     - adapter/map naming mismatches (same root cause as the above)
   """

   def _makeRegs(self, driver):
      raise NotImplementedError

   def _newAdapter(self):
      driver = FakeAddressDriver()
      regs = self._makeRegs(driver)
      component = SimpleNamespace(driver=SimpleNamespace(regs=regs))
      return LeakDetectionInterfaceV1(component)

   def _ropeBitIndependent(self, setter, getter):
      for ropeType in ROPE_TYPES:
         for ropeNum in ROPE_NUMS:
            with self.subTest(ropeType=ropeType, ropeNum=ropeNum):
               adapter = self._newAdapter()
               setter(adapter, ropeType, ropeNum)
               for otherType in ROPE_TYPES:
                  for otherNum in ROPE_NUMS:
                     val = getter(adapter, otherType, otherNum)
                     if (otherType, otherNum) == (ropeType, ropeNum):
                        self.assertTrue(val,
                           f'set bit lost at {otherType}/{otherNum}')
                     else:
                        self.assertFalse(val,
                           f'unexpected bleed into {otherType}/{otherNum} '
                           f'after setting {ropeType}/{ropeNum}')

   def testRopeChangedClearIndependent(self):
      self._ropeBitIndependent(
         setter=lambda a, t, n: a.clearRopeStatusChanged(t, n),
         getter=lambda a, t, n: a.hasRopeStatusChanged(t, n))

   def testRopeLeakForcedIndependent(self):
      self._ropeBitIndependent(
         setter=lambda a, t, n: a.setRopeLeakForced(t, n, True),
         getter=lambda a, t, n: a.isRopeLeakForced(t, n))

   def testRopeDebounceIndependent(self):
      # Multi-bit field — use a distinct value per rope to detect aliasing.
      for ropeType in ROPE_TYPES:
         for ropeNum in ROPE_NUMS:
            with self.subTest(ropeType=ropeType, ropeNum=ropeNum):
               adapter = self._newAdapter()
               adapter.setRopeDebounceS(ropeType, ropeNum, 0x42)
               for otherType in ROPE_TYPES:
                  for otherNum in ROPE_NUMS:
                     val = adapter.getRopeDebounceS(otherType, otherNum)
                     expected = 0x42 \
                        if (otherType, otherNum) == (ropeType, ropeNum) else 0
                     self.assertEqual(val, expected,
                        f'{otherType}/{otherNum} got {val:#x}, '
                        f'expected {expected:#x}')

   def testLeakActionDelayTimeEnabledRoundTrip(self):
      # Catches adapter-vs-map naming mismatches for severity-scoped fields:
      # if the map's field name doesn't match what the adapter looks up, the
      # polyfill silently no-ops and the read-back returns 0.
      for ropeType in ROPE_TYPES:
         with self.subTest(ropeType=ropeType):
            adapter = self._newAdapter()
            adapter.setLeakActionDelayTimeEnabled(ropeType, True)
            self.assertTrue(adapter.isLeakActionDelayEnabled(ropeType))


class TestCpldRegisterMapRoundTrip(RegisterMapRoundTripMixin, unittest.TestCase):
   def _makeRegs(self, driver):
      return LeakDetectionCpldRegistersV1(driver)


class TestSteamerLanePcieRegisterMapRoundTrip(RegisterMapRoundTripMixin,
                                              unittest.TestCase):
   def _makeRegs(self, driver):
      return LeakDetectionPcieRegistersV1(driver)


if __name__ == '__main__':
   unittest.main()
