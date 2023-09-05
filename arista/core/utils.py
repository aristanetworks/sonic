import fcntl
import inspect
import json
import mmap
import os
import re
import time

from datetime import datetime
from functools import wraps
from struct import pack, unpack

from .config import flashPath, tmpfsPath
from .log import getLogger
from ..libs.procfs import getCmdlineDict
from ..libs.python import isinteger

logging = getLogger(__name__)

class ResourceAccessor():
   ''' Base abstraction for accessing resource like files '''
   def __init__(self, path):
      self.path_ = path

   def openResource(self):
      raise NotImplementedError

   def closeResource(self):
      raise NotImplementedError

   def readResource(self, addr, size):
      raise NotImplementedError

   def writeResource(self, addr, size, value):
      raise NotImplementedError

   def __enter__(self):
      if not self.openResource():
         # raise the last exception from self.map()
         raise RuntimeError('failed to mmap %s' % self.path_)
      return self

   def __exit__(self, *args):
      self.closeResource()

   def _doRead(self, addr, size, unpackFormat):
      val = self.readResource(addr, size)
      return unpack('<%s' % unpackFormat, val)[0]

   def _doWrite(self, addr, size, value, packFormat):
      packedVal = pack('<%s' % packFormat, value)
      self.writeResource(addr, size, packedVal)

   def read32(self, addr):
      return self._doRead(addr, 4, 'L')

   def write32(self, addr, value):
      self._doWrite(addr, 4, value, 'L')

   def read16(self, addr):
      return self._doRead(addr, 2, 'H')

   def write16(self, addr, value):
      self._doWrite(addr, 2, value, 'H')

   def read8(self, addr):
      return self._doRead(addr, 1, 'B')

   def write8(self, addr, value):
      self._doWrite(addr, 1, value, 'B')

class MmapResource(ResourceAccessor):
   """Resource implementation for a directly-mapped memory region."""
   def __init__(self, *args, **kwargs):
      super().__init__(*args, **kwargs)
      self.mmap_ = None

   def map(self):
      assert not self.mmap_, "Resource already mapped"

      try:
         fd = os.open(self.path_, os.O_RDWR)
      except EnvironmentError:
         logging.error("failed to open file %s for mmap", self.path_)
         return False

      try:
         size = os.fstat(fd).st_size
      except EnvironmentError:
         logging.error("failed to stat file %s for mmap", self.path_)
         try:
            os.close(fd)
         except EnvironmentError:
            pass
         return False

      try:
         self.mmap_ = mmap.mmap(fd, size, mmap.MAP_SHARED,
                                mmap.PROT_READ | mmap.PROT_WRITE)
      except EnvironmentError:
         logging.error("failed to mmap file %s", self.path_)
         return False
      finally:
         try:
            # Note that closing the file descriptor has no effect on the memory map
            os.close(fd)
         except EnvironmentError:
            pass
      return True

   def openResource(self):
      return self.map()

   def closeResource(self):
      if self.mmap_:
         self.mmap_.close()
         self.mmap_ = None

   def readResource(self, addr, size):
      return self.mmap_[addr : addr + size]

   def writeResource(self, addr, size, value):
      self.mmap_[addr: addr + size] = value

class FileResource(ResourceAccessor):
   ''' Resource implementation for a file base memory region. '''
   def __init__(self, *args, **kwargs):
      super().__init__(*args, **kwargs)
      self.file_ = None

   def openResource(self):
      assert not self.file_, 'Resource already opened'
      try:
         self.file_ = open(self.path_, mode='rb+')
      except IOError:
         logging.error("failed to open file %s", self.path_)
         return False
      return True

   def closeResource(self):
      if self.file_:
         self.file_.close()
         self.file_ = None

   def readResource(self, addr, size):
      # In python3 there's os.pread()
      p = self.file_.tell()
      self.file_.seek(addr, os.SEEK_SET)
      v = self.file_.read(size)
      self.file_.seek(p, os.SEEK_SET)
      return v

   def writeResource(self, addr, size, value):
      # In python3 there's os.pwrite()
      p = self.file_.tell()
      self.file_.seek(addr, os.SEEK_SET)
      self.file_.write(value)
      self.file_.seek(p, os.SEEK_SET)

def sysfsFmtHex(x):
   return "0x%08x" % x

def sysfsFmtDec(x):
   return "%d" % x

def sysfsFmtStr(x):
   return str(x)

def incrange(start, stop):
   return list(range(start, stop + 1))

def flatten(nestedList):
   return [val for sublist in nestedList for val in sublist]

