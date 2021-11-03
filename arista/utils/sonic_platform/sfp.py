#!/usr/bin/env python

from __future__ import print_function

import time

try:
   from arista.utils.sonic_platform.thermal import SfpThermal
   from sonic_platform_base.sonic_sfp.qsfp_dd import qsfp_dd_Dom
   from sonic_platform_base.sonic_sfp.sff8436 import sff8436Dom
   from sonic_platform_base.sfp_base import SfpBase
except ImportError as e:
   raise ImportError("%s - required module not found" % e)

try:
   from .sfp_optoe import SfpOptoe
except ImportError as e:
   SfpOptoe = None

EEPROM_PATH = '/sys/class/i2c-adapter/i2c-{0}/{0}-{1:04x}/eeprom'

# XXX Remove these constants after refactor
SFP_TYPE = 'SFP'
OSFP_TYPE = 'OSFP'
QSFP_TYPE = 'QSFP'

XCVR_TYPE_OFFSET = 0
XCVR_TYPE_WIDTH = 1
QSFP_TEMP_OFFSET = 22
QSFP_TEMP_WIDTH = 2
QSFP_THRESHOLD_OFFSET = 512
QSFP_THRESHOLD_WIDTH = 24

OSFP_TEMP_OFFSET = 14
OSFP_TEMP_WIDTH = 2
OSFP_THRESHOLD_OFFSET = 384
OSFP_THRESHOLD_WIDTH = 72

SFP_TYPE_CODE_LIST = [
    '03' # SFP/SFP+/SFP28
]
QSFP_TYPE_CODE_LIST = [
    '0d', # QSFP+ or later
    '11' # QSFP28 or later
]
OSFP_TYPE_CODE_LIST = [
    '18', # QSFP-DD Double Density 8X Pluggable Transceiver
    '19' # OSFP 8X Pluggable Transceiver
]

