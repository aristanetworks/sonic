from ...core.log import getLogger
from ...core.quirk import QuirkDesc

from ...drivers.isl68137 import Raa228228KernelDriver
from .isl68137 import Isl68137

logging = getLogger(__name__)

class Raa228228GainQuirk(QuirkDesc):
   def __init__(self, model=None, gain=None, **kwargs):
      super().__init__(**kwargs)
      self.model = model
      self.gain = gain

   def run(self, component):
      driver = component.getUserDriver()
      model = driver.read_block_data(0x9a)
      if model != self.model:
         return
      driver.write_byte_data(0x00, 0x00)
      driver.write_bytes([0xde] + self.gain)
      if driver.read_bytes([0xde], 4) != self.gain:
         logging.error("Failed to apply %s", self.description)

class Raa228228(Isl68137):
   DRIVER = Raa228228KernelDriver

# isl68137 module doesn't list RAA228926, but RAA228228 should be
# compatible for monitoring
class Raa228926(Raa228228):
   pass
