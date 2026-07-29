import datetime

from types import SimpleNamespace

import pytest

from ..cpld import (
   SysCpldCause,
   SysCpldRealTimeClock,
   SysCpldReloadCauseEntry,
   SysCpldReloadCauseProvider,
)
from ...core.cause import ReloadCauseScore
from ...core.tests.helpers import getAllSystems
from ...descs.cause import CauseDesc, ReloadCauseDesc, ReloadCausePriority


def _getCauseDef(typ):
   for val in vars(ReloadCauseDesc).values():
      if isinstance(val, CauseDesc) and val.typ == typ:
         return val
   return typ


def _collectCpldCauses():
   # Walk every fixed-system platform, find all SysCpldReloadCauseProvider
   # instances and gather their cause descriptors. Deduplicate by (code, typ)
   # so each register code appears once regardless of which platform defined it.
   seen = set()
   causes = []
   for platform in getAllSystems():
      for provider in platform.getInventory().getReloadCauseProviders():
         if isinstance(provider, SysCpldReloadCauseProvider):
            for cause in provider.getReloadCauseDescs():
               key = (cause.code, cause.typ)
               if key not in seen:
                  seen.add(key)
                  causes.append(cause)
   return causes


CPLD_CAUSES = _collectCpldCauses()


class MockCpld:
   FAULT_TIME_BASE = datetime.datetime(2000, 1, 1)


class MockRegs:
   def __init__(self, clearFaultVal=1, causeVal=0, faultTimeVal=None,
                rtcVal=None):
      self.clearFaultData = clearFaultVal
      self.causeData = causeVal
      self.faultTimeData = faultTimeVal or [0] * 6
      self.rtcData = rtcVal or [0] * 6
      self.clearFaultWrites = []
      self.causeWrites = []
      self.rtcWrites = []

   def clearFault(self, val=None):
      if val is not None:
         self.clearFaultWrites.append(val)
         self.clearFaultData = val
      return self.clearFaultData

   def cause(self, val=None):
      if val is not None:
         self.causeWrites.append(val)
         self.causeData = val
      return self.causeData

   def faultTime(self):
      return self.faultTimeData

   def rtc(self, val=None):
      if val is not None:
         self.rtcWrites.append(val)
         self.rtcData = val
      return self.rtcData


class TestSysCpldRealTimeClock:
   def _makeRtc(self, rtcBytes):
      regs = MockRegs(rtcVal=rtcBytes)
      rtc = SysCpldRealTimeClock(MockCpld(), regmap=None)
      rtc.regs_ = regs
      return rtc, regs

   def testGetTime(self):
      # ticks = 0x8000 = 32768 → msecs = 32768/2**16 = 0.5; secs = 0x64 = 100
      rtc, _ = self._makeRtc([0x00, 0x80, 0x64, 0x00, 0x00, 0x00])
      expected = MockCpld.FAULT_TIME_BASE + datetime.timedelta(seconds=100.5)
      assert rtc.getTime() == expected

   def testRoundTrip(self):
      rtc, regs = self._makeRtc([0] * 6)
      target = MockCpld.FAULT_TIME_BASE + datetime.timedelta(seconds=12345.75)
      rtc.setTime(target)
      regs.rtcData = regs.rtcWrites[-1]
      result = rtc.getTime()
      assert abs((result - target).total_seconds()) < 1 / 2 ** 16


class TestSysCpldReloadCauseProvider:
   def _makeProvider(self, clearFaultVal=1, causeVal=0, faultTimeVal=None,
                     causes=None):
      regs = MockRegs(clearFaultVal=clearFaultVal, causeVal=causeVal,
                      faultTimeVal=faultTimeVal)
      provider = SysCpldReloadCauseProvider(
         cpld=MockCpld(),
         regmap=None,
         causes=causes or [],
      )
      provider.regs_ = regs
      return provider, regs

   def _assertField(self, label, actual, expected):
      assert actual == expected, f'{label}: expected {expected!r}, got {actual!r}'

   def _assertReloadCauseEntry(self, entry, cause, score=None):
      self._assertField('cause', entry.getCause(), cause.typ)
      self._assertField('description', entry.getDescription(), cause.description)
      expected_score = score if score is not None else (
         ReloadCauseScore.LOGGED | ReloadCauseScore.DETAILED |
         ReloadCauseScore.getPriority(cause.priority))
      self._assertField('score', entry.getScore(), expected_score)
      self._assertField('priority', entry.getPriority(), cause.priority)
      self._assertField('altSource', entry.getAltSource(), cause.altSource)
      assert entry.getTime(), 'time is empty'

   def testGetReloadCauseAlreadyClearedReturnsNone(self):
      provider, _ = self._makeProvider(clearFaultVal=0)
      assert provider.getReloadCause() is None

   @pytest.mark.parametrize('extra_desc', [None, 'Board-specific fault'],
                             ids=['no_desc', 'with_desc'])
   @pytest.mark.parametrize('cause', CPLD_CAUSES,
                             ids=[f'0x{c.code:02x}_{c.typ}' for c in CPLD_CAUSES])
   def testGetReloadCauseKnownCode(self, cause, extra_desc):
      test_cause = SysCpldCause(cause.code, _getCauseDef(cause.typ), extra_desc,
                                priority=cause.priority, altSource=cause.altSource)
      provider, _ = self._makeProvider(causeVal=test_cause.code, causes=[test_cause])
      entry = provider.getReloadCause()
      assert isinstance(entry, SysCpldReloadCauseEntry)
      self._assertReloadCauseEntry(entry, test_cause)

   def testGetReloadCauseUnknownCode(self):
      code = 0x3F
      provider, _ = self._makeProvider(causeVal=code)
      entry = provider.getReloadCause()
      assert isinstance(entry, SysCpldReloadCauseEntry)
      self._assertReloadCauseEntry(entry, SimpleNamespace(
         typ='unknown',
         description=f'unknown logged fault {code:#04x}',
         priority=ReloadCausePriority.NORMAL,
         altSource=None,
      ), score=ReloadCauseScore.LOGGED)
