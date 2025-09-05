from ..core.cooling import CoolingConfig
from ..core.fixed import FixedSystem, FixedChassis
from ..core.platform import registerPlatform
from ..core.port import PortLayout
from ..core.psu import PsuSlot
from ..core.xcvr import EthernetImpl, EthernetSlotImpl, XcvrSlot
from ..core.utils import incrange

from ..components.asic.xgs.tomahawk5 import Tomahawk5
from ..components.cpld import SysCpldReloadCauseRegistersV2, SysCpldCause
from ..components.lm75 import Tmp75
from ..components.max6581 import Max6581
from ..components.minke import Minke
from ..components.pci import EcrcPciQuirk
from ..components.psu.dcdc import MobyDcDc, MobyDcDcAddr18

from ..components.scd import Scd, ScdCause, ScdReloadCauseRegisters
from ..components.xcvr import CmisEeprom

# from ..descs.led import LedColor, LedDesc
from ..descs.gpio import GpioDesc
from ..descs.reset import ResetDesc
from ..descs.sensor import Position, SensorDesc
from ..descs.xcvr import Osfp800, Qsfp28, Xcvr as XcvrDesc

from .cpu.redstart import RedstartCpu

class Cartridge:
   def __init__(self, index, eeprom, interrupt, wp):
      self.index = index
      self.eeprom = eeprom
      self.interrupt = interrupt
      self.wp = wp

   def getPresence(self):
      return not self.interrupt.asserted()

class BackplaneImpl(EthernetImpl):
   def __init__(self, eeprom, slot):
      super().__init__(slot)
      self.addr = eeprom.addr

   def getType(self):
      return 'backplane'

class PaladinConnector(XcvrSlot):
   def __init__(self, *args, cartridge=None, **kwargs):
      super().__init__(*args, **kwargs)
      self.slotInv = self.inventory.addEthernetSlot(EthernetSlotImpl(self))
      self.xcvrInv = self.inventory.addEthernet(BackplaneImpl(cartridge.eeprom,
                                                              self.slotInv))
      self.xcvr = cartridge.eeprom
      self.cartridge = cartridge
      self.leds = []

   def getPresence(self):
      return self.cartridge.getPresence()

class PaladinHd(XcvrDesc):
   LANES = 48
   SPEED = 100

class MobyChassis(FixedChassis):
   FAN_SLOTS = 3
   FAN_COUNT = 2
   HEIGHT_RU = 1

   @classmethod
   def addFanboard(cls, parent, bus):
      return Minke(parent, bus)

