from .. import registerAction
from ....args.chassis.uart import uartParser

@registerAction(uartParser)
def doUart(ctx, args): # pylint: disable=unused-argument
   pass
