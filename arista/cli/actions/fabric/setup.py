
from __future__ import absolute_import, division, print_function

from .. import registerAction
from ...args.fabric.setup import setupParser
from ....core.component import Priority
from ....core.log import getLogger

logging = getLogger(__name__)

def setupFabric(fabric, args):
   if fault := fabric.slot.getFault():
      logging.warning('Not setting up fabric card due to fault: %s', fault)
   if args.early or not args.late:
      fabric.setup(Priority.defaultFilter)
   if args.late or not args.early:
      fabric.setup(Priority.lateFilter)
   if args.on:
      if fabric.poweredOn() and args.powerCycleIfOn:
         fabric.powerOnIs(False)
      fabric.powerOnIs(True)
      if args.early or not args.late:
         fabric.setupMain(Priority.defaultFilter)
      if args.late or not args.early:
         fabric.setupMain(Priority.lateFilter)

@registerAction(setupParser)
def doSetup(ctx, args):
   for fabric in ctx.fabrics:
      logging.debug('Setting up %s', fabric)
      try:
         setupFabric(fabric, args)
      except Exception as e:  # pylint: disable=broad-except
         logging.warning('Failed to setup %s: %s', fabric, str(e))

