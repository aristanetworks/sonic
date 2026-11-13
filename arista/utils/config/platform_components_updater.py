#!/usr/bin/env python

import json

from ...core.inventory import Inventory
from ...core.log import getLogger
from ...core.platform import getSonicSku, sanitizeProductName
from ...core.supervisor import Supervisor
from ...libs.fs import atomicWrite
from .updater import ConfigUpdater

logging = getLogger(__name__)

def buildComponents(chassisName, inv, existing=None):
   existingComponents = (existing or {}).get('chassis', {}).get(chassisName, {}) \
      .get('component', {})
   components = {
      str(prog.getComponent()): existingComponents.get(str(prog.getComponent()), {})
      for prog in inv.getProgrammables()
   }
   return {
      'chassis': {
         chassisName: {
            'component': components,
         },
      },
   }

def buildModules(modules, existing=None):
   existingModules = (existing or {}).get('module', {})
   result = {}
   for moduleName, moduleInv in modules.items():
      existingModComps = existingModules.get(moduleName, {}).get('component', {})
      result[moduleName] = {
         'component': {
            str(prog.getComponent()): existingModComps.get(
               str(prog.getComponent()), {})
            for prog in moduleInv.getProgrammables()
         },
      }
   return result

class PlatformComponentsUpdater(ConfigUpdater):

   FILENAME = 'platform_components.json'

   def __init__(self, platform):
      super().__init__(platform)
      self.chassisName = sanitizeProductName(
         getSonicSku(self.platform.getEeprom()))

   def __str__(self):
      return f'{self.__class__.__name__}({self.chassisName})'

   def _getModules(self):
      chassis = self.platform.getChassis()
      modules = {}
      for sup in chassis.iterSupervisors(presentOnly=False):
         if sup is not None:
            slotName = f'SUPERVISOR{sup.getSlotId() - 1}'
            # fwutil requires the module entry even though the local
            # supervisor's components belong to the chassis.
            modules[slotName] = (sup.getInventory() if sup != self.platform
                                 else Inventory())
      chassis.loadFabrics()
      for fabric in chassis.iterFabrics(presentOnly=False):
         if fabric is not None:
            slotName = f'FABRIC-CARD{fabric.getRelativeSlotId()}'
            modules[slotName] = fabric.getInventory()
      chassis.loadLinecards()
      for lc in chassis.iterLinecards(presentOnly=False):
         if lc is not None:
            slotName = f'LINE-CARD{lc.getRelativeSlotId()}'
            modules[slotName] = lc.getInventory()
      return modules

   def update(self):
      """Rebuild platform_components.json from the arista inventory.

      Returns True if the file was written, False otherwise (no change or error).
      """
      try:
         with open(self.configPath, encoding='utf-8') as f:
            existingData = json.load(f)
         if not existingData.get('chassis'):
            logging.warning('%s: %s has no chassis entry, starting fresh',
                            self, self.configPath)
            existingData = {}
      except Exception as e:  # pylint: disable=broad-except
         logging.warning('%s: failed to read %s, starting fresh: %s',
                         self, self.configPath, e)
         existingData = {}

      try:
         modules = None
         inv = self.platform.getInventory()
         if isinstance(self.platform, Supervisor):
            modules = self._getModules()
         newData = buildComponents(self.chassisName, inv, existingData)
         if modules:
            newData['module'] = buildModules(modules, existingData)
      except Exception as e:  # pylint: disable=broad-except
         logging.error('%s: failed to build component info from inventory: %s',
                       self, e)
         return False

      if existingData == newData:
         logging.info('%s: no changes to %s', self, self.FILENAME)
         return False

      try:
         atomicWrite(self.configPath,
                     json.dumps(newData, indent=4, separators=(',', ': ')))
      except OSError:
         logging.error('%s: failed to write %s', self, self.configPath)
         return False

      logging.info('%s: %s has changed', self, self.FILENAME)
      return True
