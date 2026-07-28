import sys
from unittest.mock import MagicMock

# Purpose of this testlib: mock the sonic_platform_base lib so that
# we can test complex correlated functionalities between arista core and utils

# Mock ChassisBase for the definition of Chassis
class MockChassisBase:
   REBOOT_CAUSE_POWER_LOSS = "Power Loss"
   REBOOT_CAUSE_THERMAL_OVERLOAD_CPU = "Thermal Overload: CPU"
   REBOOT_CAUSE_THERMAL_OVERLOAD_ASIC = "Thermal Overload: ASIC"
   REBOOT_CAUSE_THERMAL_OVERLOAD_OTHER = "Thermal Overload: Other"
   REBOOT_CAUSE_INSUFFICIENT_FAN_SPEED = "Insufficient Fan Speed"
   REBOOT_CAUSE_WATCHDOG = "Watchdog"
   REBOOT_CAUSE_HARDWARE_OTHER = "Hardware - Other"
   REBOOT_CAUSE_HARDWARE_BIOS = "BIOS"
   REBOOT_CAUSE_HARDWARE_CPU = "CPU"
   REBOOT_CAUSE_HARDWARE_BUTTON = "Push button"
   REBOOT_CAUSE_HARDWARE_RESET_FROM_ASIC = "Reset from ASIC"
   REBOOT_CAUSE_NON_HARDWARE = "Non-Hardware"

class MockSensorBase:
   pass

def mock():
   sys.modules['sonic_platform_base'] = MagicMock()
   sys.modules['sonic_platform_base.chassis_base'] = MagicMock()
   sys.modules['sonic_platform_base.component_base'] = MagicMock()
   sys.modules['sonic_platform_base.fan_base'] = MagicMock()
   sys.modules['sonic_platform_base.fan_drawer_base'] = MagicMock()
   sys.modules['sonic_platform_base.liquid_cooling_base'] = MagicMock()
   sys.modules['sonic_platform_base.module_base'] = MagicMock()
   sys.modules['sonic_platform_base.platform_base'] = MagicMock()
   sys.modules['sonic_platform_base.psu_base'] = MagicMock()
   sys.modules['sonic_platform_base.sensor_base'] = MagicMock()
   sys.modules['sonic_platform_base.sfp_base'] = MagicMock()
   sys.modules['sonic_platform_base.sonic_eeprom'] = MagicMock()
   sys.modules['sonic_platform_base.sonic_eeprom.eeprom_tlvinfo'] = MagicMock()
   sys.modules['sonic_platform_base.sonic_pcie'] = MagicMock()
   sys.modules['sonic_platform_base.sonic_pcie.pcie_base'] = MagicMock()
   sys.modules['sonic_platform_base.sonic_pcie.pcie_common'] = MagicMock()
   sys.modules['sonic_platform_base.sonic_sfp'] = MagicMock()
   sys.modules['sonic_platform_base.sonic_sfp.qsfp_dd'] = MagicMock()
   sys.modules['sonic_platform_base.sonic_sfp.sff8436'] = MagicMock()
   sys.modules['sonic_platform_base.sonic_thermal_control'] = MagicMock()
   sys.modules['sonic_platform_base.sonic_thermal_control.thermal_action_base'] =\
      MagicMock()
   sys.modules['sonic_platform_base.sonic_thermal_control.thermal_condition_base'] =\
      MagicMock()
   sys.modules['sonic_platform_base.sonic_thermal_control.thermal_info_base'] =\
      MagicMock()
   sys.modules['sonic_platform_base.sonic_thermal_control.thermal_json_object'] =\
      MagicMock()
   sys.modules['sonic_platform_base.sonic_thermal_control.thermal_manager_base'] =\
      MagicMock()
   sys.modules['sonic_platform_base.sonic_xcvr'] = MagicMock()
   sys.modules['sonic_platform_base.sonic_xcvr.sfp_optoe_base'] = MagicMock()
   sys.modules['sonic_platform_base.thermal_base'] = MagicMock()
   sys.modules['sonic_platform_base.watchdog_base'] = MagicMock()

def mockChassis():
   mockSensor()
   mockVoltageSensor()
   mockCurrentSensor()
   sys.modules['sonic_platform_base.chassis_base'].ChassisBase = MockChassisBase

def mockSensor():
   sys.modules['sonic_platform_base.sensor_base'].SensorBase = MockSensorBase

def mockVoltageSensor():
   sys.modules['sonic_platform_base.sensor_base'].VoltageSensorBase = MockSensorBase

def mockCurrentSensor():
   sys.modules['sonic_platform_base.sensor_base'].CurrentSensorBase = MockSensorBase
