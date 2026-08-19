from ...core.cpu import Cpu
from ...core.pci import PciPortDesc, PciRoot

from ...components.scd import Scd, ScdSmbusDesc
from ...components.cpld import SysCpld

class MarconiCpu(Cpu):

   PLATFORM = 'marconi'
   SID = ['Marconi']

   PCI_PORT_ASIC0 = PciPortDesc(0x2, 0, bus=0x14)
   PCI_PORT_ASIC1 = PciPortDesc(0x3, 0, bus=0x14)
   PCI_PORT_SCD0 = PciPortDesc(0x13, 0)
   PCI_PORT_SCD1 = PciPortDesc(0x10, 0)

   SMBUS_SC = ScdSmbusDesc(1, 0)
   SMBUS_POL = ScdSmbusDesc(1, 1)
   SMBUS_PWR = ScdSmbusDesc(1, 2)
   SMBUS_FC = ScdSmbusDesc(1, 3)
   SMBUS_BMC = ScdSmbusDesc(0, 5)

   def __init__(self, **kwargs):
      super().__init__(**kwargs)

      self.pciRoot = self.newComponent(PciRoot)

      # TODO: add CPU and/or PCH temperature, likely from components.cpu.intel

      port = self.pciRoot.pciBridge(device=0x10, func=0).downstreamPort(0)
      self.cpld = cpld = port.newComponent(Scd, addr=port.addr)
      cpld.createPowerCycle()
      cpld.addSmbusMasterRange(0x8000, 1, 0x80, 6)
      cpld.addSmbusMasterRange(0x8080, 2, 0x80, 6)

      bus = self.getSmbus(self.SMBUS_SC)
      self.syscpld = cpld.newComponent(SysCpld, addr=bus.i2cAddr(0x23))
      # TODO: define the appropriate syscpld ideally on the platform side

      # TODO: everything related ot the BMC, will likely need a new subpackage
      # under arista.platforms.bmc and a new base definition under
      # arista.core.bmc
      # eeprom is at self.getSmbus(self.SMBUS_BMC).i2cAddr(0x52)

      # TODO: leak detection if it's managed by the CPU should have some bits
      # and pieces here

      # TODO: add smbus front panel temp sensor cpld/0/0/0x48

   def addCpuDpm(self):
      # TODO: add Ucd90320, cpld/0/1/0x31
      pass

   def getSmbus(self, desc):
      busPerMaster = next(iter(self.cpld.smbusMasters.values()))['bus']
      return self.cpld.getSmbus(desc.master * busPerMaster + desc.bus)
