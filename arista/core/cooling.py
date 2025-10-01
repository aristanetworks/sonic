import copy
import csv
import os
from dataclasses import dataclass

from ..libs.python import monotonicRaw

from .config import Config
from .log import getLogger
from .utils import inSimulation

logging = getLogger(__name__)

@dataclass
class CoolingConfig:
   minSpeed: float = 30

   def update(self):
      if Config().cooling_min_speed is not None:
         self.minSpeed = Config().cooling_min_speed

class Airflow(object):
   UNKNOWN = 'unknown'
   EXHAUST = 'exhaust'
   INTAKE = 'intake'

class HistoricalData(object):
   def __init__(self, name):
      self.name = name
      self.maxlen = max(3, Config().cooling_data_points)
      self.set = []
      self.get = []

   def getValue(self, now, value):
      self.get.append((now, value))
      if len(self.get) > self.maxlen:
         self.get = self.get[1:]
      return value

   def setValue(self, now, value):
      self.set.append((now, value))
      if len(self.set) > self.maxlen:
         self.set = self.set[1:]
      return value

   @property
   def lastSet(self):
      if not self.set:
         return None
      return self.set[-1][1]

   @property
   def lastGet(self):
      if not self.get:
         return None
      return self.get[-1][1]

   def getLast(self, num):
      try:
         return self.get[-num][1]
      except IndexError:
         return None

   @property
   def data(self):
      return {
         'name': self.name,
         'get': self.get,
         'set': self.set,
      }

class CoolingObject(object):
   def __init__(self, name, inv=None):
      super().__init__()
      self.name = name
      self.data = HistoricalData(name)
      self.inv = inv
      self._initialized = False

   def __str__(self):
      return '%s(%s)' % (self.__class__.__name__, self.name)

   def getLast(self, num):
      return self.data.getLast(num)

   def dump(self):
      return self.data.data

class CoolingFanBase(CoolingObject):
   def __init__(self, *args, **kwargs):
      super().__init__(*args, **kwargs)

   @property
   def speed(self):
      return self.data.lastGet

   @speed.setter
   def speed(self, value):
      return self.data.getValue(monotonicRaw(), value)

   @property
   def current(self):
      return self.data.lastGet

   @property
   def last(self):
      return self.data.get[-2][1]

   def setSpeed(self, value):
      assert self.inv is not None or self.api is not None
      if self.inv is not None:
         self.inv.setSpeed(value)
      else:
         self.api.set_speed(value)

   def set(self, now, value):
      try:
         self.setSpeed(value)
         return self.data.setValue(now, value)
      except Exception: # pylint: disable=broad-except
         logging.exception('%s failed to write speed', self)
         return None

class CoolingThermalBase(CoolingObject):
   def __init__(self, *args, **kwargs):
      super().__init__(*args, **kwargs)
      self.overheat = None
      self.critical = None

   @property
   def temperature(self):
      return self.data.lastGet

   @temperature.setter
   def temperature(self, value):
      return self.data.getValue(monotonicRaw(), value)

   @property
   def target(self):
      if self.inv is not None:
         return self.inv.getDesc().target
      return Config().cooling_target_factor * self.overheat

   def valid(self):
      return self.temperature is not None and \
             self.overheat is not None and \
             self.critical is not None

class ThermalInfo(object):
   def __init__(self, thermal, value, target, overheat):
      self.thermal = thermal
      self.value = value
      self.target = target
      self.overheat = overheat
      self.delta = value - target
      self.deltap = self.delta / (overheat - target)

   def __str__(self):
      kwargs = ', '.join('%s=%s' % (k, str(v)) for k, v in self.__dict__.items())
      return '%s(%s)' % (self.__class__.__name__, kwargs)

class ThermalInfos(object):
   def __init__(self, targetOffset):
      self.overheat = False
      self.targetOffset = targetOffset
      self.infos = []

   def process(self, thermal):
      if not thermal.valid():
         return

      maxTemp = min(thermal.overheat, thermal.critical)
      if not int(thermal.target) or not int(maxTemp):
         return

      value = thermal.temperature

      if value > maxTemp:
         logging.debug('%s: temp is above overheat threshold', thermal)
         self.overheat = True

      target = thermal.target + self.targetOffset
      info = ThermalInfo(thermal, value, target, maxTemp)
      logging.debug('%s', info)
      self.infos.append(info)

   def choose(self):
      if not self.infos:
         return None
      selected = self.infos[0]
      for info in self.infos[1:]:
         if info.deltap > selected.deltap:
            selected = info
      return selected

