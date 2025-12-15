from __future__ import absolute_import, division, print_function

import os
import stat
import shutil
import tempfile
from struct import pack, unpack
try:
   from unittest import mock
except ImportError:
   import mock

from ...tests.testing import unittest

from ..utils import FileResource, MmapResource, ResourceAccessor, StoredData

class ResourceTestBase(object):
   class TestClass(unittest.TestCase):
      CLASS_TO_TEST = ResourceAccessor
      TEST_DATA = b'ABCDEFG1234567'

      def setUp(self):
         self.tempFile = tempfile.NamedTemporaryFile()
         self.tempFile.write(self.TEST_DATA)
         self.tempFile.flush()

      def testOpenFailure(self):
         res = self.CLASS_TO_TEST('NonExist')
         self.assertFalse(res.openResource())

      def testOkOpenAndCloseAlreadyClosed(self):
         res = self.CLASS_TO_TEST(self.tempFile.name)
         self.assertTrue(res.openResource())
         res.closeResource()
         res.closeResource()

      def _fmtChar(self, size):
         if size == 1:
            return 'B'
         if size == 2:
            return 'H'
         if size == 4:
            return 'L'

         assert False, "No support for FMT char size %d" % size
         return None

      def _testRead(self, addr, size, readMethod):
         readVal = readMethod(addr)
         readValPacked = pack('<%s' % self._fmtChar(size), readVal)
         refVal = self.TEST_DATA[addr : addr + size]
         self.assertEqual(readValPacked, refVal)

      def testRead8(self):
         with self.CLASS_TO_TEST(self.tempFile.name) as res:
            self._testRead(0, 1, res.read8)
            self._testRead(7, 1, res.read8)
            self._testRead(len(self.TEST_DATA) - 1, 1, res.read8)

      def testRead16(self):
         with self.CLASS_TO_TEST(self.tempFile.name) as res:
            self._testRead(0, 2, res.read16)
            self._testRead(7, 2, res.read16)
            self._testRead(len(self.TEST_DATA) - 2, 2, res.read16)

      def testRead32(self):
         with self.CLASS_TO_TEST(self.tempFile.name) as res:
            self._testRead(0, 4, res.read32)
            self._testRead(7, 4, res.read32)
            self._testRead(len(self.TEST_DATA) - 4, 4, res.read32)

      def _testWrite(self, addr, size, writeMethod):
         refVal = 0x10203040 >> (32 - size * 8)
         writeMethod(addr, refVal)

         self.tempFile.seek(addr, os.SEEK_SET)
         writtenData = self.tempFile.read(size)
         self.tempFile.flush()

         unpackedWrittenData = unpack('<%s' % self._fmtChar(size), writtenData)[0]

         self.assertEqual(unpackedWrittenData, refVal)

      def testWrite8(self):
         with self.CLASS_TO_TEST(self.tempFile.name) as res:
            self._testWrite(0, 1, res.write8)
            self._testWrite(7, 1, res.write8)
            self._testWrite(self.tempFile.tell() - 1, 1, res.write8)

      def testWrite16(self):
         with self.CLASS_TO_TEST(self.tempFile.name) as res:
            self._testWrite(0, 2, res.write16)
            self._testWrite(7, 2, res.write16)
            self._testWrite(self.tempFile.tell() - 2, 2, res.write16)

      def testWrite32(self):
         with self.CLASS_TO_TEST(self.tempFile.name) as res:
            self._testWrite(0, 4, res.write32)
            self._testWrite(7, 4, res.write32)
            self._testWrite(self.tempFile.tell() - 4, 4, res.write32)

class FileResourceTest(ResourceTestBase.TestClass):
   CLASS_TO_TEST = FileResource

   def testFileOffsetRead(self):
      with self.CLASS_TO_TEST(self.tempFile.name) as res:
         offset = res.file_.tell()
         res.read8(0x1)
         self.assertEqual(offset, res.file_.tell())
         res.read16(0x5)
         self.assertEqual(offset, res.file_.tell())
         res.read32(0x7)
         self.assertEqual(offset, res.file_.tell())

   def testFileOffsetWrite(self):
      with self.CLASS_TO_TEST(self.tempFile.name) as res:
         offset = res.file_.tell()
         res.write8(0x1, 0)
         self.assertEqual(offset, res.file_.tell())
         res.write16(0x5, 42)
         self.assertEqual(offset, res.file_.tell())
         res.write32(0x7, 125)
         self.assertEqual(offset, res.file_.tell())

class MmapResourceTest(ResourceTestBase.TestClass):
   CLASS_TO_TEST = MmapResource

