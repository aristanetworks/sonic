from __future__ import annotations

import re

from .exception import UnknownPlatformError
from .identity.bmc import PlatformIdentityBmc
from .identity.factory import createPlatformIdentity
from .log import getLogger
from .platform_loader import platform_loader

logging = getLogger(__name__)

syseeprom = None
syseepromData = None


class PlatformManager:
   _loader = platform_loader

   def __init__(self):
      self.identity = createPlatformIdentity()

   def detectPlatform(self):
      # TODO: refactor by obtaining a Cpu object based on the platform= from
      #       cmdline implement getEeprom on all Cpu to get the prefdl from hw
      #       add a fallback mechanism to read /etc/sonic/.syseeprom like done
      #       today
      getSysEepromData()

      names = []
      for readname in (readSid, readSku, readPlatformName):
         name = readname()
         if pc := self._loader.platforms.get(name):
            return pc
         names.append(name)

      raise UnknownPlatformError(*names)

   def getPlatformCls(self, *names):
      """Get platform class by SKU or SID (which are assumed to be distinct).
      First match wins.
      """
      if not names or not any(names):
         return self.detectPlatform()

      for name in names:
         if name and (pc := self._loader.platforms.get(name)):
            return pc

      raise UnknownPlatformError(*names)


manager = PlatformManager()

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

def getPlatforms():
   return platform_loader.all_platforms()

def registerPlatform():
   return platform_loader.platforms.add

def registerCpu():
   return platform_loader.cpus.add

def registerBmc():
   return platform_loader.bmcs.add

def registerBmcSubsystem():
   return platform_loader.bmc_subsystems.add
