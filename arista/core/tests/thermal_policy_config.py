
import copy
from dataclasses import dataclass, field

from ...tests.testing import unittest

from ..thermal_policy_config import ThermalPolicyConfig

@dataclass
class MockLogic:
   NAME: str = 'legacy'

@dataclass
class MockConfig:
   kp: float = 0.075
   ki: float = 1
   kd: float = 10
   profile: str = 'default'
   defaultZone: str = 'board'
   logic: MockLogic = field(default_factory=MockLogic)

class ThermalPolicyConfigV1Test(unittest.TestCase):

   CONFIG = MockConfig()

   DATA = {
      'version': 1,
      'profiles': {
         'default': {
            'thermals': {
               'ACPI_TEMP': {
                  'kp': 0, 'ki': 0, 'kd': 0, 'zone': 'asic_zone',
               },
               'SMB_TH6_DIODE_.*_TEMP': {
                  'kp': 0, 'ki': 0, 'kd': 0, 'zone': 'asic_zone',
               },
               'SMB_BOARD_FRONT_.*_TEMP': {
                  'kp': 0, 'ki': 0, 'kd': 0, 'zone': 'optics_zone',
               },
            },
            'fans': {
               'fan_[1-4]': {'zone': 'asic_zone'},
               'fan_[5-8]': {'zone': 'optics_zone'},
            },
            'zones': {
               'asic_zone': {'logic': 'incpid'},
               'optics_zone': {'logic': 'incpid'},
            },
         },
      },
   }

   def _makeCfg(self, data=None, config=None):
      return ThermalPolicyConfig(config or self.CONFIG,
                                 copy.deepcopy(data or self.DATA))

   def testNormalizeSensorKeepsExistingValues(self):
      cfg = self._makeCfg()
      sensor = cfg.thermalConfig['ACPI_TEMP']
      self.assertEqual(sensor['kp'], 0)
      self.assertEqual(sensor['ki'], 0)
      self.assertEqual(sensor['kd'], 0)
      self.assertEqual(sensor['zone'], 'asic_zone')

   def testNormalizeSensorInjectsDefaults(self):
      data = {
         'version': 1,
         'profiles': {
            'default': {
               'thermals': {
                  'temp1': {'kp': 0.5},
               },
            },
         },
      }
      cfg = self._makeCfg(data=data)
      sensor = cfg.thermalConfig['temp1']
      self.assertEqual(sensor['kp'], 0.5)
      self.assertEqual(sensor['ki'], self.CONFIG.ki)
      self.assertEqual(sensor['kd'], self.CONFIG.kd)
      self.assertEqual(sensor['zone'], self.CONFIG.defaultZone)

   def testNormalizeFanKeepsExistingZone(self):
      cfg = self._makeCfg()
      self.assertEqual(cfg.fanConfig['fan_[1-4]']['zone'], 'asic_zone')
      self.assertEqual(cfg.fanConfig['fan_[5-8]']['zone'], 'optics_zone')

   def testNormalizeFanInjectsDefaultZone(self):
      data = {
         'version': 1,
         'profiles': {
            'default': {
               'fans': {
                  'fan.*': {},
               },
            },
         },
      }
      cfg = self._makeCfg(data=data)
      self.assertEqual(cfg.fanConfig['fan.*']['zone'], self.CONFIG.defaultZone)

   def testNormalizeZoneKeepsExistingLogic(self):
      cfg = self._makeCfg()
      self.assertEqual(cfg.zoneConfig['asic_zone']['logic'], 'incpid')
      self.assertEqual(cfg.zoneConfig['optics_zone']['logic'], 'incpid')

   def testNormalizeZoneInjectsDefaultLogic(self):
      data = {
         'version': 1,
         'profiles': {
            'default': {
               'zones': {
                  'myzone': {},
               },
            },
         },
      }
      cfg = self._makeCfg(data=data)
      self.assertEqual(cfg.zoneConfig['myzone']['logic'], self.CONFIG.logic.NAME)

   def testGetThermalConfigExactMatch(self):
      cfg = self._makeCfg()
      result = cfg.getThermalConfig('ACPI_TEMP')
      self.assertEqual(result['kp'], 0)
      self.assertEqual(result['ki'], 0)
      self.assertEqual(result['kd'], 0)
      self.assertEqual(result['zone'], 'asic_zone')

   def testGetThermalConfigRegexMatch(self):
      cfg = self._makeCfg()
      result = cfg.getThermalConfig('SMB_TH6_DIODE_1_TEMP')
      self.assertEqual(result['zone'], 'asic_zone')

   def testGetThermalConfigNoMatchReturnsDefaults(self):
      cfg = self._makeCfg()
      result = cfg.getThermalConfig('unknown_sensor')
      self.assertEqual(result['kp'], self.CONFIG.kp)
      self.assertEqual(result['ki'], self.CONFIG.ki)
      self.assertEqual(result['kd'], self.CONFIG.kd)
      self.assertEqual(result['zone'], self.CONFIG.defaultZone)

   def testGetThermalConfigReturnsCopy(self):
      cfg = self._makeCfg()
      result = cfg.getThermalConfig('ACPI_TEMP')
      result['kp'] = 999
      self.assertEqual(cfg.getThermalConfig('ACPI_TEMP')['kp'], 0)

   def testGetFanConfigMatch(self):
      cfg = self._makeCfg()
      result = cfg.getFanConfig('fan_3')
      self.assertEqual(result['zone'], 'asic_zone')

   def testGetFanConfigRegexMatch(self):
      cfg = self._makeCfg()
      result = cfg.getFanConfig('fan_7')
      self.assertEqual(result['zone'], 'optics_zone')

   def testGetFanConfigNoMatchReturnsDefaults(self):
      cfg = self._makeCfg()
      result = cfg.getFanConfig('blower1')
      self.assertEqual(result['zone'], self.CONFIG.defaultZone)

   def testGetFanConfigReturnsCopy(self):
      cfg = self._makeCfg()
      result = cfg.getFanConfig('fan_1')
      result['zone'] = 'modified'
      self.assertEqual(cfg.getFanConfig('fan_1')['zone'], 'asic_zone')

   def testGetZoneLogicMap(self):
      cfg = self._makeCfg()
      zones = cfg.getZoneLogicMap()
      self.assertEqual(zones[self.CONFIG.defaultZone], self.CONFIG.logic.NAME)
      self.assertEqual(zones['asic_zone'], 'incpid')
      self.assertEqual(zones['optics_zone'], 'incpid')

   def testNonDefaultProfile(self):
      data = {
         'version': 1,
         'profiles': {
            'default': {
               'thermals': {'temp1': {'kp': 0.1}},
            },
            'quiet': {
               'thermals': {'temp2': {'kp': 0.2}},
            },
         },
      }
      config = MockConfig(profile='quiet')
      cfg = self._makeCfg(data=data, config=config)
      self.assertNotIn('temp1', cfg.thermalConfig)
      self.assertIn('temp2', cfg.thermalConfig)

