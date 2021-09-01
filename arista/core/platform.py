from __future__ import print_function

import os

from .config import etcPath, flashPath
from .driver import modprobe
from .exception import UnknownPlatformError
from .log import getLogger
from .prefdl import Prefdl
from .utils import simulateWith, getCmdlineDict

from ..libs.benchmark import timeit

logging = getLogger(__name__)

platforms = []
platformSidIndex = {}
platformSkuIndex = {}
syseeprom = None
syseepromData = None

host_prefdl_path = flashPath('.system-prefdl')
host_prefdl_path_bin = flashPath('.system-prefdl-bin')
fmted_prefdl_path = etcPath('.syseeprom')

def readPrefdlEeprom(*addrs):
   modprobe('eeprom')
   for addr in addrs:
      eeprompath = os.path.join('/sys/bus/i2c/drivers/eeprom', addr, 'eeprom')
      if not os.path.exists(eeprompath):
         continue
      try:
         logging.debug('reading system eeprom from %s', eeprompath)
         pfdl = Prefdl.fromBinFile(eeprompath)
         pfdl.writeToFile(fmted_prefdl_path)
         return pfdl
      except Exception as e: # pylint: disable=broad-except
         logging.warn('could not obtain prefdl from %s', eeprompath)
         logging.warn('error seen: %s', e)

   raise RuntimeError("Could not find valid system eeprom")

def readPrefdl():
   if os.path.isfile(fmted_prefdl_path) and os.path.getsize(fmted_prefdl_path) > 0:
      logging.debug('reading system eeprom from %s', fmted_prefdl_path)
      return Prefdl.fromTextFile(fmted_prefdl_path)

   if os.path.exists(host_prefdl_path_bin):
      logging.debug('reading bin system eeprom from %s', host_prefdl_path_bin)
      pfdl = Prefdl.fromBinFile(host_prefdl_path_bin)
      pfdl.writeToFile(fmted_prefdl_path)
      return pfdl

   if os.path.exists(host_prefdl_path):
      logging.debug('reading system eeprom from %s', host_prefdl_path)
      pfdl = Prefdl.fromTextFile(host_prefdl_path)
      pfdl.writeToFile(fmted_prefdl_path)
      return pfdl

   return readPrefdlEeprom('1-0052')

class SysEeprom(object):
   def prefdlSim(self):
      logging.debug('bypass prefdl reading by returning default values')
      return {
         'SKU': 'simulation',
         'HwApi': '42',
      }

   @simulateWith(prefdlSim)
   def prefdl(self):
      return self.readPrefdl().data()

   def readPrefdl(self):
      return readPrefdl()

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
   return getSysEepromData().get('SKU')

def readSid():
   return getCmdlineDict().get('sid')

def readPlatformName():
   return getCmdlineDict().get('platform')

def readHwApi():
   return getSysEepromData().get('HwApi')

def detectPlatform():
   # TODO: refactor by obtaining a Cpu object based on the platform= from cmdline
   #       implement getEeprom on all Cpu to get the prefdl from hw
   #       add a fallback mechanism to read /etc/sonic/.syseeprom like we do today
   getSysEeprom()

   sid = readSid()
   platformCls = platformSidIndex.get(sid)
   if platformCls is not None:
      return platformCls

   sku = readSku()
   platformCls = platformSkuIndex.get(sku)
   if platformCls is not None:
      return platformCls

   name = readPlatformName()
   platformCls = platformSidIndex.get(name)
   if platformCls is not None:
      return platformCls

   raise UnknownPlatformError(sku, sid, name, platforms)

def getPlatformCls(*names):
   if not names or not [name for name in names if name]:
      return detectPlatform()

   for name in names:
      if name is None:
         continue

      platformCls = platformSkuIndex.get(name)
      if platformCls is not None:
         return platformCls

      platformCls = platformSidIndex.get(name)
      if platformCls is not None:
         return platformCls

   raise UnknownPlatformError(names, platforms)

def getPlatform(name=None):
   platformCls = getPlatformCls(name)
   platform = platformCls()
   platform.refresh()
   return platform

def getPlatformSkus():
   return platformSkuIndex

def getPlatformSids():
   return platformSidIndex

def getPlatforms():
   return platforms

def loadPlatforms():
   with timeit('Loading platform definitions'):
      from .. import platforms as _
   logging.debug('Loaded %d platforms', len(platforms))

def registerPlatform():
   def wrapper(cls):
      platforms.append(cls)

      for sid in cls.SID:
         platformSidIndex[sid] = cls
      for sku in cls.SKU:
         platformSkuIndex[sku] = cls

      if cls.PLATFORM is not None:
         # this is a hack for older platforms that did not provide sid=
         assert cls.PLATFORM not in platformSidIndex
         platformSidIndex[cls.PLATFORM] = cls

      return cls
   return wrapper
