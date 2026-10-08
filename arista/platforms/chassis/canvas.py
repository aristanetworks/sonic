from ...core.fixed import FixedChassis

from ...components.rundle import Rundle

class Canvas(FixedChassis):
   FAN_SLOTS = 8
   FAN_COUNT = 8
   FAN_MAX_POWER_DRAW = 190
   PSU_SLOTS = 4
   HEIGHT_RU = 4

   @classmethod
   def addFanboard(cls, parent, bus):
      return Rundle(parent, bus, fanMaxPowerDraw=cls.FAN_MAX_POWER_DRAW)
