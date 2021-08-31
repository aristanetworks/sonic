from ..core.asic import SwitchChip
from ..core.fixed import FixedSystem
from ..core.platform import registerPlatform
from ..core.port import PortLayout
from ..core.psu import PsuSlot
from ..core.types import PciAddr
from ..core.utils import incrange

from ..components.dpm.ucd import Ucd90320, UcdGpi
from ..components.phy.babbage import Babbage
from ..components.phy.b52 import B52
from ..components.psu.delta import DPS1500AB, DPS1600CB, DPS500AB
from ..components.psu.liteon import PS2102
from ..components.scd import Scd
from ..components.tmp468 import Tmp468

from .cpu.woodpecker import WoodpeckerCpu

from ..descs.gpio import GpioDesc
from ..descs.reset import ResetDesc
from ..descs.sensor import Position, SensorDesc

@registerPlatform()
class Smartsville(FixedSystem):

   SID = ['Smartsville', 'SmartsvilleSsd']
   SKU = ['DCS-7280CR3-32P4', 'DCS-7280CR3-32P4-M']

   PHY = Babbage

   PORTS = PortLayout(
      qsfps=incrange(1, 32),
      osfps=incrange(33, 36),
   )

   def __init__(self):
      super(Smartsville, self).__init__()

      self.cpu = self.newComponent(WoodpeckerCpu)
      self.cpu.addCpuDpm()
      self.cpu.cpld.newComponent(Ucd90320, self.cpu.switchDpmAddr(), causes={
         'powerloss': UcdGpi(1),
         'reboot': UcdGpi(2),
         'watchdog': UcdGpi(3),
         'overtemp': UcdGpi(4),
      })

      self.newComponent(SwitchChip, PciAddr(bus=0x05))

      scd = self.newComponent(Scd, PciAddr(bus=0x02))

      scd.createWatchdog()

      scd.newComponent(Tmp468, scd.i2cAddr(0, 0x48), sensors=[
         SensorDesc(diode=0, name='Board Sensor',
                    position=Position.OTHER, target=65, overheat=75, critical=80),
         SensorDesc(diode=1, name='Front Air',
                    position=Position.INLET, target=55, overheat=65, critical=75),
         SensorDesc(diode=2, name='Rear Air',
                    position=Position.OTHER, target=55, overheat=65, critical=75),
         SensorDesc(diode=7, name='Fap 0 Core 0',
                    position=Position.OTHER, target=85, overheat=100, critical=110),
         SensorDesc(diode=8, name='Fap 0 Core 1',
                    position=Position.OTHER, target=85, overheat=100, critical=110),
      ])

      scd.addSmbusMasterRange(0x8000, 5, 0x80)

      scd.addLeds([
         (0x6050, 'status'),
         (0x6060, 'fan_status'),
         (0x6070, 'psu1'),
         (0x6080, 'psu2'),
         (0x6090, 'beacon'),
      ])

      scd.addResets([
         ResetDesc('switch_chip_reset', addr=0x4000, bit=0),
         ResetDesc('switch_chip_pcie_reset', addr=0x4000, bit=1),
         ResetDesc('security_asic_reset', addr=0x4000, bit=2)
      ])

      scd.addGpios([
         GpioDesc("psu1_present", 0x5000, 0, ro=True),
         GpioDesc("psu2_present", 0x5000, 1, ro=True),
         GpioDesc("psu1_status", 0x5000, 8, ro=True),
         GpioDesc("psu2_status", 0x5000, 9, ro=True),
         GpioDesc("psu1_ac_status", 0x5000, 10, ro=True, activeLow=True),
         GpioDesc("psu2_ac_status", 0x5000, 11, ro=True, activeLow=True),

         GpioDesc("psu1_present_changed", 0x5000, 16),
         GpioDesc("psu2_present_changed", 0x5000, 17),
         GpioDesc("psu1_status_changed", 0x5000, 18),
         GpioDesc("psu2_status_changed", 0x5000, 19),
         GpioDesc("psu1_ac_status_changed", 0x5000, 20),
         GpioDesc("psu2_ac_status_changed", 0x5000, 21),
      ])

      for psuId in incrange(1, 2):
         addrFunc=lambda addr, i=psuId: scd.i2cAddr(5 + i, addr, t=3, datr=3, datw=3)
         name = "psu%d" % psuId
         scd.newComponent(
            PsuSlot,
            slotId=psuId,
            addrFunc=addrFunc,
            presentGpio=scd.inventory.getGpio("%s_present" % name),
            inputOkGpio=scd.inventory.getGpio("%s_ac_status" % name),
            outputOkGpio=scd.inventory.getGpio("%s_status" % name),
            led=scd.inventory.getLed('%s' % name),
            psus=[
               PS2102,
               DPS1600CB,
               DPS1500AB,
               DPS500AB,
            ],
         )

      intrRegs = [
         scd.createInterrupt(addr=0x3000, num=0),
         scd.createInterrupt(addr=0x3030, num=1),
         scd.createInterrupt(addr=0x3060, num=2),
      ]

      scd.addQsfpSlotBlock(
         qsfpRange=self.PORTS.qsfpRange,
         addr=0xA010,
         bus=8,
         ledAddr=0x6100,
         ledLanes=4,
         intrRegs=intrRegs,
         intrRegIdxFn=lambda xcvrId: 1,
         intrBitFn=lambda xcvrId: xcvrId - self.PORTS.qsfpRange[0],
         isHwModSelAvail=False
      )

      scd.addOsfpSlotBlock(
         osfpRange=self.PORTS.osfpRange,
         addr=0xA210,
         bus=40,
         ledAddr=0x6900,
         ledAddrOffsetFn=lambda x: 0x40,
         intrRegs=intrRegs,
         intrRegIdxFn=lambda xcvrId: 2,
         intrBitFn=lambda xcvrId: xcvrId - self.PORTS.osfpRange[0],
         isHwModSelAvail=False
      )

      scd.addMdioMasterRange(0x9000, 8)

      for i in range(0, 8):
         phyId = i + 1
         reset = scd.addReset(ResetDesc('phy%d_reset' % phyId, addr=0x4000,
                                        bit=3 + i))
         mdios = [scd.addMdio(i, 0), scd.addMdio(i, 1)]
         phy = self.PHY(phyId, mdios, reset=reset)
         self.inventory.addPhy(phy)

@registerPlatform()
class SmartsvilleBK(Smartsville):
   SID = ['SmartsvilleBK']
   SKU = ['DCS-7280CR3K-32P4']

@registerPlatform()
class SmartsvilleDD(Smartsville):
   SID = ['SmartsvilleDD', 'SmartsvilleDDSsd']
   SKU = ['DCS-7280CR3-32D4', 'DCS-7280CR3-32D4-M']

@registerPlatform()
class SmartsvilleDDBK(Smartsville):
   SID = ['SmartsvilleDDBK']
   SKU = ['DCS-7280CR3K-32D4']

@registerPlatform()
class SmartsvilleBkMs(Smartsville):
   SID = ['SmartsvilleBkMs', 'SmartvilleBkMsTpm']
   SKU = ['DCS-7280CR3MK-32P4', 'DCS-7280CR3MK-32P4S']
   PHY = B52

@registerPlatform()
class SmartsvillDDBkMs(SmartsvilleBkMs):
   SID = ['SmartsvilleDDBkMs', 'SmartsvilleDDBkMsTpm']
   SKU = ['DCS-7280CR3MK-32D4', 'DCS-7280CR3MK-32D4S']
