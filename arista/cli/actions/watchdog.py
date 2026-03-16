
from . import registerAction
from ..args.watchdog import watchdogParser

from ...core.log import getLogger

logging = getLogger(__name__)

@registerAction(watchdogParser)
def doWatchdog(ctx, args):
   watchdogs = ctx.platform.getInventory().getWatchdogs()
   if not watchdogs:
      print("Watchdog not supported on this platform")
      return 0

   watchdog = watchdogs[0]
   if args.watchdog_status:
      st = watchdog.status()
      if st:
         kv = ' '.join('%s=%s' % (k, v) for k, v in st.items())
         print("Watchdog status: %s" % kv)
      else:
         print("Watchdog status - error.")
         return 1
   elif args.watchdog_stop:
      logging.info('disabling the hardware watchdog')
      if not watchdog.stop():
         logging.error('failed to stop the hardware watchdog')
         return 1
   else:
      logging.info('arming the hardware watchdog for %ds', args.watchdog_timeout)
      # Tens of milliseconds
      watchdog_timeout = args.watchdog_timeout * 100
      if watchdog_timeout > watchdog.MAX_TIMEOUT:
         logging.error('failed to arm the hardware watchdog: time value is too big')
         return 1
      if not watchdog.arm(watchdog_timeout):
         logging.error('failed to arm the hardware watchdog')
         return 1
   return 0

