
import copy

from .component import Priority
from .component.slot import SlotComponent
from .component.unmanaged import UnmanagedComponent
from .dynload import importSubmodules
from .log import getLogger
from .utils import JsonStoredData, inSimulation

from ..drivers.pmbus import PsuPmbusDetect
from ..descs.psu import PsuDesc, PsuStatusPolicy

from ..inventory.psu import PsuSlot as PsuSlotInv
from ..inventory.psu import Psu as PsuInv

logging = getLogger(__name__)

class PsuImpl(PsuInv):
   # TODO: placeholder PsuImpl, move to the psu class itself
   def __init__(self, slot, model, psu):
      self.slot = slot
      self.psu = psu
      self.model = model

   def getName(self):
      return self.slot.getName()

   def getModel(self):
      return self.model.identifier.aristaName

   def getRevision(self):
      return self.model.identifier.metadata['revision']

   def getSerial(self):
      return self.model.identifier.metadata['serial']

   def getStatus(self):
      return self.slot.getStatus()

   def getCapacity(self):
      return self.model.CAPACITY

   def getMfr(self):
      return self.model.identifier.metadata

   def getFans(self):
      return self.psu.getInventory().getFans()

   def getTemps(self):
      return self.psu.getInventory().getTemps()

   def getRails(self):
      return self.psu.getInventory().getRails()

class PsuSlotImpl(PsuSlotInv):
   def __init__(self, slot):
      self.slot = slot
      self.psu = None

   def getId(self):
      return self.slot.slotId

   def getName(self):
      return 'psu%s' % self.slot.slotId

   def getPresence(self):
      return self.slot.getPresence()

   def getStatus(self):
      return self.slot.isPowerGood()

   def getLed(self):
      return self.slot.led

   def getPsu(self):
      if not self.slot.getPresence():
         return None
      # TODO: in the future handle PSU hotswap with potentially a different model
      return self.psu

   def insertPsu(self, psu):
      if self.psu is not None:
         logging.debug("%s overriding already loaded psu with %s", self.getName(),
                       self.psu)
      self.psu = PsuImpl(self, self.slot.model, psu)

class PsuIdent:
   def __init__(self, partName=None, aristaName=None, airflow=None, metadata=None):
      self.partName = partName
      self.aristaName = aristaName
      self.airflow = airflow
      self.metadata = metadata

class PsuModel:
   MANUFACTURER = None
   MANUFACTURER_ALIASES = []
   IDENTIFIERS = []
   IPMI_ADDR = 0x50
   PMBUS_ADDR = None

   DUAL_INPUT = False
   CAPACITY = 0 # in Watts

   PMBUS_CLS = None
   DRIVER = None
   DESCRIPTION = PsuDesc()

   AUTODETECT_IPMI = False
   AUTODETECT_PMBUS = True

   SUPPORT_SMBUS_PING = True

   def __init__(self, identifier):
      self.identifier = identifier

   def getProductName(self):
      return self.identifier.aristaName

   @classmethod
   def isManufacturer(cls, name):
      name = name.rstrip()
      if name == cls.MANUFACTURER.lower():
         return True
      for alias in cls.MANUFACTURER_ALIASES:
         if name == alias.lower():
            return True
      return False

