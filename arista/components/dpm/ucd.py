from __future__ import with_statement

import datetime

from ...core.cause import (
   ReloadCauseEntry,
   HardwareReloadCauseProvider,
   ReloadCauseScore,
)
from ...core.component import Priority
from ...core.driver.user.rtc import RealTimeClockImpl
from ...core.utils import inSimulation
from ...core.log import getLogger

from ...descs.cause import ReloadCauseDesc, ReloadCausePriority

from ...drivers.dpm.ucd import UcdUserDriver

from ...inventory.programmable import Programmable

from ...libs.date import datetimeToStr
from ...libs.integer import iterBits, listToIntLsb

from .pmbus import PmbusDpm

logging = getLogger(__name__)

def _formatBytes(data):
   return ' '.join(f'{b:02x}' for b in data)

class UcdPriority(ReloadCausePriority):
   pass

class UcdGpi():
   TYPE = 'gpi'
   def __init__(self, bit, causeDesc, description=None,
                priority=UcdPriority.NORMAL, altSource=None):
      self.bit = bit
      self.causeDesc = causeDesc
      self.description = description
      self.priority = priority
      self.altSource = altSource

   def getReason(self, page=None, detailed=False):
      ptype = self.TYPE if page is None else f'{self.TYPE} {page}'
      ftype = 'detailed fault' if detailed else 'fault'
      reason = f'{ptype} {ftype} - {self.causeDesc.desc}'
      if self.description is not None:
         reason += f' - {self.description}'
      return reason

class UcdMon(UcdGpi):
   TYPE = 'mon'

class UcdReloadCauseEntry(ReloadCauseEntry):
   pass

class UcdReloadCauseProvider(HardwareReloadCauseProvider):
   def __init__(self, ucd, **kwargs):
      super().__init__(name=str(ucd), **kwargs)
      self.ucd = ucd

   def process(self):
      self.causes = self.ucd.getReloadCauses()

   def getReloadCauseDescs(self):
      return tuple(
         ReloadCauseDesc(
            f'{c.TYPE}{c.bit}',
            c.causeDesc,
            description=c.description,
            priority=c.priority,
            altSource=c.altSource,
         ) for c in self.ucd.causes
      )

class UcdFaultDesc():
   def __init__(self, paged, typ, description, unit=None, conv=None):
      self.paged = paged
      self.typ = typ
      self.description = description
      self.conv = conv
      self.unit = unit

   def getReason(self, page=None):
      if not self.paged:
         return self.description
      return '%s on rail %s' % (self.description, page)

class UcdFaultRegister():
   def __init__(self, np=1, gpi=1, fan=2, pages=9):
      self.np = np
      self.gpi = gpi
      self.fan = fan
      self.pages = pages

   def parse(self, reg):
      return UcdFaultRegister()

class UcdProgrammable(Programmable):
   def __init__(self, ucd):
      self.ucd = ucd

   def getComponent(self):
      return self.ucd

   def getDescription(self):
      return 'Power Sequencer and Manager'

   def getVersion(self):
      return self.ucd.getVersion()

