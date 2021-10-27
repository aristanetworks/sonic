
import os

from ..core.driver import (
   Driver,
   deviceListForModule,
   isModuleLoaded,
   modprobe,
   rmmod,
)
from ..core.log import getLogger
from ..core.utils import inSimulation
from ..core import utils

from .sysfs import (
   FanSysfsImpl,
   GpioSysfsImpl,
   LedSysfsImpl,
   ResetSysfsImpl,
   TempSysfsImpl,
)

logging = getLogger(__name__)

class KernelDriver(Driver):

   MODULE = None
   ARGS = []
   PATH = None
   PASSIVE = False

   def __init__(self, module=None, margs=None, **kwargs):
      super(KernelDriver, self).__init__(**kwargs)
      self.margs = margs if margs is not None else self.ARGS
      self.module = module or self.MODULE
      self.hwmonPath = None

   def __str__(self):
      return '%s(module=%s)' % (self.__class__.__name__, self.module)

   def setup(self):
      if self.PASSIVE:
         return
      if not self.loaded():
         modprobe(self.module, self.margs)

   def clean(self):
      if self.PASSIVE:
         return

      if not self.loaded():
         logging.debug('Module %s is not loaded', self.module)
         return

      devices = deviceListForModule(self.module)
      if devices:
         logging.debug('Module %s is still in use by other devices: %s',
                       self.module, devices)
         return

      try:
         rmmod(self.module)
      except Exception as e: # pylint: disable=broad-except
         logging.error('Failed to unload %s: %s', self.module, e)

   def loaded(self):
      return isModuleLoaded(self.module)

   def getSysfsPath(self):
      if self.PATH is not None:
         return self.PATH
      raise NotImplementedError

   def getHwmonPath(self):
      if self.hwmonPath is None:
         self.hwmonPath = utils.locateHwmonFolder(self.getSysfsPath())
      return self.hwmonPath

   def getHwmonEntry(self, entry):
      return os.path.join(self.getHwmonPath(), entry)

   def __diag__(self, ctx):
      return {
         "module": self.module,
         "args": self.margs,
         "sysfs": self.getSysfsPath(),
      }

   # Helpers for most drivers

   def getFan(self, desc, **kwargs):
      return FanSysfsImpl(self, desc, **kwargs)

   def getFanLed(self, desc, **kwargs):
      return LedSysfsImpl(self, desc, **kwargs)

   def getLed(self, desc, **kwargs):
      return LedSysfsImpl(self, desc, **kwargs)

   def getTempSensor(self, desc, **kwargs):
      return TempSysfsImpl(self, desc, **kwargs)

   def getReset(self, desc, **kwargs):
      return ResetSysfsImpl(self, desc, **kwargs)

   def getGpio(self, desc, **kwargs):
      return GpioSysfsImpl(self, desc, **kwargs)

class I2cKernelDriver(KernelDriver):

   NAME = None

   def __init__(self, addr=None, name=None, **kwargs):
      super(I2cKernelDriver, self).__init__(**kwargs)
      self.addr = addr
      self.name = name or self.NAME

   def setup(self):
      # Load module
      super(I2cKernelDriver, self).setup()

      devPath = self.getSysfsPath()
      path = os.path.join(self.getSysfsBusPath(), 'new_device')
      logging.debug('creating i2c device %s on bus %d at 0x%02x',
                    self.name, self.addr.bus, self.addr.address)
      if inSimulation():
         return
      if os.path.exists(devPath):
         logging.debug('i2c device %s already exists', devPath)
      else:
         with open(path, 'w') as f:
            f.write('%s 0x%02x' % (self.name, self.addr.address))

   def clean(self):
      if inSimulation():
         return

      path = os.path.join(self.getSysfsBusPath(), 'delete_device')
      if os.path.exists(self.getSysfsPath()):
         logging.debug('removing i2c device %s from bus %d at 0x%02x',
                       self.name, self.addr.bus, self.addr.address)
         with open(path, 'w') as f:
            f.write('0x%02x' % self.addr.address)
      else:
         logging.debug('i2c device %s not loaded on bus %d at 0x%02x',
                       self.name, self.addr.bus, self.addr.address)

      # Unload module
      super(I2cKernelDriver, self).clean()

   def getSysfsPath(self):
      return self.addr.getSysfsPath()

   def getSysfsBusPath(self):
      return '/sys/bus/i2c/devices/i2c-%d' % self.addr.bus

   @staticmethod
   def busNameToId(name):
      '''name is assumed to be of the form i2c-X'''
      return int(name[4:])

   def __diag__(self, ctx):
      data = super(I2cKernelDriver, self).__diag__(ctx)
      data.update({
         'addr': str(self.addr),
         'name': self.name,
      })
      return data

class PciKernelDriver(KernelDriver):
   def __init__(self, addr=None, **kwargs):
      super(PciKernelDriver, self).__init__(**kwargs)
      self.addr = addr

   def getSysfsPath(self):
      return self.addr.getSysfsPath()
