
from __future__ import absolute_import, division, print_function

from .. import registerAction
from ...args.linecard.setup import setupParser
from ....core.cause import getLinecardReloadCauseManager
from ....core.component import Priority
from ....core.config import Config
from ....core.log import getLogger
from ....core.linecard import LCpuCtx

logging = getLogger(__name__)

def setupLinecard(linecard, args, lcpu):
   if fault := linecard.slot.getFault():
      logging.warning('Not setting up linecard due to fault: %s', fault)

   if args.early or not args.late:
      linecard.setupStandby(Priority.defaultFilter)
   if args.late or not args.early:
      linecard.setupStandby(Priority.lateFilter)

   if not args.on:
      return

   if not Config().linecard_standby_only and lcpu:
      logging.warning('LCPU cannot be powered on in non standby mode')
      return

   lcpuCtx = None
   if args.lcpu:
      if not linecard.hasCpuModule():
         logging.info('%s has no LCPU module, skipping...', linecard)
         return
      lcpuCtx = LCpuCtx(provision=args.provision)

   if not Config().linecard_standby_only or lcpu:
      if linecard.poweredOn() and args.powerCycleIfOn:
         linecard.powerOnIs(False, lcpuCtx=lcpuCtx)
      linecard.powerOnIs(True, lcpuCtx=lcpuCtx)

      if args.early or not args.late:
         linecard.setupControlPlane(Priority.defaultFilter)
      if args.late or not args.early:
         linecard.setupControlPlane(Priority.lateFilter)

      if not lcpu:
         if args.early or not args.late:
            linecard.setupMain(Priority.defaultFilter)
         if args.late or not args.early:
            linecard.setupMain(Priority.lateFilter)

         # Pull down the linecard reload causes from hardware DPM
         logging.info('%s: Process reload cause info', linecard)
         getLinecardReloadCauseManager(linecard, read=True)

@registerAction(setupParser)
def doSetup(ctx, args):
   lcpu = args.lcpu if args.lcpu is not None else Config().linecard_cpu_enable
   for linecard in ctx.linecards:
      logging.debug('Setting up %s', linecard)
      try:
         setupLinecard(linecard, args, lcpu)
      except Exception as e: # pylint: disable=broad-except
         logging.warning('Failed to setup %s: %s', linecard, str(e))
