#!/usr/bin/env python

import json
import os
import tempfile
import unittest
from unittest import mock

from ..platform_config_updater import PlatformConfigUpdater

MODULE = 'arista.utils.config.platform_config_updater'
UPDATER_MODULE = 'arista.utils.config.updater'

def _named(name):
   m = mock.MagicMock()
   m.getName.return_value = name
   m.getLed.return_value = None
   return m

def _fanSlot(name, fans=None, led=None):
   m = mock.MagicMock()
   m.getName.return_value = name
   m.getFans.return_value = fans or []
   m.getLed.return_value = led
   return m

def _psuSlot(name, fans=None, led=None):
   psu = mock.MagicMock()
   psu.getFans.return_value = fans or []
   psu.getCapacity.return_value = 0
   psu.getTemps.return_value = []
   m = mock.MagicMock()
   m.getName.return_value = name
   m.getLed.return_value = led
   m.getPsu.return_value = psu if fans is not None else None
   return m

def _programmable(name):
   component = mock.MagicMock()
   component.__str__ = mock.Mock(return_value=name)
   prog = mock.MagicMock()
   prog.getComponent.return_value = component
   return prog

def _inventory(programmables=None, fanSlots=None, fans=None,
               psuSlots=None, temps=None, xcvrSlots=None):
   inv = mock.MagicMock()
   inv.getProgrammables.return_value = programmables or []
   inv.getFanSlots.return_value = fanSlots or []
   inv.getFans.return_value = fans or []
   inv.getPsuSlots.return_value = psuSlots or []
   inv.getTemps.return_value = temps or []
   inv.getXcvrSlots.return_value = xcvrSlots or {}
   return inv

