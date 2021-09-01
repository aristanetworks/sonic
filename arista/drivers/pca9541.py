
import os
import time

from contextlib import closing

from ..core.utils import inSimulation

from .kernel import I2cKernelDriver
from .i2c import I2cDevDriver

CTRL_REG = 0x01

MYBUS = (1 << 0)
NMYBUS = (1 << 1)
BUSON = (1 << 2)
NBUSON = (1 << 3)
BUSINIT = (1 << 4)
TESTON = (1 << 6)
NTESTON = (1 << 7)

CTRL_CMDS = [0x4, 0x4, 0x5, 0x5, None, 0x4, 0x5, None, None, 0x0, 0x1, None, 0x0,
             0x0, 0x1, 0x1]

ARBITRATE_RETRY_DELAY = 0.001 # 1 ms

class Pca9541I2cDevDriver(I2cDevDriver):

   def takeOwnership(self):
      try:
         with self:
            count = 10
            while not self.arbitrate() and count:
               time.sleep(ARBITRATE_RETRY_DELAY)
               count -= 1
      except IOError:
         return False
      return count != 0

   def getCtrlReg(self):
      return self.read_byte_data(CTRL_REG)

   def setCtrlReg(self, value):
      self.write_byte_data(CTRL_REG, value)

   def arbitrate(self):
      ctrl = self.getCtrlReg()
      newCtrl = CTRL_CMDS[ctrl & 0xf]
      if newCtrl:
         self.setCtrlReg(newCtrl)

      ctrl = self.getCtrlReg()

      busOn = bool(ctrl & BUSON) ^ bool(ctrl & NBUSON)
      myBus = not bool(ctrl & MYBUS) ^ bool(ctrl & NMYBUS)

      return busOn and myBus

   def getBus(self):
      return self.addr.bus

   def ping(self):
      return self.smbusPing()

class Pca9541KernelDriver(I2cKernelDriver):

   MODULE = 'i2c-mux-pca9541'
   NAME = 'pca9541'

   def getBus(self):
      if inSimulation():
         return 42
      channelPath = os.path.join(self.getSysfsPath(), 'channel-0')
      return self.busNameToId(os.path.basename(os.readlink(channelPath)))

   def ping(self):
      return True # TODO: linecard presence should not be based on pca

   def takeOwnership(self):
      return True