def klog(msg, level=2, *args):
   try:
      with open('/dev/kmsg', 'w') as f:
         f.write('<%d>arista: %s\n' % (level, msg % tuple(*args)))
   except: # pylint: disable-msg=W0702
      pass

class Retrying:
   def __init__(self, interval=1.0, delay=0.05, maxAttempts=None):
      self.interval = interval
      self.delay = delay
      self.maxAttempts = maxAttempts

   def __iter__(self):
      class Iterator:
         def __init__(self, interval, delay, maxAttempts):
            self.attempt = 0

            self.startedAt_ = datetime.now()
            self.interval_ = interval
            self.delay_ = delay
            self.maxAttempts_ = maxAttempts

         def __next__(self):
            time.sleep(self.delay_)
            if self.isExpired() or \
               self.maxAttempts_ and self.attempt >= self.maxAttempts_:
               raise StopIteration
            self.attempt += 1
            return self

         def next(self):
            return self.__next__()

         def isExpired(self):
            return self.interval_ and \
               (datetime.now() - self.startedAt_).total_seconds() > self.interval_

      return Iterator(self.interval, self.delay, self.maxAttempts)

WAITFILE_HWMON = 'hwmon'

# Depreciate this object if we want to wait on access instead of waiting at start
# and potentially failing
class FileWaiter():
   def __init__(self, waitFile=None, waitTimeout=None):
      self.waitFile = waitFile
      self.waitTimeout = float(waitTimeout) if waitTimeout else 1.0

   def waitFileReady(self):
      if not self.waitFile:
         return False

      logging.debug('Waiting file %s.', self.waitFile)

      for r in Retrying(interval=self.waitTimeout):
         if self.fileExists():
            return True
         logging.debug('Waiting file %s attempt %d.', self.waitFile, r.attempt)

      if not os.path.exists(self.waitFile):
         logging.error('Waiting file %s failed.', self.waitFile)
         return False
      return True

   def fileExists(self):
      if isinstance(self.waitFile, str):
         return os.path.exists(self.waitFile)
      def _findFile(directory, patterns):
         if not os.path.exists(directory):
            return False

         nextPattern = patterns[0]
         for filename in os.listdir(directory):
            if not re.match(nextPattern, filename):
               continue

            if len(patterns) == 1:
               return True

            subdir = os.path.join(directory, filename)
            if not os.path.isdir(subdir):
               continue

            if _findFile(subdir, patterns[1:]):
               return True

         return False

      return _findFile(self.waitFile[0], self.waitFile[1:])

class FileLock:
   def __init__(self, lock_file, auto_release=False):
      self.f = open(lock_file, 'w')
      self.auto_release = auto_release

   def lock(self):
      fcntl.flock(self.f, fcntl.LOCK_EX)

   def unlock(self):
      fcntl.flock(self.f, fcntl.LOCK_UN)
      self.f.close()

   def __enter__(self):
      self.lock()

   def __exit__(self, exc_type, exc_val, traceback):
      if self.auto_release:
         self.unlock()
      else:
         self.f.close()

class NoopObj():
   def __init__(self, *args, **kwargs):
      self.name = self.__class__.__name__
      self.classStr = '%s(%s)' % (self.name, self._fmtArgs(*args, **kwargs))
      logging.debug(self.classStr)

   def _fmtArgs(self, *args, **kwargs):
      kw = ['%s=%s' % (k, v) for k, v in kwargs.items()]
      return ', '.join(list(map(str, args)) + kw)

   def noop(self, attr):
      def wrapped(*args, **kwargs):
         funcStr = '%s(%s)' % (attr, self._fmtArgs(*args, **kwargs))
         logging.debug('%s.%s', self.classStr, funcStr)
      return wrapped

   def __getattr__(self, attr):
      return self.noop(attr)

class StoredData():
   def __init__(self, name, lifespan='temporary', path=None, append=True):
      self.name = name
      self.lifespan = lifespan
      self.mode = 'a+' if append else 'w+'
      if path is None:
         dirPath = tmpfsPath() if lifespan == 'temporary' else flashPath()
         self.maybeCreatePath(dirPath)
         self.path = os.path.join(dirPath, name)
      else:
         self.path = path

   def __str__(self):
      return '%s(%s)' % (self.__class__.__name__, self.path)

   def maybeCreatePath(self, dirPath):
      if not os.path.isdir(dirPath) and not inSimulation():
         os.makedirs(dirPath)

   def exist(self):
      return os.path.isfile(self.path)

   def writable(self):
      return os.access(self.path, os.W_OK)

   def write(self, data, mode=None):
      mode = mode or self.mode
      assert os.path.isdir(os.path.dirname(self.path)), \
            'Base directory for %s file %s not found!' % (self.lifespan, self.name)
      if not os.path.isfile(self.path):
         logging.debug('Creating %s file %s', self.lifespan, self.name)
      with open(self.path, mode) as tmpFile:
         tmpFile.write(data)

   def read(self):
      assert os.path.isfile(self.path), \
            'File %s of type %s not found!' % (self.name, self.lifespan)
      with open(self.path, 'r') as tmpFile:
         return tmpFile.read()

   def clear(self):
      if self.exist():
         os.remove(self.path)

   def readOrClear(self):
      if self.exist():
         try:
            return self.read()
         except Exception: # pylint: disable=broad-except
            logging.error("failed to load cached data %s", self)
            self.clear()
      return None

