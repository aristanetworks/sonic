
from .. import registerAction
from ...args.linecard.provision import provisionParser
from ....core.log import getLogger

logging = getLogger(__name__)

@registerAction(provisionParser)
def doProvision(ctx, args):
   for linecard in ctx.linecards:
      try:
         if not linecard.hasCpuModule():
            logging.info('%s has no LCPU module, skipping...', linecard)
            continue
         if not linecard.poweredOn():
            logging.info('%s is not powered on, skipping...', linecard)
            continue
         logging.debug('Setting provision mode to %s on %s', args.set, linecard)
         linecard.provisionIs(args.set)
      except Exception as e: # pylint: disable=broad-except
         logging.warning('Failed to set provision mode on %s: %s', linecard, str(e))