class StoredDataTest(unittest.TestCase):
   def setUp(self):
      self.tempDir = tempfile.mkdtemp(prefix='unittest-arista-storeddata-')
      self.tempFile = os.path.join(self.tempDir, 'test.txt')

   def tearDown(self):
      if os.path.exists(self.tempDir):
         shutil.rmtree(self.tempDir)

   def testWriteReadTemporary(self):
      """Test basic write and read for temporary files"""
      sd = StoredData('test.txt', lifespan='temporary',
                      path=self.tempFile, append=False)
      sd.write('test data')
      self.assertEqual(sd.read(), 'test data')

   def testWriteReadPersistent(self):
      """Test basic write and read for persistent files"""
      sd = StoredData('test.txt', lifespan='persistent',
                      path=self.tempFile, append=False)
      sd.write('persistent data')
      self.assertEqual(sd.read(), 'persistent data')

   def testClearTemporary(self):
      """Test clear for temporary files"""
      sd = StoredData('test.txt', lifespan='temporary',
                      path=self.tempFile, append=False)
      sd.write('test data')
      self.assertTrue(sd.exist())
      sd.clear()
      self.assertFalse(sd.exist())

   def testClearPersistent(self):
      """Test clear for persistent files"""
      sd = StoredData('test.txt', lifespan='persistent',
                      path=self.tempFile, append=False)
      sd.write('test data')
      self.assertTrue(sd.exist())
      sd.clear()
      self.assertFalse(sd.exist())

   def testWriteExceptionTemporary(self):
      """Test that write exceptions are caught for temporary files"""
      sd = StoredData('test.txt', lifespan='temporary',
                      path=self.tempFile, append=False)
      sd.write('initial data')
      # Make file read-only to trigger write exception
      os.chmod(self.tempFile, stat.S_IRUSR)
      # Should not raise exception for temporary files
      sd.write('new data')
      # Restore permissions for cleanup
      os.chmod(self.tempFile, stat.S_IRUSR | stat.S_IWUSR)

   def testWriteExceptionPersistent(self):
      """Test that write exceptions propagate for persistent files"""
      sd = StoredData('test.txt', lifespan='persistent',
                      path=self.tempFile, append=False)
      sd.write('initial data')
      # Make file read-only to trigger write exception
      os.chmod(self.tempFile, stat.S_IRUSR)
      # Should raise exception for persistent files
      with self.assertRaises(OSError):
         sd.write('new data')
      # Restore permissions for cleanup
      os.chmod(self.tempFile, stat.S_IRUSR | stat.S_IWUSR)

   def testClearExceptionTemporary(self):
      """Test that clear exceptions are caught for temporary files"""
      sd = StoredData('test.txt', lifespan='temporary',
                      path=self.tempFile, append=False)
      sd.write('test data')
      # Make directory read-only to trigger remove exception
      os.chmod(self.tempDir, stat.S_IRUSR | stat.S_IXUSR)
      # Should not raise exception for temporary files
      sd.clear()
      # Restore permissions for cleanup
      os.chmod(self.tempDir, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

   def testClearExceptionPersistent(self):
      """Test that clear exceptions propagate for persistent files"""
      sd = StoredData('test.txt', lifespan='persistent',
                      path=self.tempFile, append=False)
      sd.write('test data')
      # Make directory read-only to trigger remove exception
      os.chmod(self.tempDir, stat.S_IRUSR | stat.S_IXUSR)
      # Should raise exception for persistent files
      with self.assertRaises(OSError):
         sd.clear()
      # Restore permissions for cleanup
      os.chmod(self.tempDir, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

   def testReadOrClearSuccess(self):
      """Test readOrClear returns data when file is valid"""
      sd = StoredData('test.txt', lifespan='temporary',
                      path=self.tempFile, append=False)
      sd.write('test data')
      result = sd.readOrClear()
      self.assertEqual(result, 'test data')

   def testReadOrClearCorrupted(self):
      """Test readOrClear clears corrupted file and returns None"""
      sd = StoredData('test.txt', lifespan='temporary',
                      path=self.tempFile, append=False)
      # Create a file that will cause read to fail (binary data in text mode)
      with open(self.tempFile, 'wb') as f:
         f.write(b'\x80\x81\x82\x83')

      # Mock read to raise an OSError
      with mock.patch.object(sd, 'read',
                             side_effect=OSError('Read error')):
         result = sd.readOrClear()
         self.assertIsNone(result)
         # File should be cleared
         self.assertFalse(sd.exist())

   def testReadOrClearNonExistent(self):
      """Test readOrClear returns None for non-existent file"""
      sd = StoredData('test.txt', lifespan='temporary',
                      path=self.tempFile, append=False)
      result = sd.readOrClear()
      self.assertIsNone(result)

if __name__ == '__main__':
   unittest.main()
