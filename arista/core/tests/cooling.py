from dataclasses import dataclass

from ...descs.sensor import SensorDesc

from ...inventory.fan import Fan
from ...inventory.temp import Temp

from ...tests.testing import unittest

from ..cooling import (
    CoolingAlgorithm,
    CoolingConfig,
    CoolingFanBase,
    CoolingLogicLegacy,
    CoolingThermalBase,
)

from ..thermal_policy_config import ThermalPolicyConfig

@dataclass
class MockLogic:
   NAME: str = 'legacy'

class CoolingMockInvFan(Fan):
   def __init__(self, name, values):
      self.name = name
      self.get = values
      self.set = []

   def __str__(self):
      return '%s(%s)' % (self.__class__.__name__, self.getName())

   def getName(self):
      return self.name

   def getSpeed(self):
      return self.get.pop(0)

   def setSpeed(self, value):
      self.set.append(value)
      self.get.append(value)

class CoolingMockInvTemp(Temp):
   def __init__(self, name='hotspot', target=50, overheat=80, critical=100,
                values=None):
      self.name = name
      self.desc = SensorDesc(diode=1, name=name, description='', target=target,
                             overheat=overheat, critical=critical)
      self.values = [float(v) for v in values or []]

   def __str__(self):
      return '%s(%s)' % (self.__class__.__name__, self.getName())

   def getDesc(self):
      return self.desc

   def getName(self):
      return self.desc.name

   def getTemperature(self):
      return self.values.pop(0)

   def getHighThreshold(self):
      return self.desc.overheat

   def getHighCriticalThreshold(self):
      return self.desc.critical

class CoolingMockFan(CoolingFanBase):
   def update(self):
      self.speed = self.inv.getSpeed()

class CoolingMockThermal(CoolingThermalBase):
   def update(self):
      self.temperature = self.inv.getTemperature()
      self.overheat = self.inv.getHighThreshold()
      self.critical = self.inv.getHighCriticalThreshold()

class CoolingMockInventory(object):
   def __init__(self, fans, thermals):
      self.fans = fans
      self.thermals = thermals

   def getFans(self):
      return self.fans

   def getTemps(self):
      return self.thermals

class CoolingMockPlatform(object):

   COOLING = CoolingConfig(logic=MockLogic())

   def __init__(self, inventory):
      self.inventory = inventory

   def getInventory(self):
      return self.inventory

class CoolingConfigTest(unittest.TestCase):

   def testDefaultFields(self):
      config = CoolingConfig(logic=MockLogic())
      self.assertEqual(config.profile, 'default')
      self.assertEqual(config.defaultZone, 'default')
      self.assertIsNone(config.thermalPolicyConfig)

   def testSetThermalPolicyConfig(self):
      config = CoolingConfig(logic=MockLogic())
      config.loadPolicyConfig(None)
      self.assertIsInstance(config.thermalPolicyConfig, ThermalPolicyConfig)

   def testSetThermalPolicyConfigWithPartialPidData(self):
      config = CoolingConfig(logic=MockLogic())
      config.loadPolicyConfig({
         'thermals': {'temp1': {'kp': 0.5}},
      })
      result = config.thermalPolicyConfig.getThermalConfig('temp1')
      self.assertEqual(result['kp'], 0.5)
      self.assertEqual(result['ki'], 1)
      self.assertEqual(result['kd'], 10)

   def testSetThermalPolicyConfigWithFullPidData(self):
      config = CoolingConfig(logic=MockLogic(), kp=0.1, ki=2, kd=5)
      config.loadPolicyConfig({
         'thermals': {'temp1': {'kp': 0.5, 'ki': 0.6, 'kd': 0.7}},
      })
      result = config.thermalPolicyConfig.getThermalConfig('temp1')
      self.assertEqual(result['kp'], 0.5)
      self.assertEqual(result['ki'], 0.6)
      self.assertEqual(result['kd'], 0.7)

   def testSetThermalPolicyConfigInjectsDefaults(self):
      config = CoolingConfig(logic=MockLogic(), kp=0.1, ki=2, kd=5)
      config.loadPolicyConfig({
         'thermals': {'temp1': {}},
      })
      result = config.thermalPolicyConfig.getThermalConfig('temp1')
      self.assertEqual(result['kp'], 0.1)
      self.assertEqual(result['ki'], 2)
      self.assertEqual(result['kd'], 5)

