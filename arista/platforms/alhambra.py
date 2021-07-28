from ..core.fixed import FixedSystem
from ..core.platform import registerPlatform
from ..core.psu import PsuSlot
from ..core.types import PciAddr, ResetGpio
from ..core.utils import incrange

from ..components.asic.bfn.tofino import Tofino
from ..components.dpm import Ucd90120A, Ucd90160, UcdGpi
from ..components.max6658 import Max6658
from ..components.psu.delta import DPS750AB, DPS1900AB
from ..components.psu.emerson import DS750PED
from ..components.scd import Scd

from ..descs.gpio import GpioDesc
from ..descs.sensor import Position, SensorDesc

from .cpu.rook import RookCpu

@registerPlatform()
class Alhambra(FixedSystem):

   SID = ['Alhambra', 'AlhambraSsd']
   SKU = ['DCS-7170-64C', 'DCS-7170-64C-M']

   def __init__(self, ports=64, hasLmSensor=True, psus=None):
      super(Alhambra, self).__init__()

      self.qsfpRange = incrange(1, ports)
      self.sfpRange = incrange(ports + 1, ports + 2)

      self.inventory.addPorts(qsfps=self.qsfpRange, sfps=self.sfpRange)

      self.newComponent(Tofino, PciAddr(bus=0x07))

      scd = self.newComponent(Scd, PciAddr(bus=0x06))
      self.scd = scd

      scd.createWatchdog()

      scd.newComponent(Max6658, scd.i2cAddr(7, 0x4c), sensors=[
         SensorDesc(diode=0, name='Board sensor',
                    position=Position.OTHER, target=60, overheat=70, critical=80),
         SensorDesc(diode=1, name='Switch Chip sensor',
                    position=Position.OTHER, target=85, overheat=100, critical=110),
      ])

      scd.addSmbusMasterRange(0x8000, 9, 0x80)

      scd.addResets([
         ResetGpio(0x4000, 8, False, 'switch_chip_reset'),
         ResetGpio(0x4000, 1, False, 'security_chip_reset'),
         ResetGpio(0x4000, 0, False, 'repeater_sfp_reset'),
      ])

      scd.addGpios([
         GpioDesc("psu1_present", 0x5000, 0, ro=True),
         GpioDesc("psu2_present", 0x5000, 1, ro=True),
         GpioDesc("psu1_status", 0x5000, 8, ro=True),
         GpioDesc("psu2_status", 0x5000, 9, ro=True),
         GpioDesc("psu1_ac_status", 0x5000, 10, ro=True),
         GpioDesc("psu2_ac_status", 0x5000, 11, ro=True),
      ])

      addr = 0x6100
      for xcvrId in self.qsfpRange:
         leds = []
         for laneId in incrange(1, 4):
            name = "qsfp%d_%d" % (xcvrId, laneId)
            leds.append((addr, name))
            addr += 0x10
         scd.addLedGroup("qsfp%d" % xcvrId, leds)

      addr = 0x7200
      for xcvrId in self.sfpRange:
         name = "sfp%d" % xcvrId
         scd.addLedGroup(name, [(addr, name)])
         addr += 0x10

      scd.setMsiRearmOffset(0x190)

      intrRegs = [
         scd.createInterrupt(addr=0x3000, num=0, mask=0x60003ff),
         scd.createInterrupt(addr=0x3030, num=1),
         scd.createInterrupt(addr=0x3060, num=2),
      ]

      addr = 0xA010
      bus = 8
      for xcvrId in sorted(self.qsfpRange):
         name = 'qsfp%d' % xcvrId
         intr = intrRegs[xcvrId // 33 + 1].getInterruptBit(name, (xcvrId - 1) % 32)
         scd.addQsfp(addr, xcvrId, bus, interruptLine=intr,
                     leds=scd.inventory.getLedGroup(name))
         addr += 0x10
         bus += 1

      addr = 0xA500
      bus = 72
      for xcvrId in sorted(self.sfpRange):
         scd.addSfp(addr, xcvrId, bus,
                    leds=scd.inventory.getLedGroup('sfp%d' % xcvrId))
         addr += 0x10
         bus += 1

      cpu = self.newComponent(RookCpu, hasLmSensor=hasLmSensor)
      cpu.cpld.newComponent(Ucd90160, cpu.cpuDpmAddr())
      cpu.cpld.newComponent(Ucd90120A, cpu.switchDpmAddr(), causes={
         'powerloss': UcdGpi(1),
         'overtemp': UcdGpi(2),
         'reboot': UcdGpi(4),
         'watchdog': UcdGpi(5),
      })
      self.cpu = cpu
      self.syscpld = cpu.syscpld

      for psuId in incrange(1, 2):
         addrFunc=lambda addr, i=psuId: \
               scd.i2cAddr(4 + i, addr, t=3, datr=2, datw=3, block=False)
         name = "psu%d" % psuId
         scd.newComponent(
            PsuSlot,
            slotId=psuId,
            addrFunc=addrFunc,
            presentGpio=scd.inventory.getGpio("%s_present" % name),
            inputOkGpio=scd.inventory.getGpio("%s_ac_status" % name),
            outputOkGpio=scd.inventory.getGpio("%s_status" % name),
            led=cpu.leds.inventory.getLed('%s_status' % name),
            psus=psus or [
               DPS750AB,
               DPS1900AB,
               DS750PED,
            ],
         )
