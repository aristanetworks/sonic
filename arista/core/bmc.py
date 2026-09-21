from abc import ABC, abstractmethod

from .bootloader import Uboot
from .component import Component
from .fixed import FixedSystem
from .sku import Sku
from .utils import simulateWith

class Bmc(Component, ABC):
   """Base component for BMC-local hardware and EEPROM wiring."""

   MODEL = ()

   def __init__(self, *args, **kwargs):
      super().__init__(*args, **kwargs)
      self.bmcEeprom = self.createBmcEeprom()
      self.cpuEeprom = self.createCpuEeprom()
      self.chassisEeprom = self.createChassisEeprom()
      self.setupEeproms()
      self.newComponent(Uboot)

   @classmethod
   @abstractmethod
   def readChassisEeprom(cls):
      """Read and return the chassis EEPROM PreFDL."""

   def createBmcEeprom(self):
      raise NotImplementedError

   def createCpuEeprom(self):
      raise NotImplementedError

   def createChassisEeprom(self):
      raise NotImplementedError

   def setupEeproms(self):
      self.bmcEeprom.setup()
      self.cpuEeprom.setup()
      self.chassisEeprom.setup()

   def cpuCpldAddr(self):
      raise NotImplementedError

   def getEepromSim(self):
      return { 'SKU': 'simulation', 'HwApi': '42' }

   @simulateWith(getEepromSim)
   def getEeprom(self):
      return self.bmcEeprom.prefdl()

   def getBmcBaseMac(self):
      return self.bmcEeprom.prefdl().get('MAC')

class BmcHostSwitch(Sku):
   pass

class BmcSubsystem(FixedSystem):

   BMC_CLS = None
   HOST_SWITCH_CLS = None

   def __init__(self, **kwargs):
      super(BmcSubsystem, self).__init__(**kwargs)
      if self.BMC_CLS is None:
         raise NotImplementedError
      self.bmc = self.newComponent(self.BMC_CLS)
      self.bmcEeprom = self.bmc.bmcEeprom
      self.cpuEeprom = self.bmc.cpuEeprom
      self.chassisEeprom = self.bmc.chassisEeprom
      self.hostSwitch = self.createHostSwitch()

   def createHostSwitch(self):
      if self.HOST_SWITCH_CLS is not None:
         return self.newComponent(self.HOST_SWITCH_CLS)
      return None

   def cpuCpldAddr(self):
      return self.bmc.cpuCpldAddr()

   def getEeprom(self):
      return self.bmc.getEeprom()

   def getBmcBaseMac(self):
      return self.bmc.getBmcBaseMac()
