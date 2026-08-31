
from ...core.diag import DiagContext

from . import Renderer, Table, Col

class ShowXcvr(Renderer):

   NAME = 'xcvr'

   def getData(self, show):
      ctx = DiagContext()
      data = []
      for inventory, _ in show.inventories:
         for xcvr in inventory.getXcvrSlots().values():
            entry = xcvr.__diag__(ctx)
            if hasattr(xcvr, 'slot') and hasattr(xcvr.slot, 'getPresenceRaw'):
               entry['present'] = '%s/0x%x' % (entry['present'],
                                                xcvr.slot.getPresenceRaw())
            data.append(entry)
      return sorted(data, key=lambda x: x['id'])

   def renderText(self, show):
      data = self.data(show)

      Table([
         Col('Id', 'id', 3),
         Col('Type', 'xcvr.type', 9),
         Col('Present', 'present', 15),
         Col('LpMode', 'lpmode', 6),
         Col('Reset', 'reset.value', 6),
         Col('TxDisable', 'txdisable', 9),
         Col('TxFault', 'txfault', 7),
         Col('RxLos', 'rxlos', 5),
         Col('Addr', 'xcvr.addr', 7),
      ]).render(data)
