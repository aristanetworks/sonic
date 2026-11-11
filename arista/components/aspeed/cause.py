import os
from ...core.cause import (
   ReloadCauseEntry,
   HardwareReloadCauseProvider,
)
from ...core.config import flashPath
from ...core.log import getLogger
from ...libs.fs import writeFileContent
from ...libs.python import makedirs
from ...libs.rebootfs import setOsSoftwareRebootCause
from ...descs.cause import ReloadCauseDesc, ReloadCausePriority

logging = getLogger(__name__)

PSTORE_CURRENT_HASH = '/run/pstore-dmesg-ramoops-0-current-hash'
PSTORE_LAST_HASH = flashPath('reboot-cause', 'platform',
                             'pstore-dmesg-ramoops-0-last-hash')


class AspeedReloadCauseProvider(HardwareReloadCauseProvider):

   def __init__(self, regs, wdtBootstatusPaths=None, wdtBootstatusMap=None,
                **kwargs):
      super().__init__(**kwargs)
      self.regs = regs
      self.wdtBootstatusPaths = wdtBootstatusPaths or []
      self.wdtBootstatusMap = wdtBootstatusMap or {}

   def __str__(self):
      return self.__class__.__name__

   def _readBootstatus(self, path):
      try:
         with open(path, encoding='utf-8') as f:
            return int(f.read().strip())
      except (OSError, ValueError):
         return 0

   def _readFileContent(self, path):
      try:
         with open(path, encoding='utf-8') as f:
            return f.read().strip()
      except OSError:
         return ''

   def _checkPstorePanic(self):
      current_hash = self._readFileContent(PSTORE_CURRENT_HASH)
      if not current_hash:
         logging.debug('no pstore ramoops hash found for current boot')
         return False

      last_hash = self._readFileContent(PSTORE_LAST_HASH)
      if current_hash == last_hash:
         logging.debug('pstore ramoops hash unchanged, stale dump')
         return False

      logging.debug('new pstore ramoops hash detected, kernel panic')
      return True

   def _savePstoreHash(self):
      current_hash = self._readFileContent(PSTORE_CURRENT_HASH)
      if not current_hash:
         return
      try:
         folder = os.path.dirname(PSTORE_LAST_HASH)
         if not os.path.isdir(folder):
            makedirs(folder, mode=0o755, exist_ok=True)
         writeFileContent(PSTORE_LAST_HASH, current_hash)
      except OSError:
         logging.exception('failed to save pstore hash')

   def _processWatchdogBootstatus(self, causes):
      for path in self.wdtBootstatusPaths:
         bootstatus = self._readBootstatus(path)
         if not bootstatus:
            continue

         wdt_name = os.path.basename(os.path.dirname(path))

         for flag, (causeDesc, description) in self.wdtBootstatusMap.items():
            if bootstatus & flag:
               causes.append(ReloadCauseEntry(
                  cause=causeDesc.typ,
                  rcDesc=f'{wdt_name} {description}',
                  priority=ReloadCausePriority.NORMAL,
               ))
               break
         else:
            causes.append(ReloadCauseEntry(
               cause=ReloadCauseDesc.UNKNOWN.typ,
               rcDesc=f'{wdt_name} unknown reset (bootstatus=0x{bootstatus:x})',
               priority=ReloadCausePriority.NORMAL,
            ))

   def _processPstore(self, causes):
      if self._checkPstorePanic():
         logging.debug('kernel panic detected via pstore')
         setOsSoftwareRebootCause(ReloadCauseDesc.KERNEL_PANIC.desc)
         causes.append(ReloadCauseEntry(
            cause=ReloadCauseDesc.KERNEL_PANIC.typ,
            rcDesc='kernel panic (pstore dump available)',
            priority=ReloadCausePriority.HIGH,
         ))
      self._savePstoreHash()

   def process(self):
      causes = []

      if self.regs.pwrst():
         logging.debug('power-on reset detected, clearing PWRST# bit')
         self.regs.pwrst(1)
         causes.append(ReloadCauseEntry(
            cause=ReloadCauseDesc.POWERLOSS.typ,
            rcDesc='Power loss detected via SCU0_050 PWRST#',
            priority=ReloadCausePriority.NORMAL,
         ))

      self._processWatchdogBootstatus(causes)
      self._processPstore(causes)

      self.causes = causes
