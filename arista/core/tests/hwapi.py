
from ..hwapi import HwApi
from ...tests.testing import unittest

class HwApiTest(unittest.TestCase):
   def testEqual(self):
      self.assertEqual(HwApi(2), HwApi(2))
      self.assertEqual(HwApi(2), HwApi(2, 0))
      self.assertEqual(HwApi(2, 0), HwApi(2))

   def testGreater(self):
      self.assertGreater(HwApi(3), HwApi(2))
      self.assertGreater(HwApi(3), HwApi(2, 1))
      self.assertGreater(HwApi(3, 1), HwApi(3, 0))
      self.assertGreater(HwApi(3, 1), HwApi(3))
      self.assertGreater(HwApi(2, 0), HwApi(1, 9))
      self.assertFalse(HwApi(1, 9) > HwApi(2, 0))

   def testLess(self):
      self.assertLess(HwApi(2), HwApi(3))
      self.assertLess(HwApi(2, 1), HwApi(3))
      self.assertLess(HwApi(2, 0), HwApi(2, 1))
      self.assertLess(HwApi(2), HwApi(2, 1))
      self.assertLess(HwApi(1, 9), HwApi(2, 0))
      self.assertFalse(HwApi(2, 0) < HwApi(1, 9))

   def testGreaterEqual(self):
      self.assertGreaterEqual(HwApi(2), HwApi(2))
      self.assertGreaterEqual(HwApi(2), HwApi(2, 0))
      self.assertGreaterEqual(HwApi(3), HwApi(2))
      self.assertGreaterEqual(HwApi(3), HwApi(2, 1))
      self.assertGreaterEqual(HwApi(2, 1), HwApi(2, 1))
      self.assertGreaterEqual(HwApi(2, 0), HwApi(1, 9))
      self.assertFalse(HwApi(1, 9) >= HwApi(2, 0))

   def testLessEqual(self):
      self.assertLessEqual(HwApi(2), HwApi(2))
      self.assertLessEqual(HwApi(2, 0), HwApi(2))
      self.assertLessEqual(HwApi(2), HwApi(3))
      self.assertLessEqual(HwApi(2, 1), HwApi(3))
      self.assertLessEqual(HwApi(2, 1), HwApi(2, 1))
      self.assertLessEqual(HwApi(1, 9), HwApi(2, 0))
      self.assertFalse(HwApi(2, 0) <= HwApi(1, 9))

if __name__ == '__main__':
   unittest.main()
