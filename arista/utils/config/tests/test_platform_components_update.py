#!/usr/bin/env python

import json
import os
import tempfile
import unittest
from unittest import mock

from ....core.supervisor import Supervisor
from ..platform_components_updater import (
   buildComponents,
   buildModules,
   PlatformComponentsUpdater,
)

MODULE = 'arista.utils.config.platform_components_updater'
UPDATER_MODULE = 'arista.utils.config.updater'

def _mockProgrammable(name):
   prog = mock.MagicMock()
   component = mock.MagicMock()
   component.__str__ = mock.Mock(return_value=name)
   prog.getComponent.return_value = component
   return prog

def _mockInventory(programmables=None):
   inv = mock.MagicMock()
   inv.getProgrammables.return_value = programmables or []
   return inv

class BuildComponentsTest(unittest.TestCase):

   def testEmptyInventory(self):
      result = buildComponents('DCS-7050', _mockInventory())
      self.assertEqual(result, {
         'chassis': {
            'DCS-7050': {
               'component': {},
            },
         },
      })

   def testInventoryComponents(self):
      inv = _mockInventory([
         _mockProgrammable('Aboot()'),
         _mockProgrammable('Scd(addr=0000:00:18.7)'),
         _mockProgrammable('CormorantSysCpld(addr=13-0023)'),
      ])
      existing = {
         'chassis': {
            'DCS-7280DR3AK-36S': {
               'component': {
                  'Aboot()': {
                     'key1': 'value1',
                  },
                  'Scd(addr=0000:00:18.7)': {
                     'key2': 'value2',
                  },
               },
            },
         },
      }
      result = buildComponents('DCS-7280DR3AK-36S', inv, existing)
      self.assertEqual(result, {
         'chassis': {
            'DCS-7280DR3AK-36S': {
               'component': {
                  'Aboot()': {
                     'key1': 'value1',
                  },
                  'Scd(addr=0000:00:18.7)': {
                     'key2': 'value2',
                  },
                  'CormorantSysCpld(addr=13-0023)': {},
               },
            },
         },
      })

   def testModularInventoryComponents(self):
      supInv = _mockInventory([
         _mockProgrammable('Scd(addr=0000:ff:0b.3)'),
         _mockProgrammable('Ucd90160(addr=2-004e)'),
      ])
      fabricInv = _mockInventory([
         _mockProgrammable('Ucd90320(addr=18-0011)'),
      ])
      lcInv = _mockInventory([
         _mockProgrammable('Ucd90320(addr=10-0011)'),
         _mockProgrammable('Adm1266(addr=10-004f)'),
      ])
      modules = {
         'FABRIC-CARD0': fabricInv,
         'LINE-CARD0': lcInv,
      }

      result = buildComponents('DCS-7800-SUP1A', supInv)
      result['module'] = buildModules(modules)

      self.assertEqual(result, {
         'chassis': {
            'DCS-7800-SUP1A': {
               'component': {
                  'Scd(addr=0000:ff:0b.3)': {},
                  'Ucd90160(addr=2-004e)': {},
               },
            },
         },
         'module': {
            'FABRIC-CARD0': {
               'component': {
                  'Ucd90320(addr=18-0011)': {},
               },
            },
            'LINE-CARD0': {
               'component': {
                  'Ucd90320(addr=10-0011)': {},
                  'Adm1266(addr=10-004f)': {},
               },
            },
         },
      })

   def testModularInventoryComponentsWithExistingFile(self):
      existing = {
         'chassis': {
            'DCS-7800-SUP1A': {
               'component': {
                  'Scd(addr=0000:ff:0b.3)': {
                     'firmware': '/path/to/sup/fw',
                  },
               },
            },
         },
         'module': {
            'FABRIC-CARD0': {
               'component': {
                  'Ucd90320(addr=18-0011)': {
                     'firmware': '/path/to/fabric/fw',
                  },
               },
            },
         },
      }
      supInv = _mockInventory([
         _mockProgrammable('Scd(addr=0000:ff:0b.3)'),
         _mockProgrammable('Ucd90160(addr=2-004e)'),
      ])
      modules = {
         'FABRIC-CARD0': _mockInventory([
            _mockProgrammable('Ucd90320(addr=18-0011)'),
         ]),
      }
      result = buildComponents('DCS-7800-SUP1A', supInv, existing)
      result['module'] = buildModules(modules, existing)

      supComps = result['chassis']['DCS-7800-SUP1A']['component']

      self.assertEqual(supComps['Scd(addr=0000:ff:0b.3)'],
                       {'firmware': '/path/to/sup/fw'})
      self.assertEqual(supComps['Ucd90160(addr=2-004e)'], {})
      self.assertEqual(
         result['module']['FABRIC-CARD0']['component'],
         {'Ucd90320(addr=18-0011)': {'firmware': '/path/to/fabric/fw'}})

