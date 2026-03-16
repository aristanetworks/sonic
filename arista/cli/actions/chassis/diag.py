
from .. import registerAction
from ..diag import doCommonDiagCli
from ...args.chassis.diag import diagParser

@registerAction(diagParser)
def doChassisDiag(ctx, args):
   doCommonDiagCli([ctx.platform.getChassis()], args)
