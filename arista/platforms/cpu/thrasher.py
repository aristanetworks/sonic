from ...core.cpu import Cpu
from ...core.pci import PciPortDesc, PciRoot

from ...components.cpu.amd.designware import DesignWareI2cBus
from ...components.cpu.amd.k10temp import K10Temp
from ...components.cpu.thrasher import (
   ThrasherSysCpld,
   CpuScdPowerCycleOnWdFaultQuirk,
)

from ...components.dpm.adm1266 import (
   Adm1266,
   AdmCauseUnique,
   AdmGpio,
   AdmPdio,
   AdmPriority,
   maxV,
   minV
)
from ...components.scd import Scd
from ...components.lm75 import Tmp75

from ...descs.cause import ReloadCauseAltSource
from ...descs.sensor import Position, SensorDesc
from ...descs.rail import RailDesc

class ThrasherCpu(Cpu):

   PLATFORM = 'thrasher'
   SID = ['Thrasher', 'ThrasherB']
   SKU = ['DCS-7004-SUP-A']

   PREFDL_EEPROM_BUS = DesignWareI2cBus(0)

   PCI_PORT_ASIC0 = PciPortDesc(0x1, 2)
   PCI_PORT_ASIC1 = PciPortDesc(0x1, 3)
   PCI_PORT_SCD0 = PciPortDesc(0x2, 3)
   PCI_PORT_SCD1 = PciPortDesc(0x2, 4)

   SMBUS_SC = 8
   SMBUS_POL = 9
   SMBUS_PWR = 10
   SMBUS_FC = 11

   def __init__(self, **kwargs):
      super().__init__(**kwargs)

      self.pciRoot = self.newComponent(PciRoot)

      port = self.pciRoot.rootPort(device=0x18, func=3)
      port.newComponent(K10Temp, addr=port.addr, sensors=[
         SensorDesc(diode=0, name='Cpu',
                    position=Position.OTHER, target=80, overheat=95, critical=105),
      ])

      port = self.pciRoot.pciBridge(device=0x02, func=1).downstreamPort(0)
      cpld = port.newComponent(Scd, addr=port.addr)
      self.cpld = cpld

      cpld.createPowerCycle()
      cpld.addSmbusMasterRange(0x8000, 1, 0x80)

      gpioInMask = 0b000111000
      pdioInMask = 0b0010011010110000

      causeKwargs = {
         'gpioInMask': gpioInMask,
         'pdioInMask': pdioInMask,
         'pdioActiveLowMask': pdioInMask,
      }

      cpld.newComponent(Adm1266, addr=cpld.i2cAddr(6, 0x4f, block=False),
         causes=[
            AdmCauseUnique(AdmCauseUnique.SUP_UNSEATED, AdmGpio(4),
                           **causeKwargs),
            AdmCauseUnique(AdmCauseUnique.CPU, AdmGpio(5),
                           description='CPU ECB Power Cycle',
                           **causeKwargs),
            AdmCauseUnique(AdmCauseUnique.REBOOT,
                           AdmGpio.fromPins(4, 5),
                           description='CPLD ECB Power Cycle',
                           **causeKwargs),
            AdmCauseUnique(AdmCauseUnique.CPU, AdmGpio(6),
                           description='CPU PSU Power Cycle',
                           **causeKwargs),
            AdmCauseUnique(AdmCauseUnique.REBOOT,
                           AdmGpio.fromPins(4, 6),
                           description='CPLD PSU Power Cycle',
                           **causeKwargs),
            AdmCauseUnique(AdmCauseUnique.RAIL, AdmPdio(5),
                           description="Core Rail PGOOD", **causeKwargs),
            AdmCauseUnique(AdmCauseUnique.RAIL, AdmPdio(6),
                           description="SOC Rail PGOOD", **causeKwargs),
            AdmCauseUnique(AdmCauseUnique.CPU, AdmPdio(8),
                           description="APU Power OK", **causeKwargs),
            AdmCauseUnique(AdmCauseUnique.CPU_S3, AdmPdio(10), **causeKwargs),
            AdmCauseUnique(AdmCauseUnique.CPU_S5, AdmPdio(11), **causeKwargs),
            AdmCauseUnique(AdmCauseUnique.CPU_OVERTEMP, AdmPdio(14),
                           description="APU Thermal Trip", **causeKwargs),
         ], causePriority=AdmPriority.HARDWARE_SECONDARY,
         altSource=[ReloadCauseAltSource.CPU],
         rails=[
            RailDesc(railId=Adm1266.VH1, name="POS12V",
                     maxVoltage=12.0, minVoltage=12.0),
            RailDesc(railId=Adm1266.VH2, name="POS5V_ALW",
                     maxVoltage=maxV(5, 4), minVoltage=minV(5, 4)),
            RailDesc(railId=Adm1266.VH3, name="POS3V3_ALW",
                     maxVoltage=maxV(3, 4), minVoltage=minV(3, 4)),
            RailDesc(railId=Adm1266.VH4, name="POS1V8_ALW",
                     maxVoltage=maxV(1.8, 3), minVoltage=minV(1.8, 3)),
            RailDesc(railId=Adm1266.VP1, name="POS0V75_ALW",
                     maxVoltage=maxV(0.75, 3), minVoltage=minV(0.75, 3)),
            RailDesc(railId=Adm1266.VP2, name="POS1V2_CPLD",
                     maxVoltage=maxV(1.2, 4), minVoltage=minV(1.2, 4)),
            RailDesc(railId=Adm1266.VP3, name="POS2V5_CPLD",
                     maxVoltage=maxV(2.5, 4), minVoltage=minV(2.5, 4)),
            RailDesc(railId=Adm1266.VP4, name="POS1V0_MSW",
                     maxVoltage=maxV(1, 4), minVoltage=minV(1, 4)),
            RailDesc(railId=Adm1266.VP5, name="BMC_1V0",
                     maxVoltage=1.0, minVoltage=1.0),
            RailDesc(railId=Adm1266.VP6, name="POS1V1_MEM",
                     maxVoltage=maxV(1.1, 3), minVoltage=minV(1.1, 3)),
            RailDesc(railId=Adm1266.VP7, name="POS1V8_CPU",
                     maxVoltage=maxV(1.8, 4), minVoltage=minV(1.8, 4)),
            RailDesc(railId=Adm1266.VP8, name="POS3V3_CPU",
                     maxVoltage=maxV(3.3, 4), minVoltage=minV(3.3, 4)),
            RailDesc(railId=Adm1266.VP9, name="POS0V75_CPU",
                     maxVoltage=maxV(0.75, 3), minVoltage=minV(0.75, 3)),
            RailDesc(railId=Adm1266.VP10, name="POS0V78_MEM",
                     maxVoltage=maxV(0.78, 4), minVoltage=minV(0.78, 4)),
            RailDesc(railId=Adm1266.VP11, name="POS1V27_MPHY",
                     maxVoltage=1.27, minVoltage=1.27),
            RailDesc(railId=Adm1266.VP12, name="APU_VDDCR",
                     maxVoltage=1.55, minVoltage=0.6),
            RailDesc(railId=Adm1266.VP13, name="APU_VDDCR_SOC",
                     maxVoltage=1.2, minVoltage=0.6),
         ])

      cpld.newComponent(Tmp75, addr=cpld.i2cAddr(0, 0x48), sensors=[
         SensorDesc(diode=0, name='Primary Inlet Sensor',
                    position=Position.INLET, target=65, overheat=70, critical=75),
      ])

      cpld.addLeds([
         (0x6050, 'status'),
         (0x6060, 'fan_status'),
         (0x6070, 'psu_status'),
         (0x6090, 'scm_status'),
      ])

      self.fanboard = self.parent.CHASSIS.addFanboard(
          cpld,
          self.getSmbus(self.SMBUS_FC)
      )

      self.syscpld = cpld.newComponent(ThrasherSysCpld, addr=cpld.i2cAddr(8, 0x23),
                                       quirks=[CpuScdPowerCycleOnWdFaultQuirk()])

   def getSmbus(self, desc):
      return self.cpld.getSmbus(desc)
