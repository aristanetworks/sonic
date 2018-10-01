from ..core.platform import registerPlatform, Platform
from ..core.driver import KernelDriver
from ..core.utils import incrange
from ..core.types import PciAddr, I2cAddr, NamedGpio, ResetGpio
from ..core.component import Priority

from ..components.common import SwitchChip, I2cKernelComponent
from ..components.scd import Scd

@registerPlatform('DCS-7260CX3-64')
class Gardena(Platform):
   def __init__(self):
      super(Gardena, self).__init__()

      self.sfpRange = incrange(65, 66)
      self.qsfpRange = incrange(1, 64)

      self.inventory.addPorts(qsfps=self.qsfpRange, sfps=self.sfpRange)

      self.addDriver(KernelDriver, 'rook-fan-cpld')
      self.addDriver(KernelDriver, 'rook-led-driver')

      switchChip = SwitchChip(PciAddr(bus=0x07))
      self.addComponent(switchChip)

      scd = Scd(PciAddr(bus=0x06))
      self.addComponent(scd)

      self.inventory.addWatchdog(scd.createWatchdog())

      scd.addComponents([
         I2cKernelComponent(scd.i2cAddr(0, 0x4c), 'max6658',
                            '/sys/class/hwmon/hwmon1'),
         I2cKernelComponent(scd.i2cAddr(2, 0x58), 'pmbus',
                            priority=Priority.BACKGROUND),
         I2cKernelComponent(scd.i2cAddr(3, 0x58), 'pmbus',
                            priority=Priority.BACKGROUND),
      ])

      scd.addSmbusMasterRange(0x8000, 8, 0x80)

      scd.addResets([
         ResetGpio(0x4000, 0, False, 'switch_chip_reset'),
         ResetGpio(0x4000, 1, False, 'switch_chip_pcie_reset'),
         ResetGpio(0x4000, 2, False, 'security_asic_reset'),
      ])

      scd.addGpios([
         NamedGpio(0x5000, 0, True, False, "psu1_present"),
         NamedGpio(0x5000, 1, True, False, "psu2_present"),
         NamedGpio(0x5000, 8, True, False, "psu1_status"),
         NamedGpio(0x5000, 9, True, False, "psu2_status"),
         NamedGpio(0x5000, 10, True, False, "psu1_ac_status"),
         NamedGpio(0x5000, 11, True, False, "psu2_ac_status"),
      ])
      self.inventory.addPsus([
         scd.createPsu(1),
         scd.createPsu(2),
      ])

      addr = 0x6100
      for xcvrId in self.qsfpRange:
         for laneId in incrange(1, 4):
            name = "qsfp%d_%d" % (xcvrId, laneId)
            scd.addLed(addr, name)
            self.inventory.addXcvrLed(xcvrId, name)
            addr += 0x10

      addr = 0x7100
      for xcvrId in self.sfpRange:
         name = "sfp%d" % xcvrId
         scd.addLed(addr, name)
         self.inventory.addXcvrLed(xcvrId, name)
         addr += 0x10

      intrRegs = [
         scd.createInterrupt(addr=0x3000, num=0),
         scd.createInterrupt(addr=0x3030, num=1),
         scd.createInterrupt(addr=0x3060, num=2),
      ]

      addr = 0xA010
      bus = 8
      for xcvrId in sorted(self.qsfpRange):
         intr = intrRegs[xcvrId // 33 + 1].getInterruptBit((xcvrId - 1) % 32)
         self.inventory.addInterrupt('qsfp%d' % xcvrId, intr)
         xcvr = scd.addQsfp(addr, xcvrId, bus, interruptLine=intr)
         self.inventory.addXcvr(xcvr)
         addr += 0x10
         bus += 1

      addr = 0xA410
      bus = 6
      for xcvrId in sorted(self.sfpRange):
         xcvr = scd.addSfp(addr, xcvrId, bus)
         self.inventory.addXcvr(xcvr)
         addr += 0x10
         bus += 1

      cpld = Scd(PciAddr(bus=0xff, device=0x0b, func=3), newDriver=True)
      self.addComponent(cpld)

      cpld.addSmbusMasterRange(0x8000, 4, 0x80, 4)
      cpld.addComponents([
         I2cKernelComponent(cpld.i2cAddr(0, 0x4c), 'max6658',
                            '/sys/class/hwmon/hwmon2'),
         # Handling of the DPM is disabled because this functionality is unstable.
         #I2cKernelComponent(I2cAddr(74, 0x4e), 'pmbus',
         #                   priority=Priority.BACKGROUND),
         I2cKernelComponent(cpld.i2cAddr(12, 0x60), 'rook_cpld',
                            '/sys/class/hwmon/hwmon3'),
         I2cKernelComponent(cpld.i2cAddr(15, 0x20), 'rook_leds'),
         I2cKernelComponent(cpld.i2cAddr(15, 0x48), 'lm73'),
      ])

      self.inventory.addPowerCycle(cpld.createPowerCycle())
