
from . import registerAction
from ..args.setup import setupParser
from ...core import utils
from ...core.config import Config
from ...core.component import Priority
from ...core.log import getLogger
from ...core.platform import loadPrerequisites

logging = getLogger(__name__)

def reportPlatformInfo(platform):
   keys = ['SKU', 'SID', 'SerialNumber']
   fields = ['%s=%s' % (k, v) for k, v in platform.getEeprom().items() if k in keys]
   logging.debug('Platform info: %s', ' '.join(fields))

def setupXcvrs(platform):
   for xcvrSlot in platform.getInventory().getXcvrSlots().values():
      try:
         xcvrSlot.setModuleSelect(True)
      except NotImplementedError:
         pass
      xcvrSlot.setTxDisable(False)
      if Config().xcvr_lpmode_out:
         try:
            xcvrSlot.setLowPowerMode(False)
         except NotImplementedError:
            pass

@registerAction(setupParser)
def doSetup(ctx, args):
   platform = ctx.platform

   if args.debug:
      utils.debug = True

   reportPlatformInfo(platform)

   with utils.FileLock(Config().lock_file):
      if args.early or not args.late:
         logging.debug('setting up critical drivers')
         loadPrerequisites()
         platform.setup(Priority.defaultFilter)

      # NOTE: This assumes that none of the resetable devices are
      #       initialized in background.
      #       This should stay true in the future.
      if args.reset:
         logging.debug('taking devices out of reset')
         platform.resetOut()
         logging.debug('initializing xcvrs')
         setupXcvrs(platform)

      if args.late or not args.early:
         platform.setup(Priority.lateFilter)

      if args.early or not args.late:
         platform.waitForIt()
