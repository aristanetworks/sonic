
from __future__ import absolute_import, division, print_function

from .. import registerAction
from ...args.platform.blackbox import blackboxParser

from ....core.log import getLogger

logging = getLogger(__name__)

def doSingleBlackBox(args, blackbox):
   if args.blackbox_dump_path:
      return doBlackBoxDump(blackbox, args.blackbox_dump_path)

   if args.blackbox_erase:
      return doBlackBoxErase(blackbox)

   enable = args.blackbox_enable
   print('setting blackbox logging status to %r' % enable)
   blackbox.setEnabled(enable)
   return 0

def doBlackBoxDump(blackbox, outputPath):
   if blackbox.enabled():
      print('Error: Disable blackbox logging before dumping contents')
      return 1
   return blackbox.dump(outputPath)

def doBlackBoxErase(blackbox):
   if blackbox.enabled():
      print('Error: Disable blackbox logging before erasing contents')
      return 1
   return blackbox.erase()

@registerAction(blackboxParser)
def doBlackBox(ctx, args):
   blackbox = ctx.platform.getInventory().getBlackBox()
   if not blackbox:
      print("Blackbox not supported on this platform")
      return 0
   for b in blackbox:
      doSingleBlackBox(args, b)
   return 0