class PlatformComponentsUpdaterTest(unittest.TestCase):

   def setUp(self):
      self._chassisName = 'DCS-7050'
      self._platform = mock.MagicMock()
      self._srcContent = {
         'chassis': {
            self._chassisName: {
               'component': {},
            },
         },
      }
      self._tmpDir = tempfile.mkdtemp()
      self._srcPath = os.path.join(self._tmpDir, 'platform_components.json')
      with open(self._srcPath, 'w', encoding='utf-8') as f:
         json.dump(self._srcContent, f)

   def tearDown(self):
      if os.path.exists(self._srcPath):
         os.unlink(self._srcPath)
      if os.path.exists(self._tmpDir):
         os.rmdir(self._tmpDir)

   def _updater(self):
      with mock.patch(f'{UPDATER_MODULE}.getPlatformPath',
                      return_value=self._tmpDir), \
           mock.patch(f'{MODULE}.getSonicSku', return_value=self._chassisName):
         updater = PlatformComponentsUpdater(self._platform)
      updater.configPath = self._srcPath
      return updater

   def _patchInventory(self, inv):
      return mock.patch.object(self._platform, 'getInventory', return_value=inv)

   def _invWithComponent(self):
      return _mockInventory([_mockProgrammable('Aboot()')])

   # --- init ---

   def testInitExtractsChassisName(self):
      self.assertEqual(self._updater().chassisName, self._chassisName)

   # --- update: file handling ---

   def testUpdateMissingFileStartsFresh(self):
      os.unlink(self._srcPath)
      with self._patchInventory(_mockInventory()):
         self.assertTrue(self._updater().update())

   def testUpdateEmptyChassisStartsFresh(self):
      with open(self._srcPath, 'w', encoding='utf-8') as f:
         json.dump({'chassis': {}}, f)
      with self._patchInventory(_mockInventory()):
         self.assertTrue(self._updater().update())

   def testUpdateInvalidJsonStartsFresh(self):
      with open(self._srcPath, 'w', encoding='utf-8') as f:
         f.write('not valid json')
      with self._patchInventory(_mockInventory()):
         self.assertTrue(self._updater().update())

   # --- update: return value ---

   def testNoChangeReturnsFalse(self):
      with self._patchInventory(_mockInventory()):
         self.assertFalse(self._updater().update())

   def testUpdateReturnValues(self):
      with self._patchInventory(self._invWithComponent()):
         updater = self._updater()
         self.assertTrue(updater.update())
         self.assertFalse(updater.update())

   def testChangedInventoryReturnsTrue(self):
      inv1 = _mockInventory([_mockProgrammable('Aboot()')])
      inv2 = _mockInventory([
         _mockProgrammable('Aboot()'),
         _mockProgrammable('Scd(addr=0000:00:18.7)'),
      ])
      updater = self._updater()
      with self._patchInventory(inv1):
         updater.update()
      with self._patchInventory(inv2):
         self.assertTrue(updater.update())

   def testBuildExceptionReturnsFalse(self):
      inv = mock.MagicMock()
      inv.getProgrammables.side_effect = RuntimeError('hardware read failed')
      with self._patchInventory(inv):
         self.assertFalse(self._updater().update())

   # --- update: output content ---

   def testWrittenFile(self):
      self._srcContent['chassis'][self._chassisName]['component'] = {
         'Aboot()': {
            'key1': 'value1',
         },
      }
      with open(self._srcPath, 'w', encoding='utf-8') as f:
         json.dump(self._srcContent, f)

      inv = _mockInventory([
         _mockProgrammable('Aboot()'),
         _mockProgrammable('Scd(addr=0000:00:18.7)'),
      ])
      with self._patchInventory(inv):
         self._updater().update()

      with open(self._srcPath, encoding='utf-8') as f:
         written = json.load(f)

      components = written['chassis'][self._chassisName]['component']
      self.assertEqual(components['Aboot()'], {'key1': 'value1'})
      self.assertEqual(components['Scd(addr=0000:00:18.7)'], {})

   def testModularWrittenFile(self):
      self._platform = mock.MagicMock(spec=Supervisor)
      self._chassisName = 'DCS-7800-SUP1A'
      self._platform.getSlotId.return_value = 1
      self._platform.getInventory.return_value = _mockInventory([
         _mockProgrammable('Scd(addr=0000:ff:0b.3)'),
      ])

      fabric = mock.MagicMock()
      fabric.getRelativeSlotId.return_value = 0
      fabric.getInventory.return_value = _mockInventory([
         _mockProgrammable('Ucd90320(addr=18-0011)'),
      ])

      lc = mock.MagicMock()
      lc.getRelativeSlotId.return_value = 0
      lc.getInventory.return_value = _mockInventory([
         _mockProgrammable('Ucd90320(addr=10-0011)'),
      ])

      chassis = mock.MagicMock()
      chassis.iterSupervisors.return_value = [self._platform, None]
      chassis.iterFabrics.return_value = [None, fabric]
      chassis.iterLinecards.return_value = [lc, None]

      self._platform.getChassis.return_value = chassis

      updater = self._updater()
      self.assertTrue(updater.update())
      self.assertFalse(updater.update())

      with open(self._srcPath, encoding='utf-8') as f:
         written = json.load(f)

      self.assertEqual(
         written['chassis'][self._chassisName]['component'],
         {'Scd(addr=0000:ff:0b.3)': {}})
      self.assertEqual(set(written['module']),
                       {'SUPERVISOR0', 'FABRIC-CARD0', 'LINE-CARD0'})
      self.assertEqual(written['module']['SUPERVISOR0'], {'component': {}})
      self.assertEqual(
         written['module']['FABRIC-CARD0']['component'],
         {'Ucd90320(addr=18-0011)': {}})
      self.assertEqual(
         written['module']['LINE-CARD0']['component'],
         {'Ucd90320(addr=10-0011)': {}})

   def testSupervisorWithoutModules(self):
      self._platform = mock.MagicMock(spec=Supervisor)
      self._platform.getSlotId.return_value = 1
      self._platform.getInventory.return_value = self._invWithComponent()
      chassis = self._platform.getChassis.return_value
      chassis.iterSupervisors.return_value = [self._platform, None]
      chassis.iterFabrics.return_value = []
      chassis.iterLinecards.return_value = []

      self.assertTrue(self._updater().update())

      with open(self._srcPath, encoding='utf-8') as f:
         written = json.load(f)

      self.assertEqual(written, {
         'chassis': {
            self._chassisName: {'component': {'Aboot()': {}}},
         },
         'module': {
            'SUPERVISOR0': {'component': {}},
         },
      })

if __name__ == '__main__':
   unittest.main()
