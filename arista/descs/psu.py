
from enum import Enum

from ..core.desc import HwDesc

class PsuStatusPolicy(Enum):
   PMBUS_STATUS = 1
   GPIO_OR_PMBUS_POWER = 2

class PsuDesc(HwDesc):

   OID_FIELD = 'psuId'

   def __init__(self, psuId=None, led=None, sensors=None, fans=None, rails=None,
                **kwargs):
      super(PsuDesc, self).__init__(**kwargs)
      self.psuId = psuId
      self.led = led
      self.sensors = sensors or []
      self.fans = fans or []
      self.rails = rails or []

   def setPsuId(self, psuId):
      self.psuId = psuId
      for sensor in self.sensors:
         sensor.renderName(psuId=psuId)
      for fan in self.fans:
         fan.renderName(psuId=psuId)
      for rail in self.rails:
         rail.renderName(psuId=psuId)

   def setAirflow(self, airflow):
      for fan in self.fans:
          fan.airflow = airflow
