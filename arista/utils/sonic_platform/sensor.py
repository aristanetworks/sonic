#!/usr/bin/python

try:
   from sonic_platform_base.sensor_base import (
      SensorBase,
      VoltageSensorBase,
      CurrentSensorBase
   )
except ImportError as e:
   raise ImportError('%s - required module not found' % e) from e

class Sensor(SensorBase):

   def __init__(self, index, sensor):
      super().__init__()
      self._index = index
      self._sensor = sensor
      self._minimum = None
      self._maximum = None

   def get_name(self):
      return self._sensor.getName()

   def get_presence(self):
      return True

   def get_model(self):
      # TODO: get the model from component
      return 'N/A'

   def get_serial(self):
      return 'N/A'

   def get_revision(self):
      # TODO: some sensor devices may have revision info in pmbus command 0x98
      return 'N/A'

   def get_status(self):
      return True

   def get_position_in_parent(self):
      return self._index

   def is_replaceable(self):
      return False

   def get_value(self):
      value = self._sensor.getInput()
      value = round(value, 3) if isinstance(value, float) else value
      if self._minimum is None or self._minimum > value:
         self._minimum = value
      if self._maximum is None or self._maximum < value:
         self._maximum = value
      return value or 0.

   def get_high_threshold(self):
      value = self._sensor.getHighThreshold()
      return round(value, 3) if isinstance(value, float) else value

   def get_low_threshold(self):
      value = self._sensor.getLowThreshold()
      return round(value, 3) if isinstance(value, float) else value

   def get_high_critical_threshold(self):
      value = self._sensor.getHighCriticalThreshold()
      return round(value, 3) if isinstance(value, float) else value

   def get_low_critical_threshold(self):
      value = self._sensor.getLowCriticalThreshold()
      return round(value, 3) if isinstance(value, float) else value

   def get_minimum_recorded(self):
      self.get_value()
      return self._minimum

   def get_maximum_recorded(self):
      self.get_value()
      return self._maximum

class VoltageSensor(Sensor, VoltageSensorBase):

   @classmethod
   def get_unit(cls):
      return "V"

class CurrentSensor(Sensor, CurrentSensorBase):

   @classmethod
   def get_unit(cls):
      return "A"
