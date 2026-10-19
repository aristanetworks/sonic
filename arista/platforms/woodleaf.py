from ..core.fixed import FixedSystem
from ..core.platform import registerPlatform
from ..core.port import PortLayout
from ..core.psu import PsuSlot
from ..core.quirk import PciConfigQuirk
from ..core.register import Register, RegBitField, SetClearRegister
from ..core.utils import incrange

from ..components.asic.bfn.tofino2 import Tofino2
from ..components.dpm.ucd import Ucd90320, UcdGpi
from ..components.phy.b52 import B52
from ..components.psu.liteon import PS2242
from ..components.scd import Scd
from ..components.tmp468 import Tmp468

from ..descs.gpio import GpioDesc
from ..descs.reset import ResetDesc
from ..descs.sensor import Position, SensorDesc
from ..descs.xcvr import Qsfp28, Sfp

from .chassis.tuba import Tuba

from .cpu.lorikeet import LorikeetCpu, LorikeetCpldRegisters

class WoodleafCpldRegisters(LorikeetCpldRegisters):
   PWR_CYC_EN = SetClearRegister(0x11, 0x13,
      RegBitField(4, 'powerCycleOnDpPowerFail', ro=False),
      RegBitField(3, 'powerCycleOnOvertemp', ro=False),
      RegBitField(1, 'powerCycleOnWatchdog', ro=False),
      RegBitField(0, 'powerCycleOnCrc', ro=False),
   )
   FAULT_SUICIDE = Register(0x1B,
      RegBitField(3, 'suicideOnOvertemp', ro=False),
   )
   DATAPLANE_PWR = Register(0x32,
      RegBitField(6, 'gearboxLeftPower', ro=False),
      RegBitField(5, 'gearboxRightPower', ro=False),
      RegBitField(4, 'asicPower', ro=False),
      RegBitField(2, 'gearboxLeftPowerGood'),
      RegBitField(1, 'gearboxRightPowerGood'),
      RegBitField(0, 'asicPowerGood'),
   )

