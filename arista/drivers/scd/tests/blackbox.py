from ....tests.testing import unittest

from ..blackbox import ScdBlackBoxDecoder


class ScdBlackBoxDecoderTest(unittest.TestCase):
   decoder = None
   testlets = (
      ('erased', b'\xff\xff\xff\xff', ''),
      ('circular', b'A\x1aB', 'BA'),
      ('end-marker', b'log\x9aignored', 'log'),
      ('both-markers', b'log\x1a\x9aignored', 'log\x1a'),
      ('split-markers', b'log\x1aincluded\x9aignored', 'log\x1aincluded'),
   )

   @classmethod
   def setUpClass(cls):
      cls.decoder = ScdBlackBoxDecoder()

   def testDecode(self):
      for name, log, expected in self.testlets:
         with self.subTest(name=name):
            self.assertEqual(self.decoder.decode(log), expected)

class ScdBlackBoxV2DecoderTest(unittest.TestCase):
   decoder = None
   testlets = (
      ('split-circular-and-end-marker', b'A\x1aBlog\x9aignored', 'BAlog'),
      ('split-leading-erased-buffer', b'\xff\xff\xfflog\x9aignored', 'log'),
      ('split-two-circular-buffers', b'\x1aAB\x1aC', 'ABC'),
   )

   @classmethod
   def setUpClass(cls):
      cls.decoder = ScdBlackBoxDecoder(bufSplit=3)

   def testDecode(self):
      for name, log, expected in self.testlets:
         with self.subTest(name=name):
            self.assertEqual(self.decoder.decode(log), expected)


if __name__ == '__main__':
   unittest.main()
