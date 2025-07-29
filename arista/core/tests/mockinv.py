
import datetime

from ...descs.fan import FanPosition
from ...descs.sensor import SensorDesc, Position

from ...inventory.fan import Fan, FanSlot
from ...inventory.gpio import Gpio
from ...inventory.interrupt import Interrupt
from ...inventory.led import Led
from ...inventory.phy import Phy
from ...inventory.powercycle import PowerCycle
from ...inventory.psu import Psu, PsuSlot
from ...inventory.reloadcause import ReloadCause
from ...inventory.reset import Reset
from ...inventory.slot import Slot
from ...inventory.temp import Temp
from ...inventory.watchdog import Watchdog
from ...inventory.xcvr import (
   Osfp,
   OsfpSlot,
   Qsfp,
   QsfpSlot,
   Sfp,
   SfpSlot,
   Ethernet,
   EthernetSlot,
)

from ..cooling import Airflow

class MockFan(Fan):
   def __init__(self, fanId=1, name="fan1", speed=12345, direction=Airflow.EXHAUST,
                model="FAN-MODEL-A", fault=False, led=None, status=True,
                position=FanPosition.UNKNOWN):
      self.fanId = fanId
      self.name = name
      self.speed = speed
      self.direction = direction
      self.model = model
      self.fault = fault
      self.led = led
      self.status = status
      self.position = position

   def getId(self):
      return self.fanId

   def getName(self):
      return self.name

   def getModel(self):
      return self.model

   def getFault(self):
      return self.fault

   def getStatus(self):
      return self.status

   def getSpeed(self):
      return self.speed

   def setSpeed(self, speed):
      self.speed = speed

   def getDirection(self):
      return self.direction

   def getPosition(self):
      return self.position

   def getLed(self):
      return self.led

   def __eq__(self, value):
      return isinstance(value, MockFan) and self.fanId == value.fanId

class MockFanSlot(FanSlot):
   def __init__(self, slotId=1, name="fan1", fans=None, direction=Airflow.EXHAUST,
                model="FAN-MODEL-A", fault=False, led=None, status=True,
                maxPower=10., presence=True):
      self.slotId = slotId
      self.name = name
      self.fans = fans or []
      self.direction = direction
      self.model = model
      self.fault = fault
      self.led = led
      self.status = status
      self.presence = presence
      self.maxPower = maxPower

   def getId(self):
      return self.slotId

   def getName(self):
      return self.name

   def getModel(self):
      # TODO: deprecate
      return self.model

   def getFault(self):
      return self.fault

   def getDirection(self):
      return self.direction

   def getPresence(self):
      return self.presence

   def getFans(self):
      return self.fans

   def getLed(self):
      return self.led

   def getMaxPowerDraw(self):
      return self.maxPower

   def __eq__(self, value):
      return isinstance(value, MockFanSlot) and self.slotId == value.slotId

class MockPsu(Psu):
   def __init__(self, psuId=1, name="psu1", presence=True, status=True,
                model="PSU-MODEL-A", serial="PSU-SERIAL-A"):
      self.psuId = psuId
      self.name = name
      self.model = model
      self.presence = presence
      self.serial = serial
      self.status = status

   def getName(self):
      return self.name

   def getModel(self):
      return self.model

   def getSerial(self):
      return self.serial

   def getStatus(self):
      return self.status

   def __eq__(self, value):
      return isinstance(value, MockPsu) and self.psuId == value.psuId

class MockPsuSlot(PsuSlot):
   def __init__(self, slotId=1, name="psu1", presence=True, status=True, led=None,
                psu=None):
      self.slotId = slotId
      self.name = name
      self.presence = presence
      self.status = status
      self.led = led
      self.psu = psu

   def getId(self):
      return self.slotId

   def getName(self):
      return self.name

   def getStatus(self):
      return self.status

   def getPresence(self):
      return self.presence

   def getLed(self):
      return self.led

   def getPsu(self):
      return self.psu

   def __eq__(self, value):
      return isinstance(value, MockPsuSlot) and self.slotId == value.slotId

class MockWatchdog(Watchdog):
   def __init__(self, started=True, remaining=100, timeout=300):
      self.started = started
      self.remaining = remaining
      self.timeout = timeout

   def arm(self, timeout):
      self.timeout = timeout

   def stop(self):
      self.started = False
      self.remaining = 0

   def status(self):
      return self.started

   def __eq__(self, value):
      return isinstance(value, MockWatchdog) and self.__dict__ == value.__dict__

class MockPowerCycle(PowerCycle):
   def __init__(self, powered=True):
      self.powered = powered

   def ensureAvailable(self):
      pass

   def powerCycle(self):
      self.powered = not self.powered

   def __eq__(self, value):
      return isinstance(value, MockPowerCycle) and self.powered == value.powered

