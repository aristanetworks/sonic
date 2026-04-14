
from typing import Optional
from ..core.desc import HwDesc
from ..core.filters.filter_api import Filter

class Position(object):
   INLET = 'inlet'
   OUTLET = 'outlet'
   OTHER = 'other'

class SensorDesc(HwDesc):

   OID_FIELD = 'diode'

   def __init__(self, diode, name=None, position=Position.OTHER,
                target=0., overheat=0., critical=0.,
                low=0.0, lcritical=-5.0, readFilter: Optional[Filter]=None,
                scale=1., offset=0.,
                **kwargs):
      super(SensorDesc, self).__init__(**kwargs)
      self.diode = diode
      self.fmt = name
      self.name = name
      self.position = position
      self.target = float(target)
      self.overheat = float(overheat)
      self.critical = float(critical)
      self.low = float(low)
      self.lcritical = float(lcritical)
      self.filter = readFilter
      self.scale = float(scale)
      self.offset = float(offset)

   def renderName(self, **kwargs):
      values = kwargs.copy()
      values.update(self.__dict__)
      self.name = self.fmt % values

   @classmethod
   def __oid2lid__(cls, oid):
      return oid - 1

   @classmethod
   def __lid2oid__(cls, lid):
      return lid + 1
