
import os

from ..core.daemon import registerDaemonFeature, PollDaemonFeature
from ..core.log import getLogger

logging = getLogger(__name__)

SECTOR_SIZE = 512
SECONDS_IN_DAY = 60 * 60 * 24
KiB = 1024
MiB = 1024 * KiB

class IOStat(object):
   def __init__(self, deviceName):
      self.deviceName = deviceName
      self.readBytes = -1
      self.writtenBytes = -1
      self.oldReadBytes = -1
      self.oldWrittenBytes = -1
      self.uptime = -1

   def __str__(self):
      if self.readBytes == -1 or self.writtenBytes == -1 or self.uptime == -1:
         return '(unknown)'

      totalReadStr = 'total data read (MiB): %.1f' % (self.readBytes / MiB)
      totalWrittenStr = 'total data written (MiB): %.1f' % \
                        (self.writtenBytes / MiB)

      if self.oldReadBytes > -1:
         totalReadStr += ' (+%.1f)' % ((self.readBytes - self.oldReadBytes) / MiB)

      if self.oldWrittenBytes > -1:
         totalWrittenStr += ' (+%.1f)' % \
                            ((self.writtenBytes - self.oldWrittenBytes) / MiB)

      totalReadKiB = self.readBytes / KiB
      totalWrittenKiB = self.writtenBytes / KiB
      output = [
         totalReadStr,
         totalWrittenStr,
         'read (KiB/s): %.1f' % (totalReadKiB / self.uptime),
         'write (KiB/s): %.1f' % (totalWrittenKiB / self.uptime),
      ]

      uptimeDays = self.uptime / SECONDS_IN_DAY
      if uptimeDays >= 1:
         totalReadMiB = self.readBytes / MiB
         totalWrittenMiB = self.writtenBytes / MiB
         output += [
            'read (MiB/day): %.1f' % (totalReadMiB / uptimeDays),
            'write (MiB/day): %.1f' % (totalWrittenMiB / uptimeDays),
         ]

      return ', '.join(output)

   def collect(self):
      with open('/proc/uptime') as f:
         self.uptime = float(f.read().split()[0])

      # https://www.kernel.org/doc/Documentation/block/stat.txt
      statPath = '/sys/block/%s/stat' % self.deviceName
      with open(statPath) as f:
         statData = f.read().split()

      self.oldReadBytes = self.readBytes
      self.oldWrittenBytes = self.writtenBytes

      self.readBytes = int(statData[2]) * SECTOR_SIZE
      self.writtenBytes = int(statData[6]) * SECTOR_SIZE

class StorageDevice(object):
   def __init__(self, name, path):
      self.name = name
      self.path = path
      self.stat = IOStat(self.name)

   def __str__(self):
      return '%s(%s)' % (self.__class__.__name__, self.name)

   def _try(self, func):
      try:
         func()
      except Exception: # pylint: disable=broad-except
         pass

   def report(self):
      raise NotImplementedError

   def exists(self):
      return os.path.exists(self.path)

   def iostat(self):
      try:
         self.stat.collect()
      except Exception: # pylint: disable=broad-except
         return

      logging.info('iostat(%s): %s', self.name, self.stat)

   @classmethod
   def listStorageDevices(cls):
      basePath = '/sys/block'
      for name in os.listdir(basePath):
         if name.startswith('loop') or 'boot' in name:
            continue
         yield name, os.path.join(basePath, name, 'device')

   @classmethod
   def detectDevices(cls):
      raise NotImplementedError

class EmmcStorageDevice(StorageDevice):
   def _readLifeTime(self):
      values = [None, '100%', '90%', '80%', '70%', '60%', '50%', '40%', '30%',
                '20%', '10%', 'EOL']
      with open(os.path.join(self.path, 'life_time')) as f:
         slc, mlc = f.read().rstrip().split()
         return {
            'slc': values[int(slc, 16)],
            'mlc': values[int(mlc, 16)],
         }

   def _readPreEol(self):
      values = [None, 'Normal', '20%', '10%']
      with open(os.path.join(self.path, 'pre_eol_info')) as f:
         eol = f.read().rstrip()
         return {
            'reserve': values[int(eol, 16)],
         }

   def _readEnhancedArea(self):
      with open(os.path.join(self.path, 'enhanced_area_size')) as f:
         size = f.read().rstrip()
         return {
            'mlcsz': size,
         }

   def report(self):
      data = {}
      self._try(lambda: data.update(self._readLifeTime()))
      self._try(lambda: data.update(self._readPreEol()))
      self._try(lambda: data.update(self._readEnhancedArea()))
      values = ' '.join('%s=%s' % (k, v) for k, v in sorted(data.items()))
      logging.info('%s %s', self, values)

   @classmethod
   def detectDevices(cls):
      for name, path in cls.listStorageDevices():
         if name.startswith('mmcblk'):
            yield cls(name, path)

class SsdStorageDevice(StorageDevice):
   def report(self):
      pass

   @classmethod
   def detectDevices(cls):
      for name, path in cls.listStorageDevices():
         if name.startswith('sd') and 'ata' in os.path.realpath(path):
            yield cls(name, path)

class UsbStorageDevice(StorageDevice):
   def report(self):
      pass

   @classmethod
   def detectDevices(cls):
      for name, path in cls.listStorageDevices():
         if name.startswith('sd') and 'usb' in os.path.realpath(path):
            yield cls(name, path)

@registerDaemonFeature()
class StorageDaemonFeature(PollDaemonFeature):

   NAME = 'storage'
   INTERVAL = 24 * 60 * 60

   STORAGE_DEVICES = [
      EmmcStorageDevice,
      SsdStorageDevice,
      UsbStorageDevice,
   ]

   def _getStorageDevices(self):
      devices = []
      for cls in self.STORAGE_DEVICES:
         devices.extend(cls.detectDevices())
      return devices

   def init(self):
      PollDaemonFeature.init(self)
      self.devices = self._getStorageDevices()
      for device in self.devices:
         logging.debug('%s: monitoring disk %s', self, device)

   async def callback(self, elapsed):
      for device in self.devices:
         if device.exists():
            device.report()
            device.iostat()