class Ucd(PmbusDpm):

   DRIVER = UcdUserDriver
   PRIORITY = Priority.DPM

   PAGE_COUNT = 13

   FAULTS = {(f.paged, f.typ): f for f in [
      UcdFaultDesc(False, 2, 'resequence-error'),
      UcdFaultDesc(False, 3, 'watchdog-timeout'),
      UcdFaultDesc(True, 0, 'over-voltage'),
      UcdFaultDesc(True, 1, 'under-voltage'),
      UcdFaultDesc(True, 2, 'timeout-power-good'),
      UcdFaultDesc(True, 3, 'over-current'),
      UcdFaultDesc(True, 4, 'under-current'),
      UcdFaultDesc(True, 5, 'over-temperature'),
      UcdFaultDesc(True, 6, 'seq-on-timeout'),
      UcdFaultDesc(True, 7, 'seq-off-timeout'),
   ]}

   class Registers(PmbusDpm.Registers):
      REAL_TIME_CLOCK = 0xd7

      LOGGED_FAULTS = 0xea
      LOGGED_FAULT_DETAIL_INDEX = 0xeb
      LOGGED_FAULT_DETAIL = 0xec

      LOGGED_FAULTS_COUNT = 13
      LOGGED_FAULT_DETAIL_COUNT = 10

      DEVICE_ID = 0xfd

      def __str__(self):
         return '%s()' % self.__class__.__name__

   gpiSize = 1
   npfSize = 1
   faultValueSize = 2

   faultTimeBase = datetime.datetime(1970, 1, 1)
   daysOffset = 0

   def __init__(self, addr=None, causes=None, causePriority=UcdPriority.PRIMARY,
                altSource=None, **kwargs):
      super().__init__(addr=addr, **kwargs)
      self.causes = causes if causes is not None else []
      self.oldestTime = datetime.datetime(1970, 1, 1)
      self.inventory.addReloadCauseProvider(
         UcdReloadCauseProvider(self, priority=causePriority,
                                altSource=altSource))
      self.inventory.addProgrammable(UcdProgrammable(self))
      self.inventory.addRtc(RealTimeClockImpl(self))

   def setRealTimeClock(self, dt):
      diff = dt - self.oldestTime
      msecsInt = int(diff.seconds * 1000 + diff.microseconds / 1000)
      daysInt = diff.days
      daysInt += self.daysOffset
      msecsByte1 = (msecsInt >> 24) & 0xff
      msecsByte2 = (msecsInt >> 16) & 0xff
      msecsByte3 = (msecsInt >> 8) & 0xff
      msecsByte4 = msecsInt & 0xff
      daysByte1 = (daysInt >> 24) & 0xff
      daysByte2 = (daysInt >> 16) & 0xff
      daysByte3 = (daysInt >> 8) & 0xff
      daysByte4 = daysInt & 0xff
      data = [msecsByte1, msecsByte2, msecsByte3, msecsByte4,
              daysByte1, daysByte2, daysByte3, daysByte4]
      self.driver.setBlock(self.Registers.REAL_TIME_CLOCK, data)

   def getRealTimeClock(self):
      res = self.driver.getBlock(self.Registers.REAL_TIME_CLOCK)
      msecs = res[3] | (res[2] << 8) | (res[1] << 16) | (res[0] << 24)
      days = res[7] | (res[6] << 8) | (res[5] << 16) | (res[4] << 24)
      days -= self.daysOffset
      return self.oldestTime + datetime.timedelta(days=days, milliseconds=msecs)

   def getVersion(self):
      return self.driver.getVersion()

   def _parseFaultDetail(self, reg):
      msecs = (reg[0] << 24) | (reg[1] << 16) | (reg[2] << 8) | reg[3]
      fid = (reg[4] << 24) | (reg[5] << 16) | (reg[6] << 8) | reg[7]
      paged = (fid >> 31) & 0x1
      ftype = (fid >> 27) & 0xf
      page = ((fid >> 23) & 0xf) + 1
      days = fid & 0x7fffff
      value = (reg[9] << 8) | reg[8]
      return paged, ftype, page, value, days, msecs

   def _decodeFaultDetail(self, reg):
      paged, ftype, page, value, days, msecs = self._parseFaultDetail(reg)
      days = int(days)
      secs = int(msecs / 1000)
      usecs = int((msecs - secs * 1000) * 1000)

      time = self.faultTimeBase + datetime.timedelta(days=days, seconds=secs,
                                                     microseconds=usecs)
      logging.debug('paged=%d type=%d page=%d value=0x%04x time=%s',
                    paged, ftype, page, value, time)
      return paged, ftype, page, time

   def _getFaultNum(self, paged, ftype, page, time, debugInfo):
      causes = []

      found = False
      if not paged and ftype == 9:
         cause = self._getCause(page)
         if cause is not None:
            logging.debug('found detailed gpi: %s', cause.causeDesc.typ)
            causes.append(UcdReloadCauseEntry(
               cause=cause.causeDesc.typ,
               rcTime=datetimeToStr(time),
               rcDesc=cause.getReason(page=page, detailed=True),
               score=ReloadCauseScore.LOGGED | ReloadCauseScore.DETAILED |
                     ReloadCauseScore.getPriority(cause.priority),
               priority=cause.priority,
               altSource=cause.altSource,
               debugInfo=debugInfo,
            ))
         else:
            logging.debug('found unknown detailed gpi: %s', page)
            causes.append(UcdReloadCauseEntry(
                cause='gpi-%s' % page,
                rcTime=datetimeToStr(time),
                rcDesc='gpi %s detailed fault' % page,
                score=ReloadCauseScore.LOGGED | ReloadCauseScore.DETAILED |
                      ReloadCauseScore.getPriority(UcdPriority.NONE),
                priority=ReloadCausePriority.UNKNOWN,
                debugInfo=debugInfo,
            ))
         found = True
      elif paged and (ftype in (0, 1)):
         cause = self._getCause(page, typ=UcdMon)
         if cause is not None:
            logging.debug('found detailed mon: %s', cause.causeDesc.typ)
            causes.append(UcdReloadCauseEntry(
               cause=cause.causeDesc.typ,
               rcTime=datetimeToStr(time),
               rcDesc=cause.getReason(page=page, detailed=True),
               score=ReloadCauseScore.LOGGED | ReloadCauseScore.DETAILED |
                     ReloadCauseScore.getPriority(cause.priority),
               priority=cause.priority,
               altSource=cause.altSource,
               debugInfo=debugInfo,
            ))
            found = True

      if not found:
         fault = self.FAULTS.get((paged, ftype))
         if fault is not None:
            cause = UcdReloadCauseEntry(
               cause=fault.description,
               rcTime=datetimeToStr(time),
               rcDesc=fault.getReason(page),
               score=ReloadCauseScore.EVENT | ReloadCauseScore.DETAILED |
                     ReloadCauseScore.getPriority(UcdPriority.NONE),
               priority=ReloadCausePriority.UNKNOWN,
               debugInfo=debugInfo,
            )
            logging.debug('found detailed fault: %s', cause.description)
            causes.append(cause)
         else:
            logging.debug('unhandled detailed fault')

      return causes

   def _parseFaults(self, reg):
      npf = None
      gpi = None

      idx = 0
      if self.npfSize:
         npf = listToIntLsb(reg[idx:idx+self.npfSize]) & ~0x01
         npf &= ~0x01 # ignore LOG_NOT_EMPTY
         idx += self.npfSize

      if self.gpiSize:
         gpi = listToIntLsb(reg[idx:idx+self.gpiSize])
         idx += self.gpiSize

      return npf, gpi

   def _getCause(self, value, typ=UcdGpi):
      for cause in self.causes:
         if cause.TYPE != typ.TYPE:
            continue
         if cause.bit == value:
            return cause
      return None

   def _getSimpleFaults(self, reg, detailedCauses):
      npf, gpi = self._parseFaults(reg)
      causes = []
      debugInfo = _formatBytes(reg)

      if npf is not None:
         for bitpos, bit in enumerate(iterBits(npf)):
            if not bit:
               continue
            fault = self.FAULTS.get((False, bitpos))
            if fault is not None:
               logging.debug('found non paged fault: %s', fault.description)
               causes.append(UcdReloadCauseEntry(
                  cause=fault.getReason(),
                  rcDesc='non paged fault',
                  score=ReloadCauseScore.LOGGED |
                        ReloadCauseScore.getPriority(UcdPriority.NORMAL),
                  debugInfo=debugInfo,
               ))
            else:
               logging.debug('found unknown non paged fault: %s', npf)

      if gpi is not None:
         for bitpos, bit in enumerate(iterBits(gpi), 1):
            if not bit:
               continue
            # Ignore if detailed cause already presents
            if bitpos in detailedCauses:
               continue
            cause = self._getCause(bitpos)
            if cause is not None:
               logging.debug('found gpi: %s', cause.causeDesc.typ)
               causes.append(UcdReloadCauseEntry(
                  cause=cause.causeDesc.typ,
                  rcDesc=cause.getReason(page=bitpos),
                  score=ReloadCauseScore.LOGGED |
                        ReloadCauseScore.getPriority(cause.priority),
                  priority=cause.priority,
                  altSource=cause.altSource,
                  debugInfo=debugInfo,
               ))
            else:
               logging.debug('found unknown gpi: %s', bitpos)
               causes.append(UcdReloadCauseEntry(
                  cause='gpi-%d' % bitpos,
                  rcDesc='unknown gpi fault',
                  score=ReloadCauseScore.LOGGED |
                        ReloadCauseScore.getPriority(UcdPriority.NONE),
                  priority=ReloadCausePriority.UNKNOWN,
                  debugInfo=debugInfo,
               ))

      logging.debug('found %d faults', len(causes))

      return causes

   def _getReloadCauses(self, drv):
      causes = []
      detailedCauses = []

      faultCount = drv.getFaultCount()
      logging.debug('found %d detailed faults', faultCount)
      for i in range(0, faultCount):
         reg = drv.getFaultNum(i)
         if len(reg) < self.Registers.LOGGED_FAULT_DETAIL_COUNT:
            logging.debug('invalid unknown cause %s', reg)
            continue
         paged, ftype, page, time = self._decodeFaultDetail(reg)
         # Record the GPI bit number of the detailed causes, whether known or not
         if not paged and ftype == 9:
            detailedCauses.append(page)
         causes.extend(self._getFaultNum(paged, ftype, page, time,
                                         _formatBytes(reg)))

      causes.extend(self._getSimpleFaults(drv.readFaults(), detailedCauses))

      return causes

   def getReloadCauses(self, simulated=inSimulation()):
      if simulated:
         return []

      with self.driver as drv:
         causes = self._getReloadCauses(drv)
         logging.debug('clearing faults')
         drv.clearFaults()

      return causes

