from ...core.cpu import Cpu
from ...core.pci import PciPortDesc, PciRoot

from ...components.cpu.amd.k10temp import K10Temp
from ...components.dpm.ucd import Ucd90320, UcdGpi, UcdPriority
from ...components.lm75 import Tmp75
from ...components.scd import (
   Scd,
   ScdCause,
   ScdReloadCauseRegisters,
   ScdSmbusDesc
)
from ...components.vrm.tda38740 import Xdpe1e496b

from ...descs.cause import (
   ReloadCauseAltSource,
   ReloadCauseDesc,
   ReloadCausePriority,
)
from ...descs.led import LedDesc, LedKind
from ...descs.sensor import Position, SensorDesc

class MarconiCpu(Cpu):

   PLATFORM = 'marconi'
   SID = ['Marconi']

   PCI_PORT_ASIC0 = PciPortDesc(0x1, 3)
   PCI_PORT_ASIC1 = PciPortDesc(0x1, 5)
   PCI_PORT_SCD0 = PciPortDesc(0x3, 2)
   PCI_PORT_SCD1 = PciPortDesc(0x3, 5)

   SMBUS_FP = ScdSmbusDesc(0, 0)
   SMBUS_CPU_POL = ScdSmbusDesc(0, 1)
   SMBUS_CPU_PWR = ScdSmbusDesc(0, 2)
   SMBUS_BMC = ScdSmbusDesc(0, 5)
   SMBUS_CPU_TMP = ScdSmbusDesc(0, 6)

   SMBUS_SC = ScdSmbusDesc(1, 0)
   SMBUS_POL = ScdSmbusDesc(1, 1)
   SMBUS_PWR = ScdSmbusDesc(1, 2)
   SMBUS_FC = ScdSmbusDesc(1, 3)

   def __init__(self, **kwargs):
      super().__init__(cookiesPriority=ReloadCausePriority.PREREBOOT, **kwargs)

      self.pciRoot = self.newComponent(PciRoot)
      port = self.pciRoot.rootPort(device=0x18, func=3)
      port.newComponent(
         K10Temp,
         addr=port.addr,
         sensors=[
            SensorDesc(diode=0, name='CPU internal', position=Position.OTHER,
                       target=81, overheat=100, critical=105),
         ]
      )

      cpldPort = self.pciRoot.pciBridge(device=0x2, func=2).downstreamPort(0)
      self.cpld = cpldPort.newComponent(Scd, addr=cpldPort.addr)
      # In BMC mode, writing 0xDE00 will power cycle the liquid cooled
      # domain (CPU + SWC). In CPU mode, writing 0xDE00 will power cycle the
      # entire chassis.
      self.cpld.createPowerCycle(wr=0xDE00)
      self.cpld.addSmbusMasterRange(0x8000, 2, 0x80, 7)
      self.cpld.createInterrupt(addr=0x3000, num=0)
      self.cpld.addLeds([
         LedDesc(
            name=name,
            addr=addr,
            **LedKind.desc(LedKind.RGB_8_F),
         ) for name, addr in [
            ('status', 0x6050),
            ('fan_status', 0x6060), # Only used on air cooled products
            ('psu_status', 0x6070),
            ('scm_status', 0x6090),
         ]
      ])
      self.cpld.addReloadCauseProvider(
         causes=[
            ScdCause(0x01, ScdCause.OVERTEMP),
            ScdCause(0x05, ScdCause.SWITCH_CARD),
            ScdCause(0x08, ScdCause.REBOOT, 'Software Reboot'),
            ScdCause(0x09, ScdCause.POWERLOSS, 'DC to CPU'),
            ScdCause(0x0b, ScdCause.NO_FANS), # Only used if air cooled
            ScdCause(0x0c, ScdCause.CPU_CATERR),
            ScdCause(0x0d, ScdCause.CPU_S3),
            ScdCause(0x0e, ScdCause.CPU_S5),
            ScdCause(0x0f, ScdCause.SEU, 'bitshadow rx parity error'),
            ScdCause(0x11, ScdCause.SWITCH_CARD, 'switch-card unseated'),
            ScdCause(0x15, ScdCause.LEAK_ROPE_FAIL),
            ScdCause(0x16, ScdCause.LEAK_DETECTED),
         ],
         regmap=ScdReloadCauseRegisters,
         priority=ScdCause.Priority.HARDWARE_SECONDARY,
         altSource=[ReloadCauseAltSource.CPU]
      )

      # TODO: leak detection registers on CPU CPLD

      # TODO: everything related ot the BMC, will likely need a new subpackage
      # under arista.platforms.bmc and a new base definition under
      # arista.core.bmc
      # eeprom is at self.getSmbus(self.SMBUS_BMC).i2cAddr(0x52)

      cpuPwrBus = self.getSmbus(self.SMBUS_CPU_PWR)
      vrmTempParams = {'target': 85, 'overheat': 100, 'critical': 125}
      vrmRails = [
         'POS1V1_MEM',
         'POS0V8_VDDCR',
         'POS0V8_VDDMISC',
         'POS0V8_VDDSOC',
      ]
      self.cpld.newComponent(
         Xdpe1e496b,
         addr=cpuPwrBus.i2cAddr(0x68),
         sensors=[
            SensorDesc(
             diode=diodeId,
             name='CPU VRM %s' % name,
             position=Position.OTHER,
             **vrmTempParams) for diodeId, name in enumerate(vrmRails)
      ])

      # TODO: Add power rails and temp sensor
      cpuPolBus = self.getSmbus(self.SMBUS_CPU_POL)
      self.cpld.newComponent(
         Ucd90320,
         addr=cpuPolBus.i2cAddr(0x31),
         causes=[
            UcdGpi(4, ReloadCauseDesc.POWERLOSS, 'P48 ECB enable'),
            UcdGpi(5, ReloadCauseDesc.CPU_S3),
            UcdGpi(6, ReloadCauseDesc.CPU_S5),
            UcdGpi(7, ReloadCauseDesc.CPU, 'APU power loss'),
            UcdGpi(8, ReloadCauseDesc.REBOOT, 'CPLD pre-power cycle'),
            UcdGpi(9, ReloadCauseDesc.REBOOT, 'CPLD power cycle'),
            UcdGpi(10, ReloadCauseDesc.OVERTEMP, 'CPU'),
            UcdGpi(11, ReloadCauseDesc.CPU, 'Platform reset'),
            UcdGpi(12, ReloadCauseDesc.CPU, 'CPU requested full power cycle'),
            UcdGpi(13, ReloadCauseDesc.CPU, 'APU warm reset'),
            UcdGpi(14, ReloadCauseDesc.SWITCH_CARD, 'Switch card power loss'),
            UcdGpi(15, ReloadCauseDesc.OVERTEMP),
            UcdGpi(16, ReloadCauseDesc.REBOOT, 'Power cycled by BMC'),
            UcdGpi(17, ReloadCauseDesc.CPU_OVERTEMP, 'PROCHOT'),
            UcdGpi(18, ReloadCauseDesc.SWITCH_CARD, 'Switch card power cycle'),
            UcdGpi(19, ReloadCauseDesc.REBOOT, 'Powered off by BMC'),
            UcdGpi(20, ReloadCauseDesc.RAIL, 'DDR5 SODIMM power loss'),
            UcdGpi(21, ReloadCauseDesc.REBOOT, 'Rebooted by CPU'),
         ],
         causePriority=UcdPriority.HARDWARE_SECONDARY,
         altSource=[ReloadCauseAltSource.CPU]
      )

      # Front panel shim board
      fpBus = self.getSmbus(self.SMBUS_FP)
      self.cpld.newComponent(
         Tmp75,
         addr=fpBus.i2cAddr(0x48),
         sensors=[
            SensorDesc(diode=0, name='Front panel', position=Position.INLET,
                       target=85, overheat=90, critical=95),
         ]
      )
      # CPU board ambient
      cpuTmpBus = self.getSmbus(self.SMBUS_CPU_TMP)
      self.cpld.newComponent(
         Tmp75,
         addr=cpuTmpBus.i2cAddr(0x49),
         sensors=[
            SensorDesc(diode=0, name='Ambient', position=Position.INLET,
                       target=55, overheat=65, critical=70),
         ]
      )

   def getSmbus(self, desc):
      busPerMaster = next(iter(self.cpld.smbusMasters.values()))['bus']
      return self.cpld.getSmbus(desc.master * busPerMaster + desc.bus)