class CoolingFanBaseTest(unittest.TestCase):

   def _makeConfig(self, fans=None):
      config = CoolingConfig(logic=MockLogic())
      config.loadPolicyConfig({
         'fans': fans or {},
      })
      return config

   def testLoadConfigSetsFanConfig(self):
      config = self._makeConfig(fans={
         'fan_[1-4]': {'zone': 'asic_zone'},
      })
      fan = CoolingMockFan('fan_1')
      fan.loadConfig(config)
      self.assertEqual(fan.config['zone'], 'asic_zone')
      self.assertTrue(fan.configInitialized)

   def testLoadConfigAssignsZone(self):
      config = self._makeConfig(fans={
         'fan1': {'zone': 'psu_zone'},
      })
      fan = CoolingMockFan('fan1')
      fan.loadConfig(config)
      self.assertEqual(fan.zone, 'psu_zone')

   def testLoadConfigIdempotent(self):
      config1 = self._makeConfig(fans={
         'fan1': {'zone': 'asic_zone'},
      })
      config2 = self._makeConfig(fans={
         'fan1': {'zone': 'psu_zone'},
      })
      fan = CoolingMockFan('fan1')
      fan.loadConfig(config1)
      firstConfig = fan.config
      fan.loadConfig(config2)
      self.assertIs(fan.config, firstConfig)

   def testLoadConfigMissingZoneUsesDefault(self):
      config = self._makeConfig(fans={
         'fan1': {},
      })
      fan = CoolingMockFan('fan1')
      fan.loadConfig(config)
      self.assertEqual(fan.zone, config.defaultZone)

   def testLoadConfigNoMatchUsesDefaults(self):
      config = self._makeConfig()
      fan = CoolingMockFan('unknown_fan')
      fan.loadConfig(config)
      self.assertEqual(fan.config['zone'], config.defaultZone)

class CoolingThermalBaseTest(unittest.TestCase):

   def _makeConfig(self, thermals=None):
      config = CoolingConfig(logic=MockLogic())
      config.loadPolicyConfig({
         'thermals': thermals or {},
      })
      return config

   def testLoadConfigSetsThermalConfig(self):
      config = self._makeConfig(thermals={
         'temp1': {'kp': 0.5, 'ki': 0.6, 'kd': 0.7, 'zone': 'asic_zone'},
      })
      thermal = CoolingMockThermal('temp1')
      thermal.loadConfig(config)
      self.assertEqual(thermal.config['kp'], 0.5)
      self.assertEqual(thermal.config['ki'], 0.6)
      self.assertEqual(thermal.config['kd'], 0.7)
      self.assertTrue(thermal.configInitialized)

   def testLoadConfigAssignsZone(self):
      config = self._makeConfig(thermals={
         'temp1': {'zone': 'optics_zone'},
      })
      thermal = CoolingMockThermal('temp1')
      thermal.loadConfig(config)
      self.assertEqual(thermal.zone, 'optics_zone')

   def testLoadConfigIdempotent(self):
      config1 = self._makeConfig(thermals={
         'temp1': {'kp': 0.5},
      })
      config2 = self._makeConfig(thermals={
         'temp1': {'kp': 0.9, 'ki': 0.8},
      })
      thermal = CoolingMockThermal('temp1')
      thermal.loadConfig(config1)
      firstConfig = thermal.config
      thermal.loadConfig(config2)
      self.assertIs(thermal.config, firstConfig)

   def testLoadConfigMissingZoneUsesDefault(self):
      config = self._makeConfig(thermals={
         'temp1': {'kp': 0.5},
      })
      thermal = CoolingMockThermal('temp1')
      thermal.loadConfig(config)
      self.assertEqual(thermal.zone, config.defaultZone)

   def testLoadConfigNoMatchUsesDefaults(self):
      config = self._makeConfig()
      thermal = CoolingMockThermal('unknown')
      thermal.loadConfig(config)
      self.assertEqual(thermal.config['kp'], config.kp)
      self.assertEqual(thermal.config['ki'], config.ki)
      self.assertEqual(thermal.config['kd'], config.kd)
      self.assertEqual(thermal.config['zone'], config.defaultZone)

