
from __future__ import absolute_import, division, print_function

from . import registerAction
from ..args.reboot import rebootParser

@registerAction(rebootParser)
def doReboot(ctx, args):
   import arista.utils.sonic_reboot
   arista.utils.sonic_reboot.reboot(ctx.platform)
