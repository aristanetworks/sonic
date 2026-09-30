from ...tests.testing import unittest
from ..dmi import DmiType, dmiDecode


class DmiTest(unittest.TestCase):
   def testDecodeBiosIndexedStrings(self):
      data = b'\x00\x06\x00\x00\x01\x02Vendor\x00Version\x00\x00'

      self.assertEqual(dmiDecode(DmiType.BIOS, data), {
         'Vendor': 'Vendor',
         'Version': 'Version',
      })

   def testDecodePrefdlDefaultString(self):
      payload = b'Base64PrefdlPayload'
      data = b'\x80\x04\x34\x00' + payload + b'\x00\x00'

      self.assertEqual(dmiDecode(DmiType.PREFDL, data),
                       {'Prefdl': payload.decode('utf8')})

   def testDecodeDefaultStringRejectsMultipleStrings(self):
      data = b'\x80\x04\x34\x00First\x00Second\x00\x00'

      self.assertEqual(dmiDecode(DmiType.PREFDL, data), {})