class ThermalPolicyConfigV0Test(unittest.TestCase):

   CONFIG = MockConfig()

   def testV0UsesRootKeys(self):
      data = {
         'thermals': {'temp1': {'kp': 0.1}},
         'fans': {'fan.*': {'zone': 'psu'}},
         'zones': {'psu': {'logic': 'incpid'}},
      }
      cfg = ThermalPolicyConfig(self.CONFIG, data)
      self.assertIn('temp1', cfg.thermalConfig)
      self.assertIn('fan.*', cfg.fanConfig)
      self.assertIn('psu', cfg.zoneConfig)

   def testV0NormalizesData(self):
      data = {
         'thermals': {'temp1': {'kp': 0.5}},
         'fans': {'fan.*': {}},
         'zones': {'myzone': {}},
      }
      cfg = ThermalPolicyConfig(self.CONFIG, data)
      self.assertEqual(cfg.thermalConfig['temp1']['ki'], self.CONFIG.ki)
      self.assertEqual(cfg.thermalConfig['temp1']['kd'], self.CONFIG.kd)
      self.assertEqual(cfg.thermalConfig['temp1']['zone'], self.CONFIG.defaultZone)
      self.assertEqual(cfg.fanConfig['fan.*']['zone'], self.CONFIG.defaultZone)
      self.assertEqual(cfg.zoneConfig['myzone']['logic'], self.CONFIG.logic.NAME)

   def testV0GetThermalConfigReturnsDefaultsOnNoMatch(self):
      data = {
         'thermals': {'temp1': {'kp': 0.5}},
      }
      cfg = ThermalPolicyConfig(self.CONFIG, data)
      result = cfg.getThermalConfig('unknown')
      self.assertEqual(result['kp'], self.CONFIG.kp)
      self.assertEqual(result['ki'], self.CONFIG.ki)
      self.assertEqual(result['kd'], self.CONFIG.kd)
      self.assertEqual(result['zone'], self.CONFIG.defaultZone)

   def testV0GetFanConfigReturnsDefaultsOnNoMatch(self):
      data = {
         'fans': {'fan\\d+': {'zone': 'psu'}},
      }
      cfg = ThermalPolicyConfig(self.CONFIG, data)
      result = cfg.getFanConfig('blower1')
      self.assertEqual(result['zone'], self.CONFIG.defaultZone)

   def testV0EmptyData(self):
      cfg = ThermalPolicyConfig(self.CONFIG, {})
      self.assertEqual(cfg.getThermalConfig('any')['kp'], self.CONFIG.kp)
      self.assertEqual(cfg.getFanConfig('any')['zone'], self.CONFIG.defaultZone)
      self.assertEqual(cfg.getZoneLogicMap(),
                       {self.CONFIG.defaultZone: self.CONFIG.logic.NAME})

if __name__ == '__main__':
   unittest.main()
