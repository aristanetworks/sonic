#!/usr/bin/env python

import json

from ...core.log import getLogger
from ...core.platform import getSonicSku, sanitizeProductName
from ...libs.fs import atomicWrite
from .updater import ConfigUpdater

logging = getLogger(__name__)

def _mergeElementsByName(existing, new):
   """Merge items from new into existing matched by name, preserving extra fields.
   Adds non-matching objects from new, drops non-matching objects from existing.

   Returns (merged_list, changed).
   """
   byName = {item['name']: item for item in existing}
   result = []
   changed = len(existing) != len(new)
   for item in new:
      base = dict(byName.get(item['name'], {}))
      merged = dict(base)
      merged.update(item)
      if merged != base:
         changed = True
      result.append(merged)
   return result, changed

class PlatformConfigUpdater(ConfigUpdater):

   FILENAME = 'platform.json'

   def __init__(self, platform):
      super().__init__(platform)
      self.chassisName = sanitizeProductName(
         getSonicSku(self.platform.getEeprom()))
      self.changed = False
      self.componentsOrderChanged = False

   def __str__(self):
      return f'{self.__class__.__name__}({self.chassisName})'

   def _merge(self, existing, new):
      result, changed = _mergeElementsByName(existing, new)
      self.changed = self.changed or changed
      return result

   def _controlField(self, existing, field, default=False):
      """Preserve a matched control field, filling controllable if missing.
      Replace malformed non-dict values with a default control field."""
      control = existing.get(field, {})
      if not isinstance(control, dict):
         control = {}
      control = dict(control)
      control.setdefault('controllable', default)
      return control

   def _buildComponents(self, inv, existing):
      components = [
         {'name': str(prog.getComponent())}
         for prog in inv.getProgrammables()
      ]
      result = self._merge(existing, components)

      self.componentsOrderChanged = not self.changed and \
         [item['name'] for item in existing] != \
            [item['name'] for item in components]
      return result

   def _buildFans(self, fans, existing):
      byName = {f['name']: f for f in existing}
      newFans = []
      for fan in fans:
         newFans.append({
            'name': fan.getName(),
            'status_led': self._controlField(
               byName.get(fan.getName(), {}),
               'status_led',
               fan.getLed() is not None,
            ),
         })
      return self._merge(existing, newFans)

   def _buildFanDrawers(self, inv, existing):
      byName = {d['name']: d for d in existing}

      def drawer(name, led, fans):
         existingDrawer = byName.get(name, {})
         return {
            'name': name,
            'status_led': self._controlField(
               existingDrawer,
               'status_led',
               led is not None,
            ),
            'fans': self._buildFans(
               fans,
               existingDrawer.get('fans', []),
            ),
         }

      fanSlots = inv.getFanSlots()
      if fanSlots:
         drawers = [
            drawer(slot.getName(), slot.getLed(), slot.getFans())
            for slot in fanSlots
         ]
      else:
         drawers = [
            drawer(f'fixed{fan.getId()}', fan.getLed(), [fan])
            for fan in inv.getFans()
         ]
      return self._merge(existing, drawers)

   def _buildPsuFans(self, fans, existing):
      byName = {f['name']: f for f in existing}

      def psuFan(fan):
         name = fan.getName()
         existingFan = byName.get(name, {})
         return {
            'name': name,
            'speed': self._controlField(
               existingFan,
               'speed',
            ),
            'status_led': self._controlField(
               existingFan,
               'status_led',
               fan.getLed() is not None,
            ),
         }

      return self._merge(existing, [
         psuFan(fan)
         for fan in fans
      ])

   def _buildPsus(self, inv, existing):
      byName = {p['name']: p for p in existing}
      psus = []
      for slot in inv.getPsuSlots():
         name = slot.getName()
         psu = slot.getPsu()

         psuFans = []
         rails = []
         if psu is not None:
            newFans = psu.getFans()
            # getFans() returns [] when PMBus is unavailable (e.g. simulation).
            # Preserve existing entries rather than overwriting with an empty list.
            if newFans:
               psuFans = self._buildPsuFans(
                  newFans,
                  byName.get(name, {}).get('fans', []),
               )
            else:
               psuFans = byName.get(name, {}).get('fans', [])

            rails = psu.getRails()

         outputRail = rails[1] if len(rails) > 1 else None

         psus.append({
            'name': name,
            'fans': psuFans,
            'status_led': self._controlField(
               byName.get(name, {}),
               'status_led',
               slot.getLed() is not None,
            ),
            'voltage': outputRail is not None and outputRail.voltage.exists(),
            'voltage_high_threshold': \
               outputRail is not None and outputRail.voltage.max.exists(),
            'voltage_low_threshold': \
               outputRail is not None and outputRail.voltage.min.exists(),
            'current': outputRail is not None and outputRail.current.exists(),
            'power': outputRail is not None and outputRail.power.exists(),
            'temperature': len(psu.getTemps()) > 0 if psu else False,
            'max_power': psu.getCapacity() > 0 if psu else False,
         })

      return self._merge(existing, psus)

   def _buildThermals(self, inv, existing):
      byName = {t['name']: t for t in existing}
      return self._merge(existing, [
         {
            'name': t.getName(),
            'controllable': byName.get(t.getName(), {}).get(
               'controllable', False),
         }
         for t in inv.getTemps()
      ])

   def _buildSfps(self, inv, existing):
      return self._merge(existing, [
         {'name': slot.getName()}
         for slot in inv.getXcvrSlots().values()
      ])

   def update(self):
      """Update platform.json chassis section from the arista inventory.

      Returns True if the file was written, False otherwise (no change or error).
      """
      try:
         with open(self.configPath, encoding='utf-8') as f:
            platformJson = json.load(f)
      except Exception as e:  # pylint: disable=broad-except
         logging.error('%s: failed to read %s: %s', self, self.configPath, e)
         return False

      chassis = platformJson.get('chassis', {})
      self.changed = chassis.get('name') != self.chassisName
      self.componentsOrderChanged = False

      try:
         inv = self.platform.getInventory()
         components = self._buildComponents(inv, chassis.get('components', []))
         fanDrawers = self._buildFanDrawers(inv, chassis.get('fan_drawers', []))
         psus = self._buildPsus(inv, chassis.get('psus', []))
         thermals = self._buildThermals(inv, chassis.get('thermals', []))
         sfps = self._buildSfps(inv, chassis.get('sfps', []))
      except Exception as e:  # pylint: disable=broad-except
         logging.error('%s: failed to build chassis info from inventory: %s',
                       self, e)
         return False

      if 'fans' in chassis:
         self.changed = True

      if not self.changed and not self.componentsOrderChanged:
         logging.info('%s: no changes to %s', self, self.FILENAME)
         return False

      chassis.pop('fans', None)
      chassis.update({
         'name': self.chassisName,
         'components': components,
         'fan_drawers': fanDrawers,
         'psus': psus,
         'thermals': thermals,
         'sfps': sfps,
      })
      platformJson['chassis'] = chassis

      try:
         atomicWrite(self.configPath,
                     json.dumps(platformJson, indent=4, separators=(',', ': ')))
      except OSError:
         logging.error('%s: failed to write %s', self, self.configPath)
         return False

      orderStr = ''
      if self.componentsOrderChanged:
         orderStr = ' (components order only)'

      logging.info('%s: %s has changed%s', self, self.configPath, orderStr)
      return True
