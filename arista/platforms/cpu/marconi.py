from ...core.cpu import Cpu
from ...core.pci import PciPortDesc, PciRoot

from ...components.cpld import SysCpld
from ...components.cpu.amd.k10temp import K10Temp
from ...components.dpm.ucd import Ucd90320, UcdGpi, UcdPriority
from ...components.lm75 import Tmp75
from ...components.scd import Scd, ScdSmbusDesc
from ...components.vrm.tda38740 import Xdpe1e496b

from ...descs.cause import ReloadCauseDesc
from ...descs.led import LedDesc, LedKind
from ...descs.sensor import Position, SensorDesc

class MarconiCpu(Cpu):

   PLATFORM = 'marconi'
   SID = ['Marconi']

   PCI_PORT_ASIC0 = PciPortDesc(0x1, 3)
   PCI_PORT_ASIC1 = PciPortDesc(0x1, 5)
   PCI_PORT_SCD0 = PciPortDesc(0x3, 2)
   PCI_PORT_SCD1 = PciPortDesc(0x3, 5)

   SMBUS_BMC = ScdSmbusDesc(0, 5)
   SMBUS_SC = ScdSmbusDesc(1, 0)
   SMBUS_POL = ScdSmbusDesc(1, 1)
   SMBUS_PWR = ScdSmbusDesc(1, 2)
   SMBUS_FC = ScdSmbusDesc(1, 3)

   def __init__(self, **kwargs):
      super().__init__(**kwargs)

      self.pciRoot = self.newComponent(PciRoot)
      port = self.pciRoot.rootPort(device=0x18, func=3)
      port.newComponent(
         K10Temp,
         addr=port.addr,
         sensors=[
            SensorDesc(diode=0, name='CPU internal', position=Position.OTHER,
                       target=80, overheat=100, critical=105),
         ]
      )

      cpldPort = self.pciRoot.pciBridge(device=0x2, func=2).downstreamPort(0)
      self.cpld = cpldPort.newComponent(Scd, addr=cpldPort.addr)
      self.cpld.createPowerCycle()
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

      bus = self.getSmbus(self.SMBUS_SC)
      self.syscpld = self.cpld.newComponent(SysCpld, addr=bus.i2cAddr(0x23))
      # TODO: define the appropriate syscpld ideally on the platform side

      # TODO: everything related ot the BMC, will likely need a new subpackage
      # under arista.platforms.bmc and a new base definition under
      # arista.core.bmc
      # eeprom is at self.getSmbus(self.SMBUS_BMC).i2cAddr(0x52)

      # TODO: leak detection if it's managed by the CPU should have some bits
      # and pieces here

      # VRM
      vrmTempParams = {'target': 85, 'overheat': 100, 'critical': 125}
      vrmRails = [
         'POS1V1_MEM',
         'POS0V8_VDDCR',
         'POS0V8_VDDMISC',
         'POS0V8_VDDSOC',
      ]
      self.cpld.newComponent(
         Xdpe1e496b,
         addr=self.cpld.i2cAddr(2, 0x68),
         sensors=[
            SensorDesc(
             diode=diodeId,
             name='CPU VRM %s' % name,
             position=Position.OTHER,
             **vrmTempParams) for diodeId, name in enumerate(vrmRails)
      ])

      # TODO: Add power rails and temp sensor
      self.cpld.newComponent(
         Ucd90320,
         addr=self.cpld.i2cAddr(1, 0x31),
         causes=[
            # TODO: update reload cause list
            UcdGpi(6, ReloadCauseDesc.OVERTEMP),
            UcdGpi(7, ReloadCauseDesc.CPU, priority=UcdPriority.LOW),
      ])

      # Front panel shim board
      self.cpld.newComponent(
         Tmp75,
         addr=self.cpld.i2cAddr(0, 0x48),
         sensors=[
            SensorDesc(diode=0, name='Front panel', position=Position.INLET,
                       target=55, overheat=65, critical=70),
         ]
      )
      # CPU board ambient
      self.cpld.newComponent(
         Tmp75,
         addr=self.cpld.i2cAddr(6, 0x49),
         sensors=[
            SensorDesc(diode=0, name='Ambient', position=Position.INLET,
                       target=55, overheat=65, critical=70),
         ]
      )

   def getSmbus(self, desc):
      busPerMaster = next(iter(self.cpld.smbusMasters.values()))['bus']
      return self.cpld.getSmbus(desc.master * busPerMaster + desc.bus)
