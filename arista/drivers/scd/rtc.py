import datetime

from ...inventory.rtc import RealTimeClock

class ScdRealTimeClock(RealTimeClock):

   def __init__(self, scd, regmap):
      self.scd = scd
      self.regmap = regmap
      self.regs_ = None

   @property
   def regs(self):
      if self.regs_ is None:
         self.regs_ = self.regmap(self.scd.driver)
      return self.regs_

   def getName(self):
      return str(self.scd)

   def getTime(self):
      ticks = self.regs.rtcFractional()
      secs = self.regs.rtcSeconds()
      msecs = ticks / 2**16
      return self.scd.FAULT_TIME_BASE + datetime.timedelta(seconds=secs + msecs)

   def setTime(self, dt):
      delta = dt - self.scd.FAULT_TIME_BASE
      now = delta.total_seconds()
      secs = int(now)
      ticks = int(2**16 * (now - secs))
      self.regs.rtcFractional(ticks)
      self.regs.rtcSeconds(secs)
