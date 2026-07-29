
from ..core.cause import HardwareReloadCauseProvider, ReloadCauseProviderHelper
from ..core.component.component import Component

from ..drivers.rpc import LinecardRpcClientDriver

class RpcReloadCauseProviderImpl(HardwareReloadCauseProvider):
   def __init__(self, rpc, **kwargs):
      super().__init__(name=str(rpc), **kwargs)
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
      self.inventory.addReloadCauseProvider(
         RpcReloadCauseProviderImpl(
            self,
            **({'priority': kwargs['causePriority']}
               if 'causePriority' in kwargs else {}),
         ))

   def getReloadCauseData(self):
      return self.driver.getReloadCauseData()

   def addSeuReporter(self, component):
      reporter = self.driver.getSeuReporter(component)
      return self.inventory.addSeuReporter(reporter)
