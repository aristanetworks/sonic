from __future__ import with_statement

import datetime
import logging
from collections import namedtuple

from ..core.cause import datetimeToStr, ReloadCauseEntry
from ..core.component import Priority
from ..core.config import Config
from ..core.utils import JsonStoredData, inSimulation

from ..drivers.dpm import UcdI2cDevDriver

from .common import I2cComponent

UcdGpi = namedtuple( 'UcdGpi', [ 'bit' ] )
UcdMon = namedtuple( 'UcdMon', [ 'val' ] )

class UcdReloadCauseEntry(ReloadCauseEntry):
   pass

class Ucd(I2cComponent):
   class Registers(object):
      RUN_TIME_CLOCK = 0xd7
      LOGGED_FAULTS = 0xea
      LOGGED_FAULT_DETAIL_INDEX = 0xeb
      LOGGED_FAULT_DETAIL = 0xec

      LOGGED_FAULTS_COUNT = 13
      LOGGED_FAULT_DETAIL_COUNT = 10

      MFR_SERIAL = 0x9e
      DEVICE_ID = 0xfd

      def __str__(self):
         return '%s()' % self.__class__.__name__

   gpiSize = 1
   faultValueSize = 2

   faultTimeBase = datetime.datetime(1970, 1, 1)
   daysOffset = 0

   def __init__(self, addr, drivers=None, causes=None, priority=Priority.BACKGROUND,
                **kwargs):
      drivers = drivers or [UcdI2cDevDriver(addr=addr, registers=self.Registers)]
      self.causes = causes or {}
      self.oldestTime = datetime.datetime(1970, 1, 1)
      super(Ucd, self).__init__(addr=addr, drivers=drivers, priority=priority,
                                **kwargs)

   def __str__(self):
      return '%s()' % self.__class__.__name__

   def setup(self):
      with self.drivers['UcdI2cDevDriver'] as drv:
         try:
            serial = drv.getVersion()
            logging.info('%s version: %s', self, serial)
         except Exception:
            logging.error('%s: failed to version information', self)

         # DPM run time clock needs to be updated
         try:
            self._setRunTimeClock(drv)
            logging.info('%s time: %s', self, self._getRunTimeClock(drv))
         except Exception:
            logging.error('%s: failed to set run time clock', self)

   def _setRunTimeClock(self, drv):
      diff = datetime.datetime.now() - self.oldestTime
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
      drv.setBlock(self.Registers.RUN_TIME_CLOCK, data)

   def _getRunTimeClock(self, drv):
      res = drv.getBlock(self.Registers.RUN_TIME_CLOCK)
      msecs = res[3] | (res[2] << 8) | (res[1] << 16) | (res[0] << 24)
      days = res[7] | (res[6] << 8) | (res[5] << 16) | (res[4] << 24)
      days -= self.daysOffset
      return self.oldestTime + datetime.timedelta(days=days, milliseconds=msecs)

   def _getGpiFaults(self, reg):
      causes = []
      for name, typ in self.causes.items():
         if not isinstance(typ, UcdGpi):
            continue
         if reg & (1 << (typ.bit - 1)):
            causes.append(UcdReloadCauseEntry(name))
      return causes

   def _parseFaultDetail(self, reg):
      msecs = (reg[0] << 24) | (reg[1] << 16) | (reg[2] << 8) | reg[3]
      fid = (reg[4] << 24) | (reg[5] << 16) | (reg[6] << 8) | reg[7]
      paged = (fid >> 31) & 0x1
      ftype = (fid >> 27) & 0xf
      page = ((fid >> 23) & 0xf) + 1
      days = fid & 0x7fffff
      value = (reg[9] << 8) | reg[8]
      return paged, ftype, page, value, days, msecs

   def _getFaultNum(self, reg):
      causes = []

      if len(reg) < self.Registers.LOGGED_FAULT_DETAIL_COUNT:
         logging.debug('invalid unknown cause %s', reg)
         time = datetime.datetime.now()
         causes.append(UcdReloadCauseEntry('unknown', rcTime=datetimeToStr(time)))
         return causes

      paged, ftype, page, value, days, msecs = self._parseFaultDetail(reg)
      days = int(days)
      secs = int(msecs / 1000)
      usecs = int((msecs - secs * 1000) * 1000)

      time = self.faultTimeBase + datetime.timedelta(days=days, seconds=secs,
                                                     microseconds=usecs)
      logging.debug('paged=%d type=%d page=%d value=0x%04x time=%s',
                    paged, ftype, page, value, time)

      if not paged and ftype == 9:
         # this is a Gpi
         for name, typ in self.causes.items():
            if isinstance(typ, UcdGpi) and typ.bit == page:
               logging.debug('found: %s', name)
               causes.append(UcdReloadCauseEntry(name, rcTime=datetimeToStr(time)))
      elif paged and ftype in [ 0, 1 ]:
         # this is a Mon
         for name, typ in self.causes.items():
            if isinstance(typ, UcdMon) and typ.val == page:
               logging.debug('found: %s', name)
               causes.append(UcdReloadCauseEntry(name, rcTime=datetimeToStr(time)))
      else:
         logging.debug('unknown cause')
         causes.append(UcdReloadCauseEntry('unknown', rcTime=datetimeToStr(time)))

      return causes

   def _getReloadCauses(self, drv):
      reg = drv.readFaults()
      if reg[ 0 ]:
         logging.debug('some non paged faults were detected')

      causes = []
      if self.gpiSize:
         gpi = 0
         for i in range(0, self.gpiSize):
            gpi |= reg[1 + i] << (8 * i)
         causes = self._getGpiFaults(gpi)
         logging.debug('found %d gpi faults', len(causes))
         for cause in causes:
            logging.debug('found: %s', cause)

      faultCount = drv.getFaultCount()
      logging.debug('found %d faults', faultCount)
      for i in range(0, faultCount):
         causes.extend(self._getFaultNum(drv.getFaultNum(i)))

      return causes

   def getReloadCauses(self, clear=False):
      if not self.causes or inSimulation():
         return []

      rebootCauses = JsonStoredData('%s_%s' % (Config().reboot_cause_file,
                                               self.addr))
      if not rebootCauses.exist():
         with self.drivers['UcdI2cDevDriver'] as drv:
            causes = self._getReloadCauses(drv)
            if clear:
               logging.debug('clearing faults')
               drv.clearFaults()
            if not causes:
               time = datetime.datetime.now()
               causes = [UcdReloadCauseEntry('unknown', rcTime=datetimeToStr(time))]
         rebootCauses.writeList(causes)

      return rebootCauses.readList(UcdReloadCauseEntry)