class CoolingAlgorithmTest(unittest.TestCase):

   def _getPlatform(self, fans=None, thermals=None):
      inv = CoolingMockInventory(fans or [], thermals or [])
      return CoolingMockPlatform(inv)

   def testInitState(self):
      algo = CoolingAlgorithm(self._getPlatform())
      self.assertIsNone(algo.config)
      self.assertFalse(algo.initialized)
      self.assertEqual(algo.zones, {})

   def testLoadCreatesConfig(self):
      algo = CoolingAlgorithm(self._getPlatform())
      algo.load()
      self.assertIsNotNone(algo.config)
      self.assertTrue(algo.initialized)

   def testLoadCreatesDefaultZone(self):
      algo = CoolingAlgorithm(self._getPlatform())
      algo.load()
      self.assertIn('default', algo.zones)

   def testLoadIsIdempotent(self):
      algo = CoolingAlgorithm(self._getPlatform())
      algo.load()
      config = algo.config
      algo.load(policyConfig={
         'version': 1,
         'profiles': {
            'default': {
               'zones': {
                  'new_zone': {'logic': 'incpid'},
               },
            },
         },
      })
      self.assertIs(algo.config, config)

   def testLoadWithPolicyConfigCreatesZones(self):
      algo = CoolingAlgorithm(self._getPlatform())
      algo.load(policyConfig={
         'version': 1,
         'profiles': {
            'default': {
               'zones': {
                  'asic_zone': {'logic': 'incpid'},
                  'optics_zone': {'logic': 'incpid'},
               },
            },
         },
      })
      self.assertIn('default', algo.zones)
      self.assertIn('asic_zone', algo.zones)
      self.assertIn('optics_zone', algo.zones)

   def testZonesAreDict(self):
      algo = CoolingAlgorithm(self._getPlatform())
      algo.load()
      self.assertIsInstance(algo.zones, dict)

   def testRunWithNoFansOrThermals(self):
      algo = CoolingAlgorithm(self._getPlatform())
      algo.load()
      algo.run(elapsed=algo.INTERVAL)

   def testUnrecognizedLogicFallsBackToLegacy(self):
      algo = CoolingAlgorithm(self._getPlatform())
      algo.load(policyConfig={
         'version': 1,
         'profiles': {
            'default': {
               'zones': {
                  'myzone': {'logic': 'nonexistent'},
               },
            },
         },
      })
      self.assertIn('myzone', algo.zones)
      self.assertIsInstance(algo.zones['myzone'].logic, CoolingLogicLegacy)

   def testRunAddsNewThermals(self):
      algo = CoolingAlgorithm(self._getPlatform())
      algo.load(policyConfig={
         'version': 1,
         'profiles': {
            'default': {
               'thermals': {
                  'cool': {
                     'zone': 'asic_zone',
                  },
                  'hot': {
                     'kp': 0.5,
                     'ki': 0.6,
                     'kd': 0.7,
                     'zone': 'asic_zone',
                  },
               },
               'fans': {
                  'fan1': {'zone': 'asic_zone'},
                  'fan2': {'zone': 'asic_zone'},
               },
               'zones': {
                  'asic_zone': {'logic': 'incpid'},
               },
            },
         },
      })
      fans = {
         'fan1': CoolingMockFan('fan1',
            inv=CoolingMockInvFan('fan1', values=[50, 50])),
      }
      thermals = {
         'cool': CoolingMockThermal('cool',
            inv=CoolingMockInvTemp(name='cool', target=50, values=[50, 50])),
      }

      algo.run(fans=fans, thermals=thermals,
               elapsed=algo.INTERVAL, update=True)
      fans['fan2'] = CoolingMockFan('fan2',
         inv=CoolingMockInvFan('fan2', values=[50]))
      thermals['hot'] = CoolingMockThermal('hot',
         inv=CoolingMockInvTemp(name='hot', target=50, values=[70]))
      algo.run(fans=fans, thermals=thermals,
               elapsed=algo.INTERVAL, update=True)

      self.assertEqual(fans['fan2'].zone, 'asic_zone')
      self.assertEqual(thermals['hot'].zone, 'asic_zone')
      self.assertEqual(thermals['hot'].config['kp'], 0.5)
      self.assertEqual(thermals['hot'].config['ki'], 0.6)
      self.assertEqual(thermals['hot'].config['kd'], 0.7)
      self.assertIn('fan2', algo.zones['asic_zone'].fans)
      self.assertIn('hot', algo.zones['asic_zone'].thermals)
      self.assertEqual(fans['fan1'].data.lastSet, 62.0)
      self.assertEqual(fans['fan2'].data.lastSet, 62.0)

