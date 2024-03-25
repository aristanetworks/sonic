from __future__ import absolute_import, division, print_function

from ...tests.testing import unittest

from ..diag import DiagContext
from ..register import (
   ClearOnReadRegister,
   RegisterMap,
   Register,
   RegisterArray,
   RegBitField,
   RegBitRange,
   SetClearRegister,
)

class FakeRegisterMap(RegisterMap):
   REVISION = Register(0x01, name='revision')
   CONTROL = Register(0x02,
      RegBitField(0, 'writeOk', ro=False),
      RegBitField(1, 'failWrite'), # missing ro=False
      RegBitField(2, 'bit0'),
      RegBitField(3, 'bit1'),
   )
   STATUS = Register(0x03,
      RegBitField(0, 'shouldBeZero'),
      RegBitField(1, 'shouldBeOne'),
      RegBitField(2, 'invertZero', flip=True),
      RegBitField(3, 'invertOne', flip=True),
   )
   IOERROR = Register(0x04, name='ioError', ro=False)
   SCRATCHPAD = Register(0x05,
      RegBitField(3, 'bit3', ro=False),
      name='scratchpad', ro=False,
   )
   CLEAR_ON_READ = ClearOnReadRegister(0x06,
      RegBitField(0, name='clear0'),
      RegBitField(1, name='clear1'),
   )
   SET_CLEAR = SetClearRegister(0x07, 0x08,
      RegBitField(0, name='interrupt0', ro=False),
      RegBitField(1, name='interrupt1', ro=False),
   )
   # 0x08 is implicitely reserverd by SetClearRegister
   BIT_RANGE = Register(0x09,
      RegBitRange(0, 3, name='range03', ro=False),
      RegBitRange(5, 6, name='range56', ro=False, flip=True),
   )
   REG_ARRAY = RegisterArray(0x10, 0x13, name='regArray', ro=False)

class FakeOverrideRegisterMap(FakeRegisterMap):
   REVISION = Register(0x51, name='revision')
   CONTROL = Register(0x52,
      RegBitField(0, 'bit0'),
      RegBitField(1, 'bit1'),
   )

class FakeShadowRegisterMap(FakeRegisterMap):
   REVISION_OTHER = Register(0x51, name='revision')
   CONTROL_OTHER = Register(0x52,
      RegBitField(0, 'bit0'),
      RegBitField(1, 'bit1'),
   )

class FakeDriver(object):
   def __init__(self):
      self.regmap = {
         0x01: 42,
         0x02: 0,
         0x03: 0b1010,
         0x04: 0, # should IOError
         0x05: 0,
         0x06: 0, # clear on read
         0x07: 0, # set
         0x08: 0, # clear returns value of 0x07
         0x09: 0, # bit range reg
         0x10: 0, # array begin
         0x11: 0, # array
         0x12: 0, # array
         0x13: 0, # array end
         0x51: 44,
         0x52: 0b01,
      }

   def read(self, reg):
      if reg == 0x04:
         raise IOError(self, reg)
      if reg == 0x08:
         reg = 0x07
      value = self.regmap[reg]
      if reg == 0x06:
         self.regmap[reg] = 0
      return value

   def write(self, reg, value):
      if reg == 0x04:
         raise IOError(self, reg)
      if reg == 0x07:
         value |= self.regmap[reg]
      elif reg == 0x08:
         reg = 0x07
         value = self.regmap[reg] & ~value
      self.regmap[reg] = value
      return value

