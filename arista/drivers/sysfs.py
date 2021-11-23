from __future__ import division, print_function, with_statement

import os

from ..core import utils
from ..core.config import Config
from ..core.driver import Driver
from ..core.log import getLogger

from ..descs.led import LedColor

from ..inventory.fan import Fan
from ..inventory.gpio import Gpio
from ..inventory.led import Led
from ..inventory.reset import Reset
from ..inventory.temp import Temp

logging = getLogger(__name__)

class SysfsEntry(object):
   def __init__(self, parent, name, pathCallback=None):
      self.parent = parent
      self.driver = parent.driver
      self.name = name
      self.pathCallback = pathCallback or self.driver.getHwmonEntry
      self.entryPath_ = None

   def __str__(self):
      return '%s(path=%s)' % (self.__class__.__name__, self.entryPath)

   @property
   def entryPath(self):
      if self.entryPath_ is None:
         self.entryPath_ = self.pathCallback(self.name)
      return self.entryPath_

   def exists(self):
      return os.path.exists(self.entryPath)

   def _readConversion(self, value):
      return str(value)

   def _writeConversion(self, value):
      return str(value)

   def _read(self):
      if utils.inSimulation():
         return '1'
      try:
         with open(self.entryPath, 'r') as f:
            return f.read()
      except IOError:
         logging.error("read sysfs failed on %s", self.entryPath)
         return None

   def _write(self, value):
      if utils.inSimulation():
         return True
      try:
         with open(self.entryPath, 'w') as f:
            f.write(value)
      except Exception: # pylint: disable=broad-except
         return False
      return True

   def read(self):
      raw = self._read().rstrip()
      value = self._readConversion(raw)
      logging.io('%s.read(): %s -> %s', self, raw, value)
      return value

   def write(self, value):
      raw = self._writeConversion(value)
      logging.io('%s.write(%s) -> %s', self, value, raw)
      return self._write(raw)

class SysfsEntryInt(SysfsEntry):
   def _readConversion(self, value):
      return int(value)

class SysfsEntryIntLinear(SysfsEntry):
   def __init__(self, parent, name, fromRange=None, toRange=None, **kwargs):
      super(SysfsEntryIntLinear, self).__init__(parent, name, **kwargs)
      self.fromRange = fromRange
      self.toRange = toRange

   def _linearConversion(self, value, fromRange, toRange):
      value -= fromRange[0]
      value *= toRange[1] - toRange[0]
      value //= fromRange[1]
      return value + toRange[0]

   def _readConversion(self, value):
      return self._linearConversion(int(value), self.fromRange, self.toRange)

   def _writeConversion(self, value):
      return str(self._linearConversion(int(value), self.toRange, self.fromRange))

class SysfsEntryFloat(SysfsEntry):
   def __init__(self, parent, name, scale=1000., **kwargs):
      super(SysfsEntryFloat, self).__init__(parent, name, **kwargs)
      self.scale = scale

   def _readConversion(self, value):
      return float(value) / self.scale

   def _writeConversion(self, value):
      return str(int(value * self.scale))

class SysfsEntryBool(SysfsEntry):
   def _readConversion(self, value):
      return bool(int(value))

   def _writeConversion(self, value):
      return str(int(value))

class SysfsEntryIntLed(SysfsEntryInt):
   def __init__(self, parent, name, **kwargs):
      def getLedPath(n):
         ledsPath = os.path.join(parent.driver.getSysfsPath(), 'leds')
         return os.path.join(ledsPath, n, 'brightness')
      super(SysfsEntryIntLed, self).__init__(parent, name, pathCallback=getLedPath,
                                             **kwargs)

class SysfsEntryCustomLed(SysfsEntryIntLed):
   def __init__(self, parent, name, value2color=None):
      self.value2color = value2color or {
         0 : LedColor.OFF,
         1 : LedColor.GREEN,
         2 : LedColor.RED,
         3 : LedColor.AMBER,
      }
      self.color2value = { v : k for k, v in self.value2color.items() }
      super(SysfsEntryCustomLed, self).__init__(parent, name)

   def _readConversion(self, value):
      return self.value2color[int(value)]

   def _writeConversion(self, value):
      return str(self.color2value[value])

