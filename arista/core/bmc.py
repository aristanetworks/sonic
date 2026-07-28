from .bootloader import Uboot
from .fixed import FixedSystem
from .sku import Sku
from .utils import simulateWith

class HostCpuManager:
   def __init__(self):
      self.hostCpuSidIndex = {}

   def registerHostCpuCls(self, cls):
      for sid in cls.SID:
         self.hostCpuSidIndex[sid] = cls
      return cls

   def loadHostCpu(self, platform):
      sid = platform.cpuEeprom.prefdl().get('SID')
      cpuCls = self.hostCpuSidIndex.get(sid)
      if cpuCls is not None:
         return platform.newComponent(cpuCls)
      return None

hostCpuManager = HostCpuManager()

def registerHostCpu():
   def wrapper(cls):
      return hostCpuManager.registerHostCpuCls(cls)
   return wrapper

class BmcHostCpu(Sku):
   pass

class BmcSubsystem(FixedSystem):

   def __init__(self, **kwargs):
      super(BmcSubsystem, self).__init__(**kwargs)
      self.bmc = self.createBmc()
      self.bmcEeprom = self.createBmcEeprom()
      self.cpuEeprom = self.createCpuEeprom()
      self.chassisEeprom = self.createChassisEeprom()
      self.hostCpu = None
      self.newComponent(Uboot)

   def createHostCpu(self):
      self.hostCpu = hostCpuManager.loadHostCpu(self)

   def setupEeproms(self):
      self.bmcEeprom.setup()
      self.cpuEeprom.setup()

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
