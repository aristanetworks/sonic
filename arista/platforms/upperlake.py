from ..core.fixed import FixedSystem
from ..core.platform import registerPlatform
from ..core.types import PciAddr, I2cAddr, ResetGpio
from ..core.utils import incrange

from ..components.asic.xgs.tomahawk import Tomahawk
from ..components.cpu.amd.k10temp import K10Temp
from ..components.cpu.crow import KoiSysCpld, CrowFanCpldComponent
from ..components.dpm import Ucd90120A, UcdGpi
from ..components.max6658 import Max6658
from ..components.max6697 import Max6697
from ..components.psu import UpperlakePsuComponent
from ..components.scd import Scd

from ..descs.fan import FanDesc
from ..descs.gpio import GpioDesc
from ..descs.psu import PsuDesc
from ..descs.sensor import Position, SensorDesc

@registerPlatform()
class Upperlake(FixedSystem):

   SID = ['Upperlake', 'UpperlakeES', 'UpperlakeSsd']
   SKU = ['DCS-7060CX-32S', 'DCS-7060CX-32S-ES', 'DCS-7060CX-32S-SSD']

   def __init__(self):
      super(Upperlake, self).__init__()

      self.sfpRange = incrange(33, 34)
      self.qsfp100gRange = incrange(1, 32)

      self.inventory.addPorts(sfps=self.sfpRange, qsfps=self.qsfp100gRange)

      self.newComponent(Tomahawk, PciAddr(bus=0x01))

      scd = self.newComponent(Scd, PciAddr(bus=0x02))

      self.newComponent(K10Temp, sensors=[
         SensorDesc(diode=0, name='Cpu temp sensor',
                    position=Position.OTHER, target=60, overheat=90, critical=95),
      ])

      scd.createWatchdog()

      scd.newComponent(Max6697, addr=scd.i2cAddr(0, 0x1a),
                       waitFile='/sys/class/hwmon/hwmon2', sensors=[
         SensorDesc(diode=0, name='Board sensor',
                    position=Position.OTHER, target=55, overheat=65, critical=75),
         SensorDesc(diode=1, name='Switch chip left sensor',
                    position=Position.OTHER, target=55, overheat=95, critical=105),
         SensorDesc(diode=5, name='Switch chip right sensor',
                    position=Position.OTHER, target=55, overheat=95, critical=105),
         SensorDesc(diode=6, name='Front-panel temp sensor',
                    position=Position.INLET, target=55, overheat=65, critical=75),
      ])
      scd.newComponent(Max6658, addr=scd.i2cAddr(1, 0x4c),
                       waitFile='/sys/class/hwmon/hwmon3', sensors=[
         SensorDesc(diode=0, name='Cpu board temp sensor',
                    position=Position.OTHER, target=55, overheat=75, critical=80),
         SensorDesc(diode=1, name='Back-panel temp sensor',
                    position=Position.OUTLET, target=50, overheat=75, critical=80),
      ])

      scd.newComponent(CrowFanCpldComponent, addr=scd.i2cAddr(1, 0x60),
                       waitFile='/sys/class/hwmon/hwmon4', fans=[
         FanDesc(fanId) for fanId in incrange(1, 4)
      ])

      scd.newComponent(Ucd90120A, scd.i2cAddr(1, 0x4e, t=3))
      scd.newComponent(Ucd90120A, scd.i2cAddr(5, 0x4e, t=3), causes={
         'reboot': UcdGpi(1),
         'watchdog': UcdGpi(2),
         'overtemp': UcdGpi(4),
         'powerloss': UcdGpi(5),
      })

      scd.addSmbusMasterRange(0x8000, 5, 0x80)

      scd.addLeds([
         (0x6050, 'status'),
         (0x6060, 'fan_status'),
         (0x6070, 'psu1'),
         (0x6080, 'psu2'),
         (0x6090, 'beacon'),
      ])

      scd.addResets([
         ResetGpio(0x4000, 1, False, 'switch_chip_reset'),
         ResetGpio(0x4000, 2, False, 'switch_chip_pcie_reset'),
      ])

      scd.addGpios([
         GpioDesc("psu1_present", 0x5000, 0, ro=True),
         GpioDesc("psu2_present", 0x5000, 1, ro=True),
      ])

      self.syscpld = self.newComponent(KoiSysCpld, I2cAddr(1, 0x23))
      cpld = self.syscpld
      cpld.createPowerCycle()

      for psuId in incrange(1, 2):
         scd.addPsu(UpperlakePsuComponent,
                    addr=scd.i2cAddr(2 + psuId, 0x58, t=3, datr=2, datw=3),
                    waitFile='/sys/class/hwmon/hwmon%d' % (4 + psuId), cpld=cpld,
                    psus=[
            PsuDesc(psuId=psuId, led=self.inventory.getLed('psu%s' % psuId),
                    sensors=[
               SensorDesc(diode=0,
                          name='Power supply %d hotspot sensor' % psuId,
                          position=Position.OTHER,
                          target=80, overheat=95, critical=100),
               SensorDesc(diode=1,
                          name='Power supply %d inlet temp sensor' % psuId,
                          position=Position.OTHER,
                          target=55, overheat=70, critical=75),
               SensorDesc(diode=2,
                          name='Power supply %d exhaust temp sensor' % psuId,
                          position=Position.OTHER,
                          target=80, overheat=108, critical=113),
            ]),
         ])

      addr = 0x6100
      for xcvrId in self.sfpRange:
         name = "sfp%d" % xcvrId
         scd.addLedGroup(name, [(addr, name)])
         addr += 0x10

      addr = 0x6140
      for xcvrId in self.qsfp100gRange:
         leds = []
         for laneId in incrange(1, 4):
            name = "qsfp%d_%d" % (xcvrId, laneId)
            leds.append((addr, name))
            addr += 0x10
         scd.addLedGroup("qsfp%d" % xcvrId, leds)

      addr = 0x5010
      bus = 8
      for xcvrId in self.sfpRange:
         scd.addSfp(addr, xcvrId, bus,
                    leds=self.inventory.getLedGroup('sfp%d' % xcvrId))
         addr += 0x10
         bus += 1

      intrRegs = [
         scd.createInterrupt(addr=0x3000, num=0),
         scd.createInterrupt(addr=0x3030, num=1),
      ]

      addr = 0x5050
      bus = 16
      for xcvrId in self.qsfp100gRange:
         intr = intrRegs[1].getInterruptBit(xcvrId - 1)
         name = 'qsfp%d' % xcvrId
         self.inventory.addInterrupt(name, intr)
         scd.addQsfp(addr, xcvrId, bus, interruptLine=intr,
                     leds=self.inventory.getLedGroup(name))
         addr += 0x10
         bus += 1

@registerPlatform()
class UpperlakePlus(Upperlake):
   SID = ['UpperlakePlus']
   SKU = ['DCS-7060CX2-32S']