class FanSysfsImpl(Fan):

   MIN_FAN_SPEED = 30
   MAX_FAN_SPEED = 100

   def __init__(self, driver, desc, maxPwm=255, led=None, faultGpio=None, **kwargs):
      self.driver = driver
      self.desc = desc
      self.fanId = desc.fanId
      self.maxPwm = maxPwm
      self.led = led
      self.lastSpeed = None
      self.pwm = SysfsEntryIntLinear(self, 'pwm%d' % self.fanId,
                                     fromRange=(0, maxPwm), toRange=(0, 100))
      self.input = SysfsEntryInt(self, 'fan%d_input' % self.fanId)
      self.airflow = SysfsEntry(self, 'fan%d_airflow' % self.fanId)
      self.fault = SysfsEntryBool(self, 'fan%d_fault' % self.fanId)
      self.present = SysfsEntryBool(self, 'fan%d_present' % self.fanId)
      self.faultGpio = faultGpio
      self.__dict__.update(kwargs)

   def getId(self):
      return self.fanId

   def getName(self):
      if self.desc.name is None:
         self.desc.renderName()
      return self.desc.name

   def getModel(self):
      return 'N/A'

   def getSpeed(self):
      return self.pwm.read()

   def getFault(self):
      if self.faultGpio is not None:
         if self.faultGpio.isActive():
            return True
      if not self.fault.exists():
         return False
      return self.fault.read()

   def getStatus(self):
      if not self.getPresence():
         return False
      return not self.getFault()

   def setSpeed(self, speed):
      if self.lastSpeed == self.MAX_FAN_SPEED and speed != self.MAX_FAN_SPEED:
         logging.debug("%s fan speed reduced from max", self.getName())
      elif self.lastSpeed != self.MAX_FAN_SPEED and speed == self.MAX_FAN_SPEED:
         logging.warning("%s fan speed set to max", self.getName())
      self.lastSpeed = speed
      return self.pwm.write(speed)

   def getRpm(self):
      if self.input.exists():
         return self.input.read()
      return None

   def getPresence(self):
      if self.present.exists():
         return self.present.read()
      return self.input.read() != 0

   def getDirection(self):
      if self.airflow.exists():
         return self.airflow.read()
      return self.desc.airflow

   def getPosition(self):
      return self.desc.position if self.desc else 'N/A'

   def getLed(self):
      return self.led

class LedSysfsImpl(Led):
   def __init__(self, driver, desc, **kwargs):
      self.driver = driver
      self.desc = desc
      self.brightness = SysfsEntryCustomLed(self, desc.name)
      self.__dict__.update(kwargs)

   def getName(self):
      return self.desc.name

   def getColor(self):
      return self.brightness.read()

   def setColor(self, color):
      return self.brightness.write(color)

   def isStatusLed(self):
      return 'sfp' in self.desc.name

class LedRgbSysfsImpl(Led):
   def __init__(self, driver, desc, prefix, **kwargs):
      self.driver = driver
      self.desc = desc
      self.red = SysfsEntryIntLed(self, '%s:red:%s' % (prefix, desc.name))
      self.green = SysfsEntryIntLed(self, '%s:green:%s' % (prefix, desc.name))
      self.blue = SysfsEntryIntLed(self, '%s:blue:%s' % (prefix, desc.name))
      self.leds = [self.red, self.green, self.blue]
      self.color2values = {
         LedColor.OFF: (0, 0, 0),
         LedColor.RED: (1, 0, 0),
         LedColor.GREEN: (0, 1, 0),
         LedColor.BLUE: (0, 0, 1),
         LedColor.AMBER: (1, 1, 0),
      }
      self.values2color = {v : c for c, v in self.color2values.items()}

   def getName(self):
      return self.desc.name

   def getColor(self):
      values = tuple(led.read() if led.exists() else 0 for led in self.leds)
      return self.values2color.get(values)

   def setColor(self, color):
      values = self.color2values.get(color, (0, 0, 0))
      for led, value in zip(self.leds, values):
         if led.exists():
            led.write(value)
      return True

   def isStatusLed(self):
      return 'sfp' in self.desc.name

