import unittest
from collections import OrderedDict
from unittest.mock import patch, mock_open, MagicMock

from ..driver import ScdKernelDriver

def makeScdDriver(smbusMasters=None):
   scd = MagicMock()
   scd.smbusMasters = smbusMasters or OrderedDict()
   addr = MagicMock()
   addr.getSysfsPath.return_value = '/sys/devices/pci0000:00/0000:00:1c.0'
   drv = ScdKernelDriver.__new__(ScdKernelDriver)
   drv.scd = scd
   drv.addr = addr
   return drv

TWO_MASTERS = OrderedDict([
   (0x8000, {'id': 0, 'bus': 6}),
   (0x8080, {'id': 1, 'bus': 6}),
])

class ReadSmbusMastersTest(unittest.TestCase):

   def testParsesKernelOutput(self):
      drv = makeScdDriver()
      content = "smbus_master 0x8000 0 6\nsmbus_master 0x8080 1 6\n"
      with patch('builtins.open', mock_open(read_data=content)):
         result = drv.readSmbusMasters()
      self.assertEqual(result, {(0x8000, 0, 6), (0x8080, 1, 6)})

   def testReturnsEmptySetWhenFileMissing(self):
      drv = makeScdDriver()
      with patch('builtins.open', side_effect=FileNotFoundError):
         result = drv.readSmbusMasters()
      self.assertEqual(result, set())

   def testSkipsMalformedLines(self):
      drv = makeScdDriver()
      content = "smbus_master 0x8000 0 6\nbogus\nsmbus_master 0x8080 1 6\n"
      with patch('builtins.open', mock_open(read_data=content)):
         result = drv.readSmbusMasters()
      self.assertEqual(result, {(0x8000, 0, 6), (0x8080, 1, 6)})

class SetupSmbusMastersTest(unittest.TestCase):

   def testWritesAllWhenNoneConfigured(self):
      drv = makeScdDriver(TWO_MASTERS)
      with patch.object(drv, 'readSmbusMasters', return_value=set()), \
           patch.object(drv, 'waitReady') as mockWait, \
           patch.object(drv, 'writeComponents') as mockWrite, \
           patch.object(drv, 'refresh'):
         drv.setupSmbusMasters()
      mockWait.assert_called_once()
      mockWrite.assert_called_once_with(
         ['smbus_master 0x8000 0 6', 'smbus_master 0x8080 1 6'],
         'new_object',
      )

   def testSkipsAlreadyConfigured(self):
      drv = makeScdDriver(TWO_MASTERS)
      configured = {(0x8000, 0, 6)}
      with patch.object(drv, 'readSmbusMasters', return_value=configured), \
           patch.object(drv, 'waitReady') as mockWait, \
           patch.object(drv, 'writeComponents') as mockWrite, \
           patch.object(drv, 'refresh'):
         drv.setupSmbusMasters()
      mockWait.assert_called_once()
      mockWrite.assert_called_once_with(
         ['smbus_master 0x8080 1 6'],
         'new_object',
      )

   def testSkipsWriteWhenAllConfigured(self):
      drv = makeScdDriver(TWO_MASTERS)
      configured = {(0x8000, 0, 6), (0x8080, 1, 6)}
      with patch.object(drv, 'readSmbusMasters', return_value=configured), \
           patch.object(drv, 'waitReady') as mockWait, \
           patch.object(drv, 'writeComponents') as mockWrite, \
           patch.object(drv, 'refresh') as mockRefresh:
         drv.setupSmbusMasters()
      mockWait.assert_not_called()
      mockWrite.assert_not_called()
      mockRefresh.assert_called_once()
