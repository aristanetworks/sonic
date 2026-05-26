import copy
import csv
import os
from dataclasses import dataclass

from ..libs.python import monotonicRaw

from .config import Config
from .log import getLogger
from .thermal_policy_config import ThermalPolicyConfig
from .utils import inSimulation

logging = getLogger(__name__)

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
      self.config = None
      self.configInitialized = False
      self.name = name
      self.data = HistoricalData(name)
      self.inv = inv
      self.zone = None

   def __str__(self):
      return '%s(%s)' % (self.__class__.__name__, self.name)

   def getLast(self, num):
      return self.data.getLast(num)

   def dump(self):
      return self.data.data

   def assignZone(self, zone):
      self.zone = zone

   def loadConfig(self, config):
      pass

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

   def loadConfig(self, config):
      if not self.configInitialized:
         self.config = config.thermalPolicyConfig.getFanConfig(self.name)
         self.assignZone(self.config['zone'])
         self.configInitialized = True

class CoolingPwmBase(CoolingObject):
   def __init__(self, *args, **kwargs):
      super().__init__(*args, **kwargs)
      self.cooling_logic = None
      self.last_update_time = None
      self.device_name = None

   @property
   def pwm(self):
      return self.data.lastGet

   @pwm.setter
   def pwm(self, value):
      return self.data.getValue(monotonicRaw(), value)

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

   def loadConfig(self, config):
      if not self.configInitialized:
         self.config = config.thermalPolicyConfig.getThermalConfig(self.name)
         self.assignZone(self.config['zone'])
         logging.debug('%s: kp=%s ki=%s kd=%s zone=%s',
                       self.name, self.config['kp'], self.config['ki'],
                       self.config['kd'], self.zone)
         self.configInitialized = True

class ThermalInfo(object):
   def __init__(self, thermal, value, target, overheat):
      self.thermal = thermal
      self.value = value
      self.target = target
      self.overheat = overheat
      self.delta = value - target
      self.deltap = self.delta * 0.1

   def __str__(self):
      kwargs = ', '.join('%s=%s' % (k, str(v)) for k, v in self.__dict__.items())
      return '%s(%s)' % (self.__class__.__name__, kwargs)

class CoolingPwmInfo:
   def __init__(self, source, pwm, device_name=None):
      self.source = source
      self.pwm = pwm
      self.device_name = device_name

   def __str__(self):
      return (f'{self.__class__.__name__}(source={self.source}, '
              f'device_name={self.device_name}, pwm={self.pwm})')

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

class CoolingLogic:
   def __init__(self, zone):
      self.zone = zone

   @property
   def config(self):
      return self.zone.algo.config

   def computePwm(self, lastPwm):
      raise NotImplementedError

class CoolingLogicLegacy(CoolingLogic):
   NAME = 'legacy'

   def __init__(self, zone):
      super().__init__(zone)
      self.maxDecrease = Config().cooling_max_decrease
      self.maxIncrease = Config().cooling_max_increase

   def scaleOnElapsed(self, value):
      factor = min(self.zone.algo.elapsed / self.zone.algo.INTERVAL, 1.0)
      return value * factor

   def computePwm(self, lastPwm):
      infos = ThermalInfos(self.config.targetOffset)
      for thermal in self.zone.thermals.values():
         infos.process(thermal)

      # Select the most critical sensor in the system
      info = infos.choose()
      if info is None:
         # No sensor found, run at 100%
         return self.config.maxSpeed

      logging.debug('%s: using %s to set fan speed', self, info.thermal)

      # Skip any fan speed adjustment if the temperature change is between some
      # configurable values
      if -self.config.negHyst < info.delta < self.config.posHyst:
         return lastPwm

      if info.delta < 0:
         pwmDelta = max(self.maxDecrease * info.deltap, -self.maxDecrease)
      else:
         pwmDelta = min(self.maxIncrease * info.deltap, self.maxIncrease)

      # adjust speed delta based on elapsed time
      pwmDelta = self.scaleOnElapsed(pwmDelta)

      # Enforce fan speed limits
      pwm = max(lastPwm + pwmDelta, self.config.minSpeed)
      pwm = min(pwm, self.config.maxSpeed)

      return pwm

