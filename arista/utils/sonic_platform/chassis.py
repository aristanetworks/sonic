#!/usr/bin/env python

from __future__ import division, print_function

import copy
import select
import time

try:
   from sonic_platform_base.chassis_base import ChassisBase
   from arista.core import thermal_control
   from arista.core.card import Card
   from arista.core.cause import getReloadCauseManager
   from arista.core.config import Config
   from arista.core.onie import OnieEeprom
   from arista.core.platform import readPrefdl
   from arista.core.supervisor import Supervisor
   from arista.utils.sonic_platform.eeprom import Eeprom
   from arista.utils.sonic_platform.fan import Fan
   from arista.utils.sonic_platform.fan_drawer import FanDrawer, FanDrawerLegacy
   from arista.utils.sonic_platform.module import (
      SupervisorModule,
      FabricModule,
      LinecardModule,
   )
   from arista.utils.sonic_platform.psu import Psu
   from arista.utils.sonic_platform.sfp import Sfp
   from arista.utils.sonic_platform.thermal import Thermal
   from arista.utils.sonic_platform.watchdog import Watchdog
except ImportError as e:
   raise ImportError("%s - required module not found" % e)

def sanitizeProductName(name):
   # NOTE: sonic-mgmt tests expect exact match with platform.json
   #       however since we use the same platform folder for variants it leads
   #       to tests failing.
   suffixes = ['-ES', '-M', '-SSD']
   for suffix in suffixes:
      if name.endswith(suffix):
         return name[:-len(suffix)]
   return name

