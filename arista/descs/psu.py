
from __future__ import absolute_import, division, print_function

from ..core.desc import HwDesc

class PsuDesc(HwDesc):
   def __init__(self, psuId=None, led=None, sensors=None, fans=None, **kwargs):
      super(PsuDesc, self).__init__(**kwargs)
      self.psuId = psuId
      self.led = led
      self.sensors = sensors or []
      self.fans = fans or []

   def setPsuId(self, psuId):
      self.psuId = psuId
      for sensor in self.sensors:
         sensor.renderName(psuId=psuId)
      for fan in self.fans:
         fan.renderName(psuId=psuId)
