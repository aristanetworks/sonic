import contextlib
import datetime
from types import SimpleNamespace

import pytest

from ....components.scd import Scd, ScdReloadCauseRegisters
from ....core.cause import ReloadCauseScore
from ....core.inventory import Inventory
from ....core.tests.helpers import classname, getAllSystems
from ....descs.cause import CauseDesc, ReloadCauseDesc, ReloadCausePriority
from ....libs.date import datetimeToStr
from ..driver import ScdKernelDriver
from ..cause import (
   ScdCause,
   ScdReloadCauseEntry,
   ScdReloadCauseProvider,
   SimpleScdReloadCauseProvider,
)

SCD_PROVIDER_TYPES = (ScdReloadCauseProvider, SimpleScdReloadCauseProvider)

VALID_CAUSE_TYPES = {
   v.typ for v in vars(ReloadCauseDesc).values()
   if isinstance(v, CauseDesc)
}


def _getCauseDef(typ):
   for val in vars(ReloadCauseDesc).values():
      if isinstance(val, CauseDesc) and val.typ == typ:
         return val
   return typ


def _collectScdCauses():
   # Walk every fixed-system platform and collect all ScdCause descriptors from
   # ScdReloadCauseProvider and SimpleScdReloadCauseProvider instances.
   # Deduplicate by (code, typ) so each distinct register-code/cause pair appears
   # once regardless of how many platforms share the same descriptor — this gives
   # a representative set that exercises the lookup logic without redundant cases.
   seen = set()
   causes = []
   for platform in getAllSystems():
      for provider in platform.getInventory().getReloadCauseProviders():
         if isinstance(provider, SCD_PROVIDER_TYPES):
            for cause in provider.getReloadCauseDescs():
               key = (cause.code, cause.typ)
               if key not in seen:
                  seen.add(key)
                  causes.append(cause)
   return causes


SCD_CAUSES = _collectScdCauses()


@pytest.mark.parametrize('platform', getAllSystems(), ids=classname)
def testScdCauseTypValidity(platform):
   errors = []
   for provider in platform.getInventory().getReloadCauseProviders():
      if not isinstance(provider, SCD_PROVIDER_TYPES):
         continue
      for cause in provider.getReloadCauseDescs():
         if cause.typ not in VALID_CAUSE_TYPES:
            errors.append(
               f'{classname(platform)}: typ {cause.typ!r} (code={cause.code:#04x}) '
               f'is not a ReloadCauseDesc constant'
            )
   if errors:
      pytest.fail('\n'.join(errors))


class MockRegs(ScdReloadCauseRegisters):
   def __init__(self, clearFaultData=1, causeCode=0x00, fractional=0, seconds=0):
      self.clearFaultData = clearFaultData
      self.causeCode = causeCode
      self.fractionalData = fractional
      self.secondsData = seconds
      self.clearFaultWritten = None
      super().__init__(parent=ScdKernelDriver())
      self.clearFault = self._clearFault
      self.lastCause = self._lastCause
      self.lastFractional = self._lastFractional
      self.lastSeconds = self._lastSeconds

   def _clearFault(self, val=None):
      if val is not None:
         self.clearFaultWritten = val
         return None
      return self.clearFaultData

   def _lastCause(self):
      return self.causeCode

   def _lastFractional(self):
      return self.fractionalData

   def _lastSeconds(self):
      return self.secondsData


class MockScd(Scd):
   def __init__(self):
      super().__init__(addr=0, inventory=Inventory())

   def __str__(self):
      return 'MockScd'


class MockMmap:
   def __init__(self, code):
      self.code = code
      self.written = []

   def read32(self, _addr):
      return self.code

   def write32(self, addr, val):
      self.written.append((addr, val))


class MockScdSimple(Scd):
   def __init__(self, code):
      super().__init__(addr=0, inventory=Inventory())
      self.mmap = MockMmap(code)

   def __str__(self):
      return 'MockScdSimple'

   @contextlib.contextmanager
   def getMmap(self):
      yield self.mmap


