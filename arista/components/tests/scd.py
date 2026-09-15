from collections import OrderedDict

import pytest

from ..scd import Scd, ScdI2cAddr
from ...drivers.scd.driver import ScdKernelDriver


def _makeScd(instanceNumber=0):
   scd = Scd.__new__(Scd)
   scd.smbusMasters = OrderedDict()
   scd.instanceNumber = instanceNumber
   return scd

def _makeScdWithUniformSmbusMasters(instanceNumber=0):
   scd = _makeScd(instanceNumber)
   # 12 SMBus masters with 8 buses each
   for idx in range(12):
      scd.addSmbusMaster(0x8000 + 0x80 * idx, idx, 8)
   return scd

def _makeScdWithMixedSmbusMasters(instanceNumber=0):
   scd = _makeScd(instanceNumber)
   # 32 SMBus masters with 1 bus each
   for idx in range(32):
      scd.addSmbusMaster(0x8000 + 0x40 * idx, idx, 1)
   # 1 SMBus master with 8 buses
   scd.addSmbusMaster(0x8800, 32, 8)
   return scd

class TestScdSmbusMasterBus:
   @pytest.mark.parametrize('bus, expected', [
      (0, (0, 0)),
      (7, (0, 7)),
      (8, (1, 0)),
      (14, (1, 6)),
      (95, (11, 7)),
   ])
   def testUniformBusCounts(self, bus, expected):
      scd = _makeScdWithUniformSmbusMasters()
      assert scd.getSmbusMasterBus(bus) == expected

   @pytest.mark.parametrize('bus, expected', [
      (0, (0, 0)),
      (31, (31, 0)),
      (32, (32, 0)),
      (34, (32, 2)),
      (38, (32, 6)),
      (39, (32, 7)),
   ])
   def testMixedBusCounts(self, bus, expected):
      scd = _makeScdWithMixedSmbusMasters()
      assert len(scd.smbusMasters) == 33
      assert scd.getSmbusMasterBus(bus) == expected

   def testMixedBusCountAddrMaster(self):
      scd = _makeScdWithMixedSmbusMasters()
      assert ScdI2cAddr(scd, 38, 0x50).master == 32

   def testMixedBusCountDriverName(self):
      scd = _makeScdWithMixedSmbusMasters()
      driver = ScdKernelDriver.__new__(ScdKernelDriver)
      driver.scd = scd
      driver.addr = '0000:07:00.0'
      assert driver.getMasterNameForBus(38) == \
         'SCD 0000:07:00.0 SMBus master 32 bus 6'

   def testTwoScdsMapBusesIndependently(self):
      scd0 = _makeScdWithMixedSmbusMasters(instanceNumber=0)
      scd1 = _makeScd(instanceNumber=1)
      for idx in range(32):
         scd1.addSmbusMaster(0x8000 + 0x40 * idx, idx, 1)

      assert scd0.getSmbusMasterBus(38) == (32, 6)
      assert scd1.getSmbusMasterBus(31) == (31, 0)
      assert ScdI2cAddr(scd0, 38, 0x50).uniqueName == 'SCD0/32'
      assert ScdI2cAddr(scd1, 31, 0x50).uniqueName == 'SCD1/31'

   def testOutOfRangeBusRaises(self):
      scd = _makeScdWithMixedSmbusMasters()
      for bus in [-1, 40]:
         with pytest.raises(IndexError):
            scd.getSmbusMasterBus(bus)
