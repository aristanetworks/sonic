
from ..core.fixed import FixedSystem
from ..core.platform import getPlatformCls
from ..core.utils import inSimulation
from ..core.log import getLogger

logging = getLogger(__name__)

class Supervisor(FixedSystem):
   def __init__(self, chassis=None, slot=None, **kwargs):
      super(Supervisor, self).__init__(**kwargs)
      self.chassis = chassis
      self.slot = slot
      self.slotId = None
      self.chassisEeproms = []

      self.linecardSlots = []
      self.fabricSlots = []
      self.psuSlots = []
      self.fanSlots = []

   def readChassisEeprom(self):
      if inSimulation():
         return { 'SKU': 'DCS-7808-CH' }
      for eeprom in self.chassisEeproms:
         try:
            eeprom.setup()
            return eeprom.prefdl()
         except ValueError:
            logging.warning('failed to read chassis eeprom %s', eeprom)
      return None

   def getPresence(self):
      # TODO: deal with peer supervisor
      return True

   def getChassis(self):
      if self.chassis:
         return self.chassis

      logging.debug('Identifying chassis')
      eeprom = self.readChassisEeprom()
      if eeprom is None:
         raise IOError('failed to read chassis eeprom')

      chassisCls = getPlatformCls(eeprom.get('SID'), eeprom.get('SKU'))
      self.chassis = chassisCls()
      self.chassis.insertSupervisor(self, self.getSlotId(), active=True)

      return self.chassis

   def readSlotId(self):
      if inSimulation():
         return 0
      raise NotImplementedError

   def getSlotId(self):
      if self.slotId is None:
         self.slotId = self.readSlotId()
      return self.slotId