class MockReloadCause(ReloadCause):
   def __init__(self, name='unknown', time=datetime.datetime.now()):
      self.name = name
      self.time = time

   def getTime(self):
      return self.time

   def getCause(self):
      return self.name

class MockInterrupt(Interrupt):
   def __init__(self, name='unknown', status=False):
      self.name = name
      self.status = status
      self.path = '/test/path'

   def set(self):
      self.status = True

   def clear(self):
      self.status = False

   def getName(self):
      return self.name

   def getFile(self):
      return self.path

class MockReset(Reset):
   def __init__(self, name='unknown', reset=False):
      self.name = name
      self.reset = reset

   def read(self):
      return self.reset

   def resetIn(self):
      self.reset = True

   def resetOut(self):
      self.reset = False

   def getName(self):
      return self.name

class MockPhy(Phy):
   def __init__(self, phyId=1, reset=False):
      self.phyId = phyId
      self.reset = reset

   def getReset(self):
      return self.reset

   def __eq__(self, value):
      return isinstance(value, MockPhy) and self.phyId == value.phyId

class MockLed(Led):
   def __init__(self, name='unknown', color='green', status=True):
      self.name = name
      self.color = color
      self.status = status

   def getColor(self):
      return self.color

   def setColor(self, color):
      self.color = color

   def getName(self):
      return self.name

   def isStatusLed(self):
      return self.status

   def __eq__(self, value):
      return isinstance(value, MockLed) and self.name == value.name

class MockSlot(Slot):
   def __init__(self, name='unknown', present=True):
      self.name = name
      self.present = present

   def getPresence(self):
      return self.present

   def __eq__(self, value):
      return isinstance(value, MockSlot) and self.name == value.name

class MockEthernet(Ethernet):
   def __init__(self, xcvrId, name):
      self.xcvrId = xcvrId
      self.name = name

   def getId(self):
      return self.xcvrId

   def getName(self):
      return self.name

class MockSfp(Sfp):
   def __init__(self, xcvrId, name, addr=None):
      self.xcvrId = xcvrId
      self.name = name
      self.addr = addr

   def getId(self):
      return self.xcvrId

   def getName(self):
      return self.name

   def getI2cAddr(self):
      return self.addr

class MockQsfp(Qsfp):
   def __init__(self, xcvrId, name, addr=None):
      self.xcvrId = xcvrId
      self.name = name
      self.addr = addr

   def getId(self):
      return self.xcvrId

   def getName(self):
      return self.name

   def getI2cAddr(self):
      return self.addr

class MockOsfp(Osfp):
   def __init__(self, xcvrId, name, addr=None):
      self.xcvrId = xcvrId
      self.name = name
      self.addr = addr

   def getId(self):
      return self.xcvrId

   def getName(self):
      return self.name

   def getI2cAddr(self):
      return self.addr

class MockEthernetSlot(EthernetSlot):
   def __init__(self, slotId, name, presence=True, leds=None, xcvr=None):
      self.slotId = slotId
      self.name = name
      self.presence = presence
      self.leds = leds or []
      self.xcvr = xcvr

   def getId(self):
      return self.slotId

   def getName(self):
      return self.name

   def getPresence(self):
      return self.presence

   def getLeds(self):
      return self.leds

   def getLowPowerMode(self):
      return False

   def setLowPowerMode(self, value):
      return False

   def getModuleSelect(self):
      return True

   def setModuleSelect(self, value):
      return True

   def getInterruptLine(self):
      return None

   def getReset(self):
      return None

   def getRxLos(self):
      return False

   def getTxDisable(self):
      return False

   def setTxDisable(self, value):
      return False

   def getTxFault(self):
      return False

   def getXcvr(self):
      return self.xcvr

class MockSfpSlot(SfpSlot):
   def __init__(self, slotId, name, presence=True, leds=None, intr=None,
                rxLos=False, txDisable=False, txFault=False, xcvr=None):
      self.slotId = slotId
      self.name = name
      self.presence = presence
      self.leds = leds or []
      self.intr = intr
      self.rxLos = rxLos
      self.txDisable = txDisable
      self.txFault = txFault
      self.xcvr = xcvr

   def getId(self):
      return self.slotId

   def getName(self):
      return self.name

   def getPresence(self):
      return self.presence

   def getLeds(self):
      return self.leds

   def getLowPowerMode(self):
      return False

   def setLowPowerMode(self, value):
      return False

   def getModuleSelect(self):
      return True

   def setModuleSelect(self, value):
      return True

   def getInterruptLine(self):
      return self.intr

   def getReset(self):
      return None

   def getRxLos(self):
      return self.rxLos

   def getTxDisable(self):
      return self.txDisable

   def setTxDisable(self, value):
      self.txDisable = value
      return True

   def getTxFault(self):
      return self.txFault

   def getXcvr(self):
      return self.xcvr

