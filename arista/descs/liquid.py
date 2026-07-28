from typing import List

from ..core.desc import HwDesc
from ..core.liquid import LeakDetectionInterface, LeakSensorType

class LeakSensorDesc(HwDesc):
   def __init__(self, *, name: str, sensorType: LeakSensorType, addr: int,
                location: str, **kwargs):
      super().__init__(**kwargs)
      self.name = name
      self.location = location
      self.sensorType = sensorType
      self.addr = addr

class LiquidCoolingDesc(HwDesc):
   def __init__(self, interface: type[LeakDetectionInterface], *,
                sensors: List[LeakSensorDesc], **kwargs):
      super().__init__(**kwargs)
      self.interface = interface
      self.sensors = sensors
