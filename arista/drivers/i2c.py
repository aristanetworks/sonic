import os

from contextlib import closing

from ..accessors.gpio import FuncGpioImpl

from ..core.driver import Driver, KernelDriver
from ..core import utils
from ..core.log import getLogger
from ..core.utils import SMBus

logging = getLogger(__name__)

def busNameToId(name):
   '''name is assumed to be of the form i2c-X'''
   return int(name[4:])

class I2cKernelDriver(Driver):
   def __init__(self, name=None, addr=None, waitFile=None, waitTimeout=None,
                module=None, **kwargs):
      self.name = name
      self.addr = addr
      self.module = module
      if module:
         self.kernelDriver = KernelDriver(module=module, **kwargs)
      else:
         self.kernelDriver = None
      if waitFile == utils.WAITFILE_HWMON:
         waitFile = (self.getSysfsPath(), 'hwmon', r'hwmon\d')
      self.fileWaiter = utils.FileWaiter(waitFile, waitTimeout)
      super(I2cKernelDriver, self).__init__(**kwargs)
      self.hwmonPath = None

   def getSysfsPath(self):
      return self.addr.getSysfsPath()

   def getSysfsBusPath(self):
      return '/sys/bus/i2c/devices/i2c-%d' % self.addr.bus

   def getHwmonPath(self):
      if self.hwmonPath is None:
         self.hwmonPath = utils.locateHwmonFolder(self.addr.getSysfsPath())
      return self.hwmonPath

   def getHwmonEntry(self, entry):
      return os.path.join(self.getHwmonPath(), entry)

   def setup(self):
      if self.kernelDriver:
         self.kernelDriver.setup()
      addr = self.addr
      devicePath = self.getSysfsPath()
      path = os.path.join(self.getSysfsBusPath(), 'new_device')
      logging.debug('creating i2c device %s on bus %d at 0x%02x',
                    self.name, addr.bus, addr.address)
      if utils.inSimulation():
         return
      if os.path.exists(devicePath):
         logging.debug('i2c device %s already exists', devicePath)
      else:
         with open(path, 'w') as f:
            f.write('%s 0x%02x' % (self.name, self.addr.address))
         self.fileWaiter.waitFileReady()
      super(I2cKernelDriver, self).setup()

   def clean(self):
      # i2c kernel devices are automatically cleaned when the module is removed
      if utils.inSimulation():
         return
      path = os.path.join(self.getSysfsBusPath(), 'delete_device')
      addr = self.addr
      if os.path.exists(self.getSysfsPath()):
         logging.debug('removing i2c device %s from bus %d', self.name, addr.bus)
         with open(path, 'w') as f:
            f.write('0x%02x' % addr.address)
      if self.kernelDriver:
         self.kernelDriver.clean()
      super(I2cKernelDriver, self).clean()

   def __str__(self):
      return '%s(name=%s)' % (self.__class__.__name__, self.name)

   def __diag__(self, ctx):
      return {
         "name": self.name,
         "module": self.module,
         "sysfs": self.getSysfsPath(),
      }

class I2cDevDriver(Driver):

   REGISTER_CLS = None

   def __init__(self, name=None, addr=None, registerCls=None, **kwargs):
      super(I2cDevDriver, self).__init__(**kwargs)
      self.bus_ = None
      self.name = name
      self.addr = addr
      registerCls = registerCls or self.REGISTER_CLS
      self.regs = registerCls(self) if registerCls is not None else None
      # TODO:
      # introduce callback table based on value types used.

   def __str__(self):
      return '%s(addr=%s)' % (self.__class__.__name__, self.addr)

   @property
   def bus(self):
      if self.bus_ is None:
         self.bus_ = utils.SMBus(self.addr.bus)
      return self.bus_

   def close(self):
      if self.bus_ is not None:
         self.bus_.close()
         self.bus_ = None

   def smbusPing(self):
      try:
         with closing(SMBus(self.addr.bus)) as bus:
            bus.read_byte(self.addr.address)
      except IOError:
         return False
      return True

   def read_byte_data(self, reg):
      return self.bus.read_byte_data(self.addr.address, reg)

   def write_byte_data(self, reg, data):
      return self.bus.write_byte_data(self.addr.address, reg, data)

   def read_block_data(self, reg):
      if self.addr.supportSmbusBlock:
         return self.bus.read_block_data(self.addr.address, reg)
      data = self.bus.read_i2c_block_data(self.addr.address, reg)
      return data[1:data[0] + 1]

   def read_block_data_str(self, reg):
      return ''.join(chr(c) for c in self.read_block_data(reg))

   def read(self, reg):
      res = self.read_byte_data(reg)
      if res is None:
         raise IOError(self, reg)
      return res

   def write(self, reg, data):
      return self.write_byte_data(reg, data)

   def getGpio(self, attr, name=None):
      assert self.regs
      func = getattr(self.regs, attr)
      assert func
      name = name or attr
      # XXX: could be enhanced to forward all the appropriate info to the Gpio obj
      #      for now it's enough the way it is.
      return FuncGpioImpl(func, name)

   def __diag__(self, ctx):
      return {
         "name": self.name,
         "regs": self.regs.__diag__(ctx) if self.regs else None,
      }