class CoolingZone(object):

   MAX_SPEED = 100

   def __init__(self, algo, name):
      self.algo = algo
      self.name = name
      self.maxDecrease = Config().cooling_max_decrease
      self.maxIncrease = Config().cooling_max_increase
      self.minSpeed = algo.config.minSpeed
      self.targetOffset = Config().cooling_target_offset
      self.speed = HistoricalData('target')
      self.fans = None
      self.thermals = None
      self.initialized = False

   def __str__(self):
      return '%s(%s)' % (self.__class__.__name__, self.name)

   def load(self, fans=None, thermals=None):
      self.fans = fans or {}
      self.thermals = thermals or {}
      self.initialized = True

   def update(self):
      for f in self.fans.values():
         f.update()
      for t in self.thermals.values():
         t.update()

   @property
   def lastSpeed(self):
      return self.speed.lastSet

   def computeFanSpeed(self, lastSpeed, infos):
      if infos.overheat:
         # Run the fans at 100% if one sensor is in overheat state
         return self.MAX_SPEED

      # Select the most critical sensor in the system
      info = infos.choose()
      if info is None:
         # No sensor found, run at 100%
         return self.MAX_SPEED

      logging.debug('%s: using %s to set fan speed', self, info.thermal)

      # Skip any fan speed adjustment if the temperature is between some
      # percentage of target to overheat delta
      under = Config().cooling_adjust_under
      over = Config().cooling_adjust_over
      if under < info.deltap * 100. < over:
         return lastSpeed

      if info.delta < 0:
         speedDelta = max(self.maxDecrease * info.deltap, -self.maxDecrease)
      else:
         speedDelta = min(self.maxIncrease * info.deltap, self.maxIncrease)

      # adjust speed delta based on elapsed time
      speedDelta = self.scaleOnElapsed(speedDelta)

      # Enforce fan speed limits
      speed = max(lastSpeed + speedDelta, self.minSpeed)
      speed = min(speed, self.MAX_SPEED)

      return speed

   def scaleOnElapsed(self, value):
      factor = min(self.algo.elapsed / self.algo.INTERVAL, 1.0)
      return value * factor

   def readLastSpeed(self):
      lastSpeed = self.lastSpeed

      # Read the current fan speed to have it stored in the data
      for fan in self.fans.values():
         currentSpeed = fan.speed
         if lastSpeed is None: # useful when no speed has been set by the algo
            logging.debug('%s: detected last speed %d', self, currentSpeed)
            lastSpeed = currentSpeed

      if lastSpeed is None:
         logging.debug('%s: could not find last speed, assuming max', self)
         lastSpeed = self.MAX_SPEED

      return lastSpeed

   def run(self, fans=None, thermals=None, update=False):
      if not self.initialized:
         self.load(fans=fans, thermals=thermals)
      if update:
         self.update()

      lastSpeed = self.readLastSpeed()

      infos = ThermalInfos(self.targetOffset)
      for thermal in self.thermals.values():
         infos.process(thermal)

      desiredSpeed = self.computeFanSpeed(lastSpeed, infos)

      logging.debug('%s: fan speed selected is %.3f', self, desiredSpeed)
      self.speed.setValue(self.algo.now, desiredSpeed)

      # Set new fan speed
      for fan in self.fans.values():
         fan.set(self.algo.now, desiredSpeed)

   def export(self, path):
      path = os.path.join(path, '%s.cooling.csv' % self.name)
      with open(path, 'a', encoding='utf8', newline='') as f:
         writer = csv.writer(f, dialect='unix')
         for col in (self.fans, self.thermals):
            for obj in col.values():
               for op in ['get', 'set']:
                  entry = getattr(obj.data, op, None)
                  if not entry:
                     continue
                  ts, value = entry[-1]
                  writer.writerow((str(ts), obj.name, op, str(value)))

class CoolingAlgorithm(object):

   INTERVAL = 60.

   def __init__(self, platform):
      self.platform = platform
      self.config = None
      self.previous = None
      self.now = None
      self.elapsed = None
      self.zones = []
      self.load()

   def __str__(self):
      return '%s()' % self.__class__.__name__

   def load(self):
      self.config = copy.deepcopy(self.platform.COOLING)
      self.config.update()
      # NOTE: for now only one zone
      self.zones.append(CoolingZone(self, 'System'))

   def export(self, path):
      if inSimulation():
         return
      for zone in self.zones:
         zone.export(path)

   def run(self, elapsed=None, fans=None, thermals=None, update=False):
      self.previous = self.now
      self.now = monotonicRaw()
      if self.previous is None:
         self.previous = self.now - self.INTERVAL
      self.elapsed = elapsed or self.now - self.previous

      logging.debug('%s: running algorithm (elapsed %.4fs)', self, self.elapsed)
      for zone in self.zones:
         zone.run(fans=fans, thermals=thermals, update=update)
      logging.debug('%s: algorithm took %.4fs to run', self,
                    monotonicRaw() - self.now)

      if Config().cooling_export_path:
         self.export(Config().cooling_export_path)
