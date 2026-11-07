import os
import platform
import subprocess

from . import KernelDriver
from ... import utils
from ...log import getLogger
from ....libs.fs import readFileContent

logging = getLogger(__name__)


class AmdPcieKernelDriver(KernelDriver):
   """Load the AMD PCIe policy module and apply its settings during setup."""

   MODULE = 'arista-amd-pcie'
   PATH = '/sys/module/arista_amd_pcie'
   CPUINFO_PATH = '/proc/cpuinfo'
   # Keep CPU identities and profile names aligned with src/arista-amd-pcie.c.
   PROFILES = {
      (0x19, 0x44): 'V3000',
      (0x17, 0x01): 'Snowy Owl',
      (0x1a, 0x44): 'Fire Range',
   }

   def _detectProfile(self):
      fields = {}
      with open(self.CPUINFO_PATH, encoding='utf8') as cpuInfo:
         for line in cpuInfo:
            if not line.strip():
               break
            key, separator, value = line.partition(':')
            if separator:
               fields[key.strip()] = value.strip()
      if (fields.get('vendor_id') != 'AuthenticAMD' or
          not fields.get('flags') or
          'hypervisor' in fields['flags'].split()):
         return None
      try:
         identity = (int(fields['cpu family'], 10), int(fields['model'], 10))
      except (KeyError, ValueError):
         return None
      return self.PROFILES.get(identity)

   def setup(self):
      if platform.machine() != 'x86_64':
         return
      simulation = utils.inSimulation()
      try:
         profile = None
         if not simulation:
            profile = self._detectProfile()
            if profile is None:
               return
         super(AmdPcieKernelDriver, self).setup()
         path = os.path.join(self.getSysfsPath(), 'apply_policy')
         if simulation:
            logging.debug('simulate AMD PCIe policy at %s', path)
            return
         kernelProfile = readFileContent(os.path.join(self.getSysfsPath(),
                                                     'profile')).strip()
         if not kernelProfile:
            raise OSError('could not read AMD PCIe policy profile')
         if kernelProfile != profile:
            logging.error('AMD PCIe policy profile mismatch: userspace=%s kernel=%s',
                          profile, kernelProfile)
            return
         state = readFileContent(path).strip()
         if state == '1':
            return
         if state != '0':
            raise OSError('could not read AMD PCIe policy state')
         utils.writeConfig(self.getSysfsPath(), {'apply_policy': '1'})
         # writeConfig logs write errors without raising; check the result.
         if readFileContent(path).strip() != '1':
            raise OSError('AMD PCIe policy application failed')
      except (OSError, subprocess.CalledProcessError):
         logging.exception('Failed to apply AMD PCIe error policy')
