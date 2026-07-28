import datetime
import time

from ..core.cause import (
   ReloadCauseEntry,
   HardwareReloadCauseProvider,
   ReloadCauseScore,
)
from ..core.component import Priority
from ..core.component.i2c import I2cComponent
from ..core.driver import modprobe
from ..core.log import getLogger
from ..core.register import (
   Register,
   RegisterArray,
   RegisterMap,
   RegBitField,
   RegBitRange,
)
from ..core.utils import inSimulation

from ..descs.cause import ReloadCauseDesc, ReloadCausePriority

from ..drivers.cpld import SysCpldI2cDriver

from ..inventory.powercycle import PowerCycle
from ..inventory.programmable import Programmable
from ..inventory.rtc import RealTimeClock
from ..inventory.seu import SeuReporter

from ..libs.date import datetimeToStr

logging = getLogger(__name__)

class SysCpldCommonRegisters(RegisterMap):
   MINOR = Register(0x00, name='revisionMinor')
   REVISION = Register(0x01, name='revision')
   SCRATCHPAD = Register(0x02, name='scratchpad', ro=False)
   SUICIDE = Register(0x03, name='suicide', ro=False)
   POWER_CYCLE = Register(0x04, name='powerCycle', ro=False)

class SysCpldCommonRegistersV2(SysCpldCommonRegisters):
   PWR_CTRL_STS = Register(0x05,
      RegBitField(7, 'dpPower', ro=False),
      RegBitField(0, 'switchCardPowerGood'),
   )
   INT_STS = Register(0x08,
      RegBitField(4, 'dpPowerFail'),
      RegBitField(3, 'overtemp'),
      RegBitField(0, 'scdCrcError'),
   )
   SCD_CTRL_STS = Register(0x0A,
      RegBitField(5, 'scdReset', ro=False),
      RegBitField(1, 'scdInitDone'),
      RegBitField(0, 'scdConfDone'),
   )
   PWR_CYC_EN = Register(0x17,
      RegBitField(0, 'powerCycleOnCrc', ro=False),
   )

class SysCpldReloadCauseRegisters(RegisterMap):
   FAULT_REGISTER = Register(0x20,
      RegBitRange(0, 5, 'cause', ro=False),
   )
   FAULT_TIME = RegisterArray(0x21, 0x26, name='faultTime')
   FAULT_CONTROL = Register(0x28,
      RegBitField(0, 'clearFault', ro=False),
   )
   RTC = RegisterArray(0x30, 0x35, name='rtc', ro=False)

class SysCpldReloadCauseRegistersV2(RegisterMap):
   FAULT_REGISTER = Register(0x60,
      RegBitRange(0, 5, 'cause', ro=False),
   )
   FAULT_TIME = RegisterArray(0x61, 0x66, name='faultTime')
   FAULT_CONTROL = Register(0x58,
      RegBitField(0, 'clearFault', ro=False),
   )
   RTC = RegisterArray(0x40, 0x45, name='rtc', ro=False)

