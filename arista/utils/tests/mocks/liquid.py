from enum import Enum

class MockLeakSeverity(Enum):
   MINOR = "MINOR"
   CRITICAL = "CRITICAL"

class MockLeakageSensorBase:
   LEAK_SEVERITY_CRITICAL = MockLeakSeverity.CRITICAL
   LEAK_SEVERITY_MINOR = MockLeakSeverity.MINOR

   # The production base class accepts `type` as a keyword argument.
   # pylint: disable=redefined-builtin
   def __init__(self, name, *, type=None, location=None,
                severity=MockLeakSeverity.CRITICAL):
      self.name = name
      self.leaking = False
      self.leak_sensor_ok = True
      self.leak_type = type or 'unknown'
      self.leak_location = location or 'unknown'
      self.leak_severity = severity
      self.test_leak = False

   def get_name(self):
      return self.name

   def is_leak(self):
      return self.leaking

   def is_leak_sensor_ok(self):
      return self.leak_sensor_ok

   def is_test_leak(self):
      return self.leaking and self.test_leak

   def get_leak_severity(self):
      return self.leak_severity if self.leaking else None

class MockLeakSensorProfileBase:
   pass

class MockLiquidCoolingBase:
   def __init__(self, leakage_sensors_num=0, leakage_sensors_list=None,
                *, profiles=None):
      self.leakage_sensors_num = leakage_sensors_num
      self.leakage_sensors = leakage_sensors_list or []
      self.profiles = {p.get_type(): p for p in (profiles or [])}

class MockLeakageSensorTestBase:
   pass
