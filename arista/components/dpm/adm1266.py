from abc import abstractmethod
from enum import Enum
from functools import cached_property

from ...core.cause import (
   ReloadCauseEntry,
   ReloadCausePriority,
   ReloadCauseProviderHelper,
   ReloadCauseScore,
)
from ...core.component import Priority
from ...core.log import getLogger
from ...core.utils import inSimulation

from ...descs.cause import ReloadCauseDesc

from ...drivers.dpm.adm1266 import Adm1266UserDriver

from ...inventory.programmable import Programmable

from ...libs.date import datetimeToStr
from ...libs.integer import isBitSet
from ...libs.retry import retryGet

from .pmbus import PmbusDpm

logging = getLogger(__name__)

class AdmPriority(ReloadCausePriority):
   pass

class AdmPin():

   GPIO = 'gpio'
   PDIO = 'pdio'

   def __init__(self, bit, typ, priority=AdmPriority.NORMAL):
      self.bit = bit
      self.typ = typ
      self.priority = priority

class AdmGpio(AdmPin):
   def __init__(self, pin):
      super().__init__(pin, AdmPin.GPIO)

   @staticmethod
   def fromPins(*pins):
      return [AdmGpio(pin) for pin in pins]

class AdmPdio(AdmPin):
   def __init__(self, pin):
      super().__init__(pin, AdmPin.PDIO)

   @staticmethod
   def fromPins(*pins):
      return [AdmPdio(pin) for pin in pins]

class AdmCauseBase(ReloadCauseDesc):
   def __init__(self, current=None, action=None, pins=None,
                name=ReloadCauseDesc.UNKNOWN,
                description=None,
                priority=AdmPriority.NORMAL):
      self._pins = pins or []
      if not isinstance(self._pins, list):
         self._pins = [self._pins]
      super().__init__((current, action, self._pins), name, description, priority)

   def _validateConfig(self):
      if self.gpios and self.pdios:
         raise ValueError("Cannot have both GPIO and PDIO pins")
      if not self.gpios and not self.pdios:
         raise ValueError("Must provide either GPIO or PDIO pins")

   @cached_property
   def gpios(self):
      return [p for p in self._pins if p.typ == AdmPin.GPIO]

   @cached_property
   def pdios(self):
      return [p for p in self._pins if p.typ == AdmPin.PDIO]

   @property
   def name(self):
      return self.typ

   def matchesCurrentAndAction(self, fault):
      if (self.code[0] is not None and self.code[0] != fault.current) or \
         (self.code[1] is not None and self.code[1] != fault.action):
         return False
      return True

   @abstractmethod
   def matchesFault(self, fault):
      pass

class AdmCauseOneHot(AdmCauseBase):
   class Direction(Enum):
      IN = 'input'
      OUT = 'output'
      INOUT = 'both'

   def __init__(self, name, pin, direction=Direction.IN, activeLow=False,
                current=None, action=None, description=None,
                priority=AdmPriority.NORMAL):
      self.direction = direction
      self.activeLow = activeLow
      super().__init__(current, action, pin, name, description, priority)

   def _isPinActive(self, bit, inBits, outBits):
      isActiveIn = isBitSet(bit, inBits) != self.activeLow
      isActiveOut = isBitSet(bit, outBits) != self.activeLow

      if self.direction == self.Direction.INOUT:
         return isActiveIn or isActiveOut
      if self.direction == self.Direction.IN:
         return isActiveIn
      if self.direction == self.Direction.OUT:
         return isActiveOut
      return False

   def matchesFault(self, fault):
      for pin in self.gpios:
         bit = fault.GPIO_MAP.index(pin.bit)
         if not self._isPinActive(bit, fault.gpio_in, fault.gpio_out):
            return False
      for pin in self.pdios:
         bit = pin.bit - 1
         if not self._isPinActive(bit, fault.pdio_in, fault.pdio_out):
            return False
      return super().matchesCurrentAndAction(fault)

class AdmReloadCauseEntry(ReloadCauseEntry):
   pass

class AdmReloadCauseProvider(ReloadCauseProviderHelper):
   def __init__(self, adm):
      super().__init__(name=str(adm))
      self.adm = adm

   def process(self):
      self.causes = self.adm.getReloadCauses()
      self.extra = {
         # NOTE: device might need some time before grabbing the powerup
         'powerup': retryGet(self.adm.getPowerupCounter, wait=0.2, before=True),
      }

   def setRealTimeClock(self):
      self.adm.setRealTimeClock()

class AdmProgrammable(Programmable):
   def __init__(self, adm):
      self.adm = adm

   def getComponent(self):
      return self.adm

   def getDescription(self):
      return 'Power Sequencer and Manager'

   def getVersion(self):
      return self.adm.getVersion()

class Adm1266(PmbusDpm):

   DRIVER = Adm1266UserDriver
   PRIORITY = Priority.DPM

   class Registers(PmbusDpm.Registers):
      REAL_TIME_CLOCK = 0xdf

      IC_DEVICE_ID = 0xad
      IC_DEVICE_REV = 0xae

      BLACKBOX_CONFIGURATION = 0xd3
      READ_BLACKBOX = 0xde
      BLACKBOX_INFORMATION = 0xe6

      USER_DATA = 0xe3
      POWERUP_COUNTER = 0xe4

   def __init__(self, addr=None, causes=None, **kwargs):
      super().__init__(addr=addr, **kwargs)
      self.causes = causes
      self.inventory.addReloadCauseProvider(AdmReloadCauseProvider(self))
      self.inventory.addProgrammable(AdmProgrammable(self))

   def getPowerupCounter(self):
      return self.driver.getPowerupCounter()

   def getVersion(self):
      return self.driver.getVersion()

   def getRealTimeClock(self):
      return self.driver.getRealTimeClock()

   def setRealTimeClock(self):
      self.driver.setRealTimeClock()

   def _getReloadCauses(self):
      causes = []
      for fault in self.driver.getBlackboxFaults():
         logging.debug('fault: %s', fault.summary())
         for name, matcher in self.causes.items():
            if isinstance(matcher, AdmPin):
               pin = matcher
               assert pin.typ == AdmPin.GPIO, \
                  "Unhandled cause of type %s" % pin.typ
               if not fault.isGpio(pin.bit):
                  continue
            elif isinstance(matcher, AdmCauseBase):
               cause = matcher
               if not cause.matchesFault(fault):
                  continue
            else:
               raise ValueError("Unknown cause matcher %s" % matcher)
            logging.debug('found: %s', name)
            causes.append(AdmReloadCauseEntry(
               cause=name,
               rcTime=datetimeToStr(fault.getTime()),
               rcDesc='detailed fault powerup=%d' % fault.powerup,
               score=ReloadCauseScore.LOGGED | ReloadCauseScore.DETAILED |
                     ReloadCauseScore.getPriority(matcher.priority),
            ))
      return causes

   def getReloadCauses(self):
      if inSimulation():
         return []

      causes = self._getReloadCauses()
      logging.debug('%s: clearing faults', self)
      self.driver.clearBlackboxFaults()
      return causes
