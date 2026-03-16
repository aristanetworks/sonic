
from .. import registerAction
from ...args.linecard.clean import cleanParser
from ....core.config import Config
from ....core.log import getLogger
from ....core.linecard import LCpuCtx

logging = getLogger(__name__)

def cleanLinecard(linecard, args, lcpu):
   linecard.clean()

   if not args.off:
      return

   if not Config().linecard_standby_only and lcpu:
      logging.warning('LCPU cannot be powered off in non standby mode')
      return

   lcpuCtx = None
   if lcpu:
      lcpuCtx = LCpuCtx()

   if not Config().linecard_standby_only or lcpu:
      linecard.powerOnIs(False, lcpuCtx=lcpuCtx)

@registerAction(cleanParser)
def doClean(ctx, args):
   lcpu = args.lcpu if args.lcpu is not None else Config().linecard_cpu_enable

   for linecard in ctx.linecards:
      logging.debug('Cleaning %s', linecard)
      try:
         cleanLinecard(linecard, args, lcpu)
      except Exception as e: # pylint: disable=broad-except
         logging.warning('Failed to clean %s: %s', linecard, str(e))