@registerPlatform()
class Moby(FixedSystem):

   CHASSIS = MobyChassis
   CPU_CLS = RedstartCpu
   COOLING = CoolingConfig(minSpeed=15)
   LED_FP_TRICOLOR = True

   BACKPLANE_CONNECTORS = 8
   BACKPLANE_CARTRIDGES = 4

   PORTS = PortLayout(
      (Osfp800(i) for i in incrange(1, 16)),
      (PaladinHd(i) for i in range(17, 17 + BACKPLANE_CONNECTORS)),
      (Qsfp28(25),),
   )

   SID = ['Moby', 'RedstartFixed8CNMoby']
   SKU = ['DCS-7060X6-16PE-384C', 'DCS-7060X6-16PE-384C-B']

   def __init__(self):
      super().__init__()

      self.cpu = self.newComponent(self.CPU_CLS)
      self.syscpld = self.cpu.syscpld

      port = self.cpu.getPciPort(self.cpu.PCI_PORT_SCD0)
      scd = port.newComponent(Scd, addr=port.addr)
      self.scd = scd

      scd.addSmbusMasterRange(0x8000, 2, 0x80, 6)
      scd.setMsiRearmOffset(0x180)
      scd.createWatchdog()

      scd.addResets([
         ResetDesc('switch_chip_pcie_reset', addr=0x4000, bit=3, auto=False),
         ResetDesc('switch_chip_reset', addr=0x4000, bit=2, auto=False),
      ])

      scd.newComponent(Max6581, addr=scd.i2cAddr(0, 0x4d), sensors=[
         SensorDesc(diode=0, name='Switch Card temp sensor',
                    position=Position.OTHER, target=85, overheat=95, critical=105),
         SensorDesc(diode=1, name='TH5 PCB Left',
                    position=Position.OTHER, target=105, overheat=115, critical=125),
         SensorDesc(diode=2, name='TH5 PCB Right',
                    position=Position.OTHER, target=105, overheat=115, critical=125),
         SensorDesc(diode=3, name='Inlet Ambiant Air',
                    position=Position.OTHER, target=85, overheat=95, critical=105),
         SensorDesc(diode=6, name='TH5 Diode 1',
                    position=Position.OTHER, target=105, overheat=115, critical=125),
         SensorDesc(diode=7, name='TH5 Diode 2',
                    position=Position.OTHER, target=105, overheat=115, critical=125),
      ])

      scd.addLeds([
         (0x6010 + 0x4 * i, f'blade{i+1}') for i in range(0, 12)
      ])
      scd.addLeds([
         (0x6050, 'status'),
         (0x6060, 'fan_status'),
         (0x6070, 'psu_status'),
      ])

      intrs = [
         scd.createInterrupt(addr=0x3000, num=0),
      ]

      self.cartridges = [
         Cartridge(
            index=i,
            eeprom=scd.newComponent(
               CmisEeprom,
               addr=scd.i2cAddr(12 + i, 0x50),
               portName=f'cartridge{i}',
            ),
            interrupt=intrs[0].getInterruptBit(f'phd{i + 1}_det_l', 15 + i),
            wp=scd.addGpio(GpioDesc(f'phd{i + 1}_wp', addr=0x2D00, bit=i)),
         ) for i in range(0, self.BACKPLANE_CARTRIDGES)
      ]

      # Make the backplane connector appear as individual port for proper
      # integration with xcvrd
      self.backplane = [
         scd.newComponent(
            PaladinConnector,
            name=f'back{i}',
            slotId=17 + i,
            cartridge=self.cartridges[-(1 + i // 2)],
         ) for i in range(0, self.BACKPLANE_CONNECTORS)
      ]

      for psuId, psuClasses in [
         (1, [MobyDcDc]),
         (2, [MobyDcDcAddr18])
      ]:
         addrFunc=lambda addr: scd.i2cAddr(16, addr, t=3, datr=2, datw=3)
         self.scd.newComponent(
            PsuSlot,
            slotId=psuId,
            addrFunc=addrFunc,
            presentGpio=True,
            psus=psuClasses,
            forcePsuLoad=True
         )

      port = self.cpu.getPciPort(self.cpu.PCI_PORT_SCD1)
      pscd = port.newComponent(Scd, addr=port.addr)
      self.pscd = pscd

      pscd.addSmbusMasterRange(0x8000, 18, 0x80, 1)

      pscd.newComponent(Tmp75, addr=pscd.i2cAddr(0, 0x4a), sensors=[
         SensorDesc(diode=0, name='Port Card', position=Position.OTHER,
            target=65, overheat=80, critical=95),
      ])

      pscd.addReloadCauseProvider(causes=[
         ScdCause(0x01, ScdCause.OVERTEMP),
         ScdCause(0x20, ScdCause.RAIL, 'P5V0_PGOOD'),
         ScdCause(0x24, ScdCause.RAIL, 'SWITCH_PGOOD'),
         ScdCause(0x25, ScdCause.RAIL, 'P3V3_OPTICS_EN'),
         ScdCause(0x26, ScdCause.RAIL, 'P3V3_OPTICS_PGOOD'),
         ScdCause(0x27, ScdCause.RAIL, 'PC_PGOOD'),
      ], regmap=ScdReloadCauseRegisters,
         priority=ScdCause.Priority.SECONDARY)

      pintrRegs = [
         scd.createInterrupt(addr=0x3000, num=0),
         scd.createInterrupt(addr=0x3030, num=1),
      ]
      pscd.addXcvrSlots(
         ports=self.PORTS.getOsfps(),
         addr=0xA000,
         bus=2,
         ledAddr=0x6104,
         ledAddrOffsetFn=lambda x: 0x10,
         intrRegs=pintrRegs,
         intrRegIdxFn=lambda _: 1,
         intrBitFn=lambda xcvrId: xcvrId - 1,
      )
      pscd.addXcvrSlots(
         ports=self.PORTS.getQsfps(),
         addr=0xA100,
         bus=18,
         ledAddr=0x6200,
         ledAddrOffsetFn=lambda x: 0x10,
         intrRegs=pintrRegs,
         intrRegIdxFn=lambda _: 1,
         intrBitFn=lambda xcvrId: xcvrId - 1,
      )

      port = self.cpu.getPciPort(self.cpu.PCI_PORT_ASIC0)
      self.asic = port.newComponent(Tomahawk5, addr=port.addr,
         coreResets=[
            scd.inventory.getReset('switch_chip_reset'),
         ],
         pcieResets=[
            scd.inventory.getReset('switch_chip_pcie_reset'),
         ],
         quirks=[EcrcPciQuirk()],
      )

      self.syscpld.addReloadCauseProvider(causes=[
         SysCpldCause(0x00, SysCpldCause.UNKNOWN),
         SysCpldCause(0x01, SysCpldCause.OVERTEMP),
         SysCpldCause(0x02, SysCpldCause.SEU),
         SysCpldCause(0x03, SysCpldCause.WATCHDOG,
                      priority=SysCpldCause.Priority.HIGH),
         SysCpldCause(0x04, SysCpldCause.CPU, 'CPU source or CPU PGOOD',
                      priority=SysCpldCause.Priority.LOW),
         SysCpldCause(0x08, SysCpldCause.REBOOT),
         SysCpldCause(0x09, SysCpldCause.POWERLOSS, 'PSU AC'),
         SysCpldCause(0x0a, SysCpldCause.POWERLOSS, 'PSU DC'),
         SysCpldCause(0x0b, SysCpldCause.NOFANS),
         SysCpldCause(0x0f, SysCpldCause.SEU, 'bitshadow rx parity error'),
         SysCpldCause(0x10, SysCpldCause.REBOOT, 'Powercycle via CPLD'),
         SysCpldCause(0x11, SysCpldCause.POWERLOSS, 'Supervisor unseated'),
         SysCpldCause(0x20, SysCpldCause.RAIL, 'P12V_MOD_PG'),
         SysCpldCause(0x21, SysCpldCause.RAIL, 'CPLD_PWR_GOOD'),
         SysCpldCause(0x22, SysCpldCause.RAIL, 'P5V0_PGOOD'),
         SysCpldCause(0x23, SysCpldCause.RAIL, 'P3V3_PGOOD'),
         SysCpldCause(0x24, SysCpldCause.RAIL, 'P2V5_PGOOD'),
         SysCpldCause(0x25, SysCpldCause.RAIL, 'P1V8_PGOOD'),
         SysCpldCause(0x26, SysCpldCause.RAIL, 'P0V8_VDD_PGOOD'),
         SysCpldCause(0x27, SysCpldCause.RAIL, 'P1V2_PGOOD'),
         SysCpldCause(0x28, SysCpldCause.RAIL, 'P1V5_PGOOD'),
         SysCpldCause(0x29, SysCpldCause.RAIL, 'P0V8_PCIE_PGOOD'),
         SysCpldCause(0x2a, SysCpldCause.RAIL, 'P0V75_AVDD_0_PGOOD'),
         SysCpldCause(0x2b, SysCpldCause.RAIL, 'P0V75_AVDD_1_PGOOD'),
         SysCpldCause(0x2c, SysCpldCause.RAIL, 'P0V9_AVDD_0_PGOOD'),
         SysCpldCause(0x2d, SysCpldCause.RAIL, 'P0V9_AVDD_1_PGOOD'),
         SysCpldCause(0x2e, SysCpldCause.RAIL, 'PC_PGOOD'),
      ], regmap=SysCpldReloadCauseRegistersV2)