class MockQsfpSlot(QsfpSlot):
   def __init__(self, slotId, name, presence=True, leds=None, intr=None,
                reset=None, lpMode=False, modSel=False, xcvr=None):
      self.slotId = slotId
      self.name = name
      self.presence = presence
      self.leds = leds or []
      self.intr = intr
      self.reset = reset
      self.lpMode = lpMode
      self.modSel = modSel
      self.xcvr = xcvr

   def getId(self):
      return self.slotId

   def getName(self):
      return self.name

   def getPresence(self):
      return self.presence

   def getLeds(self):
      return self.leds

   def getLowPowerMode(self):
      return self.lpMode

   def setLowPowerMode(self, value):
      self.lpMode = value
      return True

   def getModuleSelect(self):
      return self.modSel

   def setModuleSelect(self, value):
      self.modSel = value
      return True

   def getInterruptLine(self):
      return self.intr

   def getReset(self):
      return self.reset

   def getRxLos(self):
      return False

   def getTxDisable(self):
      return False

   def setTxDisable(self, value):
      return False

   def getTxFault(self):
      return False

   def getXcvr(self):
      return self.xcvr

class MockOsfpSlot(OsfpSlot):
   def __init__(self, slotId, name, presence=True, leds=None, intr=None,
                reset=None, lpMode=False, modSel=False, xcvr=None):
      self.slotId = slotId
      self.name = name
      self.presence = presence
      self.leds = leds or []
      self.intr = intr
      self.reset = reset
      self.lpMode = lpMode
      self.modSel = modSel
      self.xcvr = xcvr

   def getId(self):
      return self.slotId

   def getName(self):
      return self.name

   def getPresence(self):
      return self.presence

   def getLeds(self):
      return self.leds

   def getLowPowerMode(self):
      return self.lpMode

   def setLowPowerMode(self, value):
      self.lpMode = value
      return True

   def getModuleSelect(self):
      return self.modSel

   def setModuleSelect(self, value):
      self.modSel = value
      return True

   def getInterruptLine(self):
      return self.intr

   def getReset(self):
      return self.reset

   def getRxLos(self):
      return False

   def getTxDisable(self):
      return False

   def setTxDisable(self, value):
      return False

   def getTxFault(self):
      return False

   def getXcvr(self):
      return self.xcvr

class MockTemp(Temp):
   def __init__(self, diode=1, temperature=30, lowThreshold=10, highThreshold=50):
      self.desc = SensorDesc(
         diode=diode,
         name='N/A',
         position=Position.OTHER,
         target=temperature,
         overheat=highThreshold,
         critical=highThreshold + 10,
         low=lowThreshold,
         lcritical=lowThreshold - 10,
      )
      self.diode = diode
      self.temperature = temperature

   def getName(self):
      return self.desc.name

   def getDesc(self):
      return self.desc

   def getStatus(self):
      return True

   def getPresence(self):
      return True

   def getModel(self):
      return "N/A"

   def getTemperature(self):
      return self.temperature

   def getLowThreshold(self):
      return self.desc.low

   def setLowThreshold(self, value):
      self.desc.min = value

   def getLowCriticalThreshold(self):
      return self.desc.lcritical

   def setLowCriticalThreshold(self, value):
      self.desc.lcritical = value

   def getHighThreshold(self):
      return self.desc.overheat

   def setHighThreshold(self, value):
      self.desc.overheat = value

   def getHighCriticalThreshold(self):
      return self.desc.critical

   def setHighCriticalThreshold(self, value):
      self.desc.critical = value

   def refreshHardwareThresholds(self):
      pass

   def __eq__(self, value):
      return isinstance(value, MockTemp) and self.diode == value.diode

class MockGpio(Gpio):
   def __init__(self, name='unknown', addr=0x42, bit=3, ro=False, activeLow=False,
                value=0):
      self.name = name
      self.addr = addr
      self.bit = bit
      self.ro = ro
      self.activeLow = activeLow
      self.value = value
      self.path = '/path/%s' % self.name

   def getName(self):
      return self.name

   def getAddr(self):
      return self.addr

   def getPath(self):
      return self.path

   def getBit(self):
      return self.bit

   def isRo(self):
      return self.ro

   def isActiveLow(self):
      return self.activeLow

   def getRawValue(self):
      return self.value

   def isActive(self):
      if self.activeLow:
         return self.value == 0
      return bool(self.value)

   def setActive(self, value):
      if self.ro:
         raise IOError()
      self.value = value
