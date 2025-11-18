
from . import registerAction
from ....args.show.platform.blackbox import showPlatformBlackBoxParser
from ....show.blackbox import ShowBlackBox

@registerAction(showPlatformBlackBoxParser)
def doShowPlatformBlackBox(ctx, _args):
   ctx.show.addInventory(ctx.platform.getInventory().getBlackBox())
   ctx.show.render(ShowBlackBox())
