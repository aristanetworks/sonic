
from ...core.diag import DiagContext

from . import Renderer, List, Row

class ShowBlackBox(Renderer):

   NAME = 'blackbox'

   def getData(self, show):
      ctx = DiagContext()
      data = []
      for platform in show.platforms:
         for blackbox in platform.getInventory().getBlackBox():
            data.append(blackbox.__diag__(ctx))
      return data

   def renderText(self, show):
      data = self.data(show)

      List("BlackBox:", header=("%s", 'component'), tree=[
         Row('Enabled: %r', 'enabled'),
         Row('Version: %d', 'version'),
      ]).render(data)