class CoolingIntegrationTest(unittest.TestCase):

   POLICY_CONFIG = {
      'version': 1,
      'profiles': {
         'default': {
            'thermals': {
               'asic_temp': {'kp': 0.1, 'ki': 0.5, 'kd': 5, 'zone': 'asic_zone'},
               'optics_temp': {'kp': 0.2, 'ki': 0.8, 'kd': 8, 'zone': 'optics_zone'},
            },
            'fans': {
               'fan_[1-2]': {'zone': 'asic_zone'},
               'fan_[3-4]': {'zone': 'optics_zone'},
            },
            'zones': {
               'asic_zone': {'logic': 'incpid'},
               'optics_zone': {'logic': 'incpid'},
            },
         },
      },
   }

   def _makeAlgo(self):
      inv = CoolingMockInventory([], [])
      platform = CoolingMockPlatform(inv)
      algo = CoolingAlgorithm(platform)
      algo.load(policyConfig=self.POLICY_CONFIG)
      return algo

   def _makeFansAndThermals(self):
      fans = {
         'fan_1': CoolingMockFan('fan_1',
            inv=CoolingMockInvFan('fan_1', values=[50])),
         'fan_2': CoolingMockFan('fan_2',
            inv=CoolingMockInvFan('fan_2', values=[50])),
         'fan_3': CoolingMockFan('fan_3',
            inv=CoolingMockInvFan('fan_3', values=[50])),
         'fan_4': CoolingMockFan('fan_4',
            inv=CoolingMockInvFan('fan_4', values=[50])),
      }
      thermals = {
         'asic_temp': CoolingMockThermal('asic_temp',
            inv=CoolingMockInvTemp(name='asic_temp', values=[70, 72])),
         'optics_temp': CoolingMockThermal('optics_temp',
            inv=CoolingMockInvTemp(name='optics_temp', values=[60, 62])),
      }
      return fans, thermals

   def testMultiZoneRunAssignsZones(self):
      algo = self._makeAlgo()
      fans, thermals = self._makeFansAndThermals()

      algo.run(fans=fans, thermals=thermals,
               elapsed=algo.INTERVAL, update=True)

      self.assertEqual(fans['fan_1'].zone, 'asic_zone')
      self.assertEqual(fans['fan_2'].zone, 'asic_zone')
      self.assertEqual(fans['fan_3'].zone, 'optics_zone')
      self.assertEqual(fans['fan_4'].zone, 'optics_zone')
      self.assertEqual(thermals['asic_temp'].zone, 'asic_zone')
      self.assertEqual(thermals['optics_temp'].zone, 'optics_zone')

   def testMultiZoneRunUsesPerSensorPid(self):
      algo = self._makeAlgo()
      fans, thermals = self._makeFansAndThermals()

      algo.run(fans=fans, thermals=thermals,
               elapsed=algo.INTERVAL, update=True)

      self.assertEqual(thermals['asic_temp'].config['kp'], 0.1)
      self.assertEqual(thermals['asic_temp'].config['ki'], 0.5)
      self.assertEqual(thermals['asic_temp'].config['kd'], 5)
      self.assertEqual(thermals['optics_temp'].config['kp'], 0.2)
      self.assertEqual(thermals['optics_temp'].config['ki'], 0.8)
      self.assertEqual(thermals['optics_temp'].config['kd'], 8)

   def testMultiZoneRunSetsFanSpeeds(self):
      algo = self._makeAlgo()
      fans, thermals = self._makeFansAndThermals()

      algo.run(fans=fans, thermals=thermals,
               elapsed=algo.INTERVAL, update=True)

      # All fans should have a speed set
      for fan in fans.values():
         self.assertIsNotNone(fan.data.lastSet)

