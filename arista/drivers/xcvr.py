import os

from ..core.config import Config
from ..core.driver.kernel.i2c import I2cKernelDriver
from ..core.utils import inSimulation

class XcvrKernelDriver(I2cKernelDriver):
   MODULE = 'optoe'

   def __init__(self, portName=None, **kwargs):
      super(XcvrKernelDriver, self).__init__(**kwargs)
      self.portName = portName
      if Config().xcvr_use_optoe_auto:
         self.NAME = 'optoe-auto'

   def setup(self):
      super(XcvrKernelDriver, self).setup()

      if inSimulation():
         return

      self.setPortName(self.portName)

   def setPortName(self, name):
      portNamePath = os.path.join(self.getSysfsPath(), 'port_name')
      with open(portNamePath, 'w', encoding='utf8') as f:
         f.write(name)

   def setWriteMax(self, size):
      writeMaxPath = os.path.join(self.getSysfsPath(), 'write_max')
      if os.path.exists(writeMaxPath):
         with open(writeMaxPath, 'w', encoding='utf8') as f:
            f.write(str(size))

   def getWriteMax(self):
      writeMaxPath = os.path.join(self.getSysfsPath(), 'write_max')
      if not os.path.exists(writeMaxPath):
         return 1 # NOTE: previous version of the driver hardcoded 1
      with open(writeMaxPath, encoding='utf8') as f:
         return int(f.read())

   def setBusSpeed(self, speed):
      busPath = os.path.dirname(os.path.realpath(self.getSysfsPath()))
      busSpeedPath = os.path.join(busPath, 'bus_speed')
      if os.path.exists(busSpeedPath):
         with open(busSpeedPath, 'w', encoding='utf8') as f:
            f.write(str(speed))

class CmisEepromKernelDriver(XcvrKernelDriver):
   NAME = 'optoe3'

class SfpKernelDriver(XcvrKernelDriver):
   NAME = 'optoe2'

class QsfpKernelDriver(XcvrKernelDriver):
   NAME = 'optoe1'

class OsfpKernelDriver(XcvrKernelDriver):
   NAME = 'optoe3'
