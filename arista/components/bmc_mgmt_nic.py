# Copyright (c) 2026 Arista Networks, Inc.  All rights reserved.

import re
import subprocess

from ..core.log import getLogger
from ..core.utils import inSimulation

from .nic import Nic

logging = getLogger(__name__)

MAC_RE = re.compile(r'^[0-9a-f]{2}(:[0-9a-f]{2}){5}$', re.IGNORECASE)

def addMacOffset(baseMac: str, offset: int) -> str:
   if not isinstance(baseMac, str) or not MAC_RE.match(baseMac):
      raise ValueError(f'invalid MAC address: {baseMac}')

   mac = int(baseMac.replace(':', ''), 16) + offset

   return ':'.join(f'{(mac >> shift) & 0xff:02x}'
                   for shift in range(40, -1, -8))

def isValidMac(mac: str) -> bool:
   return isinstance(mac, str) and MAC_RE.match(mac) is not None

class BmcMgmtNic(Nic):
   """BMC physical management NIC.

   Keep U-Boot ethaddr and the active Linux interface synchronized with the
   CPU EEPROM base MAC plus the platform offset.
   """

   INTERFACE = 'eth0'
   MAC_OFFSET = 3

   def __init__(self, cpuEeprom, interface=INTERFACE, macOffset=MAC_OFFSET,
                **kwargs):
      super().__init__(**kwargs)
      self.Eeprom = cpuEeprom
      self.interface = interface
      self.macOffset = macOffset

   def configure(self, ifName, addr=None, prefixLen=None):
      del addr, prefixLen

      if inSimulation():
         logging.debug('%s: simulation, skipping management MAC configure', self)
         return

      desiredMac = self.getEepromMgmtMac()
      if desiredMac is not None:
         self.syncUbootMac(desiredMac)
      else:
         desiredMac = self.readUbootMac()
      if desiredMac is None:
         raise RuntimeError(f'{self}: no valid management MAC found')

      self.waitForInterface(ifName)
      configuredMac = self.getConfiguredMac(ifName)
      if self.macEqual(configuredMac, desiredMac):
         logging.debug('%s: %s MAC is already %s', self, ifName, desiredMac)
         return

      self.setMACAddress(ifName, desiredMac)
      logging.info('%s: set %s MAC to %s', self, ifName, desiredMac)

   def unconfigure(self, ifName):
      logging.debug('%s: leaving %s MAC configured', self, ifName)

   def getEepromMgmtMac(self):
      try:
         return self.readEepromMgmtMac()
      except (OSError, TypeError, ValueError) as e:
         logging.debug('%s: failed to read CPU EEPROM MAC: %s', self, e)
         return None

   def readEepromMgmtMac(self):
      baseMac = self.Eeprom.prefdl().get('MAC')
      if not isValidMac(baseMac):
         return None
      return addMacOffset(baseMac, self.macOffset)

   def readUbootMac(self):
      try:
         mac = subprocess.check_output(
            ['fw_printenv', '-n', 'ethaddr'], text=True,
            stderr=subprocess.DEVNULL).strip()
      except (subprocess.CalledProcessError, FileNotFoundError):
         return None
      if not isValidMac(mac):
         return None
      return mac.lower()

   def writeUbootMac(self, mac):
      subprocess.check_call(['fw_setenv', 'ethaddr', mac])

   def syncUbootMac(self, desiredMac):
      ubootMac = self.readUbootMac()
      if ubootMac is not None and self.macEqual(ubootMac, desiredMac):
         logging.debug('%s: U-Boot ethaddr is already %s', self, desiredMac)
         return

      try:
         self.writeUbootMac(desiredMac)
         logging.info('%s: updated U-Boot ethaddr to %s', self, desiredMac)
      except (subprocess.CalledProcessError, OSError) as e:
         logging.warning('%s: failed to update U-Boot ethaddr: %s', self, e)

   def macEqual(self, macA, macB):
      return macA.lower() == macB.lower()