class PsuManager:
   def __init__(self):
      self.psus_ = []
      self.modules = None
      self.package = 'arista.components.psu'

   def _loadModule(self, module):
      for value in module.__dict__.values():
         if isinstance(value, type) and issubclass(value, PsuModel) and \
            value != PsuModel:
            self.psus_.append(value)
      self.psus_ = list(sorted(self.psus_, key=lambda p: not p.SUPPORT_SMBUS_PING))

   def loadPsuModels(self):
      if self.modules is not None:
         return
      self.modules = importSubmodules(self.package)
      for name, module in self.modules.items():
         if '/tests/' in name:
            continue
         self._loadModule(module)

   @property
   def psuModels(self):
      if not self.psus_:
         self.loadPsuModels()
      return self.psus_

   def psuForIdentifier(self, clsname, identifier):
      for model in self.psuModels:
         if model.__name__ == clsname:
            return model(identifier)
      return None

   def identifyPsuModel(self, model, detector):
      if not model.isManufacturer(detector.id().lower()):
         return None

      for ident in model.IDENTIFIERS:
         if ident.partName.rstrip() == detector.model().rstrip():
            ident = copy.deepcopy(ident)
            ident.metadata = detector.getMetadata()
            return ident

      return None

   def autodetectPmbusPsu(self, slot, tryAll=True):
      psus = []
      detectors = {}
      # try expected PSU models first
      models = slot.psus
      if tryAll:
         models = slot.psus + [p for p in self.psuModels \
               if p not in slot.psus and p.AUTODETECT_PMBUS]
      for model in models:
         if not model.PMBUS_ADDR:
            continue

         try:
            # cache pmbus detector to minimize IO operations
            detector = detectors.get(model.PMBUS_ADDR)
            detectorCached = True
            if detector is None:
               detector = PsuPmbusDetect(slot.addrFunc(model.PMBUS_ADDR))
               detectorCached = False
               detectors[model.PMBUS_ADDR] = detector

            if not detector.exists():
               # No PMBus device found at the address expected for this model
               if model.SUPPORT_SMBUS_PING or not detector.checkId():
                  continue

            if not detectorCached:
               logging.debug('searching for psu vendor "%s" model "%s"',
                             detector.id(), detector.model())

            ident = self.identifyPsuModel(model, detector)
            if ident is not None:
               # TODO: add logging
               logging.debug('found matching psu %s', model.__name__)
               psus.append(model(ident))
         except Exception as e: # pylint: disable=broad-except
            logging.error('something happened while trying to detect the psu: %s', e)

      return psus

_manager = PsuManager()
def getPsuManager():
   return _manager

