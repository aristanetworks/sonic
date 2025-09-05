
from ...descs.sensor import SensorDesc

from ...inventory.fan import Fan
from ...inventory.temp import Temp

from ...tests.testing import unittest

from ..cooling import (
    CoolingAlgorithm,
    CoolingConfig,
    CoolingFanBase,
    CoolingThermalBase,
)

class CoolingMockInvFan(Fan):
   def __init__(self, name, values):
      self.name = name
      self.get = values
      self.set = []

   def __str__(self):
      return '%s(%s)' % (self.__class__.__name__, self.getName())

   def getName(self):
      return self.name

   def getSpeed(self):
      return self.get.pop(0)

   def setSpeed(self, value):
      self.set.append(value)
      self.get.append(value)

class CoolingMockInvTemp(Temp):
   def __init__(self, name='hotspot', target=50, overheat=80, critical=100,
                values=None):
      self.name = name
      self.desc = SensorDesc(diode=1, name=name, description='', target=target,
                             overheat=overheat, critical=critical)
      self.values = [float(v) for v in values or []]

   def __str__(self):
      return '%s(%s)' % (self.__class__.__name__, self.getName())

   def getDesc(self):
      return self.desc

   def getName(self):
      return self.desc.name

   def getTemperature(self):
      return self.values.pop(0)

   def getHighThreshold(self):
      return self.desc.overheat

   def getHighCriticalThreshold(self):
      return self.desc.critical

class CoolingMockFan(CoolingFanBase):
   def update(self):
      self.speed = self.inv.getSpeed()

class CoolingMockThermal(CoolingThermalBase):
   def update(self):
      self.temperature = self.inv.getTemperature()
      self.overheat = self.inv.getHighThreshold()
      self.critical = self.inv.getHighCriticalThreshold()

class CoolingMockInventory(object):
   def __init__(self, fans, thermals):
      self.fans = fans
      self.thermals = thermals

   def getFans(self):
      return self.fans

   def getTemps(self):
      return self.thermals

class CoolingMockPlatform(object):

   COOLING = CoolingConfig()

   def __init__(self, inventory):
      self.inventory = inventory

   def getInventory(self):
      return self.inventory

class CoolingTest(unittest.TestCase):
   def _getPlatform(self, fans=None, thermals=None):
      inv = CoolingMockInventory(fans or [], thermals or [])
      return CoolingMockPlatform(inv)

   def _getCoolingAlgo(self, fans=None, thermals=None):
      return CoolingAlgorithm(self._getPlatform(fans, thermals))

   def _getSimpleAlgo(self, fanInitial=30, temps=None):
      fan = CoolingMockInvFan(name='fan1', values=[fanInitial])
      temp = CoolingMockInvTemp(name='hotspot', values=temps or [])
      algo = self._getCoolingAlgo(fans=[fan], thermals=[temp])

      zone = algo.zones[0]
      fans = {f.name : CoolingMockFan(f.name, inv=f) for f in [fan]}
      thermals = {t.name : CoolingMockThermal(t.name, inv=t) for t in [temp]}
      zone.load(fans=fans, thermals=thermals)

      # self.assertIn(fan, zone.fans.values())
      # self.assertIn(temp, zone.thermals.values())
      return algo

   def _lastFanSpeed(self, algo):
      zone = algo.zones[0]
      for fan in zone.fans.values():
         return fan.data.lastSet

   def _assertFanSpeed(self, algo, expected):
      self.assertEqual(self._lastFanSpeed(algo), expected)

   def _assertFanSpeedSane(self, algo):
      self.assertLessEqual(self._lastFanSpeed(algo), 100)
      self.assertGreaterEqual(self._lastFanSpeed(algo), 30)

   def _testAlgoOnce(self, fanInitial=30, fanExpected=100, temp=80):
      algo = self._getSimpleAlgo(fanInitial=fanInitial, temps=[temp])
      algo.run(update=True)

   def testEmptyCoolingAlgorithm(self):
      algo = self._getCoolingAlgo()
      algo.run(update=True)

   def testOverheatSensor(self):
      self._testAlgoOnce(fanInitial=30, fanExpected=100, temp=80)
      self._testAlgoOnce(fanInitial=30, fanExpected=100, temp=90)
      self._testAlgoOnce(fanInitial=30, fanExpected=100, temp=100)
      self._testAlgoOnce(fanInitial=30, fanExpected=100, temp=110)

   def testMinFanSpeed(self):
      self._testAlgoOnce(fanInitial=35, fanExpected=30, temp=0)

   def testDecreasingFanSpeed(self):
      algo = self._getSimpleAlgo(fanInitial=100, temps=[0] * 10)
      for _ in range(6):
         algo.run(elapsed=algo.INTERVAL, update=True)
         self.assertLessEqual(self._lastFanSpeed(algo), 100)
         self.assertGreater(self._lastFanSpeed(algo), 30)
      algo.run(elapsed=algo.INTERVAL, update=True)
      self._assertFanSpeed(algo, 30)

   def testFanRampUp(self):
      temps = list(range(30, 80, 5))
      iterl = temps.copy()
      algo = self._getSimpleAlgo(fanInitial=30, temps=temps)
      for _ in iterl:
         algo.run(elapsed=algo.INTERVAL, update=True)
         self._assertFanSpeedSane(algo)

   def testFanRampDown(self):
      temps = list(range(80, 30, -5))
      iterl = temps.copy()
      algo = self._getSimpleAlgo(fanInitial=100, temps=temps)
      for _ in iterl:
         algo.run(elapsed=algo.INTERVAL, update=True)
         self._assertFanSpeedSane(algo)

   def testFanSpeedTimeScaling(self):
      algo1 = self._getSimpleAlgo(fanInitial=30, temps=[70] * 10)
      algo1.run(elapsed=algo1.INTERVAL, update=True)

      algo2 = self._getSimpleAlgo(fanInitial=30, temps=[70] * 10)
      for _ in range(6):
         algo2.run(elapsed=algo2.INTERVAL / 6, update=True)

      delta = abs(self._lastFanSpeed(algo1) - self._lastFanSpeed(algo2))
      self.assertLess(delta, 0.0000001)

   def testSingleFanSingleTemp(self):
      algo = self._getCoolingAlgo(
         fans=[
            CoolingMockInvFan(name='fan1', values=[100]),
         ],
         thermals=[
            CoolingMockInvTemp(name='hotspot', values=[50]),
         ],
      )
      algo.run(update=True)

if __name__ == '__main__':
   unittest.main()
