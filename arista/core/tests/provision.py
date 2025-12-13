
import os
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase, TestCase

from .mockchassis import MockLinecard, MockSupervisor
from ..provision import ProvisionManifest

def serialForLinecard(lcId):
   return f'LC{lcId}'

def getFirstLinecard(sup):
   return next(sup.getChassis().iterLinecards(presentOnly=False))

def getCardName(lc):
   return f'LINE-CARD{lc.getRelativeSlotId()}'

class ProvisionTest(TestCase):
   def setUp(self):
      self.sup = MockSupervisor()
      self.sup.createLinecardSlots()
      for lcId in range(self.sup.getChassis().NUM_LINECARDS - 1):
         self.sup.insertLinecard(lcId=lcId, cls=MockLinecard,
                                 serial=serialForLinecard(lcId))

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
      lc = getFirstLinecard(self.sup)
      self.assertEqual(self.manifest.getLinecardSerial(lc.getEeprom()),
                       serialForLinecard(0))

   def testCheckLinecardSerialUnchanged(self):
      lc = getFirstLinecard(self.sup)
      cardName = getCardName(lc)
      update = self.manifest.checkLinecardSerial(lc)
      self.assertFalse(update)
      self.assertEqual(self.manifest.data['linecards'][cardName]['serial'],
                       serialForLinecard(0))
      self.assertTrue(self.manifest.data['linecards'][cardName]['provisioned'])

   def testCheckLinecardSerialAbsent(self):
      lc = getFirstLinecard(self.sup)
      cardName = getCardName(lc)
      del self.manifest.data['linecards'][cardName]
      update = self.manifest.checkLinecardSerial(lc)
      self.assertTrue(update)
      self.assertEqual(self.manifest.data['linecards'][cardName]['serial'],
                       serialForLinecard(0))
      self.assertFalse(self.manifest.data['linecards'][cardName]['provisioned'])

   def testCheckLinecardSerialChanged(self):
      lc = getFirstLinecard(self.sup)
      cardName = getCardName(lc)
      self.manifest.data['linecards'][cardName]['serial'] = 'changeme'
      update = self.manifest.checkLinecardSerial(lc)
      self.assertTrue(update)
      self.assertEqual(self.manifest.data['linecards'][cardName]['serial'],
                       serialForLinecard(0))
      self.assertFalse(self.manifest.data['linecards'][cardName]['provisioned'])

class AsyncProvisionTest(IsolatedAsyncioTestCase):
   def setUp(self):
      self.sup = MockSupervisor()
      self.sup.createLinecardSlots()
      for lcId in range(self.sup.getChassis().NUM_LINECARDS - 1):
         self.sup.insertLinecard(lcId=lcId, cls=MockLinecard,
                                 serial=serialForLinecard(lcId))

      # pylint: disable-next=consider-using-with
      self.tempdir = TemporaryDirectory(prefix='unittest-arista-provision-manifest-')
      self.manifest = ProvisionManifest(
         self.sup, os.path.join(self.tempdir.name, 'manifest.json'))
      self.manifest.read(init=True)

   async def testSetProvisioned(self):
      lc = getFirstLinecard(self.sup)
      cardName = getCardName(lc)
      self.manifest.data['linecards'][cardName]['provisioned'] = False
      await self.manifest.setLinecardProvisioned(lc)
      self.assertTrue(self.manifest.data['linecards'][cardName]['provisioned'])

   async def testSetProvisionedAbsent(self):
      lc = getFirstLinecard(self.sup)
      cardName = getCardName(lc)
      del self.manifest.data['linecards'][cardName]
      await self.manifest.setLinecardProvisioned(lc)
      assert cardName in self.manifest.data['linecards']
      self.assertEqual(self.manifest.data['linecards'][cardName]['serial'],
                       serialForLinecard(0))
      self.assertTrue(self.manifest.data['linecards'][cardName]['provisioned'])
