import datetime

from arista.core.liquid import LeakSensorType, LeakDetectionInterface
from arista.descs.liquid import LiquidCoolingDesc
from arista.core.log import getLogger

try:
   from sonic_platform_base.leakage_sensor_test_base import (
      LeakageSensorTestBase,
   )
   from sonic_platform_base.liquid_cooling_base import (
      LeakageSensorBase,
      LeakSensorProfileBase,
      LeakSeverity,
      LiquidCoolingBase,
   )
except ImportError as e:
   raise ImportError("%s - required module not found" % e) from e

logging = getLogger(__name__)


class LeakageSensor(LeakageSensorBase):

   MIN_UPDATE_INTERVAL = datetime.timedelta(milliseconds=500)

   def __init__(self, interface: LeakDetectionInterface, ropeType: LeakSensorType,
                ropeNum: int, profile: 'LeakageSensorProfile', *,
                name: str|None = None, location: str|None = None):
      name = name or f'{ropeType.value}{ropeNum}'
      location = location or 'unknown'

      super().__init__(name, type=profile.get_type(), location=location,
                       severity=LeakageSensor._sensorTypeToSeverity(ropeType))

      self.interface = interface
      self.ropeType = ropeType
      self.ropeNum = ropeNum
      self.profile = profile
      self.fixed_severity = self._sensorTypeToSeverity(ropeType)
      self.leaking = False
      self.leak_sensor_ok = True
      self.test_leak = False

      self.last_update_time = datetime.datetime.min

   @staticmethod
   def _sensorTypeToSeverity(ropeType: LeakSensorType) -> LeakSeverity:
      if ropeType == LeakSensorType.ROPE_MINOR:
         return LeakSeverity.MINOR

      return LeakSeverity.CRITICAL

   def _updateStatus(self, force: bool = False) -> None:
      now = datetime.datetime.now()
      time_since_update = now - self.last_update_time
      if not force and time_since_update < self.MIN_UPDATE_INTERVAL:
         return

      # The Changed bit only flags transitions, so on the first call we must
      # poll unconditionally to pick up state that was already set at boot
      # (e.g. a leak that persisted across a SONiC restart).
      firstCall = self.last_update_time == datetime.datetime.min
      test_leak = self.interface.isRopeLeakForced(self.ropeType, self.ropeNum)
      changed = self.interface.hasRopeStatusChanged(self.ropeType, self.ropeNum)
      if force or firstCall or changed or test_leak != self.test_leak:
         self.leaking = self.interface.isRopeLeakDetected(self.ropeType,
                                                          self.ropeNum)
         self.leak_sensor_ok = not self.interface.isRopeBroken(self.ropeType,
                                                               self.ropeNum)
         self.interface.clearRopeStatusChanged(self.ropeType, self.ropeNum)

      self.test_leak = test_leak
      self.last_update_time = now

   def refresh_status(self) -> None:
      """Refresh this sensor's cached hardware state immediately."""
      self._updateStatus(force=True)

   def is_leak(self) -> bool:
      self._updateStatus()
      return super().is_leak()

   def is_leak_sensor_ok(self) -> bool:
      self._updateStatus()
      return super().is_leak_sensor_ok()

   def is_test_leak(self) -> bool:
      self._updateStatus()
      return super().is_test_leak()

   def get_leak_severity(self) -> LeakSeverity|None:
      self._updateStatus()
      return super().get_leak_severity()

   def get_leak_profile(self) -> 'LeakageSensorProfile':
      return self.profile


