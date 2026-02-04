from datetime import datetime, timezone
from ....tests.testing import patch, unittest
from ..thermal_helper import CoolingXcvrThermal

class MockDbEntity:
   def __init__(self, readings):
      self.readings = readings
      self.read_count = 0

   def get_all(self, idx=None):
      if idx == 1:
         return {
            'temphighwarning': '70',
            'temphighalarm': '80',
         }

      reading = self.readings[min(self.read_count, len(self.readings) - 1)]
      self.read_count += 1
      return reading


class CoolingXcvrThermalTest(unittest.TestCase):
   LAST_UPDATE_TIME = 'Tue Jun 23 10:11:12 2026'
   NOW_MONO = 1000.0
   NOW_WALL = 2000.0

   def _timestamp(self, value):
      return datetime.strptime(
         value, "%a %b %d %H:%M:%S %Y"
      ).replace(tzinfo=timezone.utc).timestamp()

   def _mono_timestamp(self, value):
      return self._timestamp(value) + (self.NOW_MONO - self.NOW_WALL)

   def _makeThermal(self, readings):
      thermal = CoolingXcvrThermal('Ethernet0')
      thermal.register_db(MockDbEntity(readings))
      return thermal

   def testUpdateFromDbUsesLastUpdateTimestamp(self):
      thermal = self._makeThermal([{
         'temperature': '42.5',
         'last_update_time': self.LAST_UPDATE_TIME,
      }])

      with patch('arista.libs.date.monotonicRaw',
                 return_value=self.NOW_MONO), \
           patch('arista.libs.date.time',
                 return_value=self.NOW_WALL):
         self.assertTrue(thermal.update_from_db())

      self.assertEqual(thermal.temperature, 42.5)
      self.assertEqual(thermal.previous_last_update_time, self.LAST_UPDATE_TIME)
      self.assertEqual(
         thermal.data.get[-1],
         (self._mono_timestamp(self.LAST_UPDATE_TIME), 42.5)
      )

   def testUpdateFromDbIgnoresSameTimestamp(self):
      thermal = self._makeThermal([
         {
            'temperature': '40',
            'last_update_time': self.LAST_UPDATE_TIME,
         },
         {
            'temperature': '50',
            'last_update_time': self.LAST_UPDATE_TIME,
         },
      ])

      self.assertTrue(thermal.update_from_db())
      self.assertTrue(thermal.update_from_db())

      self.assertEqual(thermal.temperature, 40.0)
      self.assertEqual(len(thermal.data.get), 1)

   def testUpdateFromDbUsesDefaultTimestampForInvalidLastUpdateTimestamp(self):
      thermal = self._makeThermal([{
         'temperature': '42.5',
         'last_update_time': 'invalid',
      }])

      self.assertTrue(thermal.update_from_db())

      self.assertEqual(thermal.temperature, 42.5)
      self.assertEqual(thermal.previous_last_update_time, 'invalid')
      self.assertEqual(thermal.data.get[-1][1], 42.5)
      self.assertIsNotNone(thermal.data.get[-1][0])


if __name__ == '__main__':
   unittest.main()
