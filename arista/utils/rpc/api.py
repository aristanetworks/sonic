"""Implements classes for defining the JSON-RPC API."""

try:
   import asyncio
except ImportError:
   print('This feature only works in python3')
   raise

from datetime import datetime, timezone
import json

from ...core.cause import getLinecardReloadCauseManager
from ...core.config import Config, flashPath
from ...core.log import getLogger
from ...core.provision import LockBusyError, ProvisionManifest
from ...core.supervisor import Supervisor
from ...core.utils import inSimulation

from ...libs.rebootfs import getAndSetLcRebootCause

logging = getLogger(__name__)

class RpcPermissionError(Exception):
   pass

def registerMethod(method):
   def wrapper(self, ctx, *args, **kwargs):
      if not ctx.localhost():
         raise RpcPermissionError('method only available from localhost')
      return method(self, *args, *kwargs)
   wrapper.isRpcMethod = True
   return wrapper

def registerLinecardToSupMethod(method):
   def wrapper(self, ctx, *args, **kwargs):
      if not isinstance(self.platform, Supervisor):
         raise RpcPermissionError('method only available on chassis systems')

      slotId = ctx.slotId()
      if slotId is None:
         raise RpcPermissionError('method only available for linecards')

      try:
         offset = self.platform.linecardSlots[0].card.ABSOLUTE_CARD_OFFSET
         slot = self.platform.linecardSlots[slotId - offset]
      except IndexError:
         raise RpcPermissionError(f'linecard {slotId} is not available')

      # NOTE: Making sure we have the latest platform definition loaded would
      #       be the best, however we need need to check for leaks before doing
      #       so. We should not allow the daemon to grow in size over time.
      # slot.loadCard(standbyOnly=True)
      lc = slot.card
      return method(self, lc, *args, **kwargs)
   wrapper.isRpcMethod = True
   return wrapper

def registerSupToLinecardMethod(method):
   def wrapper(self, ctx, *args, **kwargs):
      slotId = ctx.slotId()
      if slotId not in (1, 2):
         raise RpcPermissionError('method only available from supervisor')
      return method(self, *args, **kwargs)
   wrapper.isRpcMethod = True
   return wrapper


class RpcApi():
   _methods = []

   def __init__(self, platform=None):
      self.platform = platform
      self.tasks = []

   async def _runCommand(self, cmd, *args):
      proc = await asyncio.create_subprocess_exec(
         cmd, *args,
         stdout=asyncio.subprocess.PIPE,
         stderr=asyncio.subprocess.PIPE)

      stdout, stderr = await proc.communicate()

      logging.info(f'{self} Command [{cmd} {" ".join(args)}] exited with {proc.returncode}')

      return {'status': proc.returncode == 0,
              'detail': '\n'.join([stdout.decode('utf-8'),
                                   stderr.decode('utf-8')])}

   async def _doSelfReboot(self):
      # We don't want the reboot to start until we have sent back the response.
      logging.debug('%s: waiting 2s to self reboot', self)
      await asyncio.sleep(2)
      logging.debug('%s: issuing reboot command', self)

      if inSimulation():
         return {'status': True, 'detail': 'Skipping reboot because we are in simulation.'}
      return await self._runCommand('reboot')

   @classmethod
   def methods(cls):
      if not cls._methods:
         cls._methods = [n for n, m in cls.__dict__.items() if getattr(m, 'isRpcMethod', False)]
      return cls._methods

