import yaml

from ...core.component import Component
from ...core.driver.user.aspeed_scu import AspeedScuDriver
from ...core.types import I2cBus
from ...core.utils import inSimulation
from ...inventory.programmable import Programmable
from ...drivers.aspeed.watchdog import AspeedWatchdog

from .cause import AspeedReloadCauseProvider

class BMCProgrammable(Programmable):
   def __init__(self, bmc):
      self.bmc = bmc

   def getComponent(self):
      return self.bmc

   def getDescription(self):
      return 'BMC'

   def getVersion(self):
      return self.bmc.getVersion()

class AspeedSoc(Component):
   I2C_BASE   = None
   I2C_STRIDE = None
   I2C_SUFFIX = None
   RELOAD_CAUSE_REGMAP = None

   def __init__(self, *args, **kwargs):
      super().__init__(*args, **kwargs)
      self.inventory.addProgrammable(BMCProgrammable(self))

   def getVersion(self):
      if inSimulation():
         return 'N/A'
      try:
         with open('/etc/sonic/sonic_version.yml', encoding='utf-8') as f:
            data = yaml.safe_load(f)
      except (FileNotFoundError, yaml.YAMLError):
         return 'N/A'
      return data.get('build_version', 'N/A')

   def getSmbus(self, bus):
      addr = self.I2C_BASE + (bus + 1) * self.I2C_STRIDE
      return I2cBus('%08x.%s' % (addr, self.I2C_SUFFIX))

   def createWatchdog(self):
      watchdog = AspeedWatchdog()
      self.inventory.addWatchdog(watchdog)
      return watchdog

   def addReloadCauseProvider(self, priority):
      if self.RELOAD_CAUSE_REGMAP is None:
         return
      driver = AspeedScuDriver()
      regs = self.RELOAD_CAUSE_REGMAP(driver) # pylint: disable=not-callable
      provider = AspeedReloadCauseProvider(regs, priority=priority)
      self.inventory.addReloadCauseProvider(provider)