class LeakDetectionCpldRegistersV1(RegisterMap):
   """
   Register map for leak detection registers in a CPLD that are accessed over an
   8-bit bus (SMBus/I2C).
   """

   MAJOR_STATUS_0 = Register(0xB0,
      RegBitField(0, 'majorRope0Present'),
      RegBitField(1, 'majorRope1Present'),
      RegBitField(2, 'majorRope2Present'),
      RegBitField(3, 'majorRope3Present'),
      RegBitField(4, 'majorRope0Break'),
      RegBitField(5, 'majorRope1Break'),
      RegBitField(6, 'majorRope2Break'),
      RegBitField(7, 'majorRope3Break'),
   )

   MAJOR_STATUS_1 = Register(0xB1,
      RegBitField(0, 'majorRope0Leak'),
      RegBitField(1, 'majorRope1Leak'),
      RegBitField(2, 'majorRope2Leak'),
      RegBitField(3, 'majorRope3Leak'),
      RegBitField(4, 'majorRope0Changed', ro=False),
      RegBitField(5, 'majorRope1Changed', ro=False),
      RegBitField(6, 'majorRope2Changed', ro=False),
      RegBitField(7, 'majorRope3Changed', ro=False),
   )

   MAJOR_DEBOUNCE_ROPE0 = Register(0xB4, RegBitRange(0, 7, 'majorRope0DebounceS',
                                                     ro=False))
   MAJOR_DEBOUNCE_ROPE1 = Register(0xB5, RegBitRange(0, 7, 'majorRope1DebounceS',
                                                     ro=False))
   MAJOR_DEBOUNCE_ROPE2 = Register(0xB6, RegBitRange(0, 7, 'majorRope2DebounceS',
                                                     ro=False))
   MAJOR_DEBOUNCE_ROPE3 = Register(0xB7, RegBitRange(0, 7, 'majorRope3DebounceS',
                                                     ro=False))

   MAJOR_TEST = Register(0xB8,
      RegBitField(0, 'majorRope0ForceLeak', ro=False),
      RegBitField(1, 'majorRope1ForceLeak', ro=False),
      RegBitField(2, 'majorRope2ForceLeak', ro=False),
      RegBitField(3, 'majorRope3ForceLeak', ro=False),
   )

   MAJOR_ACTION_0 = Register(0xB9,
      RegBitField(0, 'majorLiquidDomainPowerDownEnable', ro=False),
      RegBitField(1, 'majorSystemPowerCycleEnable', ro=False),
   )

   MAJOR_ACTION_1 = Register(0xBA,
      RegBitRange(0, 5, 'majorLeakActionDelayTimeS', ro=False),
      RegBitField(7, 'majorLeakActionDelayTimeEnable', ro=False),
   )

   # Overrides MAJOR_ACTION_0 if MAJOR_WATCHDOG_TIMEOUT_ACTION_2.watchdog_enable is
   # set.
   MAJOR_WATCHDOG_TIMEOUT_ACTION_1 = Register(0xBD,
      RegBitField(0, 'majorWatchdogLiquidDomainPowerDownEnable', ro=False),
      RegBitField(1, 'majorWatchdogSystemPowerCycleEnable', ro=False),
   )

   MAJOR_WATCHDOG_TIMEOUT_ACTION_2 = Register(0xBE,
      RegBitRange(0, 5, 'majorWatchdogTimeS', ro=False),
      RegBitField(7, 'majorWatchdogEnable', ro=False),
   )

   MINOR_STATUS_0 = Register(0xC0,
      RegBitField(0, 'minorRope0Present'),
      RegBitField(1, 'minorRope1Present'),
      RegBitField(2, 'minorRope2Present'),
      RegBitField(3, 'minorRope3Present'),
      RegBitField(4, 'minorRope0Break'),
      RegBitField(5, 'minorRope1Break'),
      RegBitField(6, 'minorRope2Break'),
      RegBitField(7, 'minorRope3Break'),
   )

   MINOR_STATUS_1 = Register(0xC1,
      RegBitField(0, 'minorRope0Leak'),
      RegBitField(1, 'minorRope1Leak'),
      RegBitField(2, 'minorRope2Leak'),
      RegBitField(3, 'minorRope3Leak'),
      RegBitField(4, 'minorRope0Changed', ro=False),
      RegBitField(5, 'minorRope1Changed', ro=False),
      RegBitField(6, 'minorRope2Changed', ro=False),
      RegBitField(7, 'minorRope3Changed', ro=False),
   )

   MINOR_DEBOUNCE_ROPE0 = Register(0xC4, RegBitRange(0, 7, 'minorRope0DebounceS',
                                                     ro=False))
   MINOR_DEBOUNCE_ROPE1 = Register(0xC5, RegBitRange(0, 7, 'minorRope1DebounceS',
                                                     ro=False))
   MINOR_DEBOUNCE_ROPE2 = Register(0xC6, RegBitRange(0, 7, 'minorRope2DebounceS',
                                                     ro=False))
   MINOR_DEBOUNCE_ROPE3 = Register(0xC7, RegBitRange(0, 7, 'minorRope3DebounceS',
                                                     ro=False))

   MINOR_TEST = Register(0xC8,
      RegBitField(0, 'minorRope0ForceLeak', ro=False),
      RegBitField(1, 'minorRope1ForceLeak', ro=False),
      RegBitField(2, 'minorRope2ForceLeak', ro=False),
      RegBitField(3, 'minorRope3ForceLeak', ro=False),
   )

   MINOR_ACTION_0 = Register(0xC9,
      RegBitField(0, 'minorLiquidDomainPowerDownEnable', ro=False),
      RegBitField(1, 'minorSystemPowerCycleEnable', ro=False),
   )

   MINOR_ACTION_1 = Register(0xCA,
      RegBitRange(0, 5, 'minorLeakActionDelayTimeS', ro=False),
      RegBitField(7, 'minorLeakActionDelayTimeEnable', ro=False),
   )

   # Overrides MINOR_ACTION_0 if MINOR_WATCHDOG_TIMEOUT_ACTION_2.watchdog_enable is
   # set.
   MINOR_WATCHDOG_TIMEOUT_ACTION_1 = Register(0xCD,
      RegBitField(0, 'minorWatchdogLiquidDomainPowerDownEnable', ro=False),
      RegBitField(1, 'minorWatchdogSystemPowerCycleEnable', ro=False),
   )

   MINOR_WATCHDOG_TIMEOUT_ACTION_2 = Register(0xCE,
      RegBitRange(0, 5, 'minorWatchdogTimeS', ro=False),
      RegBitField(7, 'minorWatchdogEnable', ro=False),
   )