class Sfp(SfpBase):
   """
   Platform-specific sfp class
   """

   RESET_DELAY = 1

   def __init__(self, index, slot):
      SfpBase.__init__(self)
      self._index = index
      self._slot = slot
      self._sfputil = None
      sfp = slot.getXcvr()
      self._eepromPath = EEPROM_PATH.format(sfp.getI2cAddr().bus,
                                            sfp.getI2cAddr().address)
      self._sfp_type = None
      self._thermal_list.append(SfpThermal(self))

   @property
   def sfp_type(self):
      if self._sfp_type is None:
         self._sfp_type = self._detect_sfp_type()

      return self._sfp_type

   def _detect_sfp_type(self):
      sfp_type_raw = self.read_eeprom(XCVR_TYPE_OFFSET, XCVR_TYPE_WIDTH)
      sfp_type = self._slot.getXcvr().getType().upper()
      if sfp_type_raw:
         sfp_type_code = self._format_bytes(sfp_type_raw)[0]
         if sfp_type_code in SFP_TYPE_CODE_LIST:
            sfp_type = SFP_TYPE
         elif sfp_type_code in QSFP_TYPE_CODE_LIST:
            sfp_type = QSFP_TYPE
         elif sfp_type_code in OSFP_TYPE_CODE_LIST:
            sfp_type = OSFP_TYPE
      return sfp_type

   def get_id(self):
      return self._index

   def get_name(self):
      return self._slot.getName()

   def get_model(self):
      if not self.get_presence():
         return None
      return self.get_transceiver_info().get('model')

   def get_serial(self):
      if not self.get_presence():
         return None
      return self.get_transceiver_info().get('serial')

   def get_revision(self):
      return None

   def get_position_in_parent(self):
      return self._index

   def get_presence(self):
      return self._slot.getPresence()

   def is_replaceable(self):
      return True

   def get_status(self):
      return self.get_presence() and bool(self.get_transceiver_bulk_status())

   def get_lpmode(self):
      try:
         return self._slot.getLowPowerMode()
      except: # pylint: disable-msg=W0702
         return False

   def set_lpmode(self, lpmode):
      try:
         self._slot.setLowPowerMode(lpmode)
      except: # pylint: disable-msg=W0702
         return False
      return True

   def get_tx_disable(self):
      return self._slot.getTxDisable()

   def tx_disable(self, tx_disable):
      try:
         self._slot.setTxDisable(tx_disable)
      except: # pylint: disable-msg=W0702
         return False
      return True

   def get_reset_status(self):
      reset = self._slot.getReset()
      return reset.read() if reset else False

   def reset(self):
      try:
         self._slot.getReset().resetIn()
      except: # pylint: disable-msg=W0702
         return False
      time.sleep(self.RESET_DELAY)
      try:
         self._slot.getReset().resetOut()
      except: # pylint: disable-msg=W0702
         return False
      # XXX: Hack to handle SFP modules plugged into non-SFP ports, which could
      # allow for a reset to "succeed" when it shouldn't
      if self.sfp_type == SFP_TYPE:
         return False
      return True

   def get_temperature(self):
      bulkStatus = self.get_transceiver_bulk_status()
      return bulkStatus["temperature"] if bulkStatus else 0.0

   def clear_interrupt(self):
      intr = self._slot.getInterruptLine()
      if not intr:
         return False
      self.get_presence()
      intr.clear()
      return True

   def get_interrupt_file(self):
      intr = self._slot.getInterruptLine()
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

   def _format_temps(self, val):
      # XXX: hack to format temps for supporting sfp thermals. Won't be needed
      # after sfp refactor is complete.
      if val.endswith('C'):
         temp = val.rstrip('C')
         numDecimals = len(temp.split('.')[1])
         if numDecimals > 3:
            temp = "{:.3f}".format(float(temp))
         return float(temp)
      return val

   def _format_bytes(self, data):
      # XXX: hack for converting bytes read from read_eeprom into format expected by
      # sonic_sfp parsers
      return ['%02x' % x for x in data]

   def get_transceiver_bulk_status(self):
      # XXX: SFP modules currently not supported
      if self.sfp_type == SFP_TYPE:
         return None
      # XXX: Hack to support thermals on OSFP/QSFP-DD modules
      elif self.sfp_type == OSFP_TYPE:
         offset = OSFP_TEMP_OFFSET
         width = OSFP_TEMP_WIDTH
         parser = qsfp_dd_Dom()
         numChannels = 8
      else:
         offset = QSFP_TEMP_OFFSET
         width = QSFP_TEMP_WIDTH
         parser = sff8436Dom()
         numChannels = 4

      tempRaw = self.read_eeprom(offset, width)
      if not tempRaw:
         return None
      domTemp = parser.parse_temperature(self._format_bytes(tempRaw), 0)
      bulkStatus = {
         'temperature': domTemp['data']['Temperature']['value'],
      }
      # Needed to avoid failing xcvrd
      bulkStatus['voltage'] = 'N/A'
      for i in range(1, numChannels + 1):
         bulkStatus['rx%spower' % i] = 'N/A'
         bulkStatus['tx%spower' % i] = 'N/A'
         bulkStatus['tx%sbias' % i] = 'N/A'

      bulkStatus = {k: self._format_temps(v) for k, v in bulkStatus.items()}
      return bulkStatus

   def get_transceiver_threshold_info(self):
      # XXX SFP modules currently not supported
      if self.sfp_type == SFP_TYPE:
         return None
      # XXX: Hack to support thermals on OSFP/QSFP-DD modules
      elif self.sfp_type == OSFP_TYPE:
         offset = OSFP_THRESHOLD_OFFSET
         width = OSFP_THRESHOLD_WIDTH
         parser = qsfp_dd_Dom()
      else:
         offset = QSFP_THRESHOLD_OFFSET
         width = QSFP_THRESHOLD_WIDTH
         parser = sff8436Dom()

      threshRaw = self.read_eeprom(offset, width)
      if not threshRaw:
         return None
      domThresh = parser.parse_module_threshold_values(
                  self._format_bytes(threshRaw), 0)
      threshInfo = {
         'temphighalarm': domThresh['data']['TempHighAlarm']['value'],
         'temphighwarning': domThresh['data']['TempHighWarning']['value'],
         'templowalarm': domThresh['data']['TempLowAlarm']['value'],
         'templowwarning': domThresh['data']['TempLowWarning']['value']
      }
      # Needed to avoid failing xcvrd
      otherFields = ['vcc', 'rxpower', 'txpower', 'txbias']
      thresholds = ['highalarm', 'highwarning', 'lowalarm', 'lowwarning']
      for field in otherFields:
         for thresh in thresholds:
            threshInfo['%s%s' % (field, thresh)] = 'N/A'
      threshInfo = {k: self._format_temps(v) for k, v in threshInfo.items()}
      return threshInfo

   def read_eeprom(self, offset, num_bytes):
      try:
         with open(self._eepromPath, mode='rb', buffering=0) as f:
            f.seek(offset)
            return bytearray(f.read(num_bytes))
      except (OSError, IOError):
         return None

   def write_eeprom(self, offset, num_bytes, write_buffer):
      try:
         with open(self._eepromPath, mode='r+b', buffering=0) as f:
            f.seek(offset)
            f.write(write_buffer[0:num_bytes])
      except (OSError, IOError):
         return False
      return True
