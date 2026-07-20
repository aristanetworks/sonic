import os
import shutil
import tempfile
from types import SimpleNamespace

from ....tests.testing import unittest, patch
from ....core.utils import StoredData

from ..blackbox import ScdBlackBoxDecoder, ScdBlackBoxDriver, ScdBlackBoxImpl


class ScdBlackBoxDecoderTest(unittest.TestCase):
   decoder = None
   testlets = (
      ('erased', b'\xff\xff\xff\xff', ''),
      ('circular', b'A\x1aB', 'BA'),
      ('end-marker', b'log\x9aignored', 'log'),
      ('both-markers', b'log\x1a\x9aignored', 'log\x1a'),
      ('split-markers', b'log\x1aincluded\x9aignored', 'log\x1aincluded'),
   )

   @classmethod
   def setUpClass(cls):
      cls.decoder = ScdBlackBoxDecoder()

   def testDecode(self):
      for name, log, expected in self.testlets:
         with self.subTest(name=name):
            self.assertEqual(self.decoder.decode(log), expected)

class ScdBlackBoxV2DecoderTest(unittest.TestCase):
   decoder = None
   testlets = (
      ('split-circular-and-end-marker', b'A\x1aBlog\x9aignored', 'BAlog'),
      ('split-leading-erased-buffer', b'\xff\xff\xfflog\x9aignored', 'log'),
      ('split-two-circular-buffers', b'\x1aAB\x1aC', 'ABC'),
   )

   @classmethod
   def setUpClass(cls):
      cls.decoder = ScdBlackBoxDecoder(bufSplit=3)

   def testDecode(self):
      for name, log, expected in self.testlets:
         with self.subTest(name=name):
            self.assertEqual(self.decoder.decode(log), expected)

class FakeSpiAddr:
   bus = 0
   cs = 1


class ScdBlackBoxDriverTest(unittest.TestCase):
   def setUp(self):
      self.tempDir = tempfile.mkdtemp(prefix='unittest-arista-blackbox-driver-')
      self.addCleanup(shutil.rmtree, self.tempDir)
      self.storedDataPatcher = patch(
         'arista.drivers.scd.blackbox.StoredData',
         side_effect=self.makeStoredData)
      self.storedDataPatcher.start()
      self.addCleanup(self.storedDataPatcher.stop)
      self.driver = ScdBlackBoxDriver(addr=FakeSpiAddr())

   def makeStoredData(self, name, *args, **kwargs):
      kwargs.setdefault('path', os.path.join(self.tempDir, name))
      return StoredData(name, *args, **kwargs)

   @patch.object(ScdBlackBoxDriver, '_runFlashromCmd')
   def testDumpCachesModelFromReadOutput(self, runFlashromCmd):
      runFlashromCmd.return_value = '\n'.join([
         'flashrom v1.0',
         'Found Cypress flash chip "FM25V05"',
         'Reading flash... done.',
      ])

      output = self.driver.dump('/tmp/blackbox.bin')

      self.assertIn('Found Cypress flash chip "FM25V05"', output)
      self.assertEqual(self.driver.cachedFramModel, 'Cypress FM25V05')
      self.assertEqual(
         self.makeStoredData('blackbox0.1_fram_model').read(),
         'Cypress FM25V05')
      runFlashromCmd.assert_called_once_with(op='-r', outputPath='/tmp/blackbox.bin')

   @patch.object(ScdBlackBoxDriver, '_detectFramModel')
   def testEnabledBlackboxUsesCacheWithoutDetection(self, detectFramModel):
      self.makeStoredData('blackbox0.1_fram_model').write('Cypress FM25V05')
      blackbox = ScdBlackBoxImpl(SimpleNamespace(
         driver=self.driver,
         enabled=lambda: True,
      ))

      self.assertEqual(blackbox.getModel(), 'Cypress FM25V05')
      detectFramModel.assert_not_called()


if __name__ == '__main__':
   unittest.main()
