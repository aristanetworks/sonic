
from ..core.driver.kernel.i2c import I2cKernelDriver
from ..core.driver.kernel.sysfs import SysfsEntryBool
from ..core.log import getLogger

logging = getLogger(__name__)

class Max31732KernelDriver(I2cKernelDriver):
   MODULE = 'amax31732'
   NAME = 'amax31732'

   def setup(self):
      super().setup()
      for desc in getattr(self, 'sensors', []):
         if desc.betaComp is None:
            continue
         name = f'temp{desc.diode + 1}_beta_comp_enable'
         entry = SysfsEntryBool(None, name, driver=self)
         action = 'enabling' if desc.betaComp else 'disabling'
         logging.debug(f"{action} beta comp for diode {desc.diode}: "
                       f"{entry.entryPath}")
         entry.write(desc.betaComp)