class PlatformConfigUpdaterTest(unittest.TestCase):

   def setUp(self):
      self._chassisName = 'DCS-7050'
      self._platform = mock.MagicMock()
      self._srcContent = {
         'chassis': {
            'name': self._chassisName,
            'components': [],
            'fan_drawers': [],
            'psus': [],
            'thermals': [],
            'sfps': [],
         },
         'interfaces': {
            'Ethernet0': {
               'lanes': '0',
            },
         },
      }
      self._tmpDir = tempfile.mkdtemp()
      self._srcPath = os.path.join(self._tmpDir, 'platform.json')
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
         updater = PlatformConfigUpdater(self._platform)
      updater.configPath = self._srcPath
      return updater

   def _patchInventory(self, inv):
      return mock.patch.object(self._platform, 'getInventory', return_value=inv)

   def testUpdateReturnsFalseIfNoSourceFile(self):
      updater = self._updater()
      updater.configPath = '/nonexistent/platform.json'
      self.assertFalse(updater.update())

   def testUpdateReturnsFalseIfInvalidJson(self):
      with open(self._srcPath, 'w', encoding='utf-8') as f:
         f.write('not valid json')
      self.assertFalse(self._updater().update())

   def testNoChangeReturnsFalse(self):
      with self._patchInventory(_inventory()):
         self.assertFalse(self._updater().update())

   def testComponentOrderChangeWritesUpdatedOrder(self):
      components = [
         {'name': 'Aboot()', 'extra': 'Aboot'},
         {'name': 'Scd(addr=0000:00:18.7)', 'extra': 'Scd'},
      ]
      self._srcContent['chassis']['components'] = components
      with open(self._srcPath, 'w', encoding='utf-8') as f:
         json.dump(self._srcContent, f)

      inv = _inventory(programmables=[
         _programmable('Scd(addr=0000:00:18.7)'),
         _programmable('Aboot()'),
      ])
      updater = self._updater()
      with self._patchInventory(inv):
         self.assertTrue(updater.update())

      self.assertFalse(updater.changed)
      self.assertTrue(updater.componentsOrderChanged)
      with open(self._srcPath, encoding='utf-8') as f:
         written = json.load(f)
      self.assertEqual(written['chassis']['components'], [
         {'name': 'Scd(addr=0000:00:18.7)', 'extra': 'Scd'},
         {'name': 'Aboot()', 'extra': 'Aboot'},
      ])

   def testUpdateReturnValues(self):
      updater = self._updater()
      with self._patchInventory(_inventory(fanSlots=[_fanSlot('FanTray1')])):
         self.assertTrue(updater.update())
         self.assertFalse(updater.update())
      with self._patchInventory(_inventory(
            fanSlots=[_fanSlot('FanTray1'), _fanSlot('FanTray2')])):
         self.assertTrue(updater.update())

   def testBuildExceptionReturnsFalse(self):
      inv = mock.MagicMock()
      inv.getFanSlots.side_effect = RuntimeError('hardware read failed')
      with self._patchInventory(inv):
         self.assertFalse(self._updater().update())

   def testFullInventory(self):
      led = mock.MagicMock()

      rail = mock.MagicMock()
      rail.voltage.exists.return_value = True
      rail.voltage.max.exists.return_value = True
      rail.voltage.min.exists.return_value = True
      rail.current.exists.return_value = True
      rail.power.exists.return_value = True

      psu1 = mock.MagicMock()
      psu1Fan = _named('Psu1/Fan1')
      psu1Fan.getLed.return_value = led
      psu1.getFans.return_value = [psu1Fan]
      psu1.getCapacity.return_value = 100
      psu1.getTemps.return_value = [mock.MagicMock()]
      psu1.getRails.return_value = [mock.MagicMock(), rail]

      psuSlot1 = mock.MagicMock()
      psuSlot1.getName.return_value = 'psu1'
      psuSlot1.getLed.return_value = led
      psuSlot1.getPsu.return_value = psu1

      self._srcContent['chassis']['fans'] = [{'name': 'legacy fan'}]
      with open(self._srcPath, 'w', encoding='utf-8') as f:
         json.dump(self._srcContent, f)

      fan1 = _named('Fan1')
      fan1.getLed.return_value = led

      inv = _inventory(
         programmables=[
            _programmable('Aboot()'),
            _programmable('Scd(addr=0000:00:18.7)'),
         ],
         fanSlots=[
            _fanSlot('FanTray1', fans=[fan1, _named('Fan2')], led=led),
            _fanSlot('FanTray2', fans=[_named('Fan3')]),
         ],
         psuSlots=[
            psuSlot1,
            _psuSlot('psu2', fans=None),
         ],
         temps=[
            _named('Temp1'),
            _named('Temp2'),
         ],
         xcvrSlots={
            1: _named('Ethernet1'),
            2: _named('Ethernet2'),
         },
      )
      with self._patchInventory(inv):
         self._updater().update()

      with open(self._srcPath, encoding='utf-8') as f:
         written = json.load(f)

      chassis = written['chassis']
      self.assertEqual(chassis['name'], self._chassisName)
      self.assertEqual(chassis['components'], [
         {'name': 'Aboot()'},
         {'name': 'Scd(addr=0000:00:18.7)'},
      ])
      self.assertNotIn('fans', chassis)

      drawers = chassis['fan_drawers']
      self.assertEqual(len(drawers), 2)
      self.assertEqual(drawers[0], {
         'name': 'FanTray1',
         'status_led': {
            'controllable': True,
         },
         'fans': [
            {
               'name': 'Fan1',
               'status_led': {
                  'controllable': True,
               },
            },
            {
               'name': 'Fan2',
               'status_led': {
                  'controllable': False,
               },
            },
         ],
      })
      self.assertFalse(drawers[1]['status_led']['controllable'])

      psus = chassis['psus']
      self.assertEqual(len(psus), 2)
      self.assertEqual(psus[0], {
         'name': 'psu1',
         'fans': [
            {
               'name': 'Psu1/Fan1',
               'speed': {
                  'controllable': False,
               },
               'status_led': {
                  'controllable': True,
               },
            },
         ],
         'status_led': {
            'controllable': True,
         },
         'voltage_high_threshold': True,
         'voltage_low_threshold': True,
         'voltage': True,
         'current': True,
         'power': True,
         'max_power': True,
         'temperature': True,
      })
      self.assertEqual(psus[1]['fans'], [])

      self.assertEqual(chassis['thermals'], [
         {
            'name': 'Temp1',
            'controllable': False,
         },
         {
            'name': 'Temp2',
            'controllable': False,
         },
      ])
      self.assertCountEqual(chassis['sfps'], [
         {'name': 'Ethernet1'},
         {'name': 'Ethernet2'},
      ])
      self.assertEqual(written['interfaces'], self._srcContent['interfaces'])

   def testPreservesExtraFields(self):
      self._srcContent['chassis']['custom_field'] = 'preserved'
      self._srcContent['chassis']['fan_drawers'] = [
         {
            'name': 'FanTray1',
            'status_led': 'malformed',
            'fans': [
               {
                  'name': 'Fan1',
                  'status_led': {
                     'controllable': True,
                  },
                  'fan_extra': 'keep',
               },
            ],
            'drawer_extra': 'keep',
         },
      ]
      self._srcContent['chassis']['psus'] = [
         {
            'name': 'psu1',
            'fans': [
               {
                  'name': 'Psu1/Fan1',
                  'speed': {
                     'controllable': True,
                  },
                  'status_led': {
                     'controllable': True,
                  },
                  'psu_fan_extra': 'keep',
               },
            ],
            'status_led': {
               'controllable': True,
            },
            'voltage_high_threshold': False,
            'voltage_low_threshold': False,
            'voltage': False,
            'current': False,
            'power': False,
            'max_power': False,
            'temperature': False,
            'psu_extra': 'keep',
         },
      ]
      self._srcContent['chassis']['thermals'] = [
         {
            'name': 'Old Temp',
            'controllable': False,
         },
         {
            'name': 'Temp1',
            'controllable': True,
            'thermal_extra': 'keep',
         },
      ]
      with open(self._srcPath, 'w', encoding='utf-8') as f:
         json.dump(self._srcContent, f)
      inv = _inventory(
         fanSlots=[_fanSlot('FanTray1', fans=[_named('Fan1')])],
         psuSlots=[_psuSlot('psu1', fans=[_named('Psu1/Fan1')])],
         temps=[
            _named('Temp1'),
            _named('Temp2'),
         ],
      )
      with self._patchInventory(inv):
         self._updater().update()
      with open(self._srcPath, encoding='utf-8') as f:
         written = json.load(f)
      chassis = written['chassis']
      self.assertEqual(chassis['custom_field'], 'preserved')
      drawer = chassis['fan_drawers'][0]
      self.assertEqual(drawer['drawer_extra'], 'keep')
      self.assertEqual(drawer['status_led']['controllable'], False)
      self.assertEqual(drawer['fans'][0]['fan_extra'], 'keep')
      self.assertEqual(drawer['fans'][0]['status_led']['controllable'], True)
      psu = chassis['psus'][0]
      self.assertEqual(psu['psu_extra'], 'keep')
      self.assertEqual(psu['status_led']['controllable'], True)
      self.assertEqual(psu['fans'][0]['psu_fan_extra'], 'keep')
      self.assertEqual(psu['fans'][0]['speed']['controllable'], True)
      self.assertEqual(psu['fans'][0]['status_led']['controllable'], True)
      self.assertEqual(chassis['thermals'], [
         {
            'name': 'Temp1',
            'controllable': True,
            'thermal_extra': 'keep',
         },
         {
            'name': 'Temp2',
            'controllable': False,
         },
      ])

   def testWriteFailureReturnsFalse(self):
      inv = _inventory(fanSlots=[_fanSlot('FanTray1')])
      with self._patchInventory(inv):
         with mock.patch(f'{MODULE}.atomicWrite', side_effect=OSError('disk full')):
            self.assertFalse(self._updater().update())

if __name__ == '__main__':
   unittest.main()
