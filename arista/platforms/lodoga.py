from ..core.fixed import FixedSystem
from ..core.platform import registerPlatform
from ..core.psu import PsuSlot
from ..core.register import Register, RegBitField
from ..core.types import PciAddr, ResetGpio
from ..core.utils import incrange

from ..components.asic.xgs.trident3 import Trident3
from ..components.dpm import Ucd90120A, UcdGpi
from ..components.max6658 import Max6658
from ..components.psu.delta import DPS495CB
from ..components.psu.artesyn import DS495SPE
from ..components.scd import Scd

from ..descs.gpio import GpioDesc
from ..descs.sensor import Position, SensorDesc

from .cpu.crow import CrowCpu, CrowCpldRegisters

class LodogaCpldRegisters(CrowCpldRegisters):
   FAULT_CTRL = Register(0x17,
       RegBitField(2, 'powerCycleOnCrc', ro=False),
   )
   FAULT_STATUS = Register(0x19,
       RegBitField(6, 'scdSeuError'),
   )

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

      cpu = self.newComponent(CrowCpu, scd, registerCls=LodogaCpldRegisters)
      self.cpu = cpu
      self.syscpld = cpu.syscpld

      scd.createWatchdog()

      scd.newComponent(Ucd90120A, scd.i2cAddr(0, 0x4e, t=3))

      scd.newComponent(Max6658, scd.i2cAddr(9, 0x4c), sensors=[
         SensorDesc(diode=0, name='Board temp sensor',
                    position=Position.OTHER, target=65, overheat=75, critical=85),
         SensorDesc(diode=1, name='Front-panel temp sensor',
                    position=Position.INLET, target=50, overheat=60, critical=65),
      ])

      scd.addSmbusMasterRange(0x8000, 6, 0x80)

      scd.addLeds([
         (0x6050, 'status'),
         (0x6060, 'fan_status'),
         (0x6070, 'psu1'),
         (0x6080, 'psu2'),
         (0x6090, 'beacon'),
      ])

      scd.newComponent(Ucd90120A, scd.i2cAddr(13, 0x4e, t=3), causes={
         'reboot': UcdGpi(1),
         'watchdog': UcdGpi(2),
         'overtemp': UcdGpi(4),
         'powerloss': UcdGpi(5),
         'systempowerloss': UcdGpi(6),
      })

      scd.addResets([
         ResetGpio(0x4000, 1, False, 'switch_chip_reset'),
         ResetGpio(0x4000, 2, False, 'switch_chip_pcie_reset'),
      ])

      scd.addGpios([
         GpioDesc("psu1_present", 0x5000, 1, ro=True),
         GpioDesc("psu2_present", 0x5000, 0, ro=True),
         GpioDesc("psu1_status", 0x5000, 9, ro=True),
         GpioDesc("psu2_status", 0x5000, 8, ro=True),
         GpioDesc("psu1_ac_status", 0x5000, 11, ro=True),
         GpioDesc("psu2_ac_status", 0x5000, 10, ro=True),
      ])

      for psuId in incrange(1, 2):
         addrFunc=lambda addr, i=psuId: \
                  scd.i2cAddr(10 + i, addr, t=3, datr=2, datw=3)
         name = "psu%d" % psuId
         scd.newComponent(
            PsuSlot,
            slotId=psuId,
            addrFunc=addrFunc,
            presentGpio=scd.inventory.getGpio("%s_present" % name),
            inputOkGpio=scd.inventory.getGpio("%s_ac_status" % name),
            outputOkGpio=scd.inventory.getGpio("%s_status" % name),
            led=scd.inventory.getLed(name),
            psus=[
               DPS495CB,
               DS495SPE,
            ],
         )

      addr = 0x6120
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

      intrRegs = [
         scd.createInterrupt(addr=0x3000, num=0),
         scd.createInterrupt(addr=0x3030, num=1),
      ]

      addr = 0xa010
      bus = 16
      for xcvrId in self.sfpRange:
         name = 'sfp%d' % xcvrId
         intr = intrRegs[0].getInterruptBit(name, 28 + xcvrId - 33)
         scd.addSfp(addr, xcvrId, bus, interruptLine=intr,
                    leds=scd.inventory.getLedGroup(name))
         addr += 0x10
         bus += 1

      addr = 0xa050
      bus = 24
      for xcvrId in self.qsfp100gRange:
         name = 'qsfp%d' % xcvrId
         intr = intrRegs[1].getInterruptBit(name, xcvrId - 1)
         scd.addQsfp(addr, xcvrId, bus, interruptLine=intr,
                     leds=scd.inventory.getLedGroup(name))
         addr += 0x10
         bus += 1
