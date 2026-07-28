from ...core.bmc import BmcHostCpu, registerHostCpu
from ...core.liquid import LeakDetectionInterfaceV1, LeakSensorType
from ...components.cpld import SysCpld
from ...components.cpu.marconi import MarconiCpldRegisters
from ...descs.liquid import LeakSensorDesc, LiquidCoolingDesc

@registerHostCpu()
class MarconiHostCpu(BmcHostCpu):
   SID = ['Marconi', 'SteamerLaneMv3']

   def __init__(self, *args, **kwargs):
      super().__init__(*args, **kwargs)
      self.cpld = self.newComponent(SysCpld,
                                    addr=self.parent.cpuCpldAddr(),
                                    registerCls=MarconiCpldRegisters)

      # TODO: update locations.
      self.cpld.addLiquidCooling(
         LiquidCoolingDesc(LeakDetectionInterfaceV1, sensors=[
            LeakSensorDesc(name="trayLeak", sensorType=LeakSensorType.ROPE_MAJOR,
                           addr=0, location="drip tray"),
            LeakSensorDesc(name="smallLeak", sensorType=LeakSensorType.ROPE_MINOR,
                           addr=0, location="unspecified"),
         ])
      )
