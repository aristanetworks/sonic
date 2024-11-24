
from .component.component import Component
from .hwapi import HwApi
from .port import PortLayout

class Sku(Component):

   PLATFORM = None
   SID = None
   SKU = None

   DEFAULT_HWAPI = (0, 0)

   PORTS = PortLayout()

   MAX_POWER_DRAW = 0
   TYP_POWER_DRAW = 0

   LED_FP_TRICOLOR = False

   def __init__(self, *args, **kwargs):
      self.hwApi = kwargs.pop('hwApi', None)
      super(Sku, self).__init__(*args, **kwargs)

   def getEeprom(self):
      return {}

   def getPresence(self):
      return True

   def poweredOn(self):
      return True

   def getHwApi(self):
      if not self.hwApi:
         self.hwApi = HwApi(*self.getEeprom().get('HwApi', self.DEFAULT_HWAPI))
      return self.hwApi

   def genDiag(self, ctx):
      output = super(Sku, self).genDiag(ctx)
      output['eeprom'] = self.getEeprom() if ctx.performIo else None
      return output
