
import os
import shutil
import tempfile
from ...tests.testing import unittest

from ...drivers.pmbus import (
   PmbusRegister,
   PmbusStatus,
   PmbusStatusManager,
   PmbusStatusRegister,
)

class PmbusTestBase(unittest.TestCase):
   def setUp(self):
      self.tempdir = tempfile.mkdtemp()
      self.manager = type('obj', (object,), {'debugfsDir': self.tempdir})()

   def tearDown(self):
      shutil.rmtree(self.tempdir)

   def _writeStatusFile(self, page, value):
      path = os.path.join(self.tempdir, f'status{page}')
      with open(path, 'w', encoding='utf-8') as f:
         f.write(value)

class TestPmbusRegister(PmbusTestBase):
   def testReadSuccess(self):
      self._writeStatusFile(0, '0x42')
      reg = PmbusRegister(self.manager, page=0)
      self.assertEqual(reg.read(), 0x42)

   def testReadNoFile(self):
      reg = PmbusRegister(self.manager, page=1)
      self.assertIsNone(reg.read())

class TestPmbusStatusRegister(PmbusTestBase):
   def testReadStatusWord(self):
      self._writeStatusFile(0, '0x0840')
      reg = PmbusStatusRegister(self.manager, page=0)
      value = reg.read()
      self.assertEqual(value, 0x0840)
      self.assertTrue(value & PmbusStatusRegister.Bit.OFF.mask)
      self.assertTrue(value & PmbusStatusRegister.Bit.POWER_GOOD_N.mask)

class TestPmbusStatus(PmbusTestBase):
   def testPowerLossMask(self):
      expectedMask = (
         PmbusStatusRegister.Bit.OFF.mask |
         PmbusStatusRegister.Bit.POWER_GOOD_N.mask
      )
      self.assertEqual(PmbusStatus.POWER_LOSS_MASK, expectedMask)

   def testHasPowerLossNone(self):
      status = PmbusStatus(self.manager, page=0)
      self.assertIsNone(status.hasPowerLoss())

   def testHasPowerLossFalse(self):
      self._writeStatusFile(0, '0x0000')
      status = PmbusStatus(self.manager, page=0)
      self.assertFalse(status.hasPowerLoss())

   def testHasPowerLossOffBit(self):
      self._writeStatusFile(0, '0x0040')
      status = PmbusStatus(self.manager, page=0)
      self.assertTrue(status.hasPowerLoss())

   def testHasPowerLossPowerGoodBit(self):
      self._writeStatusFile(0, '0x0800')
      status = PmbusStatus(self.manager, page=0)
      self.assertTrue(status.hasPowerLoss())

   def testHasPowerLossBothBits(self):
      self._writeStatusFile(0, '0x0840')
      status = PmbusStatus(self.manager, page=0)
      self.assertTrue(status.hasPowerLoss())

class MockDriver:
   def __init__(self, hwmonPath=None):
      self.hwmonPath = hwmonPath

   def getHwmonPath(self):
      if self.hwmonPath is None:
         raise FileNotFoundError('No hwmon path found for this device')
      return self.hwmonPath

class TestPmbusStatusManager(unittest.TestCase):
   def setUp(self):
      self.tempdir = tempfile.mkdtemp()
      self.hwmonDir = os.path.join(self.tempdir, 'hwmon5')
      os.makedirs(self.hwmonDir)
      self.debugfsDir = os.path.join(self.tempdir, 'debugfs', 'hwmon5')
      os.makedirs(self.debugfsDir)

   def tearDown(self):
      shutil.rmtree(self.tempdir)

   def testGetStatusNone(self):
      driver = MockDriver(hwmonPath=self.hwmonDir)
      manager = PmbusStatusManager(driver)
      self.assertIsNone(manager.getStatus())

   def testGetStatusTrue(self):
      path = os.path.join(self.debugfsDir, 'status0')
      with open(path, 'w', encoding='utf-8') as f:
         f.write('0x0000')
      driver = MockDriver(hwmonPath=self.hwmonDir)
      manager = PmbusStatusManager(driver)
      manager.DEBUGFS_BASE = os.path.join(self.tempdir, 'debugfs')
      manager.discover()
      self.assertTrue(manager.getStatus())

   def testGetStatusFalse(self):
      path = os.path.join(self.debugfsDir, 'status0')
      with open(path, 'w', encoding='utf-8') as f:
         f.write('0x0840')
      driver = MockDriver(hwmonPath=self.hwmonDir)
      manager = PmbusStatusManager(driver)
      manager.DEBUGFS_BASE = os.path.join(self.tempdir, 'debugfs')
      manager.discover()
      self.assertFalse(manager.getStatus())

   def testGetStatusNoHwmon(self):
      driver = MockDriver(hwmonPath=None)
      manager = PmbusStatusManager(driver)
      self.assertIsNone(manager.getStatus())

   def testGetStatusNoDebugfs(self):
      driver = MockDriver(hwmonPath=self.hwmonDir)
      manager = PmbusStatusManager(driver)
      manager.DEBUGFS_BASE = os.path.join(self.tempdir, 'nonexistent')
      manager.discover()
      self.assertIsNone(manager.getStatus())

   def testGetStatusNoStatusFile(self):
      driver = MockDriver(hwmonPath=self.hwmonDir)
      manager = PmbusStatusManager(driver)
      manager.DEBUGFS_BASE = os.path.join(self.tempdir, 'debugfs')
      manager.discover()
      self.assertIsNone(manager.getStatus())

if __name__ == '__main__':
   unittest.main()
