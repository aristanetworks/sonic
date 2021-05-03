
import os
import subprocess

from collections import OrderedDict

from . import utils
from .utils import FileWaiter, inDebug, inSimulation
from .log import getLogger

logging = getLogger(__name__)

def modprobe(name, args=None):
   logging.debug('loading module %s', name)
   if args is None:
      args = []
   args = ['modprobe', name.replace('-', '_')] + args
   if inDebug():
      args += ['dyndbg=+pf']
   if inSimulation():
      logging.debug('exec: %s', ' '.join(args))
   else:
      subprocess.check_call(args)

def deviceListForModule(name):
   devices = []
   moduleDriversPath = '/sys/module/%s/drivers/' % name.replace('-', '_')

   if not os.path.exists(moduleDriversPath):
      return []

   for drv in os.listdir(moduleDriversPath):
      moduleDevicesPath = os.path.join(moduleDriversPath, drv)
      for device in os.listdir(moduleDevicesPath):
         deviceLinkPath = os.path.join(moduleDevicesPath, device)
         try:
            deviceLinkValue = os.readlink(deviceLinkPath)
            deviceAbsPath = os.path.abspath(os.path.join(moduleDevicesPath,
                                                         deviceLinkValue))
            if deviceAbsPath.startswith('/sys/devices'):
               devices += [deviceAbsPath]
         except OSError:
            continue

   return devices

def rmmod(name):
   logging.debug('unloading module %s', name)
   args = ['modprobe', '-r', name.replace('-', '_')]
   if inSimulation():
      logging.debug('exec: %s', ' '.join(args))
   else:
      subprocess.check_call(args)

def isModuleLoaded(name):
   if inSimulation():
      return False

   with open('/proc/modules') as f:
      start = '%s ' % name.replace('-', '_')
      for line in f.readlines():
         if line.startswith(start):
            return True
   return False

_i2cBuses = OrderedDict()
def getKernelI2cBuses(force=False):
   if _i2cBuses and not force:
      return _i2cBuses
   _i2cBuses.clear()
   buses = {}
   root = '/sys/class/i2c-adapter'
   for busName in sorted(os.listdir(root), key=lambda x: int(x[4:])):
      busId = int(busName.replace('i2c-', ''))
      with open(os.path.join(root, busName, 'name')) as f:
         buses[busId] = f.read().rstrip()
   return buses

def i2cBusFromName(name, idx=0, force=False):
   buses = getKernelI2cBuses(force=force)
   for busId, busName in buses.items():
      if name == busName:
         if idx > 0:
            idx -= 1
         else:
            return busId
   return None

class Driver(object):
   def __init__(self, **kwargs):
      self.__dict__.update(kwargs)

   def setup(self):
      pass

   def finish(self):
      pass

   def clean(self):
      pass

   def refresh(self):
      pass

   def resetIn(self):
      pass

   def resetOut(self):
      pass

   def __diag__(self, ctx): # pylint: disable=unused-argument
      return {}

   def __try_diag__(self, ctx):
      try:
         return self.__diag__(ctx)
      except Exception: # pylint: disable=broad-except
         if not ctx.safe:
            raise
         return {}

   def genDiag(self, ctx):
      return {
         "version": 1,
         "name": self.__class__.__name__,
         "data": self.__try_diag__(ctx),
      }

   def __str__(self):
      kwargs = ['%s=%s' % (k, v) for k, v in self.__dict__.items()]
      return '%s(%s)' % (self.__class__.__name__, ', '.join(kwargs))

class KernelDriver(Driver):
   def __init__(self, waitFile=None, waitTimeout=None, args=None, **kwargs):
      self.args = args if args is not None else []
      self.fileWaiter = FileWaiter(waitFile, waitTimeout)
      self.module = self.driverName = kwargs.get('module')
      self.hwmonPath = None
      super(KernelDriver, self).__init__(**kwargs)

   def __str__(self):
      return '%s(name=%s)' % (self.__class__.__name__, self.driverName)

   def setup(self):
      if not self.loaded():
         modprobe(self.module, self.args)
      self.fileWaiter.waitFileReady()

   def clean(self):
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
      raise NotImplementedError

   def getHwmonPath(self):
      if self.hwmonPath is None:
         self.hwmonPath = utils.locateHwmonFolder(self.getSysfsPath())
      return self.hwmonPath

   def getHwmonEntry(self, entry):
      return os.path.join(self.getHwmonPath(), entry)
