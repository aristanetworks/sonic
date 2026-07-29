import datetime

from ...core.cause import (
   ReloadCauseEntry,
   HardwareReloadCauseProvider,
   ReloadCauseScore,
)
from ...core.log import getLogger
from ...descs.cause import ReloadCauseDesc, ReloadCausePriority

from ...libs.date import datetimeToStr

logging = getLogger(__name__)

class ScdCause(ReloadCauseDesc):
   pass

class ScdReloadCauseEntry(ReloadCauseEntry):
   pass

class SimpleScdReloadCauseProvider(HardwareReloadCauseProvider):
   def __init__(self, scd, addr, causes, **kwargs):
      super().__init__(name=str(scd), descs=causes, **kwargs)
      self.scd = scd
      self.addr = addr

   def __str__(self):
      return self.__class__.__name__

   def process(self):
      self.causes = [self.getReloadCause()]

   def clearFaults(self):
      with self.scd.getMmap() as mm:
         mm.write32(self.addr, 0)

   def getReloadCause(self):
      logging.debug('reading reboot causes for %s', self)
      with self.scd.getMmap() as mm:
         code = mm.read32(self.addr) & 0xff
         logging.debug('last cause code %#04x', code)

      for cause in self.descs:
         if code == cause.code:
            logging.debug('found cause %s %s', cause.typ, cause.description)
            return ScdReloadCauseEntry(
               cause=cause.typ,
               # NOTE: rcTime is not available
               rcDesc=cause.description,
               # NOTE: even though there is no great details it needs to play
               #       nicely with devices that do report detailed faults.
               score=ReloadCauseScore.LOGGED | ReloadCauseScore.DETAILED |
                     ReloadCauseScore.getPriority(ReloadCausePriority.NORMAL),
               priority=cause.priority,
               altSource=cause.altSource,
            )

      logging.debug('unhandled cause %#02x', code)
      return ScdReloadCauseEntry(
         cause='unknown',
         rcDesc=f'unknown logged fault {code:#04x}',
         score=ReloadCauseScore.LOGGED,
         priority=ReloadCausePriority.UNKNOWN,
      )

class ScdReloadCauseProvider(HardwareReloadCauseProvider):

   def __init__(self, scd, regmap, causes, **kwargs):
      super().__init__(name=str(scd), descs=causes, **kwargs)
      self.scd = scd
      self.regmap = regmap
      self.regs_ = None

   def __str__(self):
      return self.__class__.__name__

   @property
   def regs(self):
      if self.regs_ is None:
         self.regs_ = self.regmap(self.scd.driver)
      return self.regs_

   def process(self):
      cause = self.getReloadCause()
      self.causes = [] if cause is None else [cause]

   def _getRtcTime(self, ticks, secs):
      msecs = ticks / 2**16
      date = self.scd.FAULT_TIME_BASE + datetime.timedelta(seconds=secs + msecs)
      return datetimeToStr(date)

   def getReloadCauseTime(self):
      ticks = self.regs.lastFractional()
      secs = self.regs.lastSeconds()
      return self._getRtcTime(ticks, secs)

   def faultsCleared(self):
      return not self.regs.clearFault()

   def clearFaults(self):
      logging.debug('clearing faults')
      self.regs.clearFault(1)

   def getReloadCause(self):
      if self.faultsCleared():
         logging.debug('reboot cause already cleared')
         return None

      logging.debug('reading reboot causes for %s', self)
      code = self.regs.lastCause()
      rcTime = self.getReloadCauseTime()
      logging.debug('last cause code %#04x on %s', code, rcTime)
      self.clearFaults()

      for cause in self.descs:
         if code != cause.code:
            continue
         logging.debug('found cause %s %s', cause.typ, cause.description)
         return ScdReloadCauseEntry(
            cause=cause.typ,
            rcTime=rcTime,
            rcDesc=cause.description,
            # NOTE: even though there is no great details it needs to play
            #       nicely with devices that do report detailed faults.
            score=ReloadCauseScore.LOGGED | ReloadCauseScore.DETAILED |
                  ReloadCauseScore.getPriority(cause.priority),
            priority=cause.priority,
            altSource=cause.altSource,
         )

      logging.debug('unhandled cause %#02x', code)
      return ScdReloadCauseEntry(
         cause='unknown',
         rcDesc=f'unknown logged fault {code:#04x}',
         score=ReloadCauseScore.LOGGED,
         priority=ReloadCausePriority.UNKNOWN,
      )
