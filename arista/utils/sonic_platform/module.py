#!/usr/bin/env python

from __future__ import print_function

import subprocess
import time

try:
   from arista.core.onie import OnieEeprom
   from arista.libs.ping import ping
   from arista.utils.rpc.helper import RpcClientSource, getGlobalRpcClient
   from arista.utils.sonic_platform.component import Component
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
   def __init__(self, parent, sku):
      ModuleBase.__init__(self)
      self._sku = sku
      self._inventory = sku.getInventory()
      self._eeprom = sku.getEeprom()
      self._parent = parent

      for fan in self._inventory.getFans():
         self._fan_list.append(Fan(None, fan))

      # TODO: index used here to allow thermal.get_position_in_parent() to return
      # unique values but we want a proper way of uniquely identifying sensors
      for index, thermal in enumerate(self._inventory.getTemps()):
         self._thermal_list.append(Thermal(index + 1, thermal))
      # TODO: Add Xcvrs? Only linecards have access to them

      # NOTE: only declare module components when on the supervisor
      #       on linecards the components are attached to the chassis
      if self._parent._platform != sku:
         for programmable in self._inventory.getProgrammables():
            self._component_list.append(Component(self, programmable))

   def _get_rpc_client(self):
      return getGlobalRpcClient(source=self.RPC_CLIENT_SOURCE)

   def _get_eeprom(self):
      return self._eeprom

   def get_presence(self):
      return self._sku.getPresence()

   def get_model(self):
      return self._get_eeprom().get('SKU')

   def get_serial(self):
      return self._get_eeprom().get('SerialNumber')

   def get_revision(self):
      rev = self._get_eeprom().get('HwApi')
      return '.'.join('%02x' % x for x in rev) if rev is not None else rev

   def get_status(self):
      # TODO: implement logic for this
      return True

   def is_replaceable(self):
      return True

   def get_base_mac(self):
      mac = self._get_eeprom().get('MAC')
      if mac is None:
         raise NotImplementedError
      return mac

   def get_system_eeprom_info(self):
      return OnieEeprom(self._get_eeprom()).data(filterOut=[0x28])

   def get_description(self):
      name = self._get_eeprom().get('SKU')
      if name is not None:
         return name
      return self._get_eeprom().get('SID', 'Unknown')

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

   def set_admin_state(self, up):
      return False

   def get_maximum_consumed_power(self):
      return float(self._sku.MAX_POWER_DRAW)

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
   RPC_CLIENT_SOURCE = RpcClientSource.FROM_SUPERVISOR

   def get_name(self):
      mid = self.get_slot() - 1
      return '%s%s' % (self.MODULE_TYPE_SUPERVISOR, mid)

   def get_type(self):
      return self.MODULE_TYPE_SUPERVISOR

   def reboot(self, reboot_type):
      result = self._get_rpc_client().supervisorSelfReboot()
      return result['status']

class FabricModule(Module):
   RPC_CLIENT_SOURCE = RpcClientSource.FROM_SUPERVISOR

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

   def set_admin_state(self, up):
      if up:
         result = self._get_rpc_client().fabricSetup(self._sku.getSlotId())
      else:
         result = self._get_rpc_client().fabricClean(self._sku.getSlotId())
      return result.get('status', False)

   def reboot(self, reboot_type):
      setupResult = self._get_rpc_client().fabricSetup(self._sku.getSlotId(),
                                                       powerCycleIfOn=True)
      return setupResult['status']

class LinecardModule(Module):
   RPC_CLIENT_SOURCE = RpcClientSource.FROM_SUPERVISOR

   def get_name(self):
      return '%s%s' % (self.MODULE_TYPE_LINE, self._sku.getRelativeSlotId())

   def get_type(self):
      return self.MODULE_TYPE_LINE

   def is_midplane_reachable(self):
      if not self.get_presence() or not self._sku.poweredOn():
         return False
      return ping(self.get_midplane_ip())

   def get_all_asics(self):
      self._asic_list = []
      for asic_index, asic in enumerate(self._sku.asics):
         self._asic_list.append((asic_index, str(asic.addr)))
      return self._asic_list

   def set_admin_state(self, up):
      if up:
         result = self._get_rpc_client().linecardSetup(self._sku.getSlotId())
      else:
         result = self._get_rpc_client().linecardClean(self._sku.getSlotId())
      return result.get('status', False)

   def reboot(self, reboot_type):
      setupResult = self._get_rpc_client().linecardSetup(self._sku.getSlotId(),
                                                         powerCycleIfOn=True)
      return setupResult['status']

class LinecardSelfModule(LinecardModule):
   RPC_CLIENT_SOURCE = RpcClientSource.FROM_LINECARD

   def get_name(self):
      return self.MODULE_TYPE_LINE

   def reboot(self, reboot_type):
      subprocess.run(['sync'], check=False)
      time.sleep(1)
      result = self._get_rpc_client().linecardSelfPowerCycle()
      return result['status']

class LinecardSupervisorModule(SupervisorModule):
   RPC_CLIENT_SOURCE = RpcClientSource.FROM_LINECARD

   # pylint: disable=super-init-not-called
   def __init__(self, parent, linecard):
      ModuleBase.__init__(self)
      self._linecard = linecard
      self._slotId = 1
      self._eeprom = None
      self._parent = parent
      self._supMaxPowerDraw = None

   def _get_eeprom(self):
      if self._eeprom is None:
         self._eeprom = self._get_rpc_client().getSupervisorEeprom()
      return self._eeprom

   def get_presence(self):
      return True

   def get_revision(self):
      return None

   def get_status(self):
      return True

   def is_replaceable(self):
      return True

   def get_slot(self):
      return self._slotId

   def get_oper_status(self):
      return self.MODULE_STATUS_ONLINE

   def reboot(self, reboot_type):
      return False

   def set_admin_state(self, up):
      return False

   def get_maximum_consumed_power(self):
      if self._supMaxPowerDraw is None:
         power = float(self._get_rpc_client().getSupervisorMaxPowerDraw())
         self._supMaxPowerDraw = power
      return self._supMaxPowerDraw

   def is_midplane_reachable(self):
      return ping(self.get_midplane_ip())

   def get_position_in_parent(self):
      return self._slotId
