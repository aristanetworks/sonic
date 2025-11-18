
from __future__ import absolute_import, division, print_function

from .. import registerAction
from ...args.platform.blackbox import blackboxParser

from ....core.log import getLogger

logging = getLogger(__name__)

def doSingleBlackBox(args, blackbox):
   enable = args.blackbox_enable
   print('setting blackbox logging status to %r' % enable)
   blackbox.setEnabled(enable)
   return 0

@registerAction(blackboxParser)
def doBlackBox(ctx, args):
   blackbox = ctx.platform.getInventory().getBlackBox()
   if not blackbox:
      print("Blackbox not supported on this platform")
      return 0
   for b in blackbox:
      doSingleBlackBox(args, b)
   return 0
