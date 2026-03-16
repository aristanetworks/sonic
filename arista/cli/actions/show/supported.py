
from ....core.fabric import Fabric
from ....core.fixed import FixedSystem
from ....core.linecard import Linecard
from ....core.modular import Modular
from ....core.platform import getPlatforms
from ....core.supervisor import Supervisor

from ...args.show.supported import supportedParser
from ...show import Renderer

from . import registerAction

class ShowSupported(Renderer):
   def __init__(self):
      super(ShowSupported, self).__init__('supported')

   def data(self, show):
      types = {
         'Chassis': Modular,
         'Fixed': FixedSystem,
         'Fabric': Fabric,
         'Linecard': Linecard,
         'Supervisor': Supervisor,
      }
      def getPlatformType(p):
         for k, v in types.items():
            if issubclass(p, v):
               return k
         raise RuntimeError
      data = {}
      for platform in getPlatforms():
         typeCol = data.setdefault(getPlatformType(platform), [])
         typeCol.extend({
            'name': sku
         } for sku in platform.SKU)
      return data

   def renderText(self, show):
      data = self.data(show)
      for typ, skus in data.items():
         print('%s' % typ)
         print('-' * len(typ))
         for sku in sorted(skus, key=lambda x: x['name']):
            print(' - %s' % sku['name'])
         print()

@registerAction(supportedParser, needsPlatform=False)
def showSupported(ctx, args):
   ctx.show.render(ShowSupported())
