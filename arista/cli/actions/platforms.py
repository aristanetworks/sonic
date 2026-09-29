
from . import registerAction
from ..args.platforms import platformsParser
from ...core.fixed import FixedSystem
from ...core.platform_loader import platform_loader

@registerAction(platformsParser, needsPlatform=False)
def doPlatforms(ctx, args):
   print('supported platforms:')
   fixed = []
   for cls in platform_loader.all_platforms():
      if issubclass(cls, FixedSystem):
         fixed.extend(cls.SKU)
   fixed.sort()
   for sku in fixed:
      print(' -', sku)
