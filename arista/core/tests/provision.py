
import os
from tempfile import TemporaryDirectory
from unittest import TestCase

from .mockchassis import MockLinecard, MockSupervisor
from ..provision import ProvisionManifest

class ProvisionTest(TestCase):
   def _serialForLinecard(self, lcId):
      return f'LC{lcId}'

   def _getFirstLinecard(self):
      return next(self.sup.getChassis().iterLinecards(presentOnly=False))

   def _cardName(self, lc):
      return f'LINE-CARD{lc.getRelativeSlotId()}'

   def setUp(self):
      self.sup = MockSupervisor()
      self.sup.createLinecardSlots()
      for lcId in range(self.sup.getChassis().NUM_LINECARDS - 1):
         self.sup.insertLinecard(lcId=lcId, cls=MockLinecard,
                                 serial=self._serialForLinecard(lcId))

      # pylint: disable-next=consider-using-with
      self.tempdir = TemporaryDirectory(prefix='unittest-arista-provision-manifest-')
      self.manifest = ProvisionManifest(
         self.sup, os.path.join(self.tempdir.name, 'manifest.json'))
      self.manifest.read(init=True)

   def tearDown(self):
      self.tempdir.cleanup()

   def testInit(self):
      assert 'version' in self.manifest.data
      self.assertEqual(self.manifest.data['version'], self.manifest.FILE_VERSION)
      assert 'linecards' in self.manifest.data
      for lc in self.sup.getChassis().iterLinecards():
         assert f'LINE-CARD{lc.getRelativeSlotId()}' in \
            self.manifest.data['linecards']

   def testGetLinecardSerial(self):
      lc = self._getFirstLinecard()
      self.assertEqual(self.manifest.getLinecardSerial(lc),
                       self._serialForLinecard(0))

   def testCheckLinecardSerialUnchanged(self):
      lc = self._getFirstLinecard()
      cardName = self._cardName(lc)
      update = self.manifest.checkLinecardSerial(lc)
      self.assertFalse(update)
      self.assertEqual(self.manifest.data['linecards'][cardName]['serial'],
                       self._serialForLinecard(0))
      self.assertTrue(self.manifest.data['linecards'][cardName]['provisioned'])

   def testCheckLinecardSerialAbsent(self):
      lc = self._getFirstLinecard()
      cardName = self._cardName(lc)
      del self.manifest.data['linecards'][cardName]
      update = self.manifest.checkLinecardSerial(lc)
      self.assertTrue(update)
      self.assertEqual(self.manifest.data['linecards'][cardName]['serial'],
                       self._serialForLinecard(0))
      self.assertFalse(self.manifest.data['linecards'][cardName]['provisioned'])

   def testCheckLinecardSerialChanged(self):
      lc = self._getFirstLinecard()
      cardName = self._cardName(lc)
      self.manifest.data['linecards'][cardName]['serial'] = 'changeme'
      update = self.manifest.checkLinecardSerial(lc)
      self.assertTrue(update)
      self.assertEqual(self.manifest.data['linecards'][cardName]['serial'],
                       self._serialForLinecard(0))
      self.assertFalse(self.manifest.data['linecards'][cardName]['provisioned'])

   def testSetProvisioned(self):
      lc = self._getFirstLinecard()
      cardName = self._cardName(lc)
      self.manifest.data['linecards'][cardName]['provisioned'] = False
      self.manifest.setLinecardProvisioned(lc)
      self.assertTrue(self.manifest.data['linecards'][cardName]['provisioned'])

   def testSetProvisionedAbsent(self):
      lc = self._getFirstLinecard()
      cardName = self._cardName(lc)
      del self.manifest.data['linecards'][cardName]
      self.manifest.setLinecardProvisioned(lc)
      assert cardName in self.manifest.data['linecards']
      self.assertEqual(self.manifest.data['linecards'][cardName]['serial'],
                       self._serialForLinecard(0))
      self.assertTrue(self.manifest.data['linecards'][cardName]['provisioned'])