class CoreRegisterTest(unittest.TestCase):
   def setUp(self):
      self.driver = FakeDriver()
      self.regs = FakeRegisterMap(self.driver)

   def testRevision(self):
      self.assertEqual(self.regs.revision(), 42)

   def testReadWrite(self):
      val = 1 << 3
      self.assertEqual(self.regs.scratchpad(), 0)

      self.regs.scratchpad(val)
      self.assertEqual(self.regs.scratchpad(), val)
      self.assertEqual(self.regs.bit3(), 1)

      self.regs.bit3(0)
      self.assertEqual(self.regs.bit3(), 0)
      self.assertEqual(self.regs.scratchpad(), 0)

      self.regs.scratchpad(0xff)
      self.assertEqual(self.regs.scratchpad(), 0xff)
      self.assertEqual(self.regs.bit3(), 1)

      self.regs.bit3(0)
      self.assertEqual(self.regs.scratchpad(), 0xf7)
      self.assertEqual(self.regs.bit3(), 0)
      self.regs.bit3(1)
      self.assertEqual(self.regs.scratchpad(), 0xff)
      self.assertEqual(self.regs.bit3(), 1)

   def testIoError(self):
      with self.assertRaises(IOError):
         self.regs.ioError()

      with self.assertRaises(IOError):
         self.regs.ioError(42)

   def testWriteSomething(self):
      self.regs.writeOk(1)
      with self.assertRaises(AssertionError):
         self.regs.failWrite(1)

   def testReadSomething(self):
      self.assertEqual(self.regs.shouldBeZero(), 0)
      self.assertEqual(self.regs.shouldBeOne(), 1)
      self.assertEqual(self.regs.invertZero(), 1)
      self.assertEqual(self.regs.invertOne(), 0)

   def testDiag(self):
      self.regs.__diag__(DiagContext())

   def testMultipleInstances(self):
      class FakeDriver2(FakeDriver):
         def __init__(self):
            super(FakeDriver2, self).__init__()
            self.regmap[0x01] = 43
            self.regmap[0x02] = 0xf

      regs = self.regs

      driver2 = FakeDriver2()
      regs2 = FakeRegisterMap(driver2)

      self.assertEqual(regs.revision(), 42)
      self.assertEqual(regs2.revision(), 43)

      self.assertEqual(regs.bit0(), 0)
      self.assertEqual(regs2.bit0(), 1)

   def testClearOnRead(self):
      driver = self.driver
      regs = self.regs
      addr = regs.CLEAR_ON_READ.addr

      self.assertEqual(regs.clear0(), 0)
      self.assertEqual(regs.clear1(), 0)

      driver.regmap[addr] = 0x1
      self.assertEqual(regs.clear1(), 0)
      self.assertEqual(driver.regmap[addr], 0)
      self.assertEqual(regs.clear0(), 1)
      self.assertEqual(regs.clear0(), 0)

      driver.regmap[addr] = 0x2
      self.assertEqual(regs.clear0(), 0)
      self.assertEqual(driver.regmap[addr], 0)
      self.assertEqual(regs.clear1(), 1)
      self.assertEqual(regs.clear1(), 0)

      driver.regmap[addr] = 0x3
      self.assertEqual(regs.clear0(), 1)
      self.assertEqual(driver.regmap[addr], 0)
      self.assertEqual(regs.clear0(), 0)
      self.assertEqual(regs.clear1(), 1)
      self.assertEqual(regs.clear1(), 0)

   def testSetClear(self):
      driver = self.driver
      regs = self.regs
      addr = regs.SET_CLEAR.addr

      self.assertEqual(regs.interrupt0(), 0)
      self.assertEqual(regs.interrupt1(), 0)

      regs.interrupt0(1)
      self.assertEqual(driver.regmap[addr], 0x01)
      self.assertEqual(regs.interrupt0(), 1)
      self.assertEqual(regs.interrupt1(), 0)

      regs.interrupt1(1)
      self.assertEqual(driver.regmap[addr], 0x03)
      self.assertEqual(regs.interrupt0(), 1)
      self.assertEqual(regs.interrupt1(), 1)

      regs.interrupt0(0)
      self.assertEqual(driver.regmap[addr], 0x02)
      self.assertEqual(regs.interrupt0(), 0)
      self.assertEqual(regs.interrupt1(), 1)

      regs.interrupt1(0)
      self.assertEqual(driver.regmap[addr], 0x00)
      self.assertEqual(regs.interrupt0(), 0)
      self.assertEqual(regs.interrupt1(), 0)

   def testBitRange(self):
      self.assertEqual(self.regs.range03(), 0)
      val = 0b1011
      self.regs.range03(val)
      self.assertEqual(self.regs.range03(), val)

      self.assertEqual(self.regs.range56(), 0b11)
      val = 0b1
      self.regs.range56(val)
      self.assertEqual(self.regs.range56(), val)

   def testRegArray(self):
      self.assertEqual(self.regs.regArray(), [0, 0, 0, 0])
      val = [1, 2, 3, 4]
      self.regs.regArray(val)
      self.assertEqual(self.regs.regArray(), val)

      with self.assertRaises(ValueError):
         self.regs.regArray(1)

      with self.assertRaises(ValueError):
         self.regs.regArray([1, 2])

class OverrideRegisterTest(unittest.TestCase):
   def testShadowRegister(self):
      driver = FakeDriver()
      regs = FakeShadowRegisterMap(driver)
      self.assertEqual(regs.revision(), 44)
      self.assertEqual(regs.bit0(), 1)
      self.assertEqual(regs.bit1(), 0)

   def testOverrideRegister(self):
      driver = FakeDriver()
      regs = FakeOverrideRegisterMap(driver)
      self.assertEqual(regs.revision(), 44)
      self.assertEqual(regs.bit0(), 1)
      self.assertEqual(regs.bit1(), 0)

if __name__ == '__main__':
   unittest.main()
