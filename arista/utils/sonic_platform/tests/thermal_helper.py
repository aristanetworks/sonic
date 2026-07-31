from datetime import datetime, timezone
from ....tests.testing import patch, unittest
from ..thermal_helper import ChassisDbFan, CoolingEntityManager, CoolingXcvrThermal

class MockChassis:
   def __init__(self, slot=1, platform=None, thermals=None, modules=None,
                psus=None):
      self.slot = slot
      self.platform = platform or MockPlatform()
      self.thermals = thermals or []
      self.modules = modules or []
      self.psus = psus or []

   def get_my_slot(self):
      return self.slot

   def getPlatform(self):
      return self.platform

   def get_all_thermals(self):
      return self.thermals

   def get_all_modules(self):
      return self.modules

   def get_all_psus(self):
      return self.psus

   def get_num_modules(self):
      return len(self.modules)

class MockTable:
   def __init__(self):
      self.writes = []

   def set(self, name, fvs):
      self.writes.append((name, dict(fvs)))

class MockDbHelper:
   def __init__(self):
      self.tables = {}

   def get_chassis_state_table(self, table_name):
      return self.tables.setdefault(table_name, MockTable())

   def get_all_thermals(self):
      raise AssertionError('modular chassis thermals must not be read from DB')

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

class MockCoolingConfig:
   asicViaDb = False

class MockInventory:
   def getTemps(self):
      return []

   def getPsuSlots(self):
      return []

class MockPlatform:
   COOLING = MockCoolingConfig()

   def getInventory(self):
      return MockInventory()

class MockApiThermal:
   def __init__(self, name):
      self.name = name

   def get_name(self):
      return self.name

class MockModule:
   def __init__(self, slot, thermals=None):
      self.slot = slot
      self.thermals = thermals or []

   def get_slot(self):
      return self.slot

   def get_all_thermals(self):
      return self.thermals

class ChassisDbFanTest(unittest.TestCase):

   def testSetSpeedWritesThermalAlgoResult(self):
      dbhelper = MockDbHelper()
      fan = ChassisDbFan(MockChassis(slot=3), dbhelper)

      with patch('arista.utils.sonic_platform.thermal_helper.asctime',
                 return_value='Tue Jun 23 10:11:12 2026'):
         fan.setSpeed(42)

      table = dbhelper.tables['TEMPERATURE_INFO_3']
      self.assertEqual(len(table.writes), 1)
      name, data = table.writes[0]
      self.assertEqual(name, 'THERMAL_ALGO_RESULT')
      self.assertEqual(data['pwm'], '42.0')
      self.assertEqual(data['last_update_time'], 'Tue Jun 23 10:11:12 2026')
      self.assertEqual(data['device_name'], 'Linecard 3')


class CoolingEntityManagerTest(unittest.TestCase):

   def testUpdateThermalsRegistersModuleThermalsOnlyFromApi(self):
      chassis = MockChassis(
         thermals=[MockApiThermal('Chassis thermal')],
         modules=[
            MockModule(2, [MockApiThermal('Linecard2 thermal')]),
         ],
      )
      dbhelper = MockDbHelper()
      with patch('arista.utils.sonic_platform.thermal_helper.DBHelper',
                 return_value=dbhelper):
         mgr = CoolingEntityManager(chassis)
         mgr.update_thermals(chassis)

      thermals = mgr.get_all_thermals()
      self.assertIn('Chassis thermal', thermals)
      self.assertIn('CARD2 Linecard2 thermal', thermals)
      self.assertIsNotNone(thermals['CARD2 Linecard2 thermal'].api)
      self.assertIsNone(thermals['CARD2 Linecard2 thermal'].dbent)


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
