from __future__ import absolute_import, division, print_function

from .. import registerAction
from ....args.chassis.uart.reset import resetParser
from .....core.log import getLogger

logging = getLogger(__name__)

def getActiveSlots(platform, lcs=None):
   populatedSlots = []
   for slot in platform.linecardSlots:
      if lcs and slot.slotId not in lcs:
         continue
      if slot.getPresence():
         slotId = slot.slotId
         populatedSlots.append(slotId-3)
   return populatedSlots

@registerAction(resetParser)
def doReset(ctx, args):
   platform = ctx.platform

   scd = platform.scd
   if not scd.uartPorts:
      logging.warning("No uart serial ports detected in system")
      return

   if args.id:
      slots = getActiveSlots(platform, lcs=args.id)
      if not slots:
         logging.warning("LC %d is not active", args.id[0])
         return
   else:
      slots = getActiveSlots(platform)
      if not slots:
         logging.warning("No active LCs in system")
         return

   uartAddrs = {v['id']: k for k, v in scd.uartPorts.items()}
   with scd.getMmap() as mm:
      for slotId in slots:
         logging.info("Flushing Linecard: %d", slotId + 3)
         for addr in [ uartAddrs[slotId] + 0x108, uartAddrs[slotId] + 0x4 ]:
            logging.debug("scd addr: %x", addr)
            mm.write32(addr, 1)
