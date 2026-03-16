
from .. import registerAction
from ...args.fabric.clean import cleanParser
from ....core.log import getLogger

logging = getLogger(__name__)

@registerAction(cleanParser)
def doClean(ctx, args):
   for fabric in ctx.fabrics:
      logging.debug('Cleaning %s', fabric)
      try:
         fabric.clean()
         if args.off:
            fabric.powerOnIs(False)
      except Exception as e:  # pylint: disable=broad-except
         logging.warning('Failed to clean %s: %s', fabric, str(e))

