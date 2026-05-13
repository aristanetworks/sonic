
from __future__ import absolute_import, division, print_function

from ...tests.testing import unittest

from ..inventory import Inventory
from ..metainventory import MetaInventory, LazyInventory

from .mockinv import (
   MockEthernet,
   MockEthernetSlot,
   MockFan,
   MockFanSlot,
   MockInterrupt,
   MockLed,
   MockPhy,
   MockPowerCycle,
   MockOsfp,
   MockOsfpSlot,
   MockQsfp,
   MockQsfpSlot,
   MockPsu,
   MockPsuSlot,
   MockReset,
   MockSfp,
   MockSfpSlot,
   MockSlot,
   MockTemp,
   MockWatchdog,
)

class InventoryTest(unittest.TestCase):
   def _populateTestInventory(self, inv):
      eths = [MockEthernet(0, '1000BASE-T')]
      for eth in eths:
         name = eth.getName()
         sfpId = eth.getId()
         led = inv.addLed(MockLed('%s%d' % (name, sfpId)))
         inv.addEthernetSlot(MockEthernetSlot(sfpId, name, leds=[led], xcvr=eth))

      sfps = [MockSfp(1, 'SFP-1G-SX'), MockSfp(2, 'CAB-SFP-SFP-1M')]
      for sfp in sfps:
         name = sfp.getName()
         sfpId = sfp.getId()
         led = inv.addLed(MockLed('%s%d' % (name, sfpId)))
         inv.addSfpSlot(MockSfpSlot(sfpId, name, leds=[led], xcvr=sfp))

      qsfps = [MockQsfp(3, 'CAB-Q-Q-100G-1M'), MockQsfp(4, 'QSFP-100G-CWDM4')]
      for qsfp in qsfps:
         name = qsfp.getName()
         qsfpId = qsfp.getId()
         reset = inv.addReset(MockReset('%s%d_reset' % (name, qsfpId)))
         led = inv.addLed(MockLed('%s%d' % (name, qsfpId)))
         inv.addQsfpSlot(
            MockQsfpSlot(qsfpId, name, leds=[led], reset=reset, xcvr=qsfp))

      osfps = [MockOsfp(5, 'AB-O-O-400G-1M'), MockOsfp(6, 'AOC-O-O-400G-3M')]
      for osfp in osfps:
         name = osfp.getName()
         osfpId = osfp.getId()
         reset = inv.addReset(MockReset('%s%d_reset' % (name, osfpId)))
         led = inv.addLed(MockLed('%s%d' % (name, osfpId)))
         inv.addOsfpSlot(
            MockOsfpSlot(osfpId, name, leds=[led], reset=reset, xcvr=osfp))

      inv.addResets({
         'internet': MockReset('internet'),
         'humanity': MockReset('humanity'),
      })
      psus = inv.addPsus([
         MockPsu(1, 'psu1'),
         MockPsu(2, 'psu2'),
      ])
      for psu in psus:
         inv.addPsuSlot(MockPsuSlot(psu.psuId, name=psu.getName(), psu=psu))
      fans = inv.addFans([
         MockFan(1, 'fan1'),
         MockFan(2, 'fan2'),
         MockFan(3, 'fan3'),
         MockFan(4, 'fan4'),
      ])
      for fan in fans:
         inv.addFanSlot(MockFanSlot(fan.fanId, name=fan.getName(), fans=[fan]))
      inv.addPowerCycle(MockPowerCycle())
      inv.addWatchdog(MockWatchdog())
      inv.addInterrupt(MockInterrupt('intr'))
      inv.addPhy(MockPhy())
      inv.addSlot(MockSlot())
      inv.addTemp(MockTemp(diode=1))
      inv.addTemp(MockTemp(diode=2))

   def _populateSmallTestInventory(self, inv):
      inv.addPsus([
         MockPsu(3, 'psu3'),
         MockPsu(4, 'psu4'),
      ])

   def _getTestInventory(self, populate=True):
      inv = Inventory()
      if populate:
         self._populateTestInventory(inv)
      return inv

   def _getSmallInventory(self):
      inv = self._getTestInventory(populate=False)
      self._populateSmallTestInventory(inv)
      return inv

   def _getFullInventory(self):
      inv = self._getTestInventory()
      self._populateSmallTestInventory(inv)
      return inv

   def _getTestMetaInventory(self, ):
      inv = self._getTestInventory()
      meta = MetaInventory(invs=[inv])
      return meta

   def _iterInventoryGetters(self):
      for attr in dir(Inventory):
         if attr.startswith('get') and attr.endswith( 's' ):
            yield attr

   def assertInventoryEqual(self, inv1, inv2):
      for attr in self._iterInventoryGetters():
         v1 = getattr(inv1, attr)()
         v2 = getattr(inv2, attr)()
         self.assertEqual(type(v1), type(v2))
         if isinstance(v1, (list, dict, set)):
            for item in v1:
               self.assertIn(item, v2)
         else:
            self.assertEqual(v1, v2)

   def testInventory(self):
      inv = self._getTestInventory()
      inv.getXcvrs()

   def testSimpleMetaInventory(self):
      meta = self._getTestMetaInventory()
      with self.assertRaises(AttributeError):
         meta.nonExistant()
      self.assertDictEqual(meta.getXcvrs(), meta.invs[0].getXcvrs())

   def testGeneratorMetaInventory(self):
      inv1 = self._getTestInventory()
      inv2 = self._getSmallInventory()
      invs = self._getFullInventory()

      def generator():
         for inv in [ inv1, inv2 ]:
            yield inv

      meta = MetaInventory(invs=iter(generator()))
      self.assertListEqual(meta.getPsus(), invs.getPsus())

   def testLazyInventory(self):
      lazy = LazyInventory()
      self.assertEqual(len(lazy.__dict__), 0)
      self._populateTestInventory(lazy)
      self.assertNotEqual(len(lazy.__dict__), 0)

      inv = self._getTestInventory()
      self.assertGreaterEqual(len(inv.__dict__), len(lazy.__dict__))

   def testLazyMetaInventory(self):
      lazy1 = LazyInventory()
      self._populateTestInventory(lazy1)
      # lazyLen1 = len(lazy1.__dict__)
      lazy2 = LazyInventory()
      self._populateSmallTestInventory(lazy2)
      # lazyLen2 = len(lazy2.__dict__)
      meta = MetaInventory(invs=[lazy1, lazy2])

      inv = self._getFullInventory()
      self.assertInventoryEqual(inv, meta)

      # self.assertEqual(lazyLen1, len(lazy1.__dict__))
      # self.assertEqual(lazyLen2, len(lazy2.__dict__))

   def testLegacyLazyMetaInventory(self):
      inv = self._getTestInventory()
      lazy = LazyInventory()
      self._populateSmallTestInventory(lazy)
      meta = MetaInventory(invs=[inv, lazy])

      inv = self._getFullInventory()
      self.assertInventoryEqual(inv, meta)

   def testEmptyMetaInventory(self):
      meta = MetaInventory()
      inv = Inventory()
      for attr in self._iterInventoryGetters():
         metaval = getattr(meta, attr)()
         invval = getattr(inv, attr)()
         self.assertEqual(metaval, invval)

class MultiLedTest(unittest.TestCase):
   def _addMultiLed(self):
      inv = Inventory()
      led1 = MockLed('switch_status', color='green')
      led2 = MockLed('cpu_status', color='green')
      multiLed = inv.addMultiLed('status', [led1, led2])
      return inv, multiLed, led1, led2

   def testGetName(self):
      _, multiLed, _, _ = self._addMultiLed()
      self.assertEqual(multiLed.getName(), 'status')

   def testGetColor(self):
      _, multiLed, _, _ = self._addMultiLed()
      self.assertEqual(multiLed.getColor(), 'green')

   def testSetColorSyncsAllLeds(self):
      _, multiLed, led1, led2 = self._addMultiLed()
      multiLed.setColor('red')
      self.assertEqual(led1.getColor(), 'red')
      self.assertEqual(led2.getColor(), 'red')

   def testGetColorReadsFirstLed(self):
      _, multiLed, led1, _ = self._addMultiLed()
      led1.setColor('amber')
      self.assertEqual(multiLed.getColor(), 'amber')

   def testAddMultiLed(self):
      inv, multiLed, _, _ = self._addMultiLed()
      self.assertIs(inv.getLed('status'), multiLed)

if __name__ == '__main__':
   unittest.main()
