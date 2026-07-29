
from . import registerAction
from ....args.show.platform.reboot_cause import rebootCauseParser
from ....show.reboot_cause import (
   ShowPlatformRebootCause,
   ShowPlatformRebootCauseList
)

@registerAction(rebootCauseParser)
def doShowEnvironment(ctx, args):
   if args.list:
      ctx.show.render(ShowPlatformRebootCauseList())
   else:
      ctx.show.render(ShowPlatformRebootCause())
