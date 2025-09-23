
import os
from enum import IntEnum

from ..core.driver.kernel.i2c import I2cKernelDriver
from ..core.driver.user.gpio import GpioFuncImpl
from ..core.driver.user.i2c import I2cDevDriver
from ..core.log import getLogger

logging = getLogger(__name__)

class PmbusRegister:
   REGISTER_PREFIX = 'status'
   REGISTER_SUFFIX = ''

   def __init__(self, manager, page=0):
      self.page = page
      self.manager = manager
      self._debugfsPath = None
      self.cachedValue = None

   def __diag__(self, ctx):
      registerData = {
         'cachedValue': self.cachedValue,
         'debugfsPath': self.debugfsPath,
         'currentValue': self.read() if ctx.performIo else None,
      }
      return registerData

   @property
   def debugfsPath(self):
      if self._debugfsPath is None and self.manager.debugfsDir is not None:
         entry = f'{self.REGISTER_PREFIX}{self.page}{self.REGISTER_SUFFIX}'
         path = os.path.join(self.manager.debugfsDir, entry)
         if os.path.exists(path):
            self._debugfsPath = path
      return self._debugfsPath

   def read(self):
      try:
         if self.debugfsPath is None:
            return None

         if os.path.exists(self.debugfsPath):
            with open(self.debugfsPath, 'r') as f:
               valueStr = f.read().strip()
               if valueStr is not None:
                  self.cachedValue = int(valueStr, 16)
                  logging.io('%s.read(%s) -> %#x',
                             self, self.debugfsPath, self.cachedValue)
                  return self.cachedValue
         return None
      except (IOError, OSError) as e:
         logging.io('%s.read(%s) -> ERROR: %s',
                    self, self.debugfsPath, e)
         return None

   def __eq__(self, other):
      if not isinstance(other, self.__class__):
         return False
      return (self.page == other.page and
              self.cachedValue == other.cachedValue)

   def __str__(self):
      return (
         f'{self.__class__.__name__}(page={self.page}, '
         f'cachedValue={self.cachedValue})'
      )

class PmbusStatusRegister(PmbusRegister):

   class Bit(IntEnum):
      NONE_ABOVE = 0
      CML = 1
      TEMPERATURE = 2
      VIN_UV = 3
      IOUT_OC = 4
      VOUT_OV = 5
      OFF = 6
      BUSY = 7
      UNKNOWN = 8
      OTHER = 9
      FANS = 10
      POWER_GOOD_N = 11
      WORD_MFR = 12
      INPUT = 13
      IOUT_POUT = 14
      VOUT = 15

      @property
      def mask(self):
         return 1 << self.value

class PmbusCmlRegister(PmbusRegister):
   REGISTER_SUFFIX = '_cml'

class PmbusStatus:
   POWER_LOSS_MASK = (
      PmbusStatusRegister.Bit.OFF.mask |
      PmbusStatusRegister.Bit.POWER_GOOD_N.mask
   )

   def __init__(self, manager, page=0):
      self.page = page
      self.manager = manager
      self._statusReg = None
      self._cmlReg = None

   @property
   def statusReg(self):
      if self._statusReg is None and self.manager.debugfsDir is not None:
         self._statusReg = PmbusStatusRegister(self.manager, self.page)
      return self._statusReg

   @property
   def cmlReg(self):
      if self._cmlReg is None and self.manager.debugfsDir is not None:
         self._cmlReg = PmbusCmlRegister(self.manager, self.page)
      return self._cmlReg

   def hasPowerLoss(self):
      if self.statusReg is None:
         return None
      mask = self.POWER_LOSS_MASK
      value = self.statusReg.read()
      return None if value is None else ((value & mask) != 0)

   def __diag__(self, ctx):
      return {
         'registers': {
             'status': self.statusReg.__diag__(ctx),
             'cml': self.cmlReg.__diag__(ctx),
         }
      }

   def __str__(self):
      return f'{self.__class__.__name__}(page={self.page})'

class PmbusStatusManager:
   DEBUGFS_BASE = '/sys/kernel/debug/pmbus'

   def __init__(self, driver):
      self.driver = driver
      self.debugfsDir = None
      self.pages = {}
      self.discover()

   def discover(self):
      self.pages.clear()
      self.debugfsDir = None
      try:
         hwmonPath = self.driver.getHwmonPath()
         hwmonName = os.path.basename(hwmonPath.rstrip('/'))
         if not hwmonName.startswith('hwmon'):
            return

         debugfsDir = os.path.join(self.DEBUGFS_BASE, hwmonName)
         if not os.path.exists(debugfsDir):
            return

         self.debugfsDir = debugfsDir

         # TODO: Support multi-page status registers
         pmbusStatus = PmbusStatus(manager=self, page=0)
         self.pages[0] = pmbusStatus

      except Exception as e: # pylint: disable=broad-except
         logging.debug('%s: Failed to discover status registers: %s', self, e)

   #TODO: Improve this method to look at other registers like CML and Thermal faults
   def getStatus(self):
      if not self.pages:
         return None

      for pmbusStatus in self.pages.values():
         powerLoss = pmbusStatus.hasPowerLoss()
         if powerLoss is None:
            return None
         if powerLoss:
            return False
      return True

   def __str__(self):
      return f'{self.__class__.__name__}(pages={len(self.pages)})'

   def __diag__(self, ctx):
      return {
         'name': self.__class__.__name__,
         'pages': {p : status.__diag__(ctx) for p, status in self.pages.items()},
      }

