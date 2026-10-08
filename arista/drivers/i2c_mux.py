import os

from ..core.driver.kernel.i2c import I2cKernelDriver
from ..core.types import I2cBusAddr
from ..libs.i2c import i2cBusFromName

class I2cMuxBus(object):
   def __init__(self, parent, channel, smbusBlock=True):
      self.parent = parent
      self.channel = channel
      self.smbusBlock = smbusBlock
      self.bus_ = None
      self.name_ = None

   def __int__(self):
      return self.bus

   def resolvePath(self):
      channelPath = os.path.join(
          self.parent.getSysfsPath(),
          f'channel-{self.channel}',
      )
      targetDevicePath = os.path.realpath(channelPath)
      nameFilePath = os.path.join(targetDevicePath, 'name')
      with open(nameFilePath, encoding='utf-8') as f:
         self.name_ = f.read().strip()
      self.bus_ = i2cBusFromName(self.name_, force=True)

   @property
   def bus(self):
      if self.bus_ is None:
         self.resolvePath()
      return self.bus_

   def i2cAddr(self, address, **kwargs):
      return I2cBusAddr(self, address, block=self.smbusBlock, **kwargs)

class I2cMuxKernelDriver(I2cKernelDriver):

   NUM_CHANNELS = 0
   I2C_BUS_CLS = I2cMuxBus
   SMBUS_BLOCK = True

   def getBus(self, channel):
      assert 0 <= channel < self.NUM_CHANNELS
      return self.I2C_BUS_CLS(self, channel, smbusBlock=self.SMBUS_BLOCK)
