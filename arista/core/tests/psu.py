
from ...tests.testing import unittest, patch

from ...descs.fan import FanDesc, FanPosition
from ...descs.psu import PsuDesc, PsuStatusPolicy
from ...descs.rail import RailDesc, RailDirection
from ...descs.sensor import Position, SensorDesc

from ..component import Component, Priority
from ..cooling import Airflow
from ..fixed import FixedSystem
from ..psu import PsuSlot, PsuModel, PsuIdent
from ..utils import incrange

from .mockinv import (
   MockGpio,
   MockLed,
)

class MockPmbus(Component):
   def __init__(self, *args, **kwargs):
      super(MockPmbus, self).__init__(*args, **kwargs)
      self.driver = None
   def addTempSensors(self, sensors):
      pass
   def addFans(self, fans):
      pass
   def addRails(self, rails):
      pass


class MockPmbusDriver:
   def __init__(self, statusGood=True):
      self.statusGood = statusGood
   def isPmbusStatusGood(self):
      return self.statusGood

class MockPsuModel(PsuModel):
   PMBUS_CLS = MockPmbus

class PsuVendor1(MockPsuModel):
   MANUFACTURER = 'VENDOR1'
   PMBUS_ADDR = 0x58
   DESCRIPTION = PsuDesc(
      sensors=[
         SensorDesc(diode=0, name='Power supply %(psuId)d', position=Position.OTHER,
                    target=80, overheat=95, critical=100),
      ],
      fans=[
         FanDesc(fanId=1, name='FanP%(psuId)d/%(fanId)d',
                 position=FanPosition.OUTLET),
      ],
      rails=[
         RailDesc(railId=0, direction=RailDirection.INPUT),
         RailDesc(railId=1, direction=RailDirection.OUTPUT),
         RailDesc(railId=2, direction=RailDirection.OUTPUT),
      ],
   )

class PsuModel1(PsuVendor1):
   IDENTIFIERS = [
      PsuIdent('MODEL1-0', 'SKU1-F', Airflow.EXHAUST),
      PsuIdent('MODEL1-1', 'SKU1-R', Airflow.INTAKE),
   ]

class PsuModel2(PsuVendor1):
   IDENTIFIERS = [
      PsuIdent('MODEL2-0', 'SKU2-F', Airflow.EXHAUST),
      PsuIdent('MODEL2-1', 'SKU2-R', Airflow.INTAKE),
   ]

class PsuModel3(MockPsuModel):
   MANUFACTURER = 'VENDOR2'
   PMBUS_ADDR = 0x17
   IDENTIFIERS = [
      PsuIdent('MODEL-F', 'SKU3-F', Airflow.EXHAUST),
      PsuIdent('MODEL-R', 'SKU3-R', Airflow.INTAKE),
   ]

class MockPmbusDetect(object):
   def __init__(self, mockData):
      if isinstance(mockData, int):
         mockData = { 'id': 'unknown', 'model': 'unknown' }
      self.mockData = mockData

   def id(self):
      return self.mockData['id']

   def model(self):
      return self.mockData['model']

   def getMetadata(self):
      return self.mockData

   def exists(self):
      return True

class MockPsuSlot(PsuSlot):
   pass

class MockFixedSystem(FixedSystem):
   def __init__(self, psus, numPsus=2, psuFunc=lambda x: x, psuStatusPolicy=None):
      super(MockFixedSystem, self).__init__()
      self.slots = []
      self.numPsus = numPsus
      for i in incrange(1, numPsus):
         kwargs = {
            'slotId': i,
            'addrFunc': psuFunc,
            'presentGpio': MockGpio(),
            'inputOkGpio': MockGpio(),
            'outputOkGpio': MockGpio(),
            'led': MockLed(),
            'psus': psus,
         }
         if psuStatusPolicy is not None:
            kwargs['psuStatusPolicy'] = psuStatusPolicy
         self.slots.append(self.newComponent(MockPsuSlot, **kwargs))