class TempSysfsImpl(Temp):
   def __init__(self, driver, desc, **kwargs):
      self.tempId = desc.diode + 1
      self.driver = driver
      self.desc = desc
      self.reportHwThresh = Config().report_hw_thresholds
      self.__dict__.update(**kwargs)
      self.input = SysfsEntryFloat(self, 'temp%d_input' % self.tempId)
      self.max = SysfsEntryFloat(self, 'temp%d_max' % self.tempId)
      self.crit = SysfsEntryFloat(self, 'temp%d_crit' % self.tempId)
      self.min = SysfsEntryFloat(self, 'temp%d_min' % self.tempId)
      self.lcrit = SysfsEntryFloat(self, 'temp%d_lcrit' % self.tempId)
      self.fault = SysfsEntryBool(self, 'temp%d_fault' % self.tempId)
      # XXX: override the label ?

   def getName(self):
      return self.desc.name

   def getDesc(self):
      return self.desc

   def getPresence(self):
      return True

   def getModel(self):
      return "N/A"

   def getStatus(self):
      if self.fault.exists():
         if self.fault.read():
            return False
      # TODO: maintain some state to report failed sensors
      #       e.g: sensor misreporting a few times
      return True

   def getTemperature(self):
      return self.input.read()

   def getLowThreshold(self):
      if self.reportHwThresh and self.min.exists():
         return self.min.read()
      return self.desc.low

   def setLowThreshold(self, value):
      if self.min.exists():
         self.min.write(value)
         return True
      return False

   def getHighThreshold(self):
      if self.reportHwThresh and self.max.exists():
         return self.max.read()
      return self.desc.overheat

   def setHighThreshold(self, value):
      if self.max.exists():
         self.max.write(value)
         return True
      return False

   def getHighCriticalThreshold(self):
      if self.reportHwThresh and self.crit.exists():
         return self.crit.read()
      return self.desc.critical

   def setHighCriticalThreshold(self, value):
      if self.crit.exists():
         self.crit.write(value)
         return True
      return False

   def getLowCriticalThreshold(self):
      if self.reportHwThresh and self.lcrit.exists():
         return self.lcrit.read()
      return self.desc.lcritical

   def setLowCriticalThreshold(self, value):
      if self.lcrit.exists():
         self.lcrit.write(value)
         return True
      return False

   def refreshHardwareThresholds(self):
      self.setLowThreshold(self.desc.low)
      self.setLowCriticalThreshold(self.desc.lcritical)
      self.setHighThreshold(self.desc.overheat)
      self.setHighCriticalThreshold(self.desc.critical)

class ResetSysfsImpl(Reset):
   def __init__(self, driver, desc, **kwargs):
      self.driver = driver
      self.addr = desc.addr
      self.bit = desc.bit
      self.name = desc.name
      def getResetPath(name):
         return os.path.join(driver.getSysfsPath(), name)
      self.reset = SysfsEntryBool(self, desc.name, pathCallback=getResetPath)
      self.__dict__.update(**kwargs)

   def getName(self):
      return self.name

   def read(self):
      return self.reset.read()

   def resetIn(self):
      return self.reset.write(True)

   def resetOut(self):
      return self.reset.write(False)

class GpioSysfsImpl(Gpio):
   def __init__(self, driver, desc, hwActiveLow=False, **kwargs):
      self.driver = driver
      self.addr = desc.addr
      self.bit = desc.bit
      self.name = desc.name
      self.ro = desc.ro
      self.activeLow = desc.activeLow
      self.hwActiveLow = hwActiveLow
      def getGpioPath(name):
         return os.path.join(self.driver.getSysfsPath(), name)
      self.gpio = SysfsEntryBool(self, self.name, pathCallback=getGpioPath)
      self.__dict__.update(**kwargs)

   def getName(self):
      return self.name

   def getAddr(self):
      return self.addr

   def getPath(self):
      return self.gpio.entryPath

   def getBit(self):
      return self.bit

   def isRo(self):
      return self.ro

   def isActiveLow(self):
      return False if self.hwActiveLow else self.activeLow

   def getRawValue(self):
      return self.gpio.read()

   def setRawValue(self, value):
      self.gpio.write(value)

   def _activeValue(self):
      return 0 if self.isActiveLow() else 1

   def isActive(self):
      if utils.inSimulation():
         return True
      return self.getRawValue() == self._activeValue()

   def setActive(self, value):
      self.setRawValue(not value if self.isActiveLow() else value)