class TestScdReloadCauseProvider:
   def _make(self, regs, causes=None):
      provider = ScdReloadCauseProvider(MockScd(), regmap=None,
                                        causes=causes or [])
      provider.regs_ = regs
      return provider

   def _assertReloadCauseEntry(self, entry, cause, score=None):
      assert entry.getCause() == cause.typ
      assert entry.getDescription() == cause.description
      expected_score = score if score is not None else (
         ReloadCauseScore.LOGGED | ReloadCauseScore.DETAILED |
         ReloadCauseScore.getPriority(cause.priority))
      assert entry.getScore() == expected_score
      assert entry.getPriority() == cause.priority
      assert entry.getAltSource() == cause.altSource
      assert entry.getTime(), 'time is empty'

   def testGetReloadCauseAlreadyClearedReturnsNone(self):
      assert self._make(MockRegs(clearFaultData=0)).getReloadCause() is None

   @pytest.mark.parametrize('extra_desc', [None, 'Board-specific fault'],
                             ids=['no_desc', 'with_desc'])
   @pytest.mark.parametrize('cause', SCD_CAUSES,
                             ids=[f'0x{c.code:02x}_{c.typ}' for c in SCD_CAUSES])
   def testGetReloadCauseKnownCode(self, cause, extra_desc):
      test_cause = ScdCause(cause.code, _getCauseDef(cause.typ), extra_desc,
                            priority=cause.priority, altSource=cause.altSource)
      regs = MockRegs(causeCode=test_cause.code)
      entry = self._make(regs, causes=[test_cause]).getReloadCause()
      assert isinstance(entry, ScdReloadCauseEntry)
      self._assertReloadCauseEntry(entry, test_cause)
      assert regs.clearFaultWritten == 1

   def testGetReloadCauseUnknownCode(self):
      code = 0x3F
      regs = MockRegs(causeCode=code)
      entry = self._make(regs).getReloadCause()
      assert isinstance(entry, ScdReloadCauseEntry)
      self._assertReloadCauseEntry(entry, SimpleNamespace(
         typ='unknown',
         description=f'unknown logged fault {code:#04x}',
         priority=ReloadCausePriority.UNKNOWN,
         altSource=None,
      ), score=ReloadCauseScore.LOGGED)

   def testRtcTime(self):
      regs = MockRegs(causeCode=SCD_CAUSES[0].code, fractional=0x10000, seconds=1)
      # 0x10000 / 2^16 = 1.0 s fractional + seconds=1 → 2 s from FAULT_TIME_BASE
      expected = datetimeToStr(Scd.FAULT_TIME_BASE + datetime.timedelta(seconds=2))
      entry = self._make(regs, causes=[SCD_CAUSES[0]]).getReloadCause()
      assert entry.getTime() == expected

   def testProcessAlreadyClearedProducesNoCauses(self):
      provider = self._make(MockRegs(clearFaultData=0))
      provider.process()
      assert provider.getCauses() == []


class TestSimpleScdReloadCauseProvider:
   ADDR = 0x1000

   def _make(self, code, causes=None):
      scd = MockScdSimple(code)
      return SimpleScdReloadCauseProvider(scd, self.ADDR, causes or []), scd

   def _assertReloadCauseEntry(self, entry, cause, score=None):
      assert entry.getCause() == cause.typ
      assert entry.getDescription() == cause.description
      expected_score = score if score is not None else (
         ReloadCauseScore.LOGGED | ReloadCauseScore.DETAILED |
         ReloadCauseScore.getPriority(ReloadCausePriority.NORMAL))
      assert entry.getScore() == expected_score
      assert entry.getPriority() == cause.priority
      assert entry.getAltSource() == cause.altSource

   @pytest.mark.parametrize('extra_desc', [None, 'Board-specific fault'],
                             ids=['no_desc', 'with_desc'])
   @pytest.mark.parametrize('cause', SCD_CAUSES,
                             ids=[f'0x{c.code:02x}_{c.typ}' for c in SCD_CAUSES])
   def testGetReloadCauseKnownCode(self, cause, extra_desc):
      test_cause = ScdCause(cause.code, _getCauseDef(cause.typ), extra_desc,
                            priority=cause.priority, altSource=cause.altSource)
      provider, _ = self._make(test_cause.code, causes=[test_cause])
      entry = provider.getReloadCause()
      assert isinstance(entry, ScdReloadCauseEntry)
      self._assertReloadCauseEntry(entry, test_cause)
      assert entry.getTime() == 'unknown'

   def testGetReloadCauseUnknownCode(self):
      code = 0x3F
      provider, _ = self._make(code)
      entry = provider.getReloadCause()
      assert isinstance(entry, ScdReloadCauseEntry)
      self._assertReloadCauseEntry(entry, SimpleNamespace(
         typ='unknown',
         description=f'unknown logged fault {code:#04x}',
         priority=ReloadCausePriority.UNKNOWN,
         altSource=None,
      ), score=ReloadCauseScore.LOGGED)

   def testClearFaults(self):
      provider, scd = self._make(0x00)
      provider.clearFaults()
      assert (self.ADDR, 0) in scd.mmap.written