@patch('arista.core.psu.PsuPmbusDetect', MockPmbusDetect)
class TestPsu(unittest.TestCase):
   def _checkSystem(self, system):
      self.assertEqual(len(system.getInventory().getPsuSlots()), system.numPsus)
      self.assertTrue(system.components)
      system.setup(filters=Priority.backgroundFilter)
      for i, slot in enumerate(system.slots, 1):
         self.assertEqual(slot.slotId, i)

   def _checkPsu(self, system, psuId, model):
      slot = system.slots[psuId]
      self.assertIsNotNone(slot.model)
      self.assertIsInstance(slot.model, model)

   def testBasicNoPsu(self):
      system = MockFixedSystem([PsuModel1, PsuModel2])
      self._checkSystem(system)

   def testBasic1PsuPresent(self):
      system = MockFixedSystem([PsuModel1, PsuModel2])
      system.slots[0].presentGpio.value = 1
      self._checkSystem(system)

   def testBasic2PsuPresent(self):
      system = MockFixedSystem([PsuModel1, PsuModel2])
      system.slots[0].presentGpio.value = 1
      system.slots[1].presentGpio.value = 1
      self._checkSystem(system)

   def testPsuDetected(self):
      def psuFunc(_):
         return { 'id': 'VENDOR1', 'model': 'MODEL2-0' }
      system = MockFixedSystem([PsuModel1, PsuModel2], psuFunc=psuFunc)
      system.slots[0].presentGpio.value = 1
      self._checkSystem(system)
      self._checkPsu(system, 0, PsuModel2)


class TestPsuSlotPmbusStatus(unittest.TestCase):
   def _createSlot(self, psuStatusPolicy=None):
      system = MockFixedSystem([PsuModel1],
                               numPsus=1,
                               psuStatusPolicy=psuStatusPolicy)
      return system.slots[0]

   def testDefaultStatusPolicy(self):
      slot = self._createSlot()
      self.assertEqual(slot.psuStatusPolicy, PsuStatusPolicy.GPIO_OR_PMBUS_POWER)

   def testCheckPmbusStatusNoPsu(self):
      slot = self._createSlot()
      self.assertIsNone(slot.checkPmbusStatus())

   def testCheckPmbusStatusNoDriver(self):
      slot = self._createSlot()
      slot.psu = MockPmbus()
      self.assertIsNone(slot.checkPmbusStatus())

   def testCheckPmbusStatusGood(self):
      slot = self._createSlot()
      slot.psu = MockPmbus()
      slot.psu.driver = MockPmbusDriver(statusGood=True)
      self.assertTrue(slot.checkPmbusStatus())

   def testCheckPmbusStatusBad(self):
      slot = self._createSlot()
      slot.psu = MockPmbus()
      slot.psu.driver = MockPmbusDriver(statusGood=False)
      self.assertFalse(slot.checkPmbusStatus())

   def testIsPowerGoodNotPresent(self):
      slot = self._createSlot()
      slot.presentGpio.value = 0
      self.assertFalse(slot.isPowerGood())

   def testIsPowerGoodGpioOrPmbusPowerPolicy(self):
      slot = self._createSlot()
      slot.presentGpio.value = 1
      slot.inputOkGpio.value = 1
      slot.outputOkGpio.value = 1
      self.assertTrue(slot.isPowerGood())

   def testIsPowerGoodPmbusStatusPolicyGood(self):
      slot = self._createSlot(psuStatusPolicy=PsuStatusPolicy.PMBUS_STATUS)
      slot.psu = MockPmbus()
      slot.psu.driver = MockPmbusDriver(statusGood=True)
      self.assertTrue(slot.isPowerGood())

   def testIsPowerGoodPmbusStatusPolicyNoFallbackOnFalse(self):
      slot = self._createSlot(psuStatusPolicy=PsuStatusPolicy.PMBUS_STATUS)
      slot.presentGpio.value = 1
      slot.inputOkGpio.value = 1
      slot.outputOkGpio.value = 1
      slot.psu = MockPmbus()
      slot.psu.driver = MockPmbusDriver(statusGood=False)
      self.assertFalse(slot.isPowerGood())

   def testIsPowerGoodPmbusStatusPolicyFallbackOnNone(self):
      slot = self._createSlot(psuStatusPolicy=PsuStatusPolicy.PMBUS_STATUS)
      slot.presentGpio.value = 1
      slot.inputOkGpio.value = 1
      slot.outputOkGpio.value = 1
      slot.psu = MockPmbus()
      slot.psu.driver = MockPmbusDriver(statusGood=None)
      self.assertTrue(slot.isPowerGood())

   def testIsPowerGoodPmbusStatusPolicyNoFallbackOnTrue(self):
      slot = self._createSlot(psuStatusPolicy=PsuStatusPolicy.PMBUS_STATUS)
      slot.presentGpio.value = 0
      slot.inputOkGpio.value = 0
      slot.outputOkGpio.value = 0
      slot.psu = MockPmbus()
      slot.psu.driver = MockPmbusDriver(statusGood=True)
      self.assertTrue(slot.isPowerGood())

if __name__ == '__main__':
   unittest.main()
