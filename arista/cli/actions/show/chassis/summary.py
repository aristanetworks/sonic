
from . import registerAction
from ....args.show.chassis.summary import chassisSummaryParser
from .....core.prefdl import InvalidPrefdlData

def doShowCard(ctx, args, card):
   try:
      if card and card.slot.getPresence():
         eeprom = card.slot.getEeprom()
         sku = eeprom.get('SKU')
         serial = eeprom.get('SerialNumber')
         print("  %d: %s (%s)" % (card.slot.slotId, sku, serial))
      else:
         print("  %d: not present" % card.slot.slotId)
   except InvalidPrefdlData:
      print("  %d: invalid prefdl" % card.slot.slotId)
   except IOError:
      print("  %d: IO Error" % card.slot.slotId)
   except Exception: # pylint: disable=broad-except
      print("  %d: Error" % card.slot.slotId)

def doShowPsu(ctx, args, slot):
   slotId = slot.slotId
   try:
      if slot.getPresence():
         ident = slot.model.identifier
         sku = ident.aristaName
         serial = ident.metadata['serial']
         print("  %d: %s (%s)" % (slotId, sku, serial))
      else:
         print("  %d: not present" % slotId)
   except IOError:
      print("  %d: IO Error" % slotId)
   except Exception: # pylint: disable=broad-except
      print("  %d: Error" % slotId)

def doShowSupervisors(ctx, args):
   for sup in ctx.chassis.iterSupervisors():
      if sup == ctx.chassis.active: # TODO: add support for standby
         slotId = sup.getSlotId()
         eeprom = sup.getEeprom()
         sku = eeprom.get('SKU')
         serial = eeprom.get('SerialNumber')
         print("  %d: %s (%s)" % (slotId, sku, serial))

@registerAction(chassisSummaryParser)
def doChassisSummary(ctx, args):
   eeprom = ctx.chassis.getEeprom()
   print("Sku: %s" % eeprom.get('SKU'))
   print("Serial: %s" % eeprom.get('SerialNumber'))
   print("Supervisors:")
   doShowSupervisors(ctx, args)
   print("Linecards:")
   for linecard in ctx.chassis.iterLinecards():
      doShowCard(ctx, args, linecard)
   print("Fabrics:")
   for fabric in ctx.chassis.iterFabrics():
      doShowCard(ctx, args, fabric)
   print("Psus:")
   for psu in ctx.chassis.iterPsus():
      doShowPsu(ctx, args, psu)

