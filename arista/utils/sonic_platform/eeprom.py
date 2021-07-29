#!/usr/bin/env python

from __future__ import print_function

try:
   from sonic_platform_base.sonic_eeprom.eeprom_base import EepromDecoder
except ImportError as e:
   raise ImportError("%s - required module not found" % e)

class Eeprom(EepromDecoder):
   """
   Platform-specific Eeprom class
   """

   def __init__(self, prefdl, **kwargs):
      EepromDecoder.__init__(self, path=None, format=None, start=0, status='',
                             readonly=True, **kwargs)
      self._prefdl = prefdl

   def read_eeprom(self):
      return self._prefdl.data()

   def prefdl(self):
      return self._prefdl

   def set_eeprom(self, e, cmd_args):
      raise NotImplementedError

   def decode_eeprom(self, e):
      return e.show()

   def is_checksum_valid(self, e):
      return (e.isCrcValid(), e.getCrc())

   def serial_number_str(self, e):
      return e.getField('SerialNumber')

   def base_mac_addr(self, e):
      return e.getField('MAC')

   def get_eeprom_dict(self, e):
      return {'Data': e.toDict()}

   def modelstr(self, e):
      return e.getField('SKU')

