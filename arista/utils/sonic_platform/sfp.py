#!/usr/bin/env python

from __future__ import print_function

import time

try:
   from sonic_platform_base.sfp_base import SfpBase
except ImportError as e:
   raise ImportError("%s - required module not found" % e)

class Sfp(SfpBase):
   """
   Platform-specific sfp class

   Unimplemented methods:
   - get_model
   - get_serial
   - get_status
   - get_transceiver_info
   - get_transceiver_bulk_status
   - get_transceiver_threshold_info
   - get_reset_status
   - get_rx_los
   - get_tx_fault
   - get_tx_disable_channel
   - get_power_override
   - get_temperature
   - get_voltage
   - get_tx_bias
   - get_rx_power
   - get_tx_power
   - tx_disable_channel
   - set_power_override
   """

   RESET_DELAY = 1

   def __init__(self, index, sfp):
      self._index = index
      self._sfp = sfp
      self._sfputil = None

      self.sfp_type = sfp.getType().upper()

   def get_name(self):
      return self._sfp.getName()

   def get_presence(self):
      return self._sfp.getPresence()

   def get_lpmode(self):
      return self._sfp.getLowPowerMode()

   def set_lpmode(self, lpmode):
      try:
         self._sfp.setLowPowerMode(lpmode)
      except: # pylint: disable-msg=W0702
         return False
      return True

   def get_tx_disable(self):
      return self._sfp.getTxDisable()

   def tx_disable(self, tx_disable):
      try:
         self._sfp.setTxDisable(tx_disable)
      except: # pylint: disable-msg=W0702
         return False
      return True

   def reset(self):
      try:
         self._sfp.getReset().resetIn()
      except: # pylint: disable-msg=W0702
         pass
      time.sleep(self.RESET_DELAY)
      try:
         self._sfp.getReset().resetOut()
      except: # pylint: disable-msg=W0702
         pass

   def clear_interrupt(self):
      intr = self._sfp.getInterruptLine()
      if not intr:
         return False
      self.get_presence()
      intr.clear()
      return True

   def get_interrupt_file(self):
      intr = self._sfp.getInterruptLine()
      if intr:
         return intr.getFile()
      return None

   # Some Sfp functionalities still come from sfputil
   def _get_sfputil(self):
      if not self._sfputil:
         import arista.utils.sonic_sfputil
         self._sfputil = arista.utils.sonic_sfputil.getSfpUtil()()
      return self._sfputil

   def get_transceiver_info(self):
      return self._get_sfputil().get_transceiver_info_dict(self._index)

   def get_transceiver_bulk_status(self):
      return self._get_sfputil().get_transceiver_dom_info_dict(self._index)

   def get_transceiver_threshold_info(self):
      return self._get_sfputil().get_transceiver_dom_threshold_info_dict(self._index)
