
from .. import registerAction
from ...args.chassis.setup import setupParser

@registerAction(setupParser)
def doSetup(ctx, args):
   print('TODO: setup for', ctx.chassis)