class Ucd90160(Ucd):

   PAGE_COUNT = 16

   class Registers(Ucd.Registers):
      LOGGED_FAULTS_COUNT = 18

class Ucd90120(Ucd):
   gpiSize = 0

class Ucd90120A(Ucd):
   class Registers(Ucd.Registers):
      LOGGED_FAULTS_COUNT = 14

class Ucd90320(Ucd):

   PAGE_COUNT = 24

   class Registers(Ucd.Registers):
      LOGGED_FAULTS_COUNT = 37
      LOGGED_FAULT_DETAIL_COUNT = 12

   gpiSize = 4

   # The fault time is from 2000-01-01
   faultTimeBase = datetime.datetime(2000, 1, 1)
   # REAL_TIME_CLOCK is from 0001-01-01
   daysOffset = 719162    # Equals to 2000-01-01 - 0001-01-01

   def _parseFaultDetail(self, reg):
      pageAndMsecs = (reg[0] << 24) | (reg[1] << 16) | (reg[2] << 8) | reg[3]
      page = (pageAndMsecs >> 27) + 1
      msecs = pageAndMsecs & 0x7ffffff
      fid = (reg[4] << 24) | (reg[5] << 16) | (reg[6] << 8) | reg[7]
      paged = (fid >> 31) & 0x1
      ftype = (fid >> 27) & 0xf
      days = (fid >> 11) & 0xffff
      value = (reg[11] << 24) | (reg[10] << 16) | (reg[9] << 8) | reg[8]
      return paged, ftype, page, value, days, msecs

class Ucd9090A(Ucd):
   PAGE_COUNT = 11
   pass
