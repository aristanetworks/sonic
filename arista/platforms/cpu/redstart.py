from ...core.cpu import Cpu
from ...core.driver.kernel.pci import PciKernelDriver
from ...core.pci import PciPortDesc, PciRoot
from ...core.platform import registerCpu
from ...core.prerequisites import loadPrerequisites

from ...components.cpu.amd.k10temp import K10Temp
from ...components.cpu.redstart import (
    RedstartReloadCauseRegisters,
    RedstartSysCpld,
)
from ...components.eeprom import At24C512
from ...components.pci import EcrcPciQuirk
from ...components.scd import (
    BlackBoxRegisterMap,
    Scd,
    ScdBlackBox,
    ScdCause,
    ScdSpiController
)

from ...descs.cause import ReloadCauseAltSource
from ...descs.sensor import Position, SensorDesc

@registerCpu()
class RedstartCpu(Cpu):

   PLATFORM = 'redstart'
   SID = ['Redstart8Mk2']
   SKU = ['DCS-7001-SUP-L']

   PCI_PORT_ASIC0 = PciPortDesc(0x1, 2, quirks=[EcrcPciQuirk()])
   PCI_PORT_ASIC1 = PciPortDesc(0x1, 3, quirks=[EcrcPciQuirk()])
   PCI_PORT_SCD0 = PciPortDesc(0x2, 5)
   PCI_PORT_SCD1 = PciPortDesc(0x2, 3)
   PCI_PORT_SCD2 = PciPortDesc(0x2, 4)
   PCI_PORT_SCD3 = PciPortDesc(0x2, 6)

   SMBUS_SC = 6
   SMBUS_POL = 7
   SMBUS_PWR = 8
   SMBUS_FC = 9

   @staticmethod
   def _createCpld(pciRoot):
      cpldPort = pciRoot.pciBridge(device=0x02, func=1).downstreamPort(0)
      cpld = cpldPort.newComponent(Scd, addr=cpldPort.addr)
      cpld.addSmbusMasterRange(0x8000, 1, 0x80, 6)
      return cpld

   @classmethod
   def _addSwitchEeprom(cls, cpld):
      return cpld.newComponent(
         At24C512,
         addr=cpld.i2cAddr(cls.SMBUS_SC, 0x50),
         hdrSz=0,
         label='switch',
      )

   def __init__(self, syscpldCls=RedstartSysCpld, **kwargs):
      super().__init__(**kwargs)

      self.pciRoot = self.newComponent(PciRoot)

      port = self.pciRoot.rootPort(device=0x18, func=3)
      port.newComponent(K10Temp, addr=port.addr, sensors=[
         SensorDesc(diode=0, name='Cpu temp sensor',
                    position=Position.OTHER, target=70, overheat=95, critical=115),
      ])

      cpld = self._createCpld(self.pciRoot)
      self.cpld = cpld

      cpld.createPowerCycle()
      self.switchEeprom = self._addSwitchEeprom(cpld)
      cpld.addLeds([
          (0x6050, 'cpu_status'),
      ])


      self.fanboard = self.parent.CHASSIS.addFanboard(cpld,
                                                      cpld.getSmbus(self.SMBUS_FC))

      self.syscpld = cpld.newComponent(syscpldCls,
                                       addr=cpld.i2cAddr(self.SMBUS_SC, 0x23))

      bbCtrl = cpld.newComponent(
          ScdSpiController,
          addr=0x1100,
          stride=0x100,
          numCs=2
      )
      bbCtrl.newComponent(
          ScdBlackBox,
          addr=bbCtrl.spiAddr(cs=1),
          ctrl=BlackBoxRegisterMap(cpld.driver, cmd=0x1100),
          bufSplit=0x6000,
      )

      cpld.addReloadCauseProvider(causes=[
         ScdCause(0x01, ScdCause.OVERTEMP),
         ScdCause(0x08, ScdCause.REBOOT, 'Software Reboot'),
         ScdCause(0x0a, ScdCause.POWERLOSS, 'PSU DC to CPU'),
         ScdCause(0x0c, ScdCause.CPU),
         ScdCause(0x0d, ScdCause.CPU_S3, 'CPU Sleep Mode'),
         ScdCause(0x12, ScdCause.SUP_UNSEATED),
         ScdCause(0x20, ScdCause.RAIL, 'VR_VDDCR_FAULT'),
         ScdCause(0x21, ScdCause.RAIL, 'VR_VDDSOC_FAULT'),
         ScdCause(0x22, ScdCause.RAIL, 'DDR5_SODIMM2_FAULT'),
         ScdCause(0x23, ScdCause.RAIL, 'DDR5_SODIMM1_FAULT'),
         ScdCause(0x24, ScdCause.RAIL, 'P1V8_CPU_FAULT'),
         ScdCause(0x28, ScdCause.RAIL, 'P3V3_CPU_FAULT'),
         ScdCause(0x29, ScdCause.RAIL, 'P3V3_RGMII_FAULT'),
         ScdCause(0x2a, ScdCause.RAIL, 'POS1V1_MEM_FAULT'),
         ScdCause(0x2b, ScdCause.RAIL, 'POS0V78_MEM_FAULT'),
         ScdCause(0x2c, ScdCause.RAIL, 'POS5V_ALW_FAULT'),
         ScdCause(0x2d, ScdCause.RAIL, 'POS1V8_BMC_FAULT'),
         ScdCause(0x2e, ScdCause.RAIL, 'POS3V3_BMC_FAULT'),
         ScdCause(0x31, ScdCause.RAIL, 'POS1V2_BMC_FAULT'),
         ScdCause(0x32, ScdCause.RAIL, 'POS2V5_BMC_FAULT'),
         ScdCause(0x33, ScdCause.RAIL, 'POS0V75_CPU_FAULT'),
         ScdCause(0x34, ScdCause.RAIL, 'POS1V8_ALW_FAULT'),
         ScdCause(0x35, ScdCause.RAIL, 'POS1V0_MSW_FAULT'),
         ScdCause(0x36, ScdCause.RAIL, 'POS1V2_FAULT'),
         ScdCause(0x37, ScdCause.RAIL, 'POS2V5_CPLD_FAULT'),
         ScdCause(0x38, ScdCause.RAIL, 'POS0V75_ALW_FAULT'),
         ScdCause(0x39, ScdCause.RAIL, 'POS0V96_I226_FAULT'),
         ScdCause(0x3a, ScdCause.RAIL, 'APU_PWROK_FAULT'),
         ScdCause(0x3b, ScdCause.RAIL, 'POS3V3_ALW_FAULT'),
         ScdCause(0x3c, ScdCause.CPU, 'CPU ERROR_N'),
         ScdCause(0x3d, ScdCause.RAIL, 'BMC_PGOOD_FAULT'),
         ScdCause(0x3e, ScdCause.CPU, 'Bios SMN init timeout'),
      ], regmap=RedstartReloadCauseRegisters,
         priority=ScdCause.Priority.HARDWARE_SECONDARY,
         altSource=[ReloadCauseAltSource.CPU])

   @classmethod
   def readSwitchEeprom(cls):
      pciRoot = PciRoot()
      cpld = cls._createCpld(pciRoot)
      switchEeprom = cls._addSwitchEeprom(cpld)

      scdDriver = cpld.driver
      PciKernelDriver.setup(scdDriver)
      loadPrerequisites()

      scdDriver.setupSmbusMasters()
      switchEeprom.driver.setup()
      return switchEeprom.readPrefdl()

   def getPciPort(self, desc):
      bridge = self.pciRoot.pciBridge(device=desc.device, func=desc.func)
      desc.maybeAddQuirks(bridge.upstream)
      return bridge.downstreamPort(port=desc.port)

   def getSmbus(self, desc):
      return self.cpld.getSmbus(desc)
