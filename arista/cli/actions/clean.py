
from . import registerAction
from ..args.clean import cleanParser
from ...core import utils
from ...core.config import Config
from ...core.log import getLogger

logging = getLogger(__name__)

@registerAction(cleanParser)
def doClean(ctx, args):
   if args.reset:
      logging.debug('putting devices in reset')
      ctx.platform.resetIn()

   logging.debug('cleaning up platform')
   with utils.FileLock(Config().lock_file):
      ctx.platform.clean()
