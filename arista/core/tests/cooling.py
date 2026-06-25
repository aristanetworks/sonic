# pylint: disable=too-many-lines

import csv
from dataclasses import dataclass
import json
import os
import tempfile

from ...descs.sensor import SensorDesc

from ...inventory.fan import Fan
from ...inventory.temp import Temp

from ...tests.testing import unittest

from ..cooling import (
    CoolingAlgorithm,
    CoolingConfig,
    CoolingFanBase,
    CoolingLogicClassicPid,
    CoolingLogicIncPid,
    CoolingLogicLegacy,
    CoolingThermalBase,
    ThermalClassicPid,
    ThermalExporter,
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

      result = config.thermalPolicyConfig.getZoneConfigMap()
      zone = result[config.defaultZone]
      self.assertEqual(zone['logic'], config.logic.NAME)
      self.assertEqual(zone['minSpeed'], config.minSpeed)
      self.assertEqual(zone['maxSpeed'], config.maxSpeed)

   def testSetThermalPolicyConfigPerZoneSpeed(self):
      config = CoolingConfig(logic=MockLogic(), kp=0.1, ki=2, kd=5)
      MIN_SPEED = 20
      MAX_SPEED = 50
      config.loadPolicyConfig({
         'zones': {
            'psu': {
               'logic': 'incpid',
               'minSpeed': MIN_SPEED,
               'maxSpeed': MAX_SPEED
            }
         }
      })
      result = config.thermalPolicyConfig.getZoneConfigMap()
      self.assertEqual(result['psu']['logic'], 'incpid')
      self.assertEqual(result['psu']['minSpeed'], MIN_SPEED)
      self.assertEqual(result['psu']['maxSpeed'], MAX_SPEED)

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

   def testSetTemperatureUsesProvidedTimestamp(self):
      thermal = CoolingMockThermal('temp1')
      thermal.setTemperatureWithTimestamp(value=42.5, timestamp=1234.5)
      self.assertEqual(thermal.temperature, 42.5)
      self.assertEqual(thermal.data.get[-1], (1234.5, 42.5))

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

   def testZoneMinSpeedBiggerThanMaxSpeed(self):
      data = {
         'thermals': {'temp1': {'kp': 0.1}},
         'fans': {'fan.*': {'zone': 'psu'}},
         'zones': {'psu': {'logic': 'incpid', 'minSpeed': 30, 'maxSpeed': 10}},
      }
      algo = CoolingAlgorithm(self._getPlatform())
      algo.load(policyConfig=data)
      # If minSpeed > maxSpeed, then set them to config defaults
      self.assertEqual(algo.zones['psu'].minSpeed, algo.config.minSpeed)
      self.assertEqual(algo.zones['psu'].maxSpeed, algo.config.maxSpeed)

class CoolingIntegrationTest(unittest.TestCase):

   ASIC_MIN_SPEED = 45
   ASIC_MAX_SPEED = 54

   OPTICS_MIN_SPEED = 48
   OPTICS_MAX_SPEED = 61

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
               'asic_zone': {
                  'logic': 'incpid',
                  'minSpeed': ASIC_MIN_SPEED,
                  'maxSpeed': ASIC_MAX_SPEED,
               },
               'optics_zone': {
                  'logic': 'incpid',
                  'minSpeed': OPTICS_MIN_SPEED,
                  'maxSpeed': OPTICS_MAX_SPEED,
               },
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

   def _makeFansAndThermalsMultiZone(self):
      fans = {
         'fan_1': CoolingMockFan('fan_1',
            inv=CoolingMockInvFan('fan_1', values=[40])),
         'fan_2': CoolingMockFan('fan_2',
            inv=CoolingMockInvFan('fan_2', values=[40])),
         'fan_3': CoolingMockFan('fan_3',
            inv=CoolingMockInvFan('fan_3', values=[40])),
         'fan_4': CoolingMockFan('fan_4',
            inv=CoolingMockInvFan('fan_4', values=[40])),
      }
      thermals = {
         'asic_temp': CoolingMockThermal('asic_temp',
            inv=CoolingMockInvTemp(name='asic_temp', values=[10, 100])),
         'optics_temp': CoolingMockThermal('optics_temp',
            inv=CoolingMockInvTemp(name='optics_temp', values=[0, 100])),
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

   def testMultiZoneMinMaxSpeed(self):
      algo = self._makeAlgo()
      fans, thermals = self._makeFansAndThermalsMultiZone()

      algo.run(fans=fans, thermals=thermals,
         elapsed=algo.INTERVAL, update=True)

      # Drive the fans to lower speeds by starting with a low temperature
      self.assertGreaterEqual(fans['fan_1'].data.lastSet, self.ASIC_MIN_SPEED)
      self.assertGreaterEqual(fans['fan_2'].data.lastSet, self.ASIC_MIN_SPEED)
      self.assertGreaterEqual(fans['fan_3'].data.lastSet, self.OPTICS_MIN_SPEED)
      self.assertGreaterEqual(fans['fan_4'].data.lastSet, self.OPTICS_MIN_SPEED)

      algo.run(fans=fans, thermals=thermals,
         elapsed=algo.INTERVAL, update=True)

      # Drive the fans to higher speeds by sharply increasing the temperature
      self.assertLessEqual(fans['fan_1'].data.lastSet, self.ASIC_MAX_SPEED)
      self.assertLessEqual(fans['fan_2'].data.lastSet, self.ASIC_MAX_SPEED)
      self.assertLessEqual(fans['fan_3'].data.lastSet, self.OPTICS_MAX_SPEED)
      self.assertLessEqual(fans['fan_4'].data.lastSet, self.OPTICS_MAX_SPEED)

   def testMultiZoneRunSupportsMixedLogic(self):
      algo = CoolingAlgorithm(CoolingMockPlatform(CoolingMockInventory([], [])))
      algo.load(policyConfig={
         'version': 1,
         'profiles': {
            'default': {
               'thermals': {
                  'asic_temp': {
                     'kp': 0.1,
                     'ki': 0.5,
                     'kd': 5,
                     'zone': 'asic_zone',
                  },
                  'optics_temp': {
                     'kp': 1,
                     'ki': 0,
                     'kd': 0,
                     'zone': 'optics_zone',
                  },
               },
               'fans': {
                  'fan_1': {'zone': 'asic_zone'},
                  'fan_2': {'zone': 'optics_zone'},
               },
               'zones': {
                  'asic_zone': {'logic': 'incpid'},
                  'optics_zone': {'logic': 'classicpid'},
               },
            },
         },
      })
      fans = {
         'fan_1': CoolingMockFan('fan_1',
            inv=CoolingMockInvFan('fan_1', values=[50])),
         'fan_2': CoolingMockFan('fan_2',
            inv=CoolingMockInvFan('fan_2', values=[50])),
      }
      thermals = {
         'asic_temp': CoolingMockThermal('asic_temp',
            inv=CoolingMockInvTemp(name='asic_temp', target=50, values=[70])),
         'optics_temp': CoolingMockThermal('optics_temp',
            inv=CoolingMockInvTemp(name='optics_temp', target=50, values=[55])),
      }

      algo.run(fans=fans, thermals=thermals,
               elapsed=algo.INTERVAL, update=True)

      self.assertIsInstance(algo.zones['asic_zone'].logic, CoolingLogicIncPid)
      self.assertIsInstance(algo.zones['optics_zone'].logic,
                            CoolingLogicClassicPid)
      self.assertEqual(fans['fan_1'].data.lastSet, 60)
      self.assertEqual(fans['fan_2'].data.lastSet, 100)

class CoolingLogicExportTest(unittest.TestCase):

   def _makeAlgo(self, logic, thermalConfig=None):
      config = {
         'thermals': {
            'hotspot': thermalConfig or {},
         },
         'zones': {
            'default': {'logic': logic},
         },
      }
      algo = CoolingAlgorithm(CoolingMockPlatform(CoolingMockInventory([], [])))
      algo.load(policyConfig=config)
      return algo

   def _makeFansAndThermals(self, fanValues=None, tempValues=None):
      fans = {
         'fan1': CoolingMockFan('fan1',
            inv=CoolingMockInvFan('fan1', values=fanValues or [50])),
      }
      thermals = {
         'hotspot': CoolingMockThermal('hotspot',
            inv=CoolingMockInvTemp(name='hotspot', target=50,
                                   values=tempValues or [55])),
      }
      return fans, thermals

   def _exportRows(self, algo):
      with tempfile.TemporaryDirectory() as tmpdir:
         exporter = ThermalExporter(tmpdir)
         exporter.run(algo.zones, algo.now)
         exporter.close()

         with open(os.path.join(tmpdir, 'thermals.csv'),
                   encoding='utf8', newline='') as f:
            thermalRows = list(csv.reader(f))
         with open(os.path.join(tmpdir, 'fans.csv'),
                   encoding='utf8', newline='') as f:
            fanRows = list(csv.reader(f))
         return thermalRows, fanRows

   def testLegacy(self):
      algo = self._makeAlgo('legacy')
      fans, thermals = self._makeFansAndThermals()

      algo.run(fans=fans, thermals=thermals,
               elapsed=algo.INTERVAL, update=True)

      thermalRows, fanRows = self._exportRows(algo)
      self.assertEqual(thermalRows[0], ['0', '1', '55.0', '0.0', '0.5'])
      self.assertEqual(fanRows[0][1:], ['default', '62.5', 'fan1', '50'])

   def testIncPid(self):
      algo = self._makeAlgo('incpid', {
         'kp': 1,
         'ki': 2,
         'kd': 3,
      })
      fans, thermals = self._makeFansAndThermals(
         fanValues=[50, 50], tempValues=[50, 55])

      for _ in range(2):
         algo.run(fans=fans, thermals=thermals,
                  elapsed=algo.INTERVAL, update=True)

      thermalRows, fanRows = self._exportRows(algo)
      self.assertEqual(thermalRows[0],
                       ['0', '1', '55.0', '0.0', '5.0', '10.0', '15.0'])
      self.assertEqual(fanRows[0][1:], ['default', '80.0', 'fan1', '50'])

   def testClassicPid(self):
      algo = self._makeAlgo('classicpid', {
         'kp': 2,
         'ki': 0,
         'kd': 3,
      })
      fans, thermals = self._makeFansAndThermals()

      algo.run(fans=fans, thermals=thermals,
               elapsed=algo.INTERVAL, update=True)

      thermalRows, fanRows = self._exportRows(algo)
      self.assertEqual(thermalRows[0],
                       ['0', '1', '55.0', '0.0', '10.0', '0', '0'])
      self.assertEqual(fanRows[0][1:], ['default', '100', 'fan1', '50'])

   def testInfoKeepsSeenThermals(self):
      algo = self._makeAlgo('legacy')
      fans = {
         'fan1': CoolingMockFan('fan1',
            inv=CoolingMockInvFan('fan1', values=[50, 50])),
      }
      thermals = {
         'old': CoolingMockThermal('old',
            inv=CoolingMockInvTemp(name='old', target=50, values=[55])),
      }

      with tempfile.TemporaryDirectory() as tmpdir:
         exporter = ThermalExporter(tmpdir)
         algo.run(fans=fans, thermals=thermals,
                  elapsed=algo.INTERVAL, update=True)
         exporter.run(algo.zones, algo.now)

         thermals = {
            'new': CoolingMockThermal('new',
               inv=CoolingMockInvTemp(name='new', target=50, values=[56])),
         }
         algo.run(fans=fans, thermals=thermals,
                  elapsed=algo.INTERVAL, update=True)
         exporter.run(algo.zones, algo.now)
         exporter.close()

         with open(os.path.join(tmpdir, 'info.json'), encoding='utf8') as f:
            info = json.load(f)

      self.assertEqual([s['name'] for s in info['sensors']], ['old', 'new'])

class CoolingClassicPidLogicTest(unittest.TestCase):

   class ClassicPidPlatform(CoolingMockPlatform):
      COOLING = CoolingConfig(
         logic=CoolingLogicClassicPid,
         targetOffset=10,
      )

   class ClassicPidNoOffsetPlatform(CoolingMockPlatform):
      COOLING = CoolingConfig(logic=CoolingLogicClassicPid)

   class RpmSlopePlatform(CoolingMockPlatform):
      COOLING = CoolingConfig(
         logic=CoolingLogicClassicPid,
         rpmSlope=0.5,
         rpmOffset=10,
      )

   def _makeAlgo(self, platformCls=None, policyConfig=None):
      algo = CoolingAlgorithm(
         (platformCls or self.ClassicPidPlatform)(CoolingMockInventory([], [])))
      algo.load(policyConfig=policyConfig)
      return algo

   def _makeFansAndThermals(self, fanValues=None, tempValues=None, target=50):
      fans = {
         'fan1': CoolingMockFan('fan1',
            inv=CoolingMockInvFan('fan1', values=fanValues or [100])),
      }
      thermals = {
         'hotspot': CoolingMockThermal('hotspot',
            inv=CoolingMockInvTemp(
               name='hotspot', target=target, values=tempValues or [55])),
      }
      return fans, thermals

   def testTargetOffset(self):
      algo = self._makeAlgo()
      fans, thermals = self._makeFansAndThermals(tempValues=[55])

      algo.run(fans=fans, thermals=thermals,
               elapsed=algo.INTERVAL, update=True)

      self.assertEqual(fans['fan1'].data.lastSet, 99.625)

   def testRpmSlope(self):
      algo = self._makeAlgo(self.RpmSlopePlatform)
      fans, thermals = self._makeFansAndThermals(tempValues=[45])

      algo.run(fans=fans, thermals=thermals,
               elapsed=algo.INTERVAL, update=True)

      # targetRpm is converted to PWM by rpmSlope/rpmOffset.
      self.assertEqual(fans['fan1'].data.lastSet, 59.8125)
      self.assertEqual(algo.zones['default'].logic.targetRpm.lastSet, 99.625)

   def testPwmClampedToMinSpeed(self):
      MIN_SPEED = 10
      MAX_SPEED = 25
      policyConfig = {
         'version': 1,
         'profiles': {
            'default': {
               'thermals': {
                  'hotspot': {
                     'kp': 5, 'ki': 0, 'kd': 0, 'zone': 'default',
                  },
               },
               'zones': {
                  'default': {
                     'logic': 'classicpid',
                     'minSpeed': MIN_SPEED,
                     'maxSpeed': MAX_SPEED,
                  },
               },
            },
         },
      }
      algo = self._makeAlgo(self.RpmSlopePlatform, policyConfig)
      fans, thermals = self._makeFansAndThermals(
         fanValues=[100], tempValues=[30], target=50)

      algo.run(fans=fans, thermals=thermals,
               elapsed=algo.INTERVAL, update=True)

      cooling = self.RpmSlopePlatform.COOLING
      fan_pwm = MIN_SPEED * cooling.rpmSlope + cooling.rpmOffset
      self.assertEqual(fans['fan1'].data.lastSet, fan_pwm)
      self.assertEqual(algo.zones['default'].logic.targetRpm.lastSet, MIN_SPEED)

   def testPwmClampedToMaxSpeed(self):
      MIN_SPEED = 10
      MAX_SPEED = 25
      policyConfig = {
         'version': 1,
         'profiles': {
            'default': {
               'thermals': {
                  'hotspot': {
                     'kp': 5, 'ki': 0, 'kd': 0, 'zone': 'default',
                  },
               },
               'zones': {
                  'default': {
                     'logic': 'classicpid',
                     'minSpeed': MIN_SPEED,
                     'maxSpeed': MAX_SPEED,
                  },
               },
            },
         },
      }
      algo = self._makeAlgo(self.RpmSlopePlatform, policyConfig)
      fans, thermals = self._makeFansAndThermals(
         fanValues=[100], tempValues=[80], target=30)

      algo.run(fans=fans, thermals=thermals,
               elapsed=algo.INTERVAL, update=True)

      cooling = self.RpmSlopePlatform.COOLING
      fan_pwm = MAX_SPEED * cooling.rpmSlope + cooling.rpmOffset
      self.assertEqual(fans['fan1'].data.lastSet, fan_pwm)
      self.assertEqual(algo.zones['default'].logic.targetRpm.lastSet, MAX_SPEED)

   def testPidCleanup(self):
      algo = self._makeAlgo()
      fans, thermals = self._makeFansAndThermals(
         fanValues=[100, 100], tempValues=[55])

      algo.run(fans=fans, thermals=thermals,
               elapsed=algo.INTERVAL, update=True)
      self.assertEqual(len(algo.zones['default'].logic.thermalPids), 1)

      algo.zones['default'].thermals = {}
      algo.zones['default'].logic.computePwm(100)

      self.assertEqual(algo.zones['default'].logic.thermalPids, {})

   def testPerThermalTuning(self):
      algo = self._makeAlgo(
         self.ClassicPidNoOffsetPlatform,
         policyConfig={
            'thermals': {
               'warm': {'kp': 2, 'ki': 0, 'kd': 0},
               'hot': {'kp': 0.5, 'ki': 0, 'kd': 0},
            },
         },
      )
      fans, _ = self._makeFansAndThermals(fanValues=[100, 100])
      thermals = {
         'warm': CoolingMockThermal('warm',
            inv=CoolingMockInvTemp(name='warm', target=50, values=[45, 65])),
         'hot': CoolingMockThermal('hot',
            inv=CoolingMockInvTemp(name='hot', target=50, values=[45, 65])),
      }

      algo.run(fans=fans, thermals=thermals,
               elapsed=algo.INTERVAL, update=True)
      firstRpm = fans['fan1'].data.lastSet
      self.assertEqual(firstRpm, 97.5)

      algo.run(fans=fans, thermals=thermals,
               elapsed=algo.INTERVAL, update=True)

      # warm drives PID due to its more aggressive tuning
      self.assertEqual(fans['fan1'].data.lastSet, 99.5)
      self.assertGreater(fans['fan1'].data.lastSet, firstRpm)
      self.assertEqual(thermals['warm'].lastDrovePwm, algo.now)
      self.assertLess(thermals['hot'].lastDrovePwm, algo.now)

class ThermalClassicPidTest(unittest.TestCase):

   def _makeThermalPid(self, readings, target=50, kp=1, kd=0):
      thermal = CoolingMockThermal('hotspot',
         inv=CoolingMockInvTemp(name='hotspot', target=target))
      thermal.config = {'kp': kp, 'ki': 0, 'kd': kd}
      thermal.data.get = readings
      return ThermalClassicPid(thermal)

   def testLambda(self):
      for delta, expectedLambda in [
            (1.0, 0.08),
            (0.5, 0.1),
            (0.25, 0.15),
            (0.1, 0.3),
         ]:
         pid = self._makeThermalPid([(0, 50), (10, 50 + delta)])

         pid.update(10)

         self.assertAlmostEqual(pid.resolution, delta)
         self.assertEqual(pid.lambda_, expectedLambda)

   def testResolutionFloor(self):
      pid = self._makeThermalPid([(0, 50), (10, 50.25)])
      pid.update(10)
      self.assertEqual(pid.resolution, 0.25)
      self.assertEqual(pid.lambda_, 0.15)

      # Resolution is the smallest observed temperature step, so later larger
      # deltas must not make it larger.
      pid.thermal.data.get.append((20, 52))
      pid.update(20)

      self.assertEqual(pid.resolution, 0.25)
      self.assertEqual(pid.lambda_, 0.15)

   def testFirstReading(self):
      pid = self._makeThermalPid([(10, 55)])

      pid.update(10)

      self.assertEqual(pid.p, -5)
      self.assertEqual(pid.d, 0)
      self.assertEqual(pid.value, -5)

   def testSmoothing(self):
      pid = self._makeThermalPid([(0, 40), (1000, 50)], kd=1)

      pid.update(100)
      pid.thermal.data.get.append((2000, 60))
      pid.update(110)

      # lambda=0.08 smooths P first; D is then smoothed using the algorithm
      # update interval rather than the interval between thermal readings.
      self.assertEqual(pid.lambda_, 0.08)
      self.assertAlmostEqual(pid.p, -0.8)
      self.assertAlmostEqual(pid.d, -0.0064)
      self.assertAlmostEqual(pid.value, -0.8064)
      self.assertAlmostEqual(pid.thermal.logicData('p').lastGet, 0.8)
      self.assertAlmostEqual(pid.thermal.logicData('d').lastGet, 0.0064)

   def testTuning(self):
      pid = self._makeThermalPid([(0, 40), (1000, 50)], kp=2, kd=3)

      pid.update(100)
      pid.thermal.data.get.append((2000, 60))
      pid.update(110)

      self.assertAlmostEqual(pid.value, -1.6192)
      self.assertAlmostEqual(pid.thermal.logicData('p').lastGet, 1.6)
      self.assertAlmostEqual(pid.thermal.logicData('d').lastGet, 0.0192)

class CoolingLegacyLogicTest(unittest.TestCase):

   def _getPlatform(self):
      inv = CoolingMockInventory([], [])
      return CoolingMockPlatform(inv)

   def _getSimpleAlgo(self, fanInitial=30, temps=None, policyConfig=None):
      algo = CoolingAlgorithm(self._getPlatform())
      algo.load(policyConfig)
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
      MIN_SPEED = 30
      data = {
         'version': 1,
         'profiles': {
            'default': {
               'zones': {
                  'default': {'logic': 'incpid', 'minSpeed': MIN_SPEED},
               },
            },
         },
      }
      algo, fans, thermals = self._getSimpleAlgo(
         fanInitial=50, temps=[0], policyConfig=data)

      algo.run(fans=fans, thermals=thermals,
               elapsed=algo.INTERVAL, update=True)
      self.assertEqual(self._lastFanSpeed(fans), MIN_SPEED)

   def testMaxFanSpeed(self):
      MAX_SPEED = 75
      data = {
         'version': 1,
         'profiles': {
            'default': {
               'zones': {
                  'default': {'logic': 'incpid', 'maxSpeed': MAX_SPEED},
               },
            },
         },
      }
      algo, fans, thermals = self._getSimpleAlgo(
         fanInitial=70, temps=[100], policyConfig=data)
      algo.run(fans=fans, thermals=thermals,
               elapsed=algo.INTERVAL, update=True)
      self.assertEqual(self._lastFanSpeed(fans), MAX_SPEED)

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