class JsonStoredData(StoredData):

   DEFAULT_VALUE = []

   @staticmethod
   def _createObj(data, dataType):
      obj = dataType() if inspect.isclass(dataType) else dataType
      obj.__dict__.update(data)
      return obj

   @staticmethod
   def _dataDict(obj):
      denylist = getattr(obj, 'STORE_IGNORE', None)
      if denylist is None:
         return obj.__dict__
      return {k : v for k, v in obj.__dict__.items() if k not in denylist}

   def write(self, data, mode=None):
      mode = mode or self.mode
      super().write(json.dumps(data, indent=3, separators=(',', ': ')), mode)

   def read(self):
      res = super().read()
      if res:
         return json.loads(res)
      return self.DEFAULT_VALUE

   def readObj(self, dataType):
      return self._createObj(self.read(), dataType)

   def readList(self, dataType):
      return [self._createObj(data, dataType) for data in self.read()]

   def writeObj(self, data):
      self.write(self._dataDict(data))

   def writeList(self, data):
      self.write([self._dataDict(item) for item in data])

# debug flag, if enabled should use the most tracing possible
debug = False

# force simulation to be True if not on a Arista box
simulation = True

# simulation related globals
SMBus = None

def inDebug():
   return debug

def inSimulation():
   return simulation

def runningInContainer():
   # Docker containers by default have this path.
   return os.path.exists("/.dockerenv")

def simulateWith(simulatedFunc):
   def simulateThisFunc(func):
      @wraps(func)
      def funcWrapper(*args, **kwargs):
         if inSimulation():
            return simulatedFunc(*args, **kwargs)
         return func(*args, **kwargs)
      return funcWrapper
   return simulateThisFunc

def writeConfigSim(path, data):
   for filename, value in data.items():
      logging.info('writing data under %s : %r',
                   os.path.join(path, filename), value)

@simulateWith(writeConfigSim)
def writeConfig(path, data):
   for filename, value in data.items():
      try:
         filePath = os.path.join(path, filename)
         with open(filePath, 'w') as f:
            f.write(value)
      except IOError as e:
         logging.error('writeConfig path=%s data=%s error=%s',
                       path, data, e.strerror)

def locateHwmonFolder(devicePath, index=0):
   if inSimulation():
      return os.path.join(devicePath, 'hwmon', 'simulation')
   hwmonFolder = os.path.join(devicePath, 'hwmon')
   try:
      paths = [p for p in sorted(os.listdir(hwmonFolder)) if p.startswith('hwmon')]
   except FileNotFoundError:
      return os.path.join(hwmonFolder, 'hwmonX')
   return os.path.join(hwmonFolder, paths[index])

# Hwmon directories that need to be navigated
# Keeps trying to get path to show up, or search in searchPath
def locateHwmonPath(searchPath, prefix):
   for root, _, files in os.walk(os.path.join(searchPath, 'hwmon')):
      for name in files:
         if name.startswith(prefix):
            path = root
            logging.debug('got hwmon path for %s as %s', searchPath,
                          path)
            return path

   logging.error('could not locate hwmon path for %s', searchPath)
   return None

class LastRebootType:
   COLD = 'cold'
   WARM = 'warm'
   FAST = 'fast'

   _last = None

   @classmethod
   def get(cls):
      if cls._last is None:
         cls._last = getCmdlineDict().get('SONIC_BOOT_TYPE', cls.COLD)
      return cls._last

def libraryInit():
   global simulation, debug, SMBus

   cmdline = getCmdlineDict()
   if "Aboot" in cmdline:
      simulation = False

   if "arista-debug" in cmdline:
      debug = True

   if simulation:
      SMBus = type('SMBus', (NoopObj,), {})
   else:
      try:
         from smbus import SMBus
      except ImportError:
         pass

libraryInit()
