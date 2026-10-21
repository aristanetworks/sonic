from collections import OrderedDict
from unittest.mock import MagicMock, call, patch

import pytest

from ..scd import Scd, ScdI2cAddr, ScdPowerCycle
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


class TestScdPowerCycle:
   @pytest.mark.parametrize('kwargs, reg, wr, delay', [
      pytest.param({}, 0x7000, 0xDEAD, 0, id='defaults'),
      pytest.param({'delay': 0}, 0x7000, 0xDEAD, 0, id='zero-delay'),
      pytest.param({'delay': 5}, 0x7000, 0xDEAD, 5, id='delayed'),
      pytest.param({'reg': 0x10, 'wr': 0xDE}, 0x10, 0xDE, 0, id='custom-write'),
   ])
   def testPowerCycle(self, kwargs, reg, wr, delay):
      scd = MagicMock()
      scd.powerCycles = []
      powerCycle = Scd.createPowerCycle(scd, **kwargs)
      assert scd.powerCycles == [powerCycle]
      scd.inventory.addPowerCycle.assert_called_once_with(powerCycle)
      mmap = scd.getMmap.return_value
      events = MagicMock()
      events.attach_mock(mmap.__enter__.return_value.write32, 'write')
      events.attach_mock(mmap.__exit__, 'unmap')

      with patch('arista.components.scd.time.sleep') as sleep:
         events.attach_mock(sleep, 'sleep')
         assert powerCycle.powerCycle() is True

      expected = [call.write(reg, wr), call.unmap(None, None, None)]
      if delay:
         expected.append(call.sleep(delay))
      assert events.mock_calls == expected

   @pytest.mark.parametrize('failure', ['map', 'write'])
   def testFailureSkipsDelay(self, failure):
      scd = MagicMock()
      if failure == 'map':
         scd.getMmap.return_value.__enter__.side_effect = RuntimeError('map failed')
      elif failure == 'write':
         mmap = scd.getMmap.return_value.__enter__.return_value
         mmap.write32.side_effect = RuntimeError('write failed')

      with patch('arista.components.scd.time.sleep') as sleep:
         assert ScdPowerCycle(scd, delay=5).powerCycle() is False
         sleep.assert_not_called()