class SysCpldPowerCycle(PowerCycle):
   def __init__(self, parent):
      self.parent = parent

   def ensureAvailable(self):
      # Modprobe for kdump kernel
      modprobe('i2c-dev')

   def powerCycle(self):
      logging.info("Initiating powercycle through CPLD")
      self.parent.driver.regs.powerCycle(0xDE)
      logging.info("Powercycle triggered from CPLD")

class SysCpldProgrammable(Programmable):
   def __init__(self, cpld):
      self.cpld = cpld

   def getComponent(self):
      return self.cpld

   def getDescription(self):
      return 'System CPLD'

   def getVersion(self):
      return self.cpld.getVersion()

class SysCpldSeuReporter(SeuReporter):
   def __init__(self, cpld):
      self.cpld = cpld

   def getComponent(self):
      return self.cpld

   def hasSeuError(self):
      return self.cpld.driver.regs.scdCrcError()

   def powerCycleOnSeu(self, on=None):
      return self.cpld.driver.regs.powerCycleOnCrc(on)

class SysCpldCause(ReloadCauseDesc):
   pass

class SysCpldReloadCauseEntry(ReloadCauseEntry):
   pass

class SysCpldRealTimeClock(RealTimeClock):

   def __init__(self, cpld, regmap):
      self.cpld = cpld
      self.regmap = regmap
      self.regs_ = None

   @property
   def regs(self):
      if self.regs_ is None:
         self.regs_ = self.regmap(self.cpld.driver)
      return self.regs_

   def getName(self):
      return str(self.cpld)

   def getTime(self):
      ftime = self.regs.rtc()
      secs = ftime[5] << 24 | ftime[4] << 16 | ftime[3] << 8 | ftime[2]
      msecs = (ftime[1] << 8 | ftime[0]) / 2**16
      return self.cpld.FAULT_TIME_BASE + datetime.timedelta(seconds=secs + msecs)

   def setTime(self, dt):
      delta = dt - self.cpld.FAULT_TIME_BASE
      now = delta.total_seconds()
      secs = int(now)
      ticks = int(2**16 * (now - secs))
      self.regs.rtc([
         ticks & 0xff,
         (ticks >> 8) & 0xff,
         secs & 0xff,
         (secs >> 8) & 0xff,
         (secs >> 16) & 0xff,
         (secs >> 24) & 0xff,
      ])

