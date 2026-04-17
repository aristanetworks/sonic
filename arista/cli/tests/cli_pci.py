from __future__ import absolute_import

from multiprocessing import Process
import os
from tempfile import NamedTemporaryFile, TemporaryDirectory

from ...tests.testing import unittest, patch
from .. import main

class CliPciTest(unittest.TestCase):
   FAKE_DEVICE: str = '0000:46:00.0'

   def setUp(self) -> None:
      # pylint: disable-next=consider-using-with
      self.tmpdir = TemporaryDirectory(prefix='arista-sonic')
      devdir = os.path.join(self.tmpdir.name, self.FAKE_DEVICE)
      os.mkdir(devdir)
      with open(os.path.join(devdir, 'enable'), 'w', encoding='utf-8') as f:
         f.write('1\n')
      with open(os.path.join(devdir, 'resource0'), 'wb') as f:
         f.write(b'\x00' * 4096)
         f.write(b'\x01\x02\x03\x04')
         f.write(b'\x00' * 4092)
      # pylint: disable-next=consider-using-with
      self.fakeStdout = NamedTemporaryFile(mode='w+t', encoding='utf-8',
                                           prefix='arista-sonic')

   def tearDown(self) -> None:
      self.tmpdir.cleanup()
      self.fakeStdout.close()

   def _runMain(self, args: list[str], code: int=0) -> None:
      args = ['-s', '-v', '.*/DEBUG'] + args
      with patch('arista.cli.actions.pci.DEVICE_SYSFS_ROOT', self.tmpdir.name), \
           patch('sys.stdout', self.fakeStdout):
         p = Process(target=main, args=(args,))
         p.start()
         p.join()
         self.assertEqual(p.exitcode, code,
                          msg='Command %s failed with code %s' % (args, p.exitcode))

   def _checkOutputValue(self, expected: str) -> None:
      self.fakeStdout.seek(0)
      for line in self.fakeStdout:
         if line.startswith('INFO:'):
            continue
         self.assertEqual(line.strip(), expected, msg='Did not get expected output')
         return
      self.fail(msg='Did not get any output')

   def testSimplePciRead(self) -> None:
      self._runMain(['pci', 'read', self.FAKE_DEVICE, '4096'])
      self._checkOutputValue('0x4030201')

   def testSimplePciReadHexAddr(self) -> None:
      self._runMain(['pci', 'read', self.FAKE_DEVICE, '0x1000'])
      self._checkOutputValue('0x4030201')

   def testSimplePciReadBinaryOutput(self) -> None:
      self._runMain(['pci', 'read', self.FAKE_DEVICE, '0x1000', '--binary'])
      self._checkOutputValue('0000_0100_0000_0011_0000_0010_0000_0001')

   def testSimplePciWrite(self) -> None:
      self._runMain(['pci', 'write', '--verify',
                     self.FAKE_DEVICE, '1024', '0x42424242'])

if __name__ == '__main__':
   unittest.main()
