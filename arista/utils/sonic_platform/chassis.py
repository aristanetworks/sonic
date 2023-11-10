#!/usr/bin/env python

from __future__ import division, print_function

try:
   from sonic_platform_base.chassis_base import ChassisBase
   from sonic_platform_base.sfp_base import SfpBase
   from arista.core import thermal_control
   from arista.core.card import Card
   from arista.core.cause import getReloadCauseManager
   from arista.core.config import Config
   from arista.core.onie import OnieEeprom
   from arista.core.platform import getPlatform, readPrefdl, getFanDirectionSku
   from arista.core.supervisor import Supervisor
   from arista.core.linecard import Linecard
   from arista.utils.sonic_platform.component import Component
   from arista.utils.sonic_platform.eeprom import Eeprom
   from arista.utils.sonic_platform.fan_drawer import (
      FanDrawer,
      FixedFanDrawer,
   )
   from arista.utils.sonic_platform.module import (
      SupervisorModule,
      FabricModule,
      LinecardModule,
      LinecardSelfModule,
      LinecardSupervisorModule,
   )
   from arista.utils.sonic_platform.psu import Psu
   from arista.utils.sonic_platform.sfp import Sfp
   from arista.utils.sonic_platform.sfp import SfpOptoe
   from arista.utils.sonic_platform.thermal import Thermal
   from arista.utils.sonic_platform.watchdog import Watchdog
   from arista.utils.sonic_platform.event import EventWatcher
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
      'unknown': ChassisBase.REBOOT_CAUSE_NON_HARDWARE,
      'powerloss': ChassisBase.REBOOT_CAUSE_POWER_LOSS,
      'powerloss2': ChassisBase.REBOOT_CAUSE_POWER_LOSS,
      'overtemp': ChassisBase.REBOOT_CAUSE_THERMAL_OVERLOAD_OTHER,
      'reboot': ChassisBase.REBOOT_CAUSE_NON_HARDWARE,
      'button': ChassisBase.REBOOT_CAUSE_HARDWARE_BUTTON,
      'watchdog': ChassisBase.REBOOT_CAUSE_WATCHDOG,
      'cpu': ChassisBase.REBOOT_CAUSE_HARDWARE_CPU,
      'rail': ChassisBase.REBOOT_CAUSE_HARDWARE_OTHER,
      'killswitch': ChassisBase.REBOOT_CAUSE_HARDWARE_OTHER,
      'seu': ChassisBase.REBOOT_CAUSE_HARDWARE_OTHER,
      'under-voltage': ChassisBase.REBOOT_CAUSE_HARDWARE_OTHER,
      'over-voltage': ChassisBase.REBOOT_CAUSE_HARDWARE_OTHER,
      'asic-overtemp': ChassisBase.REBOOT_CAUSE_THERMAL_OVERLOAD_ASIC,
      'cpu-overtemp': ChassisBase.REBOOT_CAUSE_THERMAL_OVERLOAD_CPU,
      'cpu-s3': ChassisBase.REBOOT_CAUSE_HARDWARE_CPU,
      'cpu-s5': ChassisBase.REBOOT_CAUSE_HARDWARE_CPU,
      'over-current': ChassisBase.REBOOT_CAUSE_HARDWARE_OTHER,
      'no-fans': ChassisBase.REBOOT_CAUSE_INSUFFICIENT_FAN_SPEED,
   }

   # Intervals in milliseconds
   POLL_INTERVAL = 1000.

   def __init__(self, platform=None):
      platform = platform or getPlatform()
      ChassisBase.__init__(self)
      self._platform = platform
      self._eeprom = Eeprom(readPrefdl())
      self._inventory = platform.getInventory()
      self._event_watcher = None
      self._chassis = None
      if isinstance(self._platform, Supervisor):
         chassis = self._platform.getChassis()
         for supervisor in chassis.iterSupervisors(presentOnly=False):
            if supervisor is not None:
               self._module_list.append(SupervisorModule(self, supervisor))
         chassis.loadFabrics()
         for fabric in chassis.iterFabrics(presentOnly=False):
            self._module_list.append(FabricModule(self, fabric))
         chassis.loadLinecards()
         for lc in chassis.iterLinecards(presentOnly=False):
            self._module_list.append(LinecardModule(self, lc))
         for slot in chassis.iterPsus():
            self._psu_list.append(Psu(slot.psuSlot))
         self._chassis = chassis
      elif isinstance(self._platform, Linecard):
         self._module_list.append(LinecardSelfModule(self, self._platform))
         self._module_list.append(LinecardSupervisorModule(self, self._platform))
         for programmable in self._inventory.getProgrammables():
            self._component_list.append(Component(self, programmable))
      else:
         for slot in self._inventory.getPsuSlots():
            self._psu_list.append(Psu(slot))
         for programmable in self._inventory.getProgrammables():
            self._component_list.append(Component(self, programmable))

      if self._inventory.getFanSlots():
         for slot in self._inventory.getFanSlots():
            self._fan_drawer_list.append(FanDrawer(self, slot))
      else:
         # NOTE: SONiC expect fixed fans to be in a FanDrawer anyways
         for fan in self._inventory.getFans():
            self._fan_drawer_list.append(FixedFanDrawer(self, fan))

      self._sfp_list = []
      xcvrSlots = self._inventory.getXcvrSlots()
      if xcvrSlots:
         sfpCls = SfpOptoe if Config().api_use_sfpoptoe else Sfp
         self._sfp_list = [None] * len(xcvrSlots)
         for index, slot in xcvrSlots.items():
            self._sfp_list[index - 1] = sfpCls(index, slot)

      # TODO: index used here to allow thermal.get_position_in_parent() to return
      # unique values but we want a proper way of uniquely identifying sensors
      for index, thermal in enumerate(self._inventory.getTemps()):
         self._thermal_list.append(Thermal(index + 1, thermal))

      watchdogs = self._inventory.getWatchdogs()
      if watchdogs:
         self._watchdog = Watchdog(watchdogs[0])

   def get_name(self):
      sku = getFanDirectionSku(self._eeprom.read_eeprom().data())
      return sanitizeProductName(sku)

   def get_presence(self):
      return True

   def get_model(self):
      return getFanDirectionSku(self._eeprom.read_eeprom().data())

   def get_base_mac(self):
      return self._eeprom.read_eeprom().getField("MAC")

   def get_serial(self):
      return self._eeprom.read_eeprom().getField("SerialNumber")

   def get_revision(self):
      rev = self._eeprom.read_eeprom().getField('HwApi')
      return '.'.join('%02x' % x for x in rev) if rev is not None else rev

   def get_serial_number(self):
      return self.get_serial()

   def get_system_eeprom_info(self):
      return OnieEeprom(self._eeprom.read_eeprom().data()).data()

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
      if isinstance(self._platform, Linecard):
         # FIXME: Linecards need to compute the slot id of the supervisor
         #        for now always return 1 as we don't support dual sup
         return 1
      return SupervisorModule.MODULE_INVALID_SLOT

   def get_my_slot(self):
      try:
         return self._platform.getSlotId()
      except AttributeError:
         return SupervisorModule.MODULE_INVALID_SLOT

   def is_modular_chassis(self):
      return isinstance(self._platform, (Supervisor, Card))

   def _get_event_watcher(self):
      if self._event_watcher is None:
         self._event_watcher = EventWatcher(preserve=Config().persistent_presence_check)
      return self._event_watcher

   def get_change_event(self, timeout=0):
      ew = self._get_event_watcher()
      ew.load({
         'component': None, #self._component_list,
         'fan': self._fan_drawer_list,
         'module': None, #self._module_list,
         'psu': self._psu_list,
         'sfp': self._sfp_list,
         'thermal': None, #self._thermal_list,
      })
      status = ew.wait(timeout=timeout)
      return True, status

   def get_thermal_manager(self):
      import arista.utils.sonic_platform.thermal_manager
      return arista.utils.sonic_platform.thermal_manager.ThermalManager

   def getThermalControl(self):
      return thermal_control

   def getPlatform(self):
      return self._platform

   def get_port_or_cage_type(self, index):
      # pylint: disable=redefined-outer-name

      if not hasattr( SfpBase, 'SFP_PORT_TYPE_BIT_RJ45' ):
         raise NotImplementedError

      from arista.descs.xcvr import Osfp, Qsfp, Qsfp28, Qsfp56, QsfpDD, QsfpPlus, Rj45, Sfp, Sfp28
      mapping = {
         (Rj45, SfpBase.SFP_PORT_TYPE_BIT_RJ45),
         (Sfp, SfpBase.SFP_PORT_TYPE_BIT_SFP | SfpBase.SFP_PORT_TYPE_BIT_SFP_PLUS),
         (Sfp28, SfpBase.SFP_PORT_TYPE_BIT_SFP28 ),
         (Qsfp, SfpBase.SFP_PORT_TYPE_BIT_QSFP | SfpBase.SFP_PORT_TYPE_BIT_QSFP_PLUS),
         (Qsfp28, SfpBase.SFP_PORT_TYPE_BIT_QSFP28),
         (Qsfp56, SfpBase.SFP_PORT_TYPE_BIT_QSFP56),
         (QsfpPlus, SfpBase.SFP_PORT_TYPE_BIT_QSFP_PLUS),
         (QsfpDD, SfpBase.SFP_PORT_TYPE_BIT_QSFPDD),
         (Osfp, SfpBase.SFP_PORT_TYPE_BIT_OSFP | SfpBase.SFP_PORT_TYPE_BIT_QSFPDD),
      }

      xcvr = self._platform.PORTS.getPort(index)
      mask = 0x0
      for cls, flag in mapping:
         if isinstance(xcvr, cls):
            mask |= flag
      return mask

   def get_position_in_parent(self):
      return -1

   def is_replaceable(self):
      return False

   # NOTE: yes there is a typo in the function name and it's not part of the
   #       API. But eh, that's how `show system-health` works
   #       Not doing anything in this call for now, we already have some logic
   def initizalize_system_led(self):
      pass

   def init_midplane_switch(self):
      return True

   def get_module_index(self, module_name):
      for index, module in enumerate(self.get_all_modules()):
         if module.get_name() == module_name:
            return index
      return None
