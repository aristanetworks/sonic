
from .. import registerAction
from ...args.linecard.eeprom import eepromParser
from ....core.log import getLogger

logging = getLogger(__name__)

def resetEeprom(linecard):
   if not linecard.getPresence():
      logging.debug('%s: linecard not present', linecard)
      return

   logging.debug('%s: clearing eeprom data', linecard)
   linecard.eeprom.clearPrefdlCache()
   linecard.slot.getEeprom()

@registerAction(eepromParser)
def doSetup(ctx, args):
   for linecard in ctx.linecards:
      try:
         if args.reset:
            resetEeprom(linecard)
      except Exception as e: # pylint: disable=broad-except
         logging.warning('Failed to reset eeprom %s: %s', linecard, str(e))
