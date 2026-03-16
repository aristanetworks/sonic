
from .. import registerAction
from ..diag import doCommonDiagCli
from ...args.linecard.diag import diagParser

@registerAction(diagParser)
def doLinecardDiag(ctx, args):
   doCommonDiagCli(ctx.linecards, args)
