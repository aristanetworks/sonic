import time
from ..core import platform as core_platform
from .. import platforms

try:
    from sonic_sfp.sfputilbase import SfpUtilBase
except ImportError as e:
    raise ImportError("%s - required module not found" % str(e))


def getSfpUtil():
    platform = core_platform.getPlatform()
    inventory = platform.getInventory()
    xcvrs = inventory.getXcvrs()

    class SfpUtil(SfpUtilBase):
        """Platform-specific SfpUtil class"""

        # FIXME; Maybe these should be part of xcvrs?
        if isinstance(platform, platforms.a7050qx32.Cloverdale):
            SCD_MODULE_DIR_PATH = "/sys/bus/pci/drivers/scd/0000:04:00.0"
            QSFP_SCD_OFFSET = 1
        elif isinstance(platform, platforms.a7050qx32s.Clearlake):
            SCD_MODULE_DIR_PATH = "/sys/bus/pci/drivers/scd/0000:02:00.0"
            QSFP_SCD_OFFSET = 5
        else:
            print "getSfpUtil(): Error - Unsupported platform!"

        @property
        def port_start(self):
            return xcvrs.port_start

        @property
        def port_end(self):
            return xcvrs.port_end

        @property
        def qsfp_ports(self):
            return range(xcvrs.qsfp_start, xcvrs.qsfp_end + 1)

        @property
        def port_to_eeprom_mapping(self):
            return xcvrs.port_eeprom_mapping

        def __init__(self):
            SfpUtilBase.__init__(self)

        def get_presence(self, port_num):

            # Check for invalid port_num
            if port_num < self.port_start or port_num > self.port_end:
                return False

            presence_value_device_file = "{0}/qsfp{1}_present/value".format(
                    self.SCD_MODULE_DIR_PATH,
                    port_num + self.QSFP_SCD_OFFSET)

            with open(presence_value_device_file) as f:
                content = f.readline().rstrip()

            # content is a string, either "0" or "1"
            if content == "1":
                return True

            return False

        def get_low_power_mode(self, port_num):
            # Check for invalid port_num
            if port_num < self.port_start or port_num > self.port_end:
                return False

            lpmode_direction_device_file_path = "{0}/qsfp{1}_lp_mode/direction".format(
                    self.SCD_MODULE_DIR_PATH,
                    port_num + self.QSFP_SCD_OFFSET)

            # First, set the direction to 'in' to enable reading value
            try:
                direction_file = open(lpmode_direction_device_file_path, "w")
            except IOError as e:
                print "Error: unable to open file: %s" % str(e)
                return False

            direction_file.write("in")
            direction_file.close()

            lpmode_value_device_file_path = "{0}/qsfp{1}_lp_mode/value".format(
                    self.SCD_MODULE_DIR_PATH,
                    port_num + self.QSFP_SCD_OFFSET)

            try:
                lpmode_value_file = open(lpmode_value_device_file_path)
            except IOError as e:
                print "Error: unable to open file: %s" % str(e)
                return False

            content = lpmode_value_file.readline().rstrip()

            # content is a string, either "0" or "1"
            if content == "1":
                return True

            return False

        def set_low_power_mode(self, port_num, lpmode):
            # Check for invalid port_num
            if port_num < self.port_start or port_num > self.port_end:
                return False

            lpmode_direction_device_file_path = "{0}/qsfp{1}_lp_mode/direction".format(
                    self.SCD_MODULE_DIR_PATH,
                    port_num + self.QSFP_SCD_OFFSET)

            # First, set the direction to 'out' to enable writing value
            try:
                direction_file = open(lpmode_direction_device_file_path, "w")
            except IOError as e:
                print "Error: unable to open file: %s" % str(e)
                return False

            direction_file.write("out")
            direction_file.close()

            lpmode_value_device_file_path = "{0}/qsfp{1}_lp_mode/value".format(
                    self.SCD_MODULE_DIR_PATH,
                    port_num + self.QSFP_SCD_OFFSET)

            try:
                lpmode_value_file = open(lpmode_value_device_file_path)
            except IOError as e:
                print "Error: unable to open file: %s" % str(e)
                return False

            value_file.write("1" if lpmode is True else "0")
            value_file.close()

            return True

        def reset(self, port_num):
            # Check for invalid port_num
            if port_num < self.port_start or port_num > self.port_end:
                return False

            reset_direction_device_file_path = "{0}/qsfp{1}_reset/direction".format(
                    self.SCD_MODULE_DIR_PATH,
                    port_num + self.QSFP_SCD_OFFSET)

            # First, set the direction to 'out' to enable writing value
            try:
                direction_file = open(reset_direction_device_file_path, "w")
            except IOError as e:
                print "Error: unable to open file: %s" % str(e)
                return False

            direction_file.write("out")
            direction_file.close()

            reset_value_device_file_path = "{0}/qsfp{1}_reset/value".format(
                    self.SCD_MODULE_DIR_PATH,
                    port_num + self.QSFP_SCD_OFFSET)

            try:
                lpmode_value_file = open(reset_value_device_file_path)
            except IOError as e:
                print "Error: unable to open file: %s" % str(e)
                return False

            value_file.write("1")
            value_file.close()

            # Sleep 1 second to allow it to settle
            time.sleep(1)

            try:
                lpmode_value_file = open(reset_value_device_file_path)
            except IOError as e:
                print "Error: unable to open file: %s" % str(e)
                return False

            value_file.write("0")
            value_file.close()

            return True

    return SfpUtil
