from collections import defaultdict

# NOTE: these import are for inventory objects critical to the .core package
# pylint: disable=unused-import
from ..inventory.reloadcause import ReloadCause, ReloadCauseProvider
from ..inventory.slot import Slot

class Inventory():
   def __init__(self):
      self.leds = {}
      self.ledGroups = {}

      self.ethernets = {}
      self.sfps = {}
      self.qsfps = {}
      self.osfps = {}

      self.ethernetSlots = {}
      self.sfpSlots = {}
      self.qsfpSlots = {}
      self.osfpSlots = {}

      self.psus = []

      self.psuSlots = []

      self.fans = []

      self.fanSlots = []

      self.watchdogs = []

      self.powerCycles = []

      self.interrupts = {}

      self.rails = []

      self.resets = {}

      self.phys = []

      self.slots = []

      self.temps = []

      self.gpios = {}

      self.causeProviders = []

      self.programmables = []

      self.seuReporters = []

      self.switchAsics = {}

   def getXcvrs(self):
      xcvrs = {}
      xcvrs.update(self.getEthernets())
      xcvrs.update(self.getSfps())
      xcvrs.update(self.getQsfps())
      xcvrs.update(self.getOsfps())
      return xcvrs

   def addEthernet(self, eth):
      self.ethernets[eth.getId()] = eth
      return eth

   def getEthernets(self):
      return self.ethernets

   def getEthernet(self, xcvrId):
      return self.ethernets[xcvrId]

   def addSfp(self, sfp):
      self.sfps[sfp.getId()] = sfp
      return sfp

   def getSfps(self):
      return self.sfps

   def getSfp(self, xcvrId):
      return self.sfps[xcvrId]

   def addQsfp(self, qsfp):
      self.qsfps[qsfp.getId()] = qsfp
      return qsfp

   def getQsfps(self):
      return self.qsfps

   def getQsfp(self, xcvrId):
      return self.qsfps[xcvrId]

   def addOsfp(self, osfp):
      self.osfps[osfp.getId()] = osfp
      return osfp

   def getOsfps(self):
      return self.osfps

   def getOsfp(self, xcvrId):
      return self.osfps[xcvrId]

   def getXcvrSlot(self, slotId):
      return self.ethernetSlots.get(slotId) or \
             self.sfpSlots.get(slotId) or \
             self.qsfpSlots.get(slotId) or \
             self.osfpSlots.get(slotId)

   def getXcvrSlots(self):
      xcvrSlots = {}
      xcvrSlots.update(self.getEthernetSlots())
      xcvrSlots.update(self.getSfpSlots())
      xcvrSlots.update(self.getQsfpSlots())
      xcvrSlots.update(self.getOsfpSlots())
      return xcvrSlots

   def addEthernetSlot(self, slot):
      self.ethernetSlots[slot.getId()] = slot
      return slot

   def addSfpSlot(self, slot):
      self.sfpSlots[slot.getId()] = slot
      return slot

   def addQsfpSlot(self, slot):
      self.qsfpSlots[slot.getId()] = slot
      return slot

   def addOsfpSlot(self, slot):
      self.osfpSlots[slot.getId()] = slot
      return slot

   def getEthernetSlots(self):
      return self.ethernetSlots

   def getSfpSlots(self):
      return self.sfpSlots

   def getQsfpSlots(self):
      return self.qsfpSlots

   def getOsfpSlots(self):
      return self.osfpSlots

   def getPortToEepromMapping(self):
      eepromPath = '/sys/bus/i2c/devices/i2c-{0}/{0}-{1:04x}/eeprom'
      return {xcvrId : eepromPath.format(
                       xcvr.getI2cAddr().bus, xcvr.getI2cAddr().address)
              for xcvrId, xcvr in self.getXcvrs().items()}

   def getPortToI2cAdapterMapping(self):
      return {xcvrId : xcvr.getI2cAddr().bus
              for xcvrId, xcvr in self.getXcvrs().items()}

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
      self.watchdogs.append(watchdog)
      return watchdog

   def getWatchdogs(self):
      return self.watchdogs

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

   def getReset(self, name):
      return self.resets[name]

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

   def addRail(self, rail):
      self.rails.append(rail)
      return rail

   def getRails(self):
      return self.rails

   def addProgrammable(self, programmable):
      self.programmables.append(programmable)

   def getProgrammables(self):
      return self.programmables

   def addSeuReporter(self, seuReporter):
      self.seuReporters.append(seuReporter)

   def getSeuReporters(self):
      return self.seuReporters

   def addSwitchAsic(self, switchAsic):
      self.switchAsics[switchAsic.getId()] = switchAsic
      return switchAsic

   def getSwitchAsics(self):
      return self.switchAsics

   def getSwitchAsic(self, asicId):
      return self.switchAsics.get(asicId)

   def addReloadCauseProvider(self, provider):
      self.causeProviders.append(provider)

   def addReloadCauseProviders(self, providers):
      self.causeProviders.extend(providers)

   def getReloadCauseProviders(self):
      return self.causeProviders

   def __diag__(self, ctx):
      return {
         "version": 1,
         "name": self.__class__.__name__,
         # objects
         "leds": [l.genDiag(ctx) for l in self.leds.values()],
         # TODO led groups
         # TODO watchdog
         "xcvrs": [x.genDiag(ctx) for x in self.getXcvrs().values()],
         "xcvrSlots": [s.genDiag(ctx) for s in self.getXcvrSlots().values()],
         "psus": [p.genDiag(ctx) for p in self.psus],
         "psuSlots": [s.genDiag(ctx) for s in self.psuSlots],
         "fans": [f.genDiag(ctx) for f in self.fans],
         "fanSlots": [s.genDiag(ctx) for s in self.fanSlots],
         "interrupts": [i.genDiag(ctx) for i in self.interrupts.values()],
         "rails": [r.genDiag(ctx) for r in self.rails],
         "resets" : [r.genDiag(ctx) for r in self.resets.values()],
         "phys" : [p.genDiag(ctx) for p in self.phys],
         "slot" : [s.genDiag(ctx) for s in self.slots],
         "temps" : [t.genDiag(ctx) for t in self.temps],
         "gpios" : [g.genDiag(ctx) for g in self.gpios.values()],
         "programmables" : [c.genDiag(ctx) for c in self.programmables],
         "switchAsics" : [a.genDiag(ctx) for a in self.getSwitchAsics().values()],
      }
