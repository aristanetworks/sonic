#!/usr/bin/env python

from __future__ import print_function

try:
   from arista.core.onie import OnieEeprom
   from arista.utils.sonic_platform.fan import Fan
   from arista.utils.sonic_platform.thermal import Thermal
   from sonic_platform_base.module_base import ModuleBase
except ImportError as e:
   raise ImportError("%s - required module not found" % e)

class Module(ModuleBase):
   """
   Platform-specific class for interfacing with a module
   (supervisor module, line card module, etc. applicable for a modular chassis)
   """
   def __init__(self, sku):
      ModuleBase.__init__(self)
      self._sku = sku
      self._inventory = sku.getInventory()
      self._eeprom = sku.getEeprom()

      for fan in self._inventory.getFans():
         self._fan_list.append(Fan(None, fan))

      # TODO: index used here to allow thermal.get_position_in_parent() to return
      # unique values but we want a proper way of uniquely identifying sensors
      for index, thermal in enumerate(self._inventory.getTemps()):
         self._thermal_list.append(Thermal(index + 1, thermal))
      # TODO: Add Xcvrs? Only linecards have access to them

   def get_presence(self):
      return self._sku.getPresence()

   def get_model(self):
      return self._sku.getEeprom().get('SKU')

   def get_serial(self):
      return self._sku.getEeprom().get('SerialNumber')

   def get_status(self):
      # TODO: implement logic for this
      return True

   def is_replaceable(self):
      return True

   def get_base_mac(self):
      mac = self._sku.getEeprom().get('MAC')
      if mac is None:
         raise NotImplementedError
      return mac

   def get_system_eeprom_info(self):
      return OnieEeprom(self._eeprom).data(filterOut=[0x28])

   def get_description(self):
      name = self._sku.getEeprom().get('SKU')
      if name is not None:
         return name
      return self._sku.getEeprom().get('SID', 'Unknown')

   def get_slot(self):
      return self._sku.getSlotId()

   def get_oper_status(self):
      # TODO: Implement the following modes
      #  - MODULE_STATUS_POWERED_DOWN
      #  - MODULE_STATUS_PRESENT
      #  - MODULE_STATUS_FAULT
      if not self.get_presence():
         return self.MODULE_STATUS_EMPTY
      if not self._sku.poweredOn():
         return self.MODULE_STATUS_OFFLINE
      if not self.get_status():
         return self.MODULE_STATUS_FAULT
      return self.MODULE_STATUS_ONLINE

   def reboot(self, reboot_type):
      # TODO: implement reboot mechanism
      return False

   def set_admin_state(self, up):
      # TODO: implement power on/off methods
      return False

   def get_maximum_consumed_power(self):
      # TODO: add power consumption to various skus
      return 0

   def is_midplane_reachable(self):
      return True

   def get_position_in_parent(self):
      return self._sku.getSlotId()

   def get_midplane_ip(self):
      # TODO: will this work from the linecard side? comment is not that clear
      return "127.100.%d.1" % self.get_slot()

   def get_all_asics(self):
      return []

class SupervisorModule(Module):
   def get_name(self):
      mid = self._sku.getSlotId() - 1
      return '%s%s' % (self.MODULE_TYPE_SUPERVISOR, mid)

   def get_type(self):
      return self.MODULE_TYPE_SUPERVISOR

class FabricModule(Module):
   def get_name(self):
      return '%s%s' % (self.MODULE_TYPE_FABRIC, self._sku.getRelativeSlotId())

   def get_type(self):
      return self.MODULE_TYPE_FABRIC

   def is_midplane_reachable(self):
      return False

   def get_all_asics(self):
      self._asic_list = []
      starting_index = self._sku.getRelativeSlotId() * len(self._sku.asics)
      for asic_index, asic in enumerate(self._sku.asics):
         global_asic_index = starting_index + asic_index
         self._asic_list.append((global_asic_index, str(asic.addr)))
      return self._asic_list

class LinecardModule(Module):
   def get_name(self):
      return '%s%s' % (self.MODULE_TYPE_LINE, self._sku.getRelativeSlotId())

   def get_type(self):
      return self.MODULE_TYPE_LINE

   def get_all_asics(self):
      self._asic_list = []
      for asic_index, asic in enumerate(self._sku.asics):
         self._asic_list.append((asic_index, str(asic.addr)))
      return self._asic_list