class PsuSlot(SlotComponent):

   PRIORITY = Priority.POWER

   def __init__(self, slotId=None, desc=None, addrFunc=None, psus=None,
                presentGpio=None, inputOkGpio=None, outputOkGpio=None, led=None,
                forcePsuLoad=False, autoDetectTryAll=True,
                psuStatusPolicy=PsuStatusPolicy.GPIO_OR_PMBUS_POWER,
                **kwargs):
      super().__init__(**kwargs)
      self.slotId = slotId
      self.model = None

      self.desc = desc
      self.addrFunc = addrFunc
      self.presentGpio = presentGpio
      self.inputOkGpio = inputOkGpio
      self.outputOkGpio = outputOkGpio
      self.led = led
      self.psus = psus or []
      self.forcePsuLoad = forcePsuLoad
      self.autoDetectTryAll = autoDetectTryAll and not forcePsuLoad
      self.psuStatusPolicy = psuStatusPolicy

      if self.addrFunc:
         self.addrFunc(0x00) # workaround to configure a bus wide parameter
      else:
         assert len(psus) == 1, "Fixed PSU cannot list more than one"
      self.psuSlot = self.inventory.addPsuSlot(PsuSlotImpl(self))
      self.psuInv = None
      self.psu = None
      self.load(cacheOnly=True) # no IO in the constructor

   def genDiag(self, ctx):
      data = super().genDiag(ctx)
      data.update({
             'psu': self.psu.genDiag(ctx) if self.psu else None,
      })
      return data

   def _forcePsuModel(self, model):
      ident = copy.deepcopy(model.IDENTIFIERS[0])
      ident.metadata = PsuPmbusDetect.UNKNOWN_METADATA
      return model(ident)

   def autodetectPsuModel(self):
      psus = getPsuManager().autodetectPmbusPsu(self, self.autoDetectTryAll)
      if not psus:
         if self.forcePsuLoad:
            assert len(self.psus) == 1, "Forcing only works with one model"
            return self._forcePsuModel(self.psus[0])
         return None

      assert len(psus) == 1, 'Multiple PSUs matched the description'
      return psus[0]

   def getCacheStore(self):
      return JsonStoredData('psu_slot_%d.json' % self.slotId)

   def getCache(self):
      cache = self.getCacheStore()
      return cache.readOrClear()

   def setCache(self):
      cache = self.getCacheStore()
      cache.write({
         'cls': self.model.__class__.__name__,
         'identifier': self.model.identifier.__dict__,
      }, mode='w+')

   def clearCache(self):
      self.getCacheStore().clear()

   def loadModelFromCache(self):
      data = self.getCache()
      if data is None:
         return None

      clsname = data['cls']
      identifier = PsuIdent(**data['identifier'])
      return getPsuManager().psuForIdentifier(clsname, identifier)

   def logPsuInformation(self):
      logging.debug("PSU %d name: %s", self.slotId, self.model.identifier.aristaName)
      for key, value in self.model.identifier.metadata.items():
         logging.debug("PSU %d %s: %s", self.slotId, key, value)

   def loadPsuModel(self, useCache=True, cacheOnly=False):
      if useCache:
         self.model = self.loadModelFromCache()
         if self.model is not None:
            logging.debug("PSU %d loaded from cache", self.slotId)
            return self.model

      if cacheOnly:
         logging.debug("PSU %d model not found in cache, skipping IO",
                       self.slotId)
         return None

      self.model = self.autodetectPsuModel()
      if self.model is None:
         logging.error("PSU %d unknown, discovery failed", self.slotId)
         return None

      logging.debug("PSU %d discovered", self.slotId)
      self.logPsuInformation()

      if not inSimulation():
         self.setCache()

      return self.model

   def addPsu(self, desc):
      if self.addrFunc:
         addr = self.addrFunc(self.model.PMBUS_ADDR)
         psu = self.newComponent(
            self.model.PMBUS_CLS,
            name=self.model.DRIVER,
            addr=addr,
         )
      else:
         psu = self.newComponent(UnmanagedComponent)
      psu.addTempSensors(desc.sensors)
      psu.addFans(desc.fans)
      psu.addRails(desc.rails)
      self.psu = psu
      self.components = self.components[:-1]
      return psu

   def maybeLoadPsuDefinitions(self):
      if self.psusLoaded:
         return

   def load(self, useCache=True, cacheOnly=False):
      if not useCache:
         self.clearCache()

      if not cacheOnly and not self.getPresence():
         logging.debug("PSU %d is not inserted", self.slotId)
         self.clearCache()
         return

      if not self.loadPsuModel(useCache=useCache, cacheOnly=cacheOnly):
         return

      desc = copy.deepcopy(self.model.DESCRIPTION)
      desc.setPsuId(self.slotId)
      desc.setAirflow(airflow=self.model.identifier.airflow)
      psu = self.addPsu(desc)
      self.psuSlot.insertPsu(psu)

      if self.inputOkGpio is None:
         self.inputOkGpio = psu.driver.getInputOkGpio()
      if self.outputOkGpio is None:
         self.outputOkGpio = psu.driver.getOutputOkGpio()

   def getPresence(self):
      # If the GPIO is just set to True, it's fixed and it's always present.
      if self.presentGpio is True:
         return True
      return self.presentGpio.isActive()

   def _getGpioActiveOr(self, gpio):
      if gpio is None:
         return True
      if isinstance(gpio, list):
         return bool((g for g in gpio if g.isActive()))
      return gpio.isActive()

   def isInputGood(self):
      return self._getGpioActiveOr(self.inputOkGpio)

   def isOutputGood(self):
      return self._getGpioActiveOr(self.outputOkGpio)

   def checkPmbusStatus(self):
      if self.psu and self.psu.driver is not None:
         try:
            return self.psu.driver.isPmbusStatusGood()
         except Exception as e: # pylint: disable=broad-except
            logging.error("PSU %d failed to read PMBus status: %s",
                          self.slotId, e)
            return None
      else:
         logging.debug("PSU %d has no PMBus driver cannot read status", self.slotId)
         return None

   def isPowerGood(self):
      if not self.getPresence():
         return False
      if self.psuStatusPolicy == PsuStatusPolicy.PMBUS_STATUS:
         pmbusStatus = self.checkPmbusStatus()
         if pmbusStatus is True:
            return True
         if pmbusStatus is None:
            logging.debug("PSU %d PMBus status unknown, "
                          "falling back to input and output pins for status",
                           self.slotId)
         else:
            logging.debug("PSU %d PMBus status check failed, "
                          "falling back to input and output pins for status",
                          self.slotId)
      if not self.isInputGood():
         return False
      return self.isOutputGood()

   def setup(self):
      self.load(useCache=False)
      if self.psu:
         # initialize the PSU, iterComponent will not run on it since the list
         # has already been computed.
         self.psu.setup()
         self.psu.finish()
