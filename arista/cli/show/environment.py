
from ...core.diag import DiagContext

from . import Renderer, Table, Col

class ShowEnvironment(Renderer):

   NAME = 'environment'

   def getData(self, show):
      ctx = DiagContext()
      data = {
         'fans': [],
         'temps': [],
         'psuSlots': [],
      }
      for inventory, _ in show.inventories:
         for temp in inventory.getTemps():
            data['temps'].append(temp.__diag__(ctx))
         for fan in inventory.getFans():
            data['fans'].append(fan.__diag__(ctx))
         for slot in inventory.getPsuSlots():
            data['psuSlots'].append(slot.__diag__(ctx))
      return data

   def renderText(self, show):
      data = self.data(show)

      Table([
         Col('Name', 'name', 40),
         Col('Temp', 'value', 8),
         Col('Alert', 'highThresh', 8),
         Col('Critical', 'highCritThresh', 8),
      ]).render(data['temps'], newline=True)

      Table([
         Col('Name', 'name', 10),
         Col('Model', 'model', 15),
         Col('Status', 'status', 6),
         Col('Speed', 'speed', 5),
         Col('Rpm', 'rpm', 5)
      ]).render(data['fans'], newline=True)

      Table([
         Col('Name', 'name', 10),
         Col('Model', 'psu.model', 19),
         Col('Serial', 'psu.serial', 15),
         Col('Power', 'psu.rails.0.power', 7),
         Col('Max', 'psu.capacity', 5),
         Col('Status', 'status', 6),
      ]).render(data['psuSlots'])
