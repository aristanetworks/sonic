
from __future__ import absolute_import, division, print_function

from ...tests.testing import unittest
from ..fan import FanDesc
from ..led import LedDesc
from ..psu import PsuDesc
from ..sensor import Position, SensorDesc

class DescTest(unittest.TestCase):
   def _testAttributes(self, cls, **kwargs):
      desc = cls(**kwargs)
      for k, v in kwargs.items():
         assert hasattr(desc, k)
         assert getattr(desc, k) == v

   def testFanDesc(self):
      self._testAttributes(FanDesc, fanId=1, extra='blah')

   def testFanDescWithNamespace(self):
      self._testAttributes(FanDesc, fanId=1, namespaceFn = lambda: 1)

   def testLedDesc(self):
      self._testAttributes(LedDesc, name='led', colors=[ 'blue', 'red' ],
                           extra='blah')

   def testPsuDesc(self):
      self._testAttributes(PsuDesc, psuId=1, extra='blah')

   def testSensorDesc(self):
      self._testAttributes(SensorDesc, diode=3, name='sensor',
                           position=Position.OTHER, target=10, overheat=20,
                           critical=30, extra='blah')

if __name__ == "__main__":
   unittest.main()
