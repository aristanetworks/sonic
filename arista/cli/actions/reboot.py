
from . import registerAction
from ..args.reboot import rebootParser

@registerAction(rebootParser)
def doReboot(ctx, args):
   import arista.utils.sonic_reboot
   arista.utils.sonic_reboot.do_reboot(ctx.platform)
