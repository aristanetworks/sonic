from __future__ import print_function

import os

from .exception import UnknownPlatformError
from .utils import simulateWith, getCmdlineDict
from .driver import modprobe
from .log import getLogger

from . import prefdl

from ..libs.benchmark import timeit

logging = getLogger(__name__)

platforms = []
platformSidIndex = {}
platformSkuIndex = {}
syseeprom = None

host_prefdl_path = '/host/.system-prefdl'
host_prefdl_path_bin = '/host/.system-prefdl-bin'
fmted_prefdl_path = '/etc/sonic/.syseeprom'

def formatPrefdlData(data):
   formatDict = {
      "ASY": ["ASY"],
      "MAC": ["MAC", "MacAddrBase", "Mac"],
      "SKU": ["SKU", "Sku"],
      "SerialNumber": ["SerialNumber"],
   }
   fdata = { }
   for k, v in data.items():
      for kfmt, vfmt in formatDict.items():
         if k in vfmt:
            if kfmt == "MAC" and ':' not in v:
               val = prefdl.showMac(v)
            else:
               val = v
            fdata[kfmt] = val
   return fdata

def writeFormattedPrefdl(pfdl, f):
   fdata = formatPrefdlData(pfdl.data())
   with open(f, 'w+', 0) as fp:
      for k, v in fdata.items():
         fp.write("%s: %s\n" % (k, v))

def readPrefdlEeprom(*addrs):
   for addr in addrs:
      eeprompath = os.path.join('/sys/bus/i2c/drivers/eeprom', addr, 'eeprom')
      if not os.path.exists(eeprompath):
         continue
      try:
         with open(eeprompath) as fp:
            logging.debug('reading system eeprom from %s', eeprompath)
            pfdl = prefdl.decode(fp)
            pfdl.writeToFile(fmted_prefdl_path)
            return pfdl
      except Exception as e:
         logging.warn('could not obtain prefdl from %s', eeprompath)
         logging.warn('error seen: %s', e)

   raise RuntimeError("Could not find valid system eeprom")

def readPrefdl():
   if os.path.isfile(fmted_prefdl_path) and \
      os.path.getsize(fmted_prefdl_path) > 0:
      with open(fmted_prefdl_path) as fp:
         logging.debug('reading system eeprom from %s', fmted_prefdl_path)
         return prefdl.PreFdlFromFile(fp)

   if os.path.exists(host_prefdl_path_bin):
      with open(host_prefdl_path_bin) as fp:
         logging.debug('reading bin system eeprom from %s',
                       host_prefdl_path_bin)
         pfdl = prefdl.decode(fp)
         writeFormattedPrefdl(pfdl, fmted_prefdl_path)
         return pfdl

   if os.path.exists(host_prefdl_path):
      with open(host_prefdl_path) as fp:
         logging.debug('reading system eeprom from %s', host_prefdl_path)
         pfdl = prefdl.PreFdlFromFile(fp)
      writeFormattedPrefdl(pfdl, fmted_prefdl_path)
      with open(fmted_prefdl_path) as fp:
         return prefdl.PreFdlFromFile(fp)

   modprobe('eeprom')
   return readPrefdlEeprom('1-0052')

def getPrefdlDataSim():
   logging.debug('bypass prefdl reading by returning default values')
   return {
      'SKU': 'simulation',
      'HwApi': '42',
   }

@simulateWith(getPrefdlDataSim)
def getPrefdlData():
   return readPrefdl().data()

def getSysEeprom():
   global syseeprom
   if not syseeprom:
      syseeprom = getPrefdlData()
      assert 'SKU' in syseeprom
   return syseeprom

def readSku():
   return getSysEeprom().get('SKU')

def readSid():
   return getCmdlineDict().get('sid')

def readPlatformName():
   return getCmdlineDict().get('platform')

def readHwApi():
   return getSysEeprom().get('HwApi')

def detectPlatform():
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