class SysCpldReloadCauseProvider(HardwareReloadCauseProvider):

   def __init__(self, cpld, regmap, causes, **kwargs):
      super().__init__(descs=causes, **kwargs)
      self.cpld = cpld
      self.regmap = regmap
      self.regs_ = None

   def __str__(self):
      return self.__class__.__name__

   def getSourceName(self):
      return str(self.cpld)

   @property
   def regs(self):
      if self.regs_ is None:
         self.regs_ = self.regmap(self.cpld.driver)
      return self.regs_

   def process(self):
      cause = self.getReloadCause()
      self.causes = [cause] if cause is not None else []

   def faultsCleared(self):
      return not self.regs.clearFault()

   def clearFaults(self):
      logging.debug('clearing faults')
      if self.regs.clearFault():
         self.regs.clearFault(0x01)
      self.regs.cause(0)

   def getReloadCauseTime(self):
      ftime = self.regs.faultTime()
      secs = ftime[5] << 24 | ftime[4] << 16 | ftime[3] << 8 | ftime[2]
      msecs = (ftime[1] << 8 | ftime[0]) / 2**16
      date = self.cpld.FAULT_TIME_BASE + datetime.timedelta(seconds=secs + msecs)
      return datetimeToStr(date)

   def getReloadCause(self):
      if self.faultsCleared():
         logging.debug('reboot cause already cleared')
         return None

      logging.debug('reading reboot causes for %s', self)
      code = self.regs.cause()
      rcTime = self.getReloadCauseTime()
      logging.debug('last cause code %#04x', code)
      self.clearFaults()

      for cause in self.descs:
         if code != cause.code:
            continue
         logging.debug('found cause %s %s', cause.typ, cause.description)
         return SysCpldReloadCauseEntry(
            cause=cause.typ,
            rcTime=rcTime,
            rcDesc=cause.description,
            score=ReloadCauseScore.LOGGED | ReloadCauseScore.DETAILED |
                  ReloadCauseScore.getPriority(cause.priority),
            priority=cause.priority,
            altSource=cause.altSource,
         )

      logging.debug('unhandled cause %02x', code)
      return SysCpldReloadCauseEntry(
         cause='unknown',
         rcTime=rcTime,
         rcDesc=f'unknown logged fault {code:#04x}',
         score=ReloadCauseScore.LOGGED,
         priority=ReloadCausePriority.NORMAL,
      )

class SysCpld(I2cComponent):
   DRIVER = SysCpldI2cDriver
   PRIORITY = Priority.DEFAULT

   SEU_REPORTER_CLS = SysCpldSeuReporter
   FAULT_TIME_BASE = datetime.datetime(2000, 1, 1)

   def __init__(self, *args, **kwargs):
      super(SysCpld, self).__init__(*args, **kwargs)
      self.inventory.addProgrammable(SysCpldProgrammable(self))
      self.inventory.addSeuReporter(self.SEU_REPORTER_CLS(self))

   def getVersion(self):
      if inSimulation():
         return '4.2'
      major = self.driver.regs.revision()
      minor = self.driver.regs.revisionMinor()
      return f'{major:x}.{minor:x}'

   def addPowerCycle(self):
      return self.inventory.addPowerCycle(SysCpldPowerCycle(self))

   def resetScd(self, sleep=1, wait=True):
      state = self.driver.regs.scdReset()
      logging.debug('%s: scd reset: %s', self, state)

      self.driver.regs.scdReset(1)
      if wait:
         time.sleep(sleep) # could be lower
      self.driver.regs.scdReset(0)

   def addGpio(self, attr, name=None):
      name = name or attr
      gpio = self.driver.getGpio(attr, name=name)
      self.inventory.addGpio(gpio)
      return gpio

   def addGpios(self, infos):
      gpios = []
      for info in infos:
         if isinstance(info, tuple):
            gpios.append(self.addGpio(*info))
         else:
            gpios.append(self.addGpio(info))
      return gpios

   def addReloadCauseProvider(self, causes, regmap=SysCpldReloadCauseRegisters,
                              **kwargs):
      provider = SysCpldReloadCauseProvider(self, regmap, causes, **kwargs)
      self.inventory.addReloadCauseProvider(provider)
      self.inventory.addRtc(SysCpldRealTimeClock(self, regmap))
      return provider