class RpcSupervisorApi(RpcApi):
   """An RpcApi object implements the functionality of the JSON-RPC API.

   The JSON-RPC server should call methods on this object to run the
   functionality associated with the method. A JSON-RPC client may use
   the `methods` class property to determine what JSON-RPC methods are
   supported."""

   async def _runAristaFabric(self, slot, *args):
      allArgs = ['-l', '/var/log/arista-fabric.log',
                 'fabric', '-i', str(slot)]
      allArgs.extend(args)
      return await self._runCommand('arista', *allArgs)

   async def _runAristaLinecard(self, slot, *args):
      allArgs = ['-l', '/var/log/arista-linecard.log',
                 'linecard', '-i', str(slot)]
      allArgs.extend(args)
      return await self._runCommand('arista', *allArgs)

   async def _runAsyncAristaLinecard(self, slot, *args, delay=0):
      allArgs = ['-l', '/var/log/arista-linecard.log',
                 'linecard', '-i', str(slot)]
      allArgs.extend(args)
      if delay:
         logging.info('%s: Delay for %d seconds', self, delay)
         await asyncio.sleep(delay)
      logging.info('%s: issue arista command: %s', self, str(allArgs))
      return await self._runCommand('arista', *allArgs)

   @registerMethod
   async def linecardSetup(self, slot, powerCycleIfOn=False):
      """Power on the linecard identified by slot.

      This method returns a dictionary with two elements:
        - status: True if the command succeeded, false otherwise.
        - detail: Any output produced by the power on command."""
      args = [slot, 'setup', '--lcpu', '--on']
      if powerCycleIfOn:
         args.append('--powerCycleIfOn')
      return await self._runAristaLinecard(*args)

   @registerMethod
   async def linecardClean(self, slot):
      """Power off the linecard identified by slot.

      This method returns a dictionary with two elements:
        - status: True if the command succeeded, false otherwise.
        - detail: Any output produced by the power off command."""
      return await self._runAristaLinecard(slot, 'clean', '--lcpu', '--off')

   @registerMethod
   async def fabricSetup(self, slot, powerCycleIfOn=False):
      """Power on the fabric card identified by slot.

      This method returns a dictionary with two elements:
        - status: True if the command succeeded, false otherwise.
        - detail: Any output produced by the power on command."""
      args = [slot, 'setup', '--on']
      if powerCycleIfOn:
         args.append('--powerCycleIfOn')
      return await self._runAristaFabric(*args)

   @registerMethod
   async def fabricClean(self, slot):
      """Power off the fabric card identified by slot.

      This method returns a dictionary with two elements:
        - status: True if the command succeeded, false otherwise.
        - detail: Any output produced by the power off command."""
      return await self._runAristaFabric(slot, 'clean')

   @registerMethod
   async def supervisorSelfReboot(self):
      """Reboot the supervisor."""
      self.tasks.append(asyncio.create_task(self._doSelfReboot()))
      return {'status': True, 'detail': 'Reboot started'}

   @registerLinecardToSupMethod
   async def linecardStatusLedColorGet(self, lc):
      return lc.getInventory().getLed('status').getColor()

   @registerLinecardToSupMethod
   async def linecardStatusLedColorSet(self, lc, color):
      return lc.getInventory().getLed('status').setColor(color)

   @registerLinecardToSupMethod
   async def linecardSelfPowerCycle(self, lc):
      if Config().api_linecard_reboot_graceful:
         cmd = ('reboot', '--mode=hard')
         delay = 5
      else:
         cmd = ('setup', '--on', '--lcpu', '--powerCycleIfOn')
         delay = 2
      self.tasks.append(asyncio.create_task(
         self._runAsyncAristaLinecard(lc.getSlotId(), *cmd, delay=delay)))
      logging.info('%s: Return from linecardSelfPowerCycle', self)
      return {'status': True, 'detail': 'Reboot started'}

   @registerLinecardToSupMethod
   async def getLinecardRebootCause(self, lc):
      return getLinecardReloadCauseManager(lc, read=True).toDict(latestOnly=True)

   # pylint: disable=unused-argument
   @registerLinecardToSupMethod
   async def getSupervisorEeprom(self, lc):
      return self.platform.getEeprom()

   # pylint: disable=unused-argument
   @registerLinecardToSupMethod
   async def getSupervisorMaxPowerDraw(self, lc):
      return self.platform.MAX_POWER_DRAW

   @registerLinecardToSupMethod
   async def hasSeuError(self, lc, name):
      return lc.plx.driver.regs.hasScdSeuError()

   @registerLinecardToSupMethod
   async def getRebootCause(self, lc):
      return {'status': True, 'reboot_cause' : getAndSetLcRebootCause(lc)}

   @registerLinecardToSupMethod
   async def provisionComplete(self, lc):
      manifest = ProvisionManifest(self.platform)
      try:
         await manifest.setLinecardProvisioned(lc)
         return {'status': True}
      except LockBusyError:
         return {'status': False, 'reason': 'failed to acquire lock for linecard manifest'}

class RpcLinecardApi(RpcApi):

   @registerSupToLinecardMethod
   async def gracefulShutdown(self):
      """Shutdown the linecard itself."""
      with open(flashPath('reboot-cause', 'platform', 'reboot-extra-info.json'), 'w', encoding='utf-8') as f:
         json.dump({
            'from': 'supervisor',
            'when': datetime.now(timezone.utc).strftime("%a %b %d %I:%M:%S %p %Z %Y"),
            'version': 1,
         }, f, indent=4, separators=(',', ': '))
      self.tasks.append(asyncio.create_task(self._doSelfReboot()))
      return {'status': True, 'detail': 'Reboot started'}
