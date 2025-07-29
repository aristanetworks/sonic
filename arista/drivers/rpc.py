
from ..core.config import Config
from ..core.driver.user import UserDriver
from ..inventory.led import Led
from ..inventory.powercycle import PowerCycle
from ..inventory.seu import SeuReporter
from ..utils.rpc.client import RpcClient

class RpcLedImpl(Led):
   def __init__(self, driver, desc, **kwargs):
      self.driver = driver
      self.desc = desc

   def getName(self):
      return self.desc.name

   def getColor(self):
      return self.driver.client.linecardStatusLedColorGet()

   def setColor(self, color):
      return self.driver.client.linecardStatusLedColorSet(color)

   def isStatusLed(self):
      return True

class RpcPowerCycleImpl(PowerCycle):
   def __init__(self, driver, desc, **kwargs):
      self.driver = driver
      self.desc = desc

   def ensureAvailable(self):
      pass

   def powerCycle(self):
      return self.driver.client.linecardSelfPowerCycle()

class RpcSeuReporter(SeuReporter):
   def __init__(self, driver, component):
      self.driver = driver
      self.component = component

   def getComponent(self):
      return self.component

   def powerCycleOnSeu(self, on=None):
      return False

   def hasSeuError(self):
      return self.driver.client.hasSeuError(str(self.component))

class LinecardRpcClientDriver(UserDriver):
   def __init__(self, slotId=None, **kwargs):
      super().__init__(**kwargs)
      self.client = RpcClient(Config().api_rpc_sup, Config().api_rpc_port)

   def getLed(self, desc, **kwargs):
      return RpcLedImpl(self, desc, **kwargs)

   def getPowerCycle(self, desc, **kwargs):
      return RpcPowerCycleImpl(self, desc, **kwargs)

   def getReloadCauseData(self):
      return self.client.getLinecardRebootCause()

   def getSeuReporter(self, component):
      return RpcSeuReporter(self, component)
