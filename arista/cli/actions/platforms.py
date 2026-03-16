
from . import registerAction
from ..args.platforms import platformsParser
from ...core.fixed import FixedSystem
from ...core.platform import getPlatformSkus

@registerAction(platformsParser, needsPlatform=False)
def doPlatforms(ctx, args):
   print('supported platforms:')
   for plat, cls in sorted(getPlatformSkus().items()):
      if issubclass(cls, FixedSystem):
         print(' -', plat)
