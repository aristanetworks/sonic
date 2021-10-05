#!/usr/bin/env python

from __future__ import print_function

try:
   from sonic_platform_base.sonic_eeprom.eeprom_tlvinfo import TlvInfoDecoder
except ImportError as e:
   raise ImportError("%s - required module not found" % e)

class Eeprom(TlvInfoDecoder):
   """
   Platform-specific Eeprom class
   """

   def __init__(self, prefdl, **kwargs):
      TlvInfoDecoder.__init__(self, path=None, start=0, status='',
                              ro=True, **kwargs)
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

   def visit_eeprom(self, e, visitor):
      visitor.visit_header(None, None, None)
      for (code, name, value) in e.toList():
         visitor.visit_tlv(name, code, len(value), value)
      visitor.visit_end(e)