@registerPlatform()
class Woodleaf(FixedSystem):

   SID = ['Woodleaf']
   SKU = ['DCS-7170B-64C']

   CHASSIS = Tuba

   PHY = B52

   PORTS = PortLayout(
      (Qsfp28(i) for i in incrange(1, 64)),
      (Sfp(i) for i in incrange(65, 66)),
   )

   def __init__(self):
      super(Woodleaf, self).__init__()

      self.cpu = self.newComponent(LorikeetCpu,
                                   cpldRegisterCls=WoodleafCpldRegisters)
      self.cpu.addCpuDpm()
      self.cpu.cpld.newComponent(Ucd90320, addr=self.cpu.switchDpmAddr(0x11),
                                 causes={
         'overtemp': UcdGpi(4),
         'powerloss': UcdGpi(8),
         'reboot': UcdGpi(9),
         'watchdog': UcdGpi(10),
      })

      self.syscpld = self.cpu.syscpld

      port = self.cpu.getPciPort(0)
      scd = port.newComponent(Scd, addr=port.addr)
      self.scd = scd

      scd.createWatchdog()
      scd.setMsiRearmOffset(0x180)

      scd.addSmbusMasterRange(0x8000, 9, 0x80)

      scd.newComponent(Tmp468, addr=scd.i2cAddr(0, 0x49), sensors=[
         SensorDesc(diode=0, name='Switch card',
                    position=Position.OTHER, target=85, overheat=100, critical=110),
         SensorDesc(diode=1, name='Front',
                    position=Position.INLET, target=75, overheat=85, critical=90),
         SensorDesc(diode=2, name='Rear',
                    position=Position.OTHER, target=75, overheat=85, critical=90),
         SensorDesc(diode=3, name='FrontLT',
                    position=Position.OTHER, target=75, overheat=85, critical=90),
         SensorDesc(diode=4, name='FrontRT',
                    position=Position.OTHER, target=75, overheat=85, critical=90),
         SensorDesc(diode=5, name='RearLT',
                    position=Position.OTHER, target=75, overheat=85, critical=90),
         SensorDesc(diode=6, name='RearRT',
                    position=Position.OTHER, target=75, overheat=85, critical=90),
         SensorDesc(diode=7, name='Tofino2',
                    position=Position.OTHER, target=90, overheat=100, critical=102),
      ])

      scd.addResets([
         ResetDesc('switch_chip_core_reset', addr=0x4000, bit=16, auto=False),
         ResetDesc('switch_chip_pcie_reset', addr=0x4000, bit=17, auto=False),
         ResetDesc('switch_chip_power_on_reset', addr=0x4000, bit=18, auto=False),
         ResetDesc('cpld_right_reset', addr=0x4000, bit=19),
         ResetDesc('cpld_left_reset', addr=0x4000, bit=20),
         ResetDesc('tpm_reset', addr=0x4000, bit=21),
      ] + [
         ResetDesc('phy%d_reset' % i, addr=0x4000, bit=i) for i in incrange(0, 15)
      ])

      scd.addGpios([
         GpioDesc("psu1_present", 0x5000, 0, ro=True),
         GpioDesc("psu2_present", 0x5000, 1, ro=True),
         GpioDesc("psu1_status", 0x5000, 8, ro=True),
         GpioDesc("psu2_status", 0x5000, 9, ro=True),
         GpioDesc("psu1_ac_status", 0x5000, 10, ro=True),
         GpioDesc("psu2_ac_status", 0x5000, 11, ro=True),
      ])

      intrRegs = [
         scd.createInterrupt(addr=0x3000, num=0),
         scd.createInterrupt(addr=0x3030, num=1),
         scd.createInterrupt(addr=0x3060, num=2),
         scd.createInterrupt(addr=0x3090, num=3),
         scd.createInterrupt(addr=0x30C0, num=4),
      ]

      scd.addXcvrSlots(
         ports=self.PORTS.getQsfps(),
         addr=0xA010,
         bus=8,
         ledAddr=0x6100,
         ledAddrOffsetFn=lambda x: 0x10,
         intrRegs=intrRegs,
         intrRegIdxFn=lambda xcvrId: xcvrId // 33 + 3,
         intrBitFn=lambda xcvrId: (xcvrId - 1) % 32,
      )

      scd.addXcvrSlots(
         ports=self.PORTS.getSfps(),
         addr=0xA410,
         bus=5,
         ledAddr=0x7100,
         ledAddrOffsetFn=lambda x: 0x10,
      )

      for psuId, bus in [(1, 3), (2, 4)]:
         addrFunc=lambda addr, bus=bus: \
                  scd.i2cAddr(bus, addr, t=3, datr=2, datw=3)
         name = "psu%d" % psuId
         scd.newComponent(
            PsuSlot,
            slotId=psuId,
            addrFunc=addrFunc,
            presentGpio=scd.inventory.getGpio("%s_present" % name),
            inputOkGpio=scd.inventory.getGpio("%s_ac_status" % name),
            outputOkGpio=scd.inventory.getGpio("%s_status" % name),
            led=self.cpu.cpld.inventory.getLed('%s' % name),
            psus=[
               PS2242,
            ],
         )

      scd.addMdioMasterRange(0x9000, 16)
      for i in incrange(0, 15):
         phyId = i + 1
         reset = scd.inventory.getReset('phy%d_reset' % i)
         mdios = [scd.addMdio(i, 0)]
         phy = self.PHY(phyId, mdios, reset=reset)
         self.inventory.addPhy(phy)

      port = self.cpu.getPciPort(1)
      bridge = port.parent
      port.newComponent(Tofino2, addr=port.addr,
         powerGpios=[
            self.syscpld.addGpio('gearboxLeftPower'),
            self.syscpld.addGpio('gearboxRightPower'),
            self.syscpld.addGpio('asicPower'),
         ],
         powerGoodGpios=[
            self.syscpld.addGpio('gearboxLeftPowerGood'),
            self.syscpld.addGpio('gearboxRightPowerGood'),
            self.syscpld.addGpio('asicPowerGood'),
         ],
         coreResets=[
            scd.inventory.getReset('switch_chip_power_on_reset'),
            scd.inventory.getReset('switch_chip_core_reset'),
         ],
         pcieResets=[
            scd.inventory.getReset('switch_chip_pcie_reset'),
         ],
         pciResetDelay=200,
         quirks=[
            PciConfigQuirk(bridge.addr, 'BRIDGE_CONTROL=0x1:0x1', 'enable SERR'),
            PciConfigQuirk(bridge.addr,
                           'CAP_EXP+0x10.w=0x20:0x20', 'enable Training'),
         ],
      )
