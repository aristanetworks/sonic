import time

from .sonic_utils import getInventory

try:
    from sonic_sfp.sfputilbase import SfpUtilBase
except ImportError as e:
    raise ImportError("%s - required module not found" % str(e))


def getSfpUtil():
    inventory = getInventory()

    class SfpUtilCommon(SfpUtilBase):
        @property
        def port_start(self):
            return inventory.portStart

        @property
        def port_end(self):
            return inventory.portEnd

        @property
        def osfp_ports(self):
            return inventory.osfpRange

        @property
        def qsfp_ports(self):
            return inventory.qsfpRange

        # XXX: defining the sfp_ports property currently can't be done as
        #      it affect the code logic of the sfputil tool by preventing
        #      the qsfp ports from being detected
        #@property
        #def sfp_ports(self):
        #    return inventory.sfpRange

        @property
        def port_to_eeprom_mapping(self):
            return inventory.getPortToEepromMapping()

        @property
        def port_to_i2cbus_mapping(self):
            return inventory.getPortToI2cAdapterMapping()

        def __init__(self):
            SfpUtilBase.__init__(self)

    class SfpUtilNative(SfpUtilCommon):
        """Native Sonic SfpUtil class"""
        XCVR_PRESENCE_POLL_PERIOD_SECS = 1

        def __init__(self):
            self.xcvr_presence_map = {}
            xcvrs = inventory.getXcvrs()
            for xcvr in xcvrs:
                self.xcvr_presence_map[xcvr.xcvrId] = xcvr.getPresence()

        def get_presence(self, port_num):
            if not self._is_valid_port(port_num):
                return False

            return inventory.getXcvr(port_num).getPresence()

        def get_low_power_mode(self, port_num):
            if not self._is_valid_port(port_num):
                return False

            return inventory.getXcvr(port_num).getLowPowerMode()

        def set_low_power_mode(self, port_num, lpmode):
            if not self._is_valid_port(port_num):
                return False

            try:
               return inventory.getXcvr(port_num).setLowPowerMode(lpmode)
            except:
               #print('failed to set low power mode for xcvr %d' % port_num)
               return False

        def reset(self, port_num):
            if not self._is_valid_port(port_num):
                return False

            xcvr = inventory.getXcvr(port_num).getReset()
            if xcvr is None:
               return False

            try:
               xcvr.resetIn()
            except:
               #print('failed to put xcvr %d in reset' % port_num)
               return False

            # Sleep 1 second to allow it to settle
            time.sleep(1)

            try:
               xcvr.resetOut()
            except:
               #print('failed to take xcvr %d out of reset' % port_num)
               return False

            return True

        def get_transceiver_change_event(self, timeout=0):
            xcvrs = inventory.getXcvrs()
            ret = {}
            start_time = time.time()
            timeout = timeout / float(1000) # convert msec to sec
            while True:
                for xcvr in xcvrs:
                    presence = xcvr.getPresence()
                    if self.xcvr_presence_map[xcvr.xcvrId] != presence:
                        ret[str(xcvr.xcvrId)] = '1' if presence else '0'
                        self.xcvr_presence_map[xcvr.xcvrId] = presence

                if len(ret) != 0:
                    return True, ret

                if timeout != 0:
                    elapsed_time = time.time() - start_time
                    if elapsed_time >= timeout:
                        return True, {}

                # Poll for presence change every 1 second
                time.sleep(SfpUtilNative.XCVR_PRESENCE_POLL_PERIOD_SECS)
            return False, {}

    return SfpUtilNative
