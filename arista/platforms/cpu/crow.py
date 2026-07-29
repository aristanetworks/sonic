from ...core.cpu import Cpu
from ...core.driver.user.i2c import I2cDevDriver
from ...core.fan import FanSlot
from ...core.pci import PciPortDesc, PciRoot
from ...core.types import I2cAddr
from ...core.utils import incrange
from ...libs.i2c import i2cBusFromName

from ...components.cpu.amd.k10temp import K10Temp
from ...components.cpu.amd.piix import PiixI2cBus
from ...components.cpu.crow import (
   CrowCpldRegisters,
   CrowFanCpld,
   CrowSysCpld,
)
from ...components.dpm.ucd import Ucd90120A, UcdGpi, UcdPriority
from ...components.max6658 import Max6658

from ...descs.cause import ReloadCauseDesc
from ...descs.fan import FanDesc, FanPosition
from ...descs.led import LedDesc, LedColor
from ...descs.rail import RailDesc
from ...descs.sensor import Position, SensorDesc
from ...core.filters.ratelimit import RateLimitFilter

class CrowCpu(Cpu):

   PLATFORM = 'crow'

   PCI_PORT_ASIC0 = PciPortDesc(0x02, 1)
   PCI_PORT_SCD0 = PciPortDesc(0x02, 2)

   CPU_DPM_RAILS = (
      RailDesc(railId=1, name='POS12V standby'),
      RailDesc(railId=2, name='POS5V'),
      RailDesc(railId=3, name='POS3V3'),
      RailDesc(railId=4, name='POS1V8'),
      RailDesc(railId=5, name='POS1V5'),
      RailDesc(railId=6, name='POS1V35'),
      RailDesc(railId=7, name='POS0V67'),
      RailDesc(railId=8, name='POS0V95'),
      RailDesc(railId=9, name='POS1V8'),
      RailDesc(railId=10, name='POS3V3'),
      RailDesc(railId=11, name='POS0V95'),
      RailDesc(railId=12, name='POS1V2'),
   )

   CPU_DPM_1V5_SERIAL_PREFIX = 'SFT00284'

   def __init__(self, registerCls=CrowCpldRegisters, sysCpldCls=CrowSysCpld,
                **kwargs):
      super().__init__(**kwargs)

      self.pciRoot = self.newComponent(PciRoot)

      port = self.pciRoot.rootPort(device=0x18, func=3)
      port.newComponent(K10Temp, addr=port.addr, sensors=[
         SensorDesc(diode=0, name='Cpu temp sensor',
                    position=Position.OTHER, target=60, overheat=90, critical=95,
                    readFilter=RateLimitFilter(9.5)),
      ])

      bus = PiixI2cBus(1, 0x0b20)
      self.syscpld = self.newComponent(sysCpldCls, addr=bus.i2cAddr(0x23),
                                       registerCls=registerCls)
      self.syscpld.addPowerCycle()

   def addScdComponents(self, scd, hwmonBus=0):
      scd.newComponent(Max6658, addr=scd.i2cAddr(hwmonBus, 0x4c), sensors=[
         SensorDesc(diode=0, name='Cpu board temp sensor',
                    position=Position.OTHER, target=55, overheat=75, critical=80),
         SensorDesc(diode=1, name='Back-panel temp sensor',
                    position=Position.OUTLET, target=50, overheat=75, critical=85),
      ])

      cpld = scd.newComponent(CrowFanCpld, addr=scd.i2cAddr(hwmonBus, 0x60))
      for slotId in incrange(1, 4):
         fanDesc = FanDesc(fanId=slotId, position=FanPosition.INLET)
         ledDesc = LedDesc(name='fan%d' % slotId,
                           colors=[LedColor.RED, LedColor.GREEN, LedColor.OFF])
         self.newComponent(
            FanSlot,
            slotId=slotId,
            led=cpld.addFanLed(ledDesc),
            fans=[
               cpld.addFan(fanDesc),
            ]
         )

   def _getCpuDpmRailAltNames(self, scd, i2cBus):
      rail6 = self.CPU_DPM_RAILS[5].fmt
      rail7 = self.CPU_DPM_RAILS[6].fmt

      try:
         with I2cDevDriver(addr=I2cAddr(0, 0x51)) as driver:
            if driver.read_byte_data(0x06) == 0x00:
               return 'POS1V5', 'POS0V75'
      except (IOError, OSError):
         pass

      try:
         busName = scd.driver.getMasterNameForBus(i2cBus)
         busId = i2cBusFromName(busName, force=True)
         if busId is None:
            return rail6, rail7
         with I2cDevDriver(addr=I2cAddr(busId, 0x4e)) as driver:
            size = driver.read_byte_data(0x9e) + 1
            data = driver.read_i2c_block_data(0x9e, size)
         serial = ''.join(chr(x) for x in data[1:1 + data[0]])
         if serial.startswith(self.CPU_DPM_1V5_SERIAL_PREFIX):
            return 'POS1V5', 'POS0V75'
      except (IOError, OSError):
         pass

      return rail6, rail7

   def _getCpuDpmRails(self, scd, i2cBus):
      rail6, rail7 = self._getCpuDpmRailAltNames(scd, i2cBus)
      if (rail6, rail7) == (self.CPU_DPM_RAILS[5].fmt,
                            self.CPU_DPM_RAILS[6].fmt):
         return self.CPU_DPM_RAILS

      rails = list(self.CPU_DPM_RAILS)
      rails[5] = RailDesc(railId=6, name=rail6)
      rails[6] = RailDesc(railId=7, name=rail7)
      return tuple(rails)

   def addCpuDpm(self, scd, i2cBus, rails=None):
      rails = rails if rails is not None else self._getCpuDpmRails(scd, i2cBus)
      scd.newComponent(Ucd90120A, addr=scd.i2cAddr(i2cBus, 0x4e, t=3), causes=[
         UcdGpi(1, ReloadCauseDesc.CPU_S5),
         UcdGpi(2, ReloadCauseDesc.CPU_S3),
         # GPI3-7 skipped
         ], rails=rails,
         causePriority=UcdPriority.HARDWARE_SECONDARY)
