import datetime

from arista.core.liquid import LeakSensorType, LeakDetectionInterface
from arista.descs.liquid import LiquidCoolingDesc

try:
   from sonic_platform_base.liquid_cooling_base import (
      LeakageSensorBase,
      LeakSensorProfileBase,
      LeakSeverity,
      LiquidCoolingBase,
   )
except ImportError as e:
   raise ImportError("%s - required module not found" % e) from e


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
      self.leaking = False
      self.leak_sensor_ok = True

      self.last_update_time = datetime.datetime.min

   @staticmethod
   def _sensorTypeToSeverity(ropeType: LeakSensorType) -> LeakSeverity:
      if ropeType == LeakSensorType.ROPE_MINOR:
         return LeakSeverity.MINOR

      return LeakSeverity.CRITICAL

   def _updateStatus(self) -> None:
      now = datetime.datetime.now()
      time_since_update = now - self.last_update_time
      if time_since_update < self.MIN_UPDATE_INTERVAL:
         return

      # The Changed bit only flags transitions, so on the first call we must
      # poll unconditionally to pick up state that was already set at boot
      # (e.g. a leak that persisted across a SONiC restart).
      firstCall = self.last_update_time == datetime.datetime.min
      if firstCall or self.interface.hasRopeStatusChanged(self.ropeType,
                                                          self.ropeNum):
         self.leaking = self.interface.isRopeLeakDetected(self.ropeType,
                                                          self.ropeNum)
         self.leak_sensor_ok = not self.interface.isRopeBroken(self.ropeType,
                                                               self.ropeNum)
         self.interface.clearRopeStatusChanged(self.ropeType, self.ropeNum)

      self.last_update_time = now

   def is_leak(self) -> bool:
      self._updateStatus()
      return super().is_leak()

   def is_leak_sensor_ok(self) -> bool:
      self._updateStatus()
      return super().is_leak_sensor_ok()

   def get_leak_profile(self) -> 'LeakageSensorProfile':
      return self.profile


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
