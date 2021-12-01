
from __future__ import absolute_import, division, print_function

from .. import registerAction
from ...exception import ActionError
from ...fork import processIterParentWait
from ...args.fabric import fabricParser
from ....core.supervisor import Supervisor

@registerAction(fabricParser)
def doFabric(ctx, args):
   if not isinstance(ctx.platform, Supervisor):
      raise ActionError('platform %s is not a supervisor' % ctx.platform)

   chassis = ctx.platform.getChassis()
   setattr(ctx, 'chassis', chassis)

   chassis.loadFabrics(args.id)

   fabrics = []
   for fabric in chassis.iterFabrics():
      if (fabric.slot.getPresence() and
          (args.id is None or fabric.slot.slotId in args.id)):
         fabrics.append(fabric)

   if args.parallel:
      for fabric in processIterParentWait(fabrics):
         setattr(ctx, 'fabrics', [fabric])
   else:
      setattr(ctx, 'fabrics', fabrics)
