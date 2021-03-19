
from __future__ import absolute_import, division, print_function

from ..core.desc import HwDesc
from ..core.cooling import Airflow

class FanPosition(object):
   UNKNOWN = 'unknown'
   INLET = 'inlet'
   OUTLET = 'outlet'

class FanDesc(HwDesc):
   def __init__(self, fanId, name='fan%(fanId)s', position=FanPosition.UNKNOWN,
                airflow=Airflow.UNKNOWN, ledId=None, **kwargs):
      super(FanDesc, self).__init__(**kwargs)
      self.fmt = name
      self.name = None
      self.fanId = fanId
      self.ledId = ledId
      self.position = position
      self.airflow = airflow

   def renderName(self, **kwargs):
      values = kwargs.copy()
      values.update(self.__dict__)
      self.name = self.fmt % values

class FanSlotDesc(HwDesc):
   def __init__(self, slotId, name=None, fans=None, ledId=None, **kwargs):
      super(FanSlotDesc, self).__init__(**kwargs)
      self.slotId = slotId
      self.name = name
      self.fans = fans