class CoolingLogicIncPid(CoolingLogic):
   NAME = 'incpid'

   def computePwmForThermal(self, lastPwm, thermal):
      temperature = thermal.temperature
      lastTemperature = thermal.getLast(2) or temperature
      llastTemperature = thermal.getLast(3) or lastTemperature
      target = thermal.target + self.config.targetOffset
      minVal = target - self.config.negHyst
      maxVal = target + self.config.posHyst

      kp, ki, kd = thermal.config['kp'], thermal.config['ki'], thermal.config['kd']

      pwmDelta = 0
      if temperature < minVal or temperature > maxVal:
         pwmDelta = kp * (temperature - lastTemperature) + \
                    ki * (temperature - target) + \
                    kd * (temperature - 2 * lastTemperature +
                          llastTemperature)

      logging.debug('%s temperature=%f target=%f pwmDelta=%f',
                    thermal, temperature, target, pwmDelta)

      return lastPwm + pwmDelta

   def computePwm(self, lastPwm):
      pwms = [self.computePwmForThermal(lastPwm, thermal)
              for thermal in self.zone.thermals.values() if thermal.valid()]
      if not pwms:
         return self.config.maxSpeed
      return min(max(*pwms, self.config.minSpeed), self.config.maxSpeed)

class ThermalClassicPid:
   def __init__(self, thermal):
      self.thermal = thermal

      if thermal.config['ki'] != 0:
         logging.warning('%s ki!=0, integral is currently not implemented', thermal)

      self.resolution = 1
      self.lambda_ = 0.3

      self.p = 0
      self.i = 0
      self.d = 0
      self.value = 0

   def update(self):
      curTs, temperature = self.thermal.data.get[-1]
      if len(self.thermal.data.get) < 2:
         lastTs = curTs
         lastTemperature = temperature
      else:
         lastTs, lastTemperature = self.thermal.data.get[-2]

      delta = abs(temperature - lastTemperature)
      self.resolution = min(self.resolution, delta)
      if self.resolution >= 1:
         self.lambda_ = 0.08
      elif self.resolution >= 0.5:
         self.lambda_ = 0.1
      elif self.resolution >= 0.25:
         self.lambda_ = 0.15
      else:
         self.lambda_ = 0.3

      err = self.thermal.target - temperature
      if lastTs == curTs:
         # First reading, initialise P to current error
         self.p = err
      else:
         lastP = self.p
         self.p = (1 - self.lambda_) * self.p + self.lambda_ * err

         d = (self.p - lastP) / (curTs - lastTs)
         self.d = (1 - self.lambda_) * self.d + self.lambda_ * d

      value = 0
      for term in 'p', 'i', 'd':
         tunedVal = self.thermal.config[f'k{term}'] * getattr(self, term)
         value += tunedVal

      self.value = value

class CoolingLogicClassicPid(CoolingLogic):
   NAME = 'classicpid'

   def __init__(self, zone):
      super().__init__(zone)
      self.thermalPids = {}
      self.targetRpm = HistoricalData('targetRpm')

   def computePwm(self, lastPwm):
      pids = []
      seen = set()
      for thermal in self.zone.thermals.values():
         if not thermal.valid() or thermal.config['kp'] + thermal.config['kd'] == 0:
            continue

         thermalPid = self.thermalPids.get(thermal)
         if thermalPid is None:
            self.thermalPids[thermal] = thermalPid = ThermalClassicPid(thermal)

         thermalPid.update()
         pids.append(thermalPid.value)
         seen.add(thermal)
      for thermal in self.zone.thermals.values():
         if thermal not in seen and thermal in self.thermalPids:
            # thermal went away, clear its PID state
            self.thermalPids.pop(thermal)

      if not pids:
         return self.config.maxSpeed

      worstPid = min(pids)
      newRpm = (self.targetRpm.lastSet or self.config.maxSpeed) - worstPid
      if newRpm < self.config.minSpeed:
         newRpm = self.config.minSpeed
      elif newRpm > self.config.maxSpeed:
         newRpm = self.config.maxSpeed
      self.targetRpm.setValue(self.zone.algo.now, newRpm)

      pwm = (self.config.rpmSlope * newRpm) + self.config.rpmOffset
      return pwm

@dataclass
class CoolingConfig:

   minSpeed: float = 30
   maxSpeed: float = 100
   targetOffset: float = 0
   logic: CoolingLogic = CoolingLogicLegacy
   kp: float = 0.075
   ki: float = 1
   kd: float = 10
   negHyst: float = 1
   posHyst: float = 1
   rpmSlope: float = 1
   rpmOffset: float = 0
   profile: str = 'default'
   thermalPolicyConfig: ThermalPolicyConfig = None
   defaultZone: str = 'default'
   asicViaDb: bool = False

   def loadPolicyConfig(self, policyConfig):
      self.thermalPolicyConfig = ThermalPolicyConfig(self, policyConfig)

   def update(self):
      for kgc, kcc in [
            ('cooling_min_speed', 'minSpeed'),
            ('cooling_profile', 'profile'),
            ('cooling_target_offset', 'targetOffset'),
            ('cooling_kp', 'kp'),
            ('cooling_ki', 'ki'),
            ('cooling_kd', 'kd'),
            ('cooling_rpm_slope', 'rpmSlope'),
            ('cooling_rpm_offset', 'rpmOffset'),
            ('cooling_hysteresis_negative', 'negHyst'),
            ('cooling_hysteresis_positive', 'posHyst'),
            ('cooling_asic_via_db', 'asicViaDb'),
         ]:
         if value := getattr(Config(), kgc, None):
            # TODO: ensure type is correct or convert
            setattr(self, kcc, value)

