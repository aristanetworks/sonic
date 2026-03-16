
from .. import registerAction
from ..diag import doCommonDiagCli
from ...args.platform.diag import diagParser

@registerAction(diagParser)
def doPlatformDiag(ctx, args):
   doCommonDiagCli([ctx.platform], args)
