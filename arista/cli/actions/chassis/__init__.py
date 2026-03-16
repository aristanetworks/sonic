
from .. import registerAction
from ...exception import ActionError
from ...args.chassis import chassisParser
from ....core.supervisor import Supervisor

@registerAction(chassisParser)
def doChassis(ctx, args):
   if not isinstance(ctx.platform, Supervisor):
      raise ActionError('platform %s is not a supervisor' % ctx.platform)

   chassis = ctx.platform.getChassis()
   setattr(ctx, 'chassis', chassis)