class AristaLeakageSensorTest(LeakageSensorTestBase):
   """Leak-test API backed by each rope's hardware force-leak bit."""

   def __init__(self, interface: LeakDetectionInterface, sensors,
                ensureMitigationDisabled):
      super().__init__()
      self.interface = interface
      self.sensors = {}
      self.ensureMitigationDisabled = ensureMitigationDisabled

      for sensor in sensors:
         name = sensor.get_name()
         if name in self.sensors:
            raise ValueError(f"duplicate leakage sensor name: {name}")
         self.sensors[name] = sensor

   def is_leak_test_supported(self) -> bool:
      return bool(self.sensors)

   def set_test_leak(self, sensor_name: str, enable: bool,
                     severity: LeakSeverity|None = LeakSeverity.MINOR) -> bool:
      """Set a rope's hardware leak-test override.

      While the force bit is enabled, hardware leak status cannot distinguish
      the injected test state from a real leak. Clearing it refreshes the
      sensor from the underlying hardware state.
      """
      sensor = self.sensors.get(sensor_name)
      if sensor is None:
         return False

      if enable and severity is not None and severity != sensor.fixed_severity:
         requested = getattr(severity, 'value', None)
         if requested is None:
            requested = repr(severity)
         raise ValueError(
            f"sensor {sensor_name} has fixed severity "
            f"{sensor.fixed_severity.value}; cannot inject {requested}")

      try:
         if enable and not self.ensureMitigationDisabled():
            logging.error(
               "refusing leak test for %s: hardware leak mitigation is enabled",
               sensor_name)
            return False

         self.interface.setRopeLeakForced(
            sensor.ropeType, sensor.ropeNum, bool(enable))
         enabled = self.interface.isRopeLeakForced(
            sensor.ropeType, sensor.ropeNum)
         sensor.refresh_status()
      except Exception: # pylint: disable=broad-except
         logging.exception("failed to set test leak state for %s", sensor_name)
         return False

      success = enabled == bool(enable)
      logging.info("test leak %s for sensor %s (severity=%s, success=%s)",
                   "enabled" if enable else "disabled", sensor_name,
                   sensor.fixed_severity.value if enable else "ignored",
                   success)
      return success

   def is_test_leak_enabled(self, sensor_name: str) -> bool:
      sensor = self.sensors.get(sensor_name)
      if sensor is None:
         return False
      try:
         return self.interface.isRopeLeakForced(sensor.ropeType, sensor.ropeNum)
      except Exception: # pylint: disable=broad-except
         logging.exception("failed to read test leak state for %s", sensor_name)
         return False

   def clear_test_leaks(self) -> bool:
      # Evaluate every sensor even after a failed clear so one bad register
      # does not leave other injections armed.
      results = [self.set_test_leak(name, False)
                 for name in self.sensors]
      return all(results)


class LeakageSensorProfile(LeakSensorProfileBase):
   def get_type(self) -> str:
      return "rope"

   def get_leak_max_minor_duration_sec(self) -> int:
      # TODO: confirm time with hardware team
      return 60

class LiquidCooling(LiquidCoolingBase):

   def __init__(self, desc: LiquidCoolingDesc):
      sensorDescs = desc.sensors
      self.interface = desc.interface(desc.component)

      profile = LeakageSensorProfile()
      sensors = [LeakageSensor(self.interface, s.sensorType, s.addr, profile,
                               name=s.name, location=s.location)
                 for s in sensorDescs]

      super().__init__(len(sensors), sensors, profiles=[profile])

      try:
         mitigationDisabled = \
            self.interface.ensureLeakTriggeredMitigationDisabled()
      except Exception: # pylint: disable=broad-except
         logging.exception("failed to disable hardware leak mitigation")
         mitigationDisabled = False

      self._leak_test_supported = bool(self.leakage_sensors) and \
         mitigationDisabled

      if not self.leakage_sensors:
         logging.info("leak test injection unavailable: no leakage sensors")
      elif not mitigationDisabled:
         logging.error(
            "leak test injection unavailable: hardware leak mitigation "
            "could not be verified disabled")

      self._leak_sensor_test = AristaLeakageSensorTest(
         self.interface, self.leakage_sensors,
         self.interface.ensureLeakTriggeredMitigationDisabled)

   def get_name(self) -> str:
      return "Liquid Cooling"

   def get_presence(self) -> bool:
      return True

   def get_model(self) -> str:
      return "N/A"

   def get_serial(self) -> str:
      return "N/A"

   def get_revision(self) -> str:
      return "N/A"

   def get_status(self) -> bool:
      return all(s.is_leak_sensor_ok() for s in self.leakage_sensors)

   def get_position_in_parent(self) -> int:
      return -1

   def is_replaceable(self) -> bool:
      return False

   def get_leak_sensor_test(self) -> AristaLeakageSensorTest|None:
      if not self._leak_test_supported:
         return None
      return self._leak_sensor_test
