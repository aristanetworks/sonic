
from __future__ import absolute_import, division, print_function

from .. import registerAction
from ...exception import ActionError
from ...fork import processIterParentWait
from ...args.linecard import linecardParser
from ....core.supervisor import Supervisor

@registerAction(linecardParser)
def doLinecard(ctx, args):
   if not isinstance(ctx.platform, Supervisor):
      raise ActionError('platform %s is not a supervisor' % ctx.platform)

   chassis = ctx.platform.getChassis()
   setattr(ctx, 'chassis', chassis)

   chassis.loadLinecards(args.id)

   linecards = []
   for linecard in chassis.iterLinecards():
      if (linecard.slot.getPresence() and
          (args.id is None or linecard.slot.slotId in args.id)):
         linecards.append(linecard)

   if args.parallel:
      for linecard in processIterParentWait(linecards):
         setattr(ctx, 'linecards', [linecard])
   else:
      setattr(ctx, 'linecards', linecards)