class CoolingZone(object):

   MAX_SPEED = 100

   def __init__(self, algo, name, logicCls):
      self.algo = algo
      self.name = name
      self.logic = logicCls(self)
      self.speed = HistoricalData('target')
      self.fans = None
      self.thermals = None
      self._pwm_infos = None
      self.initialized = False

   def __str__(self):
      return '%s(%s)' % (self.__class__.__name__, self.name)

   def load(self, fans=None, thermals=None):
      self._pwm_infos = {}
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

   def computeFinalPwm(self, extraPwms):
      lastSpeed = self.readLastSpeed()
      desiredSpeed = self.logic.computePwm(lastSpeed)

      if extraPwms:
         # Log each device PWM individually (similar to ThermalInfo logging)
         for source, pwm_obj in extraPwms.items():
            pwmValue = pwm_obj.pwm
            deviceName = pwm_obj.device_name

            pwmInfo = self._pwm_infos.get(source)
            if pwmInfo is None:
               pwmInfo = CoolingPwmInfo(source, pwmValue, deviceName)
               self._pwm_infos[source] = pwmInfo
            else:
               pwmInfo.pwm = pwmValue
               pwmInfo.device_name = deviceName
            logging.debug('%s', pwmInfo)

         maxExtraPwm = max(pwm_obj.pwm for pwm_obj in extraPwms.values())
         logging.debug('%s: max extra PWM from modules: %.3f (from %s)',
                       self, maxExtraPwm,
                       {v.device_name: v.pwm for k, v in extraPwms.items()})
         if maxExtraPwm > desiredSpeed:
            logging.debug('%s: using extra PWM %.3f instead of computed %.3f',
                          self, maxExtraPwm, desiredSpeed)
            desiredSpeed = maxExtraPwm

      logging.debug('%s: fan speed selected is %.3f from %.3f (%+.3f)', self,
                    desiredSpeed, lastSpeed, desiredSpeed - lastSpeed)
      return desiredSpeed

   def run(self, fans=None, thermals=None, update=False, extraPwms=None):
      if not self.initialized:
         self.load(fans=fans, thermals=thermals)
      if update:
         self.update()

      desiredSpeed = self.computeFinalPwm(extraPwms)
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
   LOGICS = {l.NAME: l for l in [
      CoolingLogicLegacy,
      CoolingLogicIncPid,
      CoolingLogicClassicPid,
   ]}

   def __init__(self, platform):
      self.platform = platform
      self.config = None
      self.previous = None
      self.now = None
      self.elapsed = None
      self.initialized = False
      self.zones = {}

   def __str__(self):
      return '%s()' % self.__class__.__name__

   def loadZones(self):
      zones = self.config.thermalPolicyConfig.getZoneLogicMap()
      for zoneName, logic in zones.items():
         logicCls = self.LOGICS.get(logic, CoolingLogicLegacy)
         zone = CoolingZone(self, zoneName, logicCls)
         logging.debug('%s: creating zone %s with logic %s', self, zone, logic)
         self.zones[zoneName] = zone

   def load(self, policyConfig=None):
      if not self.initialized:
         self.initialized = True
         self.config = copy.deepcopy(self.platform.COOLING)
         self.config.update()
         self.config.loadPolicyConfig(policyConfig)
         logging.debug('%s: with config %s', self, self.config)
         self.loadZones()

   def export(self, path):
      if inSimulation():
         return
      for zone in self.zones.values():
         zone.export(path)

   def run(self, elapsed=None, fans=None, thermals=None, update=False,
           extraPwms=None):
      self.previous = self.now
      self.now = monotonicRaw()
      if self.previous is None:
         self.previous = self.now - self.INTERVAL
      self.elapsed = elapsed or self.now - self.previous
      logging.debug('%s: running algorithm (elapsed %.4fs)', self, self.elapsed)
      fans = fans or {}
      thermals = thermals or {}
      for thermal in thermals.values():
         thermal.loadConfig(self.config)
      for fan in fans.values():
         fan.loadConfig(self.config)

      for zoneName, zone in self.zones.items():
         zoneFans = {n: f for n, f in fans.items() if f.zone == zoneName}
         zoneThermals = {n: t for n, t in thermals.items()
                        if t.zone == zoneName}
         zone.run(fans=zoneFans,
                  thermals=zoneThermals,
                  update=update,
                  extraPwms=extraPwms)
      logging.debug('%s: algorithm took %.4fs to run', self,
                    monotonicRaw() - self.now)

      if Config().cooling_export_path:
         self.export(Config().cooling_export_path)
