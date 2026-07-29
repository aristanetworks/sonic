
from ..core.cause import HardwareReloadCauseProvider, ReloadCauseProviderHelper
from ..core.component.component import Component

from ..descs.cause import ReloadCausePriority

from ..drivers.rpc import LinecardRpcClientDriver

class RpcReloadCauseProviderImpl(HardwareReloadCauseProvider):
   def __init__(self, rpc, priority=ReloadCausePriority.PRIMARY):
      super().__init__(name=str(rpc), priority=priority)
      self.rpc = rpc
      self.providers = []

   def process(self):
      data = self.rpc.getReloadCauseData()
      if 'reports' not in data or not data['reports']:
         return
      self.providers = data['reports'][0]['providers']

   def getRemoteProviders(self):
      return [ReloadCauseProviderHelper.fromDict(x) for x in self.providers]

class LinecardRpcClient(Component):
   DRIVER = LinecardRpcClientDriver

   def __init__(self, *args, **kwargs):
      super().__init__(*args, **kwargs)
      self.inventory.addReloadCauseProvider(RpcReloadCauseProviderImpl(self))

   def getReloadCauseData(self):
      return self.driver.getReloadCauseData()

   def addSeuReporter(self, component):
      reporter = self.driver.getSeuReporter(component)
      return self.inventory.addSeuReporter(reporter)