class Chassis(ChassisBase):
   REBOOT_CAUSE_DICT = {
      'unknown':ChassisBase.REBOOT_CAUSE_NON_HARDWARE,
      'powerloss': ChassisBase.REBOOT_CAUSE_POWER_LOSS,
      'overtemp': ChassisBase.REBOOT_CAUSE_THERMAL_OVERLOAD_OTHER,
      'reboot': ChassisBase.REBOOT_CAUSE_NON_HARDWARE,
      'watchdog': ChassisBase.REBOOT_CAUSE_WATCHDOG,
      'under-voltage': ChassisBase.REBOOT_CAUSE_HARDWARE_OTHER,
      'over-voltage': ChassisBase.REBOOT_CAUSE_HARDWARE_OTHER,
   }

   # Intervals in milliseconds
   POLL_INTERVAL = 1000.

   def __init__(self, platform):
      ChassisBase.__init__(self)
      self._platform = platform
      self._eeprom = Eeprom(readPrefdl())
      self._inventory = platform.getInventory()
      if isinstance(platform, Supervisor):
         chassis = platform.getChassis()
         for supervisor in chassis.iterSupervisors(presentOnly=False):
            if supervisor is not None:
               self._module_list.append(SupervisorModule(supervisor))
         chassis.loadFabrics()
         for fabric in chassis.iterFabrics(presentOnly=False):
            self._module_list.append(FabricModule(fabric))
         chassis.loadLinecards()
         for fabric in chassis.iterLinecards(presentOnly=False):
            self._module_list.append(LinecardModule(fabric))

      if self._inventory.getFanSlots():
         for slot in self._inventory.getFanSlots():
            self._fan_drawer_list.append(FanDrawer(self, slot))
      else:
         # TODO: Remove this block of code once FanDrawer is implemented everywhere
         for fan in self._inventory.getFans():
            self._fan_list.append(Fan(None, fan))
         for fan in self._fan_list:
            self._fan_drawer_list.append(FanDrawerLegacy(fan))
      for slot in self._inventory.getPsuSlots():
         self._psu_list.append(Psu(slot))
      self._sfp_list = []
      if self._inventory and self._inventory.portEnd:
         self._sfp_list = [None] * (self._inventory.portEnd)
         for index, sfp in self._inventory.getXcvrs().items():
            self._sfp_list[index - 1] = Sfp(index, sfp)
      # TODO: index used here to allow thermal.get_position_in_parent() to return
      # unique values but we want a proper way of uniquely identifying sensors
      for index, thermal in enumerate(self._inventory.getTemps()):
         self._thermal_list.append(Thermal(index + 1, thermal))
      self._watchdog = Watchdog(self._inventory.getWatchdog())

      self._interrupt_dict, self._presence_dict = \
         self._get_interrupts_for_components()

   def get_name(self):
      return sanitizeProductName(self._eeprom.prefdl().getField("SKU"))

   def get_presence(self):
      return True

   def get_model(self):
      return self._eeprom.prefdl().getField("SKU")

   def get_base_mac(self):
      return self._eeprom.prefdl().getField("MAC")

   def get_serial(self):
      return self._eeprom.prefdl().getField("SerialNumber")

   def get_serial_number(self):
      return self.get_serial()

   def get_system_eeprom_info(self):
      return OnieEeprom(self._eeprom.read_eeprom()).data()

   def get_status(self):
      return True

   def set_status_led(self, color):
      # FIXME: add support for blinking
      color = color.replace('_blink', '')
      return self._inventory.getLed('status').setColor(color)

   def get_status_led(self):
      return self._inventory.getLed('status').getColor()

   def get_sfp(self, index):
      # NOTE: the platform API specifies _sfp_list to be 0 based as well as get_sfp
      #       however, in practice the get_sfp is called with 1 based indexes
      return super(Chassis, self).get_sfp(index - 1)

   def get_reboot_cause(self):
      rcm = getReloadCauseManager(self._platform)
      report = rcm.lastReport()
      if report is None:
         return (ChassisBase.REBOOT_CAUSE_NON_HARDWARE, None)
      return (
         self.REBOOT_CAUSE_DICT.get(report.cause.getCause(),
                                    ChassisBase.REBOOT_CAUSE_HARDWARE_OTHER),
         str(report.cause)
      )

   def get_supervisor_slot(self):
      if isinstance(self._platform, Supervisor):
         return self._platform.getSlotId()
      # FIXME: Linecards need to compute the slot id of the supervisor
      return SupervisorModule.MODULE_INVALID_SLOT

   def get_my_slot(self):
      try:
         return self._platform.getSlotId()
      except AttributeError:
         return SupervisorModule.MODULE_INVALID_SLOT

   def is_modular_chassis(self):
      return isinstance(self._platform, (Supervisor, Card))

   def _get_interrupts_for_components(self):
      interrupt_dict = {
         'component': {},
         'fan': {},
         'module': {},
         'psu': {},
         'sfp': {},
         'thermal': {},
      }
      presence_dict = copy.deepcopy(interrupt_dict)

      def process_component(component_type, component):
         if not component:
            return
         interrupt_file = component.get_interrupt_file()
         if interrupt_file:
            interrupt_dict[component_type][component.get_name()] = \
               (component, interrupt_file)
         else:
            presence_dict[component_type][component.get_name()] = \
               (component, component.get_presence())

      #for component in self._component_list:
      #   process_component('component', component)
      for fan in self._fan_list:
         process_component('fan', fan)
      #for module in self._module_list:
      #   process_component('module', module)
      for psu in self._psu_list:
         process_component('psu', psu)
      for sfp in self._sfp_list:
         process_component('sfp', sfp)
      #for thermal in self._thermal_list:
      #   process_component('thermal', thermal)
      return interrupt_dict, presence_dict

   def _process_epoll_result(self, epoll, poll_ret, open_files, res_dict):
      detected = False
      poll_ret = dict(poll_ret)
      for fd in poll_ret:
         if fd in open_files:
            detected = True
            component_type, component, open_file = open_files[fd]
            res_dict[component_type][component.get_id()] = '1' \
               if component.get_presence() else '0'
            epoll.unregister(fd)
            open_file.close()
            component.clear_interrupt()
            del open_files[fd]
            newFile = open(component.get_interrupt_file())
            open_files[newFile.fileno()] = (component_type, component, newFile)
            epoll.register(newFile.fileno(), select.EPOLLIN)
      return detected

   def _process_poll_result(self, res_dict):
      detected = False
      for component_type, component_names in self._presence_dict.items():
         for component_name, (component, old_presence) in component_names.items():
            presence = component.get_presence()
            if presence != old_presence:
               detected = True
               res_dict[component_type][component_name] = '1' if \
                     presence else '0'
               self._presence_dict[component_type][component_name] = \
                     (component, presence)
      return detected

   def get_change_event(self, timeout=0):
      if not Config().persistent_presence_check:
         self._interrupt_dict, self._presence_dict = \
            self._get_interrupts_for_components()

      open_files = {}
      res_dict = {
         'component': {},
         'fan': {},
         'module': {},
         'psu': {},
         'sfp': {},
         'thermal': {},
      }
      block = (timeout == 0)

      epoll = select.epoll()

      for component_type in self._interrupt_dict:
         component_dict = self._interrupt_dict[component_type]
         for component_name in component_dict:
            component, interrupt_file = component_dict[component_name]
            component.clear_interrupt()
            open_file = open(interrupt_file)
            open_files[open_file.fileno()] = (component_type, component, open_file)
            epoll.register(open_file.fileno(), select.EPOLLIN)

      while True:
         timer_value = min(timeout, self.POLL_INTERVAL) if not block \
                       else self.POLL_INTERVAL
         pre_time = time.time()

         epoll_detected = False
         try:
            poll_ret = epoll.poll(timer_value / 1000.)
            if poll_ret:
               epoll_detected = self._process_epoll_result(epoll, poll_ret,
                                                           open_files, res_dict)
         except select.error:
            pass

         poll_detected = self._process_poll_result(res_dict)

         detected = epoll_detected or poll_detected
         if detected and block or timeout == 0 and not block:
            break

         real_elapsed_time = min(int((time.time() - pre_time) * 1000), timeout)
         timeout = timeout - real_elapsed_time

      for _, _, open_file in open_files.values():
         open_file.close()
      epoll.close()

      return True, res_dict

   def get_thermal_manager(self):
      import arista.utils.sonic_platform.thermal_manager
      return arista.utils.sonic_platform.thermal_manager.ThermalManager

   def getThermalControl(self):
      return thermal_control

   def get_position_in_parent(self):
      return -1

   def is_replaceable(self):
      return False
