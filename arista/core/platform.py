import re

from .dynload import importSubmodules
from .exception import UnknownPlatformError
from .identity.bmc import PlatformIdentityBmc
from .identity.factory import createPlatformIdentity
from .log import getLogger

from ..libs.benchmark import timeit

logging = getLogger(__name__)

syseeprom = None
syseepromData = None

class PlatformManager:
   def __init__(self):
      self.cpus = []
      self.platforms = []
      self.platformSidIndex = {}
      self.platformSkuIndex = {}
      self.bmcIndex = {}
      self.bmcSubsystemIndex = {}
      self.identity = createPlatformIdentity(self)

   def registerPlatform(self, cls):
      self.platforms.append(cls)

      for sid in cls.SID:
         self.platformSidIndex[sid] = cls
      for sku in cls.SKU:
         self.platformSkuIndex[sku] = cls

      if cls.PLATFORM is not None:
         # this is a hack for older platforms that did not provide sid=
         assert cls.PLATFORM not in self.platformSidIndex
         self.platformSidIndex[cls.PLATFORM] = cls

      return cls

   def registerCpu(self, cls):
      self.cpus.append(cls)
      return cls

   def registerBmc(self, cls):
      for model in cls.MODEL:
         self.bmcIndex[model] = cls
      return cls

   def registerBmcSubsystem(self, cls):
      for model in cls.BMC_CLS.MODEL:
         for sid in cls.HOST_SWITCH_CLS.SID:
            self.bmcSubsystemIndex[(model, sid)] = cls
      return cls

   def detectPlatform(self):
      # TODO: refactor by obtaining a Cpu object based on the platform= from
      #       cmdline implement getEeprom on all Cpu to get the prefdl from hw
      #       add a fallback mechanism to read /etc/sonic/.syseeprom like done
      #       today
      getSysEepromData()

      sid = readSid()
      platformCls = self.platformSidIndex.get(sid)
      if platformCls is not None:
         return platformCls

      sku = readSku()
      platformCls = self.platformSkuIndex.get(sku)
      if platformCls is not None:
         return platformCls

      name = readPlatformName()
      platformCls = self.platformSidIndex.get(name)
      if platformCls is not None:
         return platformCls

      raise UnknownPlatformError(sku, sid, name, self.platforms)

   def getPlatformCls(self, *names):
      if not names or not [name for name in names if name]:
         return self.detectPlatform()

      for name in names:
         if name is None:
            continue

         platformCls = self.platformSkuIndex.get(name)
         if platformCls is not None:
            return platformCls

         platformCls = self.platformSidIndex.get(name)
         if platformCls is not None:
            return platformCls

      raise UnknownPlatformError(names, self.platforms)

   def loadPlatforms(self, package):
      return importSubmodules(package).keys()

manager = PlatformManager()

def getManager():
   return manager

def getPlatformIdentity():
   return manager.identity

def getSonicSku(prefdlData):
   sku = prefdlData.get("SKU")
   sid = prefdlData.get("SID")
   hwApi = prefdlData.get("HwApi")

   newSku = sku

   # Add fan direction for Pikez
   fandirRe = "-.*(?P<fandir>(R|F))$"
   sid_mo = re.search(fandirRe, sid)
   sku_mo = re.search(fandirRe, sku)
   if sid_mo and not sku_mo:
      newSku += sid_mo.group('fandir')

   # Add -B for Moby512
   if sku == 'DCS-7060X6-16PE-384C' and hwApi != (1, 0):
      newSku += '-B'

   return newSku

class SysEeprom(object):
   def prefdl(self):
      return self.readPrefdl().data()

   def readPrefdl(self):
      identity = getPlatformIdentity()
      return identity.syseeprom

   def readPrefdlRaw(self):
      raise NotImplementedError

def getSysEeprom():
   global syseeprom
   if not syseeprom:
      syseeprom = SysEeprom()
   return syseeprom

def getSysEepromData():
   global syseepromData
   if not syseepromData:
      syseepromData = getSysEeprom().prefdl()
      assert 'SKU' in syseepromData
   return syseepromData

def readSku():
   return getPlatformIdentity().sku

def readSid():
   return getPlatformIdentity().sid

def readPlatformName():
   return getPlatformIdentity().platform

def readHwApi():
   return getPlatformIdentity().hwApi

def getPlatformCls(*names):
   return manager.getPlatformCls(*names)

def getPlatform(name=None):
   identity = getPlatformIdentity()
   # TODO: make getPlatformCls part of PlatformIdentity. For now, only BMC
   # identity implements it; generic lookup remains in PlatformManager.
   if isinstance(identity, PlatformIdentityBmc):
      platformCls = identity.getPlatformCls(name)
   else:
      platformCls = manager.getPlatformCls(name)
   platform = platformCls()
   platform.refresh()
   return platform

def getPlatformSkus():
   return manager.platformSkuIndex

def getPlatformSids():
   return manager.platformSidIndex

def getPlatforms():
   return manager.platforms

def loadPlatforms():
   with timeit('Loading platform definitions'):
      from .. import platforms as _  # pylint: disable=cyclic-import
   logging.debug('Loaded %d platforms', len(manager.platforms))

def registerPlatform():
   def wrapper(cls):
      return manager.registerPlatform(cls)
   return wrapper

def registerCpu():
   def wrapper(cls):
      return manager.registerCpu(cls)
   return wrapper

def registerBmc():
   def wrapper(cls):
      return manager.registerBmc(cls)
   return wrapper

def registerBmcSubsystem():
   def wrapper(cls):
      return manager.registerBmcSubsystem(cls)
   return wrapper