class Ucd90160(Ucd):
   class Registers(Ucd.Registers):
      LOGGED_FAULTS_COUNT = 18

class Ucd90120(Ucd):
   gpiSize = 0

class Ucd90120A(Ucd):
   class Registers(Ucd.Registers):
      LOGGED_FAULTS_COUNT = 14

class Ucd90320(Ucd):
   class Registers(Ucd.Registers):
      LOGGED_FAULTS_COUNT = 37
      LOGGED_FAULT_DETAIL_COUNT = 12

   gpiSize = 4

   # The fault time is from 2000-01-01
   faultTimeBase = datetime.datetime(2000, 1, 1)
   # RUN_TIME_CLOCK is from 0001-01-01
   daysOffset = 719162    # Equals to 2000-01-01 - 0001-01-01

   def _parseFaultDetail(self, reg):
      pageAndMsecs = (reg[0] << 24) | (reg[1] << 16) | (reg[2] << 8) | reg[3]
      page = (pageAndMsecs >> 27) + 1
      msecs = pageAndMsecs & 0x7ffffff
      fid = (reg[4] << 24) | (reg[5] << 16) | (reg[6] << 8) | reg[7]
      paged = (fid >> 31) & 0x1
      ftype = (fid >> 27) & 0xf
      days = (fid >> 11) & 0xffff
      value = (reg[9] << 8) | reg[8]
      return paged, ftype, page, value, days, msecs
