
from . import registerAction
from ..args.reboot_cause import rebootCauseParser
from ...core import utils
from ...core.cause import getReloadCauseManager
from ...core.config import Config

@registerAction(rebootCauseParser)
def doRebootCause(ctx, args):
   if utils.inSimulation():
      return

   with utils.FileLock(Config().lock_file):
      rcm = getReloadCauseManager(ctx.platform, read=args.process)

   if args.history:
      causes = [report.cause for report in rcm.allReports()]
   else:
      report = rcm.lastReport()
      causes = [report.cause] if report else []
   if not causes:
      print('No reboot cause detected')
      return
   print('Found reboot cause(s):')
   print('----------------------')
   for item in causes:
      print(item)
