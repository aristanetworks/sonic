import contextlib
import tempfile

from ...tests.testing import unittest

from ..prefdl import Prefdl, PrefdlBase

PREFDL2 = b"0002PCA012345678MFG1234567812304000cASY012345678090010unknownfield0001" \
          b"0A000502.000B000502.1105000c11223344556602000e202010201255420C0007Prod" \
          b"uct03000dDCS-1234AB-42000000CE9B25EC\xff\xff\xff\xff\xff\xff"
PREFDL3 = b"00030d000cPCA0123456780E000bMFG123456780F000312304000cASY0123456780900" \
          b"10unknownfield00010A000502.000B000502.1105000c11223344556602000e202010" \
          b"201255420C0007Product03000dDCS-1234AB-42000000D4CDA7F2\xff\xff\xff\xff"
PREFDL_EMPTY = b"0003000000318A626B\xff"
PREFDL_INVALID_CRC = b"0003000000318A626C\xff"

PREFDL_EXPECT = {
   'PCA': 'PCA012345678',
   'SerialNumber': 'MFG12345678',
   'KVN': '123',
   'ASY': 'ASY012345678',
   'HwApi': '02.00',
   'HwRev': '02.11',
   'MAC': '11:22:33:44:55:66',
   'MfgTime': '20201020125542',
   'SID': 'Product',
   'SKU': 'DCS-1234AB-42',
}

class PrefdlTest(unittest.TestCase):
   def testNoDuplicates(self):
      names = sum(1 + len(f.aliases) for f in PrefdlBase.FIELDS)
      self.assertEqual(names, len(PrefdlBase.FIELD_NAME))
      self.assertEqual(len(PrefdlBase.FIELDS), len(PrefdlBase.FIELD_CODE))

   def _checkPrefdl(self, pfdl, expected):
      self.assertTrue(pfdl.isCrcValid())
      self.assertDictEqual(expected, pfdl.toDict())
      pfdl.show()

   def _testFromBytes(self, prefdl, expected):
      self._checkPrefdl(Prefdl.fromBytes(prefdl), expected)

   def testPrefdl2FromBytes(self):
      self._testFromBytes(PREFDL2, PREFDL_EXPECT)

   def testPrefdl3FromBytes(self):
      self._testFromBytes(PREFDL3, PREFDL_EXPECT)

   def testPrefdlFromDict(self):
      pfdl = Prefdl.fromDict(PREFDL_EXPECT)
      self._checkPrefdl(pfdl, PREFDL_EXPECT)

   def testEmptyPrefdl(self):
      self._checkPrefdl(Prefdl.fromBytes(PREFDL_EMPTY), {})

   def testInvalidCrc(self):
      pfdl = Prefdl.fromBytes(PREFDL_INVALID_CRC)
      self.assertFalse(pfdl.isCrcValid())

   @contextlib.contextmanager
   def _tempTextPrefdl(self, data):
      with tempfile.NamedTemporaryFile(mode='w+') as f:
         for key, value in data.items():
            f.write('%s: %s\n' % (key, value))
         f.flush()
         yield f

   @contextlib.contextmanager
   def _tempBinPrefdl(self, data):
      with tempfile.NamedTemporaryFile(mode='w+b') as f:
         f.write(data)
         f.flush()
         yield f

   def testPrefdlFromTextFile(self):
      data = {
         'MacAddrBase': '11:22:33:44:55:66',
         'Sku': 'Test',
         'Sid': 'Sloth',
      }
      expected = {
         'MAC': '11:22:33:44:55:66',
         'SKU': 'Test',
         'SID': 'Sloth',
      }
      with self._tempTextPrefdl(data) as f:
         self._checkPrefdl(Prefdl.fromTextFile(f.name), expected)

   def testPrefdl2FromBinFile(self):
      with self._tempBinPrefdl(PREFDL2) as f:
         pfdl = Prefdl.fromBinFile(f.name)
         f.seek(0)
         pfdl.writeToFile(f.name)

   def testPrefdl3FromBinFile(self):
      with self._tempBinPrefdl(PREFDL2) as f:
         pfdl = Prefdl.fromBinFile(f.name)
         f.seek(0)
         pfdl.writeToFile(f.name)

if __name__ == '__main__':
   unittest.main()
