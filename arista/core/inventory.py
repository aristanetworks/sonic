from collections import defaultdict

# NOTE: these import are for inventory objects critical to the .core package
# pylint: disable=unused-import
from ..inventory.reloadcause import ReloadCause
from ..inventory.slot import Slot
from ..inventory.watchdog import Watchdog

class Inventory(object):
   def __init__(self):
      self.sfpRange = []
      self.qsfpRange = []
      self.osfpRange = []
      self.allXcvrsRange = []

      self.portStart = None
      self.portEnd = None

      self.leds = {}
      self.ledGroups = {}

      self.xcvrs = {}

      # These two are deprecated
      self.xcvrLeds = defaultdict(list)
      self.statusLeds = []

      self.psus = []

      self.psuSlots = []

      self.fans = []

      self.fanSlots = []

      self.watchdog = Watchdog()

      self.powerCycles = []

      self.interrupts = {}

      self.resets = {}

      self.phys = []

      self.slots = []

      self.temps = []

      self.gpios = {}

   def addPorts(self, sfps=None, qsfps=None, osfps=None):
      if sfps:
         self.sfpRange = sfps
      if qsfps:
         self.qsfpRange = qsfps
      if osfps:
         self.osfpRange = osfps

      self.allXcvrsRange = sorted(self.sfpRange + self.qsfpRange +
                                  self.osfpRange)
      self.portStart = self.allXcvrsRange[0]
      self.portEnd = self.allXcvrsRange[-1]

   def addXcvr(self, xcvr):
      self.xcvrs[xcvr.xcvrId] = xcvr
      xcvrReset = xcvr.getReset()
      if xcvrReset is not None:
         self.resets[xcvrReset.getName()] = xcvrReset
      return xcvr

   def getXcvrs(self):
      return self.xcvrs

   def getXcvr(self, xcvrId):
      return self.xcvrs[xcvrId]

   def getPortToEepromMapping(self):
      eepromPath = '/sys/class/i2c-adapter/i2c-{0}/{0}-{1:04x}/eeprom'
      return {xcvrId : eepromPath.format(xcvr.addr.bus, xcvr.addr.address)
               for xcvrId, xcvr in self.xcvrs.items()}

   def getPortToI2cAdapterMapping(self):
      return {xcvrId : xcvr.addr.bus for xcvrId, xcvr in self.xcvrs.items()}

   def addLed(self, led):
      self.leds[led.getName()] = led
      return led

   def addLedGroup(self, name, leds):
      self.ledGroups[name] = leds
      for led in leds:
         self.addLed(led)
      return name, leds

   def addLeds(self, leds):
      for led in leds:
         self.addLed(led)
      return leds

   def getLed(self, name):
      return self.leds[name]

   def getLedGroup(self, name):
      return self.ledGroups[name]

   def getLeds(self):
      return self.leds

   def getLedGroups(self):
      return self.ledGroups

   def addPsuSlot(self, slot):
      self.psuSlots.append(slot)
      return slot

   def getPsuSlot(self, index):
      return self.psuSlots[index]

   def getPsuSlots(self):
      return self.psuSlots

   def getNumPsuSlots(self):
      return len(self.psuSlots)

   def addPsu(self, psu):
      self.psus.append(psu)
      return psu

   def addPsus(self, psus):
      self.psus.extend(psus)
      return psus

   def getPsus(self):
      return self.psus

   def getPsu(self, index):
      return self.psus[index]

   def getNumPsus(self):
      return len(self.psus)

   def addFan(self, fan):
      self.fans.append(fan)
      return fan

   def addFans(self, fans):
      self.fans.extend(fans)
      return fans

   def getFan(self, index):
      return self.fans[index]

   def getFans(self):
      return self.fans

   def getNumFans(self):
      return len(self.fans)

   def addFanSlot(self, slot):
      self.fanSlots.append(slot)
      return slot

   def addFanSlots(self, slots):
      self.fanSlots.extend(slots)
      return slots

   def getFanSlot(self, slotId):
      return self.fanSlots[slotId]

   def getFanSlots(self):
      return self.fanSlots

   def addWatchdog(self, watchdog):
      self.watchdog = watchdog
      return watchdog

   def getWatchdog(self):
      return self.watchdog

   def addPowerCycle(self, powerCycle):
      self.powerCycles.append(powerCycle)
      return powerCycle

   def getPowerCycles(self):
      return self.powerCycles

   def addInterrupt(self, interrupt):
      self.interrupts[interrupt.getName()] = interrupt
      return interrupt

   def addInterrupts(self, interrupts):
      self.interrupts.update(interrupts)
      return interrupts

   def getInterrupts(self):
      return self.interrupts

   def addReset(self, reset):
      self.resets[reset.getName()] = reset
      return reset

   def addResets(self, resets):
      self.resets.update(resets)
      return resets

   def getResets(self):
      return self.resets

   def addPhy(self, phy):
      self.phys.append(phy)
      return phy

   def getPhys(self):
      return self.phys

   def addSlot(self, slot):
      self.slots.append(slot)
      return slot

   def getSlots(self):
      return self.slots

   def addTemp(self, temp):
      self.temps.append(temp)
      return temp

   def getTemps(self):
      return self.temps

   def addGpio(self, gpio):
      self.gpios[gpio.getName()] = gpio
      return gpio

   def addGpios(self, gpios):
      self.gpios.update(gpios)
      return gpios

   def getGpios(self):
      return self.gpios

   def getGpio(self, name):
      return self.gpios[name]

   def __diag__(self, ctx):
      return {
         "version": 1,
         "name": self.__class__.__name__,
         # vars
         "sfp": self.sfpRange,
         "qsfp": self.qsfpRange,
         "osfp": self.osfpRange,
         "port_start": self.portStart,
         "port_end": self.portEnd,
         # objects
         "leds": [l.genDiag(ctx) for l in self.leds.values()],
         # TODO led groups
         # TODO watchdog
         "xcvrs": [x.genDiag(ctx) for x in self.xcvrs.values()],
         "psus": [p.genDiag(ctx) for p in self.psus],
         "psuSlots": [s.genDiag(ctx) for s in self.psuSlots],
         "fans": [f.genDiag(ctx) for f in self.fans],
         "fanSlots": [s.genDiag(ctx) for s in self.fanSlots],
         "interrupts": [i.genDiag(ctx) for i in self.interrupts.values()],
         "resets" : [r.genDiag(ctx) for r in self.resets.values()],
         "phys" : [p.genDiag(ctx) for p in self.phys],
         "slot" : [s.genDiag(ctx) for s in self.slots],
         "temps" : [t.genDiag(ctx) for t in self.temps],
         "gpios" : [g.genDiag(ctx) for g in self.gpios.values()],
      }
