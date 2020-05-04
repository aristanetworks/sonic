from ..core.fixed import FixedSystem
from ..core.platform import registerPlatform
from ..core.types import PciAddr, I2cAddr, NamedGpio, ResetGpio
from ..core.utils import incrange

from ..components.asic.xgs.trident3 import Trident3
from ..components.cpu.crow import CrowSysCpld, CrowFanCpldComponent
from ..components.dpm import Ucd90120A, UcdGpi
from ..components.max6658 import Max6658
from ..components.psu import PmbusPsu
from ..components.scd import Scd

from ..descs.fan import FanDesc

@registerPlatform()
class Lodoga(FixedSystem):

   SID = ['Lodoga', 'LodogaSsd']
   SKU = ['DCS-7050CX3-32S', 'DCS-7050CX3-32S-SSD']

   def __init__(self):
      super(Lodoga, self).__init__()

      self.sfpRange = incrange(33, 34)
      self.qsfp100gRange = incrange(1, 32)

      self.inventory.addPorts(sfps=self.sfpRange, qsfps=self.qsfp100gRange)

      self.newComponent(Trident3, PciAddr(bus=0x01))

      scd = self.newComponent(Scd, PciAddr(bus=0x02))

      scd.createWatchdog()

      scd.newComponent(Max6658, scd.i2cAddr(0, 0x4c),
                       waitFile='/sys/class/hwmon/hwmon2')
      scd.newComponent(Ucd90120A, scd.i2cAddr(0, 0x4e, t=3))

      scd.newComponent(CrowFanCpldComponent, addr=scd.i2cAddr(0, 0x60),
                       waitFile='/sys/class/hwmon/hwmon3', fans=[
         FanDesc(fanId) for fanId in incrange(1, 4)
      ])

      scd.newComponent(Max6658, scd.i2cAddr(9, 0x4c),
                       waitFile='/sys/class/hwmon/hwmon4')
      scd.newComponent(PmbusPsu, scd.i2cAddr(11, 0x58, t=3, datr=2, datw=3))
      scd.newComponent(PmbusPsu, scd.i2cAddr(12, 0x58, t=3, datr=2, datw=3))
      scd.newComponent(Ucd90120A, scd.i2cAddr(13, 0x4e, t=3), causes={
         'reboot': UcdGpi(1),
         'watchdog': UcdGpi(2),
         'overtemp': UcdGpi(4),
         'powerloss': UcdGpi(5),
         'systempowerloss': UcdGpi(6),
      })

      scd.addSmbusMasterRange(0x8000, 6, 0x80)

      self.inventory.addLeds(scd.addLeds([
         (0x6050, 'status'),
         (0x6060, 'fan_status'),
         (0x6070, 'psu1'),
         (0x6080, 'psu2'),
         (0x6090, 'beacon'),
      ]))

      scd.addResets([
         ResetGpio(0x4000, 1, False, 'switch_chip_reset'),
         ResetGpio(0x4000, 2, False, 'switch_chip_pcie_reset'),
      ])

      self.syscpld = self.newComponent(CrowSysCpld, I2cAddr(1, 0x23))
      cpld = self.syscpld
      cpld.createPowerCycle()
      scd.addGpios([
         NamedGpio(0x5000, 1, True, False, "psu1_present"),
         NamedGpio(0x5000, 0, True, False, "psu2_present"),
         NamedGpio(0x5000, 9, True, False, "psu1_status"),
         NamedGpio(0x5000, 8, True, False, "psu2_status"),
         NamedGpio(0x5000, 11, True, False, "psu1_ac_status"),
         NamedGpio(0x5000, 10, True, False, "psu2_ac_status"),
      ])
      scd.createPsu(1, led=self.inventory.getLed('psu1'))
      scd.createPsu(2, led=self.inventory.getLed('psu2'))

      addr = 0x6100
      for xcvrId in self.sfpRange:
         name = "sfp%d" % xcvrId
         self.inventory.addLedGroup(name, [scd.addLed(addr, name)])
         addr += 0x10

      addr = 0x6140
      for xcvrId in self.qsfp100gRange:
         leds = []
         for laneId in incrange(1, 4):
            name = "qsfp%d_%d" % (xcvrId, laneId)
            leds.append(scd.addLed(addr, name))
            addr += 0x10
         self.inventory.addLedGroup("qsfp%d" % xcvrId, leds)

      intrRegs = [
         scd.createInterrupt(addr=0x3000, num=0),
         scd.createInterrupt(addr=0x3030, num=1),
      ]

      addr = 0xa010
      bus = 16
      for xcvrId in self.sfpRange:
         intr = intrRegs[0].getInterruptBit(28 + xcvrId - 33)
         name = 'sfp%d' % xcvrId
         self.inventory.addInterrupt(name, intr)
         scd.addSfp(addr, xcvrId, bus, interruptLine=intr,
                    leds=self.inventory.getLedGroup(name))
         addr += 0x10
         bus += 1

      addr = 0xa050
      bus = 24
      for xcvrId in self.qsfp100gRange:
         intr = intrRegs[1].getInterruptBit(xcvrId - 1)
         name = 'qsfp%d' % xcvrId
         self.inventory.addInterrupt(name, intr)
         scd.addQsfp(addr, xcvrId, bus, interruptLine=intr,
                     leds=self.inventory.getLedGroup(name))
         addr += 0x10
         bus += 1

