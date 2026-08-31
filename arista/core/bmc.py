from .bootloader import Uboot
from .fixed import FixedSystem
from .sku import Sku
from .utils import simulateWith

class HostSwitchManager:
   def __init__(self):
      self.hostSwitchSidIndex = {}

   def registerHostSwitchCls(self, cls):
      for sid in cls.SID:
         self.hostSwitchSidIndex[sid] = cls
      return cls

   def loadHostSwitch(self, platform):
      sid = platform.chassisEeprom.prefdl().get('SID')
      hostSwitchCls = self.hostSwitchSidIndex.get(sid)
      if hostSwitchCls is not None:
         return platform.newComponent(hostSwitchCls)
      return None

hostSwitchManager = HostSwitchManager()

def registerHostSwitch():
   def wrapper(cls):
      return hostSwitchManager.registerHostSwitchCls(cls)
   return wrapper

class BmcHostSwitch(Sku):
   pass

class BmcSubsystem(FixedSystem):

   def __init__(self, **kwargs):
      super(BmcSubsystem, self).__init__(**kwargs)
      self.bmc = self.createBmc()
      self.bmcEeprom = self.createBmcEeprom()
      self.cpuEeprom = self.createCpuEeprom()
      self.chassisEeprom = self.createChassisEeprom()
      self.hostSwitch= None
      self.newComponent(Uboot)

   def createHostSwitch(self):
      self.hostSwitch = hostSwitchManager.loadHostSwitch(self)

   def setupEeproms(self):
      self.bmcEeprom.setup()
      self.cpuEeprom.setup()
      self.chassisEeprom.setup()

   def createBmc(self):
      raise NotImplementedError

   def createBmcEeprom(self):
      raise NotImplementedError

   def createCpuEeprom(self):
      raise NotImplementedError

   def createChassisEeprom(self):
      raise NotImplementedError

   def cpuCpldAddr(self):
      raise NotImplementedError

   def getEepromSim(self):
      return { 'SKU': 'simulation', 'HwApi': '42' }

   @simulateWith(getEepromSim)
   def getEeprom(self):
      return self.bmcEeprom.prefdl()
