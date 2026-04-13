from .config import Config
from .log import getLogger
from .metainventory import MetaInventory
from .reboot import LinecardRebootManager
from .sku import Sku
from .utils import clog

logging = getLogger(__name__)

class Modular(Sku):

   NUM_SUPERVISORS = None
   NUM_LINECARDS = None
   NUM_FABRICS = None
   NUM_FANS = None
   NUM_PSUS = None

   def __init__(self, inventory=None, **kwargs):
      inventory = inventory or MetaInventory()
      super(Modular, self).__init__(inventory=inventory, **kwargs)
      self.inventory.invs = iter(self.iterAllInventories())

      self.supervisors = [None] * self.NUM_SUPERVISORS
      self.active = None

   def genDiag(self, ctx):
      if ctx.performIo:
         self.loadAll()

      data = super(Modular, self).genDiag(ctx)
      data.update({
         "supervisors": [s.genDiag(ctx) for s in self.iterSupervisors()],
         "linecardSlots": [s.genDiag(ctx) for s in
                           self.iterLinecards(presentOnly=False, key=lambda s: s)],
         "fabricSlots": [s.genDiag(ctx) for s in
                         self.iterFabrics(presentOnly=False, key=lambda s: s)],
         "fanSlots": [s.genDiag(ctx) for s in self.iterFans()],
         "psuSlots": [s.genDiag(ctx) for s in self.iterPsus()],
      })
      return data

   def iterCards(self):
      for linecard in self.iterLinecards():
         yield linecard
      for fabric in self.iterFabrics():
         yield fabric

   def iterAllInventories(self):
      for inv in self.active.iterInventory():
         yield inv
      for card in self.iterCards():
         yield card.inventory

   def getEeprom(self):
      assert self.active
      return self.active.readChassisEeprom()

   def insertSupervisor(self, supervisor, slotId, active=False):
      assert self.supervisors[slotId - 1] is None
      self.supervisors[slotId - 1] = supervisor
      if active:
         self.active = supervisor

   def iterSupervisors(self, presentOnly=True):
      for sup in self.supervisors:
         if sup is None and presentOnly:
            continue
         yield sup

   def loadLinecards(self, slotIds=None):
      for slot in self.active.linecardSlots[:self.NUM_LINECARDS]:
         if slotIds is not None and slot.slotId not in slotIds:
            continue
         try:
            logging.debug('Loading linecard slot %d', slot.slotId)
            standbyOnly = Config().linecard_standby_only
            slot.loadCard(standbyOnly=standbyOnly)
         except Exception as ex: # pylint: disable=broad-except
            logging.error('Failed to load linecard slot %d: %s', slot.slotId, ex)

   def loadFabrics(self, slotIds=None):
      for slot in self.active.fabricSlots[:self.NUM_FABRICS]:
         if slotIds is not None and slot.slotId not in slotIds:
            continue
         try:
            logging.debug('Loading fabric slot %d', slot.slotId)
            slot.loadCard()
         except Exception as ex: # pylint: disable=broad-except
            logging.error('Failed to load fabric slot %d: %s', slot.slotId, ex)

   def loadPsus(self, slotIds=None):
      for slot in self.active.psuSlots[:self.NUM_PSUS]:
         if slotIds is not None and slot.slotId not in slotIds:
            continue
         logging.debug('Loading psu slot %d', slot.slotId)
         slot.load()

   def loadAll(self):
      self.loadPsus()
      self.loadFabrics()
      self.loadLinecards()

   def _iterSlots(self, slots, count, presentOnly=True, key=lambda s: s):
      for slot in slots[:count]:
         item = key(slot)
         if item is None and presentOnly:
            continue
         yield item

   def iterLinecards(self, presentOnly=True, key=lambda s: s.card):
      return self._iterSlots(self.active.linecardSlots, self.NUM_LINECARDS,
                             presentOnly=presentOnly, key=key)

   def iterFabrics(self, presentOnly=True, key=lambda s: s.card):
      return self._iterSlots(self.active.fabricSlots, self.NUM_FABRICS,
                             presentOnly=presentOnly, key=key)

   def iterFans(self, presentOnly=True):
      return self._iterSlots(self.active.fanSlots, self.NUM_FANS,
                             presentOnly=presentOnly)

   def iterPsus(self, presentOnly=True):
      return self._iterSlots(self.active.psuSlots, self.NUM_PSUS,
                             presentOnly=presentOnly)

   def powerOffLinecards(self, linecards=None):
      return LinecardRebootManager(self, linecards).powerOffLinecards()

   def rebootLinecards(self, linecards=None, mode='soft'):
      return LinecardRebootManager(self, linecards).rebootLinecards(mode)

   def powerOffFabrics(self, fabrics=None):
      if fabrics is None:
         fabrics = self.iterFabrics()

      for fabric in fabrics:
         try:
            if fabric.slot.getPresence() and fabric.poweredOn():
               logging.info('Power off fabric card %s...', fabric)
               fabric.powerOnIs(False)
               logging.info('Power off fabric card %s succeeded', fabric)
            else:
               logging.info('Fabric card %s not present or powered off', fabric)
         except:  # pylint: disable=bare-except
            logging.exception('Failed to power off fabric %s', fabric)
            clog('Failed to power off fabric %s', fabric)