class PsuPmbusDetect(I2cDevDriver):

   MFR_ID = 0x99
   MFR_MODEL = 0x9a
   MFR_REVISION = 0x9b
   MFR_LOCATION = 0x9c
   MFR_DATE = 0x9d
   MFR_SERIAL = 0x9e

   VENDOR_MFR_ID = 0xc9
   VENDOR_MFR_MODEL = 0xca
   VENDOR_MFR_REVISION = 0xcb
   ARISTA_MFR_SKU = 0xcc

   UNKNOWN_METADATA = {
      key : 'N/A'
      for key in ['id', 'model', 'revision', 'location', 'date', 'serial']
   }

   def __init__(self, addr):
      super(PsuPmbusDetect, self).__init__(name='pmbus-detect', addr=addr)
      self.addr = addr
      self.exists_ = None
      self.id_ = None
      self.model_ = None
      self.revision_ = None
      self.location_ = None
      self.date_ = None
      self.serial_ = None

      self._prepare()

   def _prepare(self):
      if not self.exists():
         return
      try:
         # init device on page 0
         self.write_byte_data(0x00, 0x00)
      except Exception: # pylint: disable=broad-except
         pass

   def exists(self):
      if self.exists_ is None:
         self.exists_ = self.smbusPing()
      return self.exists_

   def checkId(self):
      try:
         self.id()
         return True
      except IOError:
         return False

   def _tryReadBlockStr(self, reg, default='N/A'):
      try:
         return self.read_block_data_str(reg)
      except IOError:
         return default

   def id(self):
      if self.id_ is None:
         self.id_ = self.read_block_data_str(self.MFR_ID)
      return self.id_

   def model(self):
      if self.model_ is None:
         self.model_ = self.read_block_data_str(self.MFR_MODEL)
      return self.model_

   def revision(self):
      if self.revision_ is None:
         self.revision_ = self._tryReadBlockStr(self.MFR_REVISION)
      return self.revision_

   def location(self):
      if self.location_ is None:
         self.location_ = self._tryReadBlockStr(self.MFR_LOCATION)
      return self.location_

   def date(self):
      if self.date_ is None:
         self.date_ = self._tryReadBlockStr(self.MFR_DATE)
      return self.date_

   def serial(self):
      if self.serial_ is None:
         self.serial_ = self._tryReadBlockStr(self.MFR_SERIAL)
      return self.serial_

   def getMfrMetadata(self):
      return {
         'id': self.id(),
         'model': self.model(),
         'revision': self.revision(),
         'location': self.location(),
         'date': self.date(),
         'serial': self.serial(),
      }

   def getAristaMetadata(self):
      return {
         'mfr_id': self._tryReadBlockStr(self.VENDOR_MFR_ID),
         'mfr_model': self._tryReadBlockStr(self.VENDOR_MFR_MODEL),
         'mfr_revision': self._tryReadBlockStr(self.VENDOR_MFR_REVISION),
         'sku': self._tryReadBlockStr(self.ARISTA_MFR_SKU, None),
      }

   def getMetadata(self):
      data = self.getMfrMetadata()
      if data['id'] == 'Arista':
         data['arista'] = self.getAristaMetadata()
      return data

class PmbusKernelDriver(I2cKernelDriver):
   MODULE = 'pmbus'
   NAME = 'pmbus'

   def __init__(self, *args, **kwargs):
      super().__init__(*args, **kwargs)
      self._statusManager = None

   def clean(self):
      self._statusManager = None
      super().clean()

   @property
   def statusManager(self):
      if self._statusManager is None:
         self._statusManager = PmbusStatusManager(self)
      return self._statusManager

   def createIsGoodFunc(self, entries):
      def func():
         # Iterate entries, return _input of the first with matching labelPrefix
         for entry, labelPrefix in entries:
            try:
               with open(self.getHwmonEntry("%s_label" % entry),
                         encoding='utf8') as f:
                  label = f.read()
                  if not label.startswith(labelPrefix):
                     continue
            except Exception: # pylint: disable=broad-except
               continue

            try:
               with open(self.getHwmonEntry("%s_input" % entry),
                         encoding='utf8') as f:
                  return 1 if int(f.read()) else 0
            except Exception: # pylint: disable=broad-except
               return 0
         return 0
      return func

   def getInputOkGpio(self):
      _isGood = self.createIsGoodFunc([('power1', 'pin'), ('in1', 'vin')])
      return GpioFuncImpl(self, _isGood, name='input_ok')

   def getOutputOkGpio(self, name=''):
      _isGood = self.createIsGoodFunc([('power2', 'pout'), ('power1', 'pout')])
      return GpioFuncImpl(self, _isGood, name='output_ok')

   def isPmbusStatusGood(self):
      if self.statusManager is None:
         return None
      return self.statusManager.getStatus()

   def __diag__(self, ctx):
      data = super().__diag__(ctx)
      sm = self.statusManager
      data.update({
         'statusManager': sm.__diag__(ctx) if sm else None,
      })
      return data
