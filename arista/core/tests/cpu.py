import struct

from unittest.mock import MagicMock

from ...tests.testing import unittest, patch

from ...components.eeprom import RawI2cPrefdlEeprom
from ..cpu import Cpu
from ..hwapi import HwApi

PREFDL_DATA = b'00030A000501.000C0008CpuBoard000000C3D78858'
PREFDL_HDR = struct.pack('>LL', RawI2cPrefdlEeprom.TYPE_PREFDL,
                         len(PREFDL_DATA))

def _mockMsg(hdr, payload):
   def readBytes(self, addr, cmd, length): # pylint: disable=unused-argument
      if length == RawI2cPrefdlEeprom.HDR_SIZE:
         return list(hdr)
      assert length == len(payload), \
         'expected %d bytes, got %d' % (len(payload), length)
      return list(payload)
   return type('MockMsg', (), {
      'read_bytes': readBytes,
      '__enter__': lambda self: self,
      '__exit__': lambda self, *a: None,
   })()

class CpuEepromTest(unittest.TestCase):

   def _makeCpu(self, hwApi=None, prefdlBus=None):
      cpu = object.__new__(Cpu)
      cpu.hwApi = hwApi
      cpu.DEFAULT_HWAPI = (0, 0)
      cpu.PREFDL_EEPROM_BUS = prefdlBus
      cpu.PREFDL_EEPROM_ADDR = 0x50
      return cpu

   @patch('arista.core.cpu.loadPrerequisites')
   @patch('arista.components.eeprom.I2cMsg',
          return_value=_mockMsg(PREFDL_HDR, PREFDL_DATA))
   def testGetEepromI2cRead(self, mockMsgCls, mockLoadPrereqs): # pylint: disable=unused-argument
      cpu = self._makeCpu(prefdlBus=MagicMock())
      data = cpu.getEeprom()
      self.assertEqual(data.get('HwApi'), (1, 0))
      self.assertEqual(data.get('SID'), 'CpuBoard')

   @patch('arista.core.cpu.loadPrerequisites')
   @patch('arista.components.eeprom.I2cMsg',
          side_effect=IOError('bus error'))
   def testGetEepromReadFailure(self, mockMsgCls, mockLoadPrereqs): # pylint: disable=unused-argument
      cpu = self._makeCpu(prefdlBus=MagicMock())
      self.assertEqual(cpu.getEeprom(), {})

   def testGetEepromNoBusConfig(self):
      cpu = self._makeCpu()
      self.assertEqual(cpu.getEeprom(), {})

   @patch('arista.core.cpu.loadPrerequisites')
   @patch('arista.components.eeprom.I2cMsg',
          return_value=_mockMsg(PREFDL_HDR, PREFDL_DATA))
   def testGetHwApiFromEeprom(self, mockMsgCls, mockLoadPrereqs): # pylint: disable=unused-argument
      cpu = self._makeCpu(prefdlBus=MagicMock())
      self.assertEqual(cpu.getHwApi(), HwApi(1, 0))

   def testGetHwApiDefault(self):
      cpu = self._makeCpu()
      self.assertEqual(cpu.getHwApi(), HwApi(0, 0))

   def testGetHwApiInjected(self):
      cpu = self._makeCpu(hwApi=HwApi(3, 0))
      self.assertEqual(cpu.getHwApi(), HwApi(3, 0))

if __name__ == '__main__':
   unittest.main()
