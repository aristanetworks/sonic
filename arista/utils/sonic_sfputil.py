import time

from .sonic_utils import getPlatform

try:
    from sonic_sfp.sfputilbase import SfpUtilBase
except ImportError as e:
    raise ImportError("%s - required module not found" % str(e))


def getSfpUtil():
    platform = getPlatform()
    inventory = platform.getInventory()

    class SfpUtilCommon(SfpUtilBase):
        @property
        def port_start(self):
            return platform.PORTS.allRange[0]

        @property
        def port_end(self):
            return platform.PORTS.allRange[-1]

        @property
        def osfp_ports(self):
            return platform.PORTS.osfpRange

        @property
        def qsfp_ports(self):
            return platform.PORTS.qsfpRange

        # XXX: defining the sfp_ports property currently can't be done as
        #      it affect the code logic of the sfputil tool by preventing
        #      the qsfp ports from being detected
        #@property
        #def sfp_ports(self):
        #    return platform.PORTS.sfpRange

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
            xcvrSlots = inventory.getXcvrSlots()
            for xcvrSlot in xcvrSlots.values():
                self.xcvr_presence_map[xcvrSlot.getId()] = xcvrSlot.getPresence()

        def get_presence(self, port_num):
            if not self._is_valid_port(port_num):
                return False

            return inventory.getXcvrSlot(port_num).getPresence()

        def get_low_power_mode(self, port_num):
            if not self._is_valid_port(port_num):
                return False

            try:
                return inventory.getXcvrSlot(port_num).getLowPowerMode()
            except:
                return False

        def set_low_power_mode(self, port_num, lpmode):
            if not self._is_valid_port(port_num):
                return False

            try:
               return inventory.getXcvrSlot(port_num).setLowPowerMode(lpmode)
            except:
               #print('failed to set low power mode for xcvr %d' % port_num)
               return False

        def reset(self, port_num):
            if not self._is_valid_port(port_num):
                return False

            xcvr = inventory.getXcvrSlot(port_num).getReset()
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
            xcvrSlots = inventory.getXcvrSlots()
            ret = {}
            start_time = time.time()
            timeout = timeout / float(1000) # convert msec to sec
            while True:
            	for xcvrSlot in xcvrSlots.values():
                    presence = xcvrSlot.getPresence()
                    if self.xcvr_presence_map[xcvrSlot.getId()] != presence:
                        ret[str(xcvrSlot.getId())] = '1' if presence else '0'
                        self.xcvr_presence_map[xcvrSlot.getId()] = presence

                if len(ret) != 0:
                    return True, ret

                if timeout != 0:
                    elapsed_time = time.time() - start_time
                    if elapsed_time >= timeout:
                        return True, {}

                # Poll for Xcvr presence change every 1 second
                time.sleep(XCVR_PRESENCE_POLL_PERIOD_SECS)
            return False, {}

    return SfpUtilNative
