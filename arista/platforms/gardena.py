from ..core.fixed import FixedSystem
from ..core.platform import registerPlatform
from ..core.port import PortLayout
from ..core.psu import PsuSlot
from ..core.quirk import RegMapSetQuirk
from ..core.register import Register, RegBitField
from ..core.utils import incrange

from ..components.asic.xgs.tomahawk2 import Tomahawk2
from ..components.cpld import SysCpldCommonRegistersV2
from ..components.dpm.ucd import Ucd90120A, UcdGpi
from ..components.max6658 import Max6658
from ..components.psu.delta import DPS750AB, DPS1900AB
from ..components.psu.emerson import DS750PED
from ..components.scd import Scd

from ..descs.gpio import GpioDesc
from ..descs.reset import ResetDesc
from ..descs.sensor import Position, SensorDesc
from ..descs.xcvr import Qsfp28, Sfp

from .cpu.rook import RookCpu

class GardenaCpldRegisters(SysCpldCommonRegistersV2):
   PWR_CYC_EN = Register(0x17,
      RegBitField(0, 'powerCycleOnCrc', ro=False),
      RegBitField(4, 'powerCycleOnDpPowerFail', ro=False),
   )

class GardenaDpPwrFailQuirk(RegMapSetQuirk):
   DESCRIPTION = 'enable DP_PWR_FAIL'
   REG_NAME = 'powerCycleOnDpPowerFail'
   REG_VALUE = True

@registerPlatform()
class Gardena(FixedSystem):

   SID = ['Gardena', 'GardenaE']
   SKU = ['DCS-7260CX3-64', 'DCS-7260CX3-64E']

   PORTS = PortLayout(
      (Qsfp28(i, leds=4) for i in incrange(1, 64)),
      (Sfp(i) for i in incrange(65, 66)),
   )

   def __init__(self):
      super(Gardena, self).__init__()

      cpu = self.newComponent(RookCpu, cpldRegisterCls=GardenaCpldRegisters,
                              sysCpldQuirks=[GardenaDpPwrFailQuirk()])
      cpu.addCpuDpm()
      cpu.cpld.newComponent(Ucd90120A, addr=cpu.switchDpmAddr(0x34), causes={
         'powerloss': UcdGpi(1),
         'reboot': UcdGpi(2),
         'watchdog': UcdGpi(3),
         'overtemp': UcdGpi(4),
      })
      self.cpu = cpu
      self.syscpld = cpu.syscpld

      port = self.cpu.getPciPort(self.cpu.PCI_PORT_SCD0)
      scd = port.newComponent(Scd, addr=port.addr)
      self.scd = scd

      scd.createWatchdog()

      scd.newComponent(Max6658, addr=scd.i2cAddr(0, 0x4c), sensors=[
         SensorDesc(diode=0, name='Board sensor',
                    position=Position.OTHER, target=65, overheat=75, critical=85),
      ])

      scd.addSmbusMasterRange(0x8000, 8, 0x80)

      scd.addResets([
         ResetDesc('switch_chip_reset', addr=0x4000, bit=0, auto=False),
         ResetDesc('switch_chip_pcie_reset', addr=0x4000, bit=1, auto=False),
         ResetDesc('security_asic_reset', addr=0x4000, bit=2),
      ])

      scd.addGpios([
         GpioDesc("psu1_present", 0x5000, 0, ro=True),
         GpioDesc("psu2_present", 0x5000, 1, ro=True),
         GpioDesc("psu1_status", 0x5000, 8, ro=True),
         GpioDesc("psu2_status", 0x5000, 9, ro=True),
         GpioDesc("psu1_ac_status", 0x5000, 10, ro=True),
         GpioDesc("psu2_ac_status", 0x5000, 11, ro=True),
      ])

      for psuId in incrange(1, 2):
         addrFunc=lambda addr, i=psuId: scd.i2cAddr(1 + i, addr, t=3, datr=2, datw=3)
         name = "psu%d" % psuId
         scd.newComponent(
            PsuSlot,
            slotId=psuId,
            addrFunc=addrFunc,
            presentGpio=scd.inventory.getGpio("%s_present" % name),
            inputOkGpio=scd.inventory.getGpio("%s_ac_status" % name),
            outputOkGpio=scd.inventory.getGpio("%s_status" % name),
            led=cpu.leds.inventory.getLed('%s_status' % name),
            psus=[
               DPS750AB,
               DPS1900AB,
               DS750PED,
            ],
         )

      intrRegs = [
         scd.createInterrupt(addr=0x3000, num=0),
         scd.createInterrupt(addr=0x3030, num=1),
         scd.createInterrupt(addr=0x3060, num=2),
      ]

      scd.addXcvrSlots(
         ports=self.PORTS.getQsfps(),
         addr=0xA010,
         bus=8,
         ledAddr=0x6100,
         intrRegs=intrRegs,
         intrRegIdxFn=lambda xcvrId: xcvrId // 33 + 1,
         intrBitFn=lambda xcvrId: (xcvrId - 1) % 32,
         isHwLpModeAvail=False
      )

      scd.addXcvrSlots(
         ports=self.PORTS.getSfps(),
         addr=0xA410,
         bus=6,
         ledAddr=0x7100
      )

      port = self.cpu.getPciPort(self.cpu.PCI_PORT_ASIC0)
      port.newComponent(Tomahawk2, addr=port.addr,
         coreResets=[
            scd.inventory.getReset('switch_chip_reset'),
         ],
         pcieResets=[
            scd.inventory.getReset('switch_chip_pcie_reset'),
         ],
      )
