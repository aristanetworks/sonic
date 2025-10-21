import enum
import os

from collections import namedtuple

from ..libs.i2c import i2cBusFromName
from .utils import inSimulation

Register = namedtuple("Register", ["addr", "ro"])
NamedRegister = namedtuple("NamedRegister", Register._fields + ("name", ))

Gpio = namedtuple("Gpio", ["bit", "ro", "activeLow"])

class SysfsPath(object):
   def getSysfsPath(self):
      raise NotImplementedError

class I2cAddr(SysfsPath):
   def __init__(self, bus, address, block=True):
      self.bus_ = bus
      self.address_ = address
      self.block_ = block

   @property
   def bus(self):
      return self.bus_

   @property
   def address(self):
      return self.address_

   @property
   def supportSmbusBlock(self):
      return self.block_

   def __repr__(self):
      return "%s(%d, %#x)" % (
         self.__class__.__name__, self.bus, self.address)

   def __str__(self):
      return '%d-00%02x' % (self.bus, self.address)

   def getSysfsPath(self):
      return os.path.join('/sys/bus/i2c/devices', str(self))

class PciAddr(SysfsPath):
   def __init__(self, domain=0, bus=0, device=0, func=0):
      self.domain = domain
      self.bus = bus
      self.device = device
      self.func = func

   def __str__(self):
      return '%04x:%02x:%02x.%d' % (self.domain, self.bus, self.device, self.func)

   def getSysfsPath(self):
      return os.path.join('/sys/bus/pci/devices', str(self))

class I2cBusAddr(I2cAddr):
   def __init__(self, bus, address):
      super().__init__(bus, address)

   @property
   def bus(self):
      return self.bus_.bus

class I2cBus(object):

   ADDR_CLS = I2cBusAddr

   def __init__(self, name, idx=0):
      self.name_ = name
      self.bus_ = None
      self.idx_ = idx

   @property
   def bus(self):
      if self.bus_ is None:
         if inSimulation():
            self.bus_ = 1
         else:
            self.bus_ = i2cBusFromName(self.name_, idx=self.idx_)
      return self.bus_

   def i2cAddr(self, address, **kwargs):
      return self.ADDR_CLS(self, address, **kwargs)

class SpiAddr(SysfsPath):

   @property
   def bus(self):
      raise NotImplementedError

   @property
   def cs(self):
      raise NotImplementedError

   def __str__(self):
      return f'spi{self.bus}.{self.cs}'

   def __repr__(self):
      return "%s(%d, %#x)" % (
         self.__class__.__name__, self.bus, self.cs)

   def getSysfsPath(self):
      return os.path.join('/sys/bus/spi/devices', str(self))

class MdioClause(enum.IntEnum):
   C22 = 1
   C45 = 2

class MdioSpeed(enum.IntEnum):
   S20 = 0
   S2_5 = 1
   S5 = 2
   S10 = 3

class MdioSpeedV2(enum.IntEnum):
   S15 = 0
   S10 = 1
   S5 = 2
   S7_5 = 3