class CoolingLegacyLogicTest(unittest.TestCase):

   def _getPlatform(self):
      inv = CoolingMockInventory([], [])
      return CoolingMockPlatform(inv)

   def _getSimpleAlgo(self, fanInitial=30, temps=None):
      algo = CoolingAlgorithm(self._getPlatform())
      algo.load()
      fans = {
         'fan1': CoolingMockFan('fan1',
            inv=CoolingMockInvFan('fan1', values=[fanInitial])),
      }
      thermals = {
         'hotspot': CoolingMockThermal('hotspot',
            inv=CoolingMockInvTemp(name='hotspot', values=temps or [])),
      }
      return algo, fans, thermals

   def _lastFanSpeed(self, fans):
      return fans['fan1'].data.lastSet

   def _assertFanSpeedSane(self, fans):
      speed = self._lastFanSpeed(fans)
      self.assertLessEqual(speed, 100)
      self.assertGreaterEqual(speed, 15)

   def testOverheatSensor(self):
      for temp in [80, 90, 100, 110]:
         algo, fans, thermals = self._getSimpleAlgo(
            fanInitial=30, temps=[temp])
         algo.run(fans=fans, thermals=thermals,
                  elapsed=algo.INTERVAL, update=True)
         self._assertFanSpeedSane(fans)

   def testMinFanSpeed(self):
      algo, fans, thermals = self._getSimpleAlgo(
         fanInitial=35, temps=[0])
      algo.run(fans=fans, thermals=thermals,
               elapsed=algo.INTERVAL, update=True)
      self.assertEqual(self._lastFanSpeed(fans), 30)

   def testDecreasingFanSpeed(self):
      algo, fans, thermals = self._getSimpleAlgo(
         fanInitial=100, temps=[0] * 10)
      for _ in range(6):
         algo.run(fans=fans, thermals=thermals,
                  elapsed=algo.INTERVAL, update=True)
         self.assertLessEqual(self._lastFanSpeed(fans), 100)
         self.assertGreater(self._lastFanSpeed(fans), 30)
      algo.run(fans=fans, thermals=thermals,
               elapsed=algo.INTERVAL, update=True)
      self.assertEqual(self._lastFanSpeed(fans), 30)

   def testFanRampUp(self):
      temps = list(range(30, 80, 5))
      algo, fans, thermals = self._getSimpleAlgo(
         fanInitial=30, temps=temps)
      for _ in temps:
         algo.run(fans=fans, thermals=thermals,
                  elapsed=algo.INTERVAL, update=True)
         self._assertFanSpeedSane(fans)

   def testFanRampDown(self):
      temps = list(range(80, 30, -5))
      algo, fans, thermals = self._getSimpleAlgo(
         fanInitial=100, temps=temps)
      for _ in temps:
         algo.run(fans=fans, thermals=thermals,
                  elapsed=algo.INTERVAL, update=True)
         self._assertFanSpeedSane(fans)

   def testFanSpeedTimeScaling(self):
      algo1, fans1, thermals1 = self._getSimpleAlgo(
         fanInitial=30, temps=[70] * 10)
      algo1.run(fans=fans1, thermals=thermals1,
                elapsed=algo1.INTERVAL, update=True)

      algo2, fans2, thermals2 = self._getSimpleAlgo(
         fanInitial=30, temps=[70] * 10)
      for _ in range(6):
         algo2.run(fans=fans2, thermals=thermals2,
                   elapsed=algo2.INTERVAL / 6, update=True)

      delta = abs(self._lastFanSpeed(fans1) - self._lastFanSpeed(fans2))
      self.assertLess(delta, 0.0000001)

   def testSingleFanSingleTemp(self):
      algo, fans, thermals = self._getSimpleAlgo(
         fanInitial=100, temps=[50])
      algo.run(fans=fans, thermals=thermals,
               elapsed=algo.INTERVAL, update=True)
      self._assertFanSpeedSane(fans)

if __name__ == '__main__':
   unittest.main()
