from ..core.cooling import CoolingConfig, CoolingLogicIncPid
from ..core.fixed import FixedSystem
from ..core.hwapi import HwApi
from ..core.platform import registerPlatform
from ..core.port import PortLayout
from ..core.psu import PsuSlot
from ..core.quirk import Quirk
from ..core.utils import incrange

from ..components.asic.xgs.tomahawk5 import Tomahawk5
from ..components.cpld import SysCpldReloadCauseRegistersV2, SysCpldCause
from ..components.lm75 import Tmp75
from ..components.max6581 import Max6581
from ..components.psu.delta import ECD1502005
from ..components.scd import Scd
from ..components.vrm.raa228228 import Raa228926

from ..descs.gpio import GpioDesc
from ..descs.reset import ResetDesc
from ..descs.sensor import Position, SensorDesc
from ..descs.xcvr import Osfp, QsfpDD, Sfp

from .chassis.maunakea import MaunaKea2
from .cpu.shearwater import ShearwaterCpu

class QuicksilverRaaQuirk(Quirk):
   def __init__(self):
      self.model = [0x03, 0x50, 0x19, 0x00]
      self.rev = [0xa0, 0x0, 0x0, 0x0]

   def __str__(self):
      return 'Update TH5_Core config'

   def _dmaWrite(self, component, addr, value):
      component.driver.write_bytes([
         0xc7,
         addr & 0xff,
         (addr >> 8) & 0xff,
      ])
      component.driver.write_bytes([
         0xc5,
         value & 0xff,
         (value >> 8) & 0xff,
         (value >> 16) & 0xff,
         (value >> 24) & 0xff,
      ])
      component.driver.read_bytes([0xc5], 4)

   def run(self, component):
      if self.model != component.driver.read_block_data(0x9a) or \
         self.rev != component.driver.read_block_data(0x9b):
         return

      component.driver.write_byte_data(0x00, 0x00)

      uvBefore = component.driver.read_byte_data(0x45)
      component.driver.write_byte_data(0x45, 0x04)

      self._dmaWrite(component, 0xE0E0, 0x00009B53)
      self._dmaWrite(component, 0xE0DD, 0xA70907C4)
      self._dmaWrite(component, 0xE028, 0x00000006)
      self._dmaWrite(component, 0xEA27, 0xE80E8682)
      self._dmaWrite(component, 0xEA24, 0x00000660)
      self._dmaWrite(component, 0xEA30, 0x00000802)

      component.driver.send_byte(0x03)
      component.driver.write_byte_data(0x45, uvBefore)

class QuicksilverBase(FixedSystem):

   CHASSIS = MaunaKea2
   CPU_CLS = ShearwaterCpu
   LED_FP_TRICOLOR = True

   HAS_TH5_EXT_DIODE = True

   COOLING = CoolingConfig(
      logic=CoolingLogicIncPid,
      kp=9,
      ki=0.75,
      kd=0,
      negHyst=0,
      posHyst=0,
   )

   def __init__(self):
      super().__init__()

      self.cpu = self.newComponent(self.CPU_CLS)
      self.syscpld = self.cpu.syscpld

      port = self.cpu.getPciPort(self.cpu.PCI_PORT_SCD0)
      scd = port.newComponent(Scd, addr=port.addr)
      self.scd = scd
      scd.setMsiRearmOffset(0x180)
      scd.createWatchdog()
      scd.addSmbusMasterRange(0x8000, 11, 0x80)

      scd.newComponent(Max6581, addr=scd.i2cAddr(8, 0x4d), sensors=[
         SensorDesc(diode=0, name='Switch Card temp sensor',
                    position=Position.OTHER, target=85, overheat=95, critical=105),
         SensorDesc(diode=1, name='Air Exit Behind TH5',
                    position=Position.OTHER, target=85, overheat=95, critical=105),
         SensorDesc(diode=2, name='Left Edge PCB Near Rear of Switch',
                    position=Position.OTHER, target=85, overheat=95, critical=105),
         SensorDesc(diode=3, name='Air Inlet',
                    position=Position.INLET, target=85, overheat=95, critical=105),
      ] + ([
         SensorDesc(diode=6, name='TH5 Diode 1',
                    position=Position.OTHER, target=90, overheat=115, critical=125),
         SensorDesc(diode=7, name='TH5 Diode 2',
                    position=Position.OTHER, target=90, overheat=115, critical=125),
      ] if self.HAS_TH5_EXT_DIODE else []))

      if self.getHwApi() >= HwApi(2): # Kona
         scd.newComponent(Tmp75, addr=scd.i2cAddr(13, 0x48), sensors=[
            SensorDesc(diode=0, name='Management Card Inlet',
                       position=Position.INLET, target=85, overheat=95,
                       critical=105),
         ])

      scd.addLeds([
         (0x6050, 'status'),
         (0x6060, 'fan_status'),
         (0x6070, 'psu_status'),
         (0x6090, 'beacon'),
         (0x60A0, 'scm')
      ])

      scd.addResets([
         ResetDesc('switch_chip_pcie_reset', addr=0x4000, bit=3, auto=False),
         ResetDesc('switch_chip_reset', addr=0x4000, bit=2, auto=False),
      ])

      scd.addGpios([
         GpioDesc("psu1_present", addr=0x5000, bit=0, ro=True),
         GpioDesc("psu2_present", addr=0x5000, bit=1, ro=True),
         GpioDesc("psu1_status", addr=0x5000, bit=8, ro=True),
         GpioDesc("psu2_status", addr=0x5000, bit=9, ro=True),
         GpioDesc("psu1_ac_status", addr=0x5000, bit=10, ro=True),
         GpioDesc("psu2_ac_status", addr=0x5000, bit=11, ro=True),
      ])

      intrRegs = [
         scd.createInterrupt(addr=0x3000, num=0),
         scd.createInterrupt(addr=0x3030, num=1),
         scd.createInterrupt(addr=0x3060, num=2),
         scd.createInterrupt(addr=0x3090, num=3),
      ]

      scd.addXcvrSlots(
         ports=self.PORTS.getOsfps(),
         addr=0xA000,
         bus=24,
         ledAddr=0x6104,
         ledAddrOffsetFn=lambda x: 0x10,
         intrRegs=intrRegs,
         intrRegIdxFn=lambda xcvrId: xcvrId // 33 + 1,
         intrBitFn=lambda xcvrId: (xcvrId - 1) % 32,
      )

      scd.addXcvrSlots(
         ports=self.PORTS.getSfps(),
         addr=0xA900,
         bus=88,
         ledAddr=0x6900,
         ledAddrOffsetFn=lambda x: 0x40,
         # no interrupts
      )

      for psuId, bus in [(1, 11), (2, 12)]:
         addrFunc=lambda addr, bus=bus: \
                  self.scd.i2cAddr(bus, addr, t=3, datr=2, datw=3)
         name = "psu%d" % psuId
         self.scd.newComponent(
            PsuSlot,
            slotId=psuId,
            addrFunc=addrFunc,
            presentGpio=self.scd.inventory.getGpio("%s_present" % name),
            inputOkGpio=self.scd.inventory.getGpio("%s_ac_status" % name),
            outputOkGpio=self.scd.inventory.getGpio("%s_status" % name),
            psus=[
               ECD1502005,
            ],
         )

      scd.newComponent(Raa228926, addr=scd.i2cAddr(16, 0x45),
                       quirks=[QuicksilverRaaQuirk()])

      port = self.cpu.getPciPort(self.cpu.PCI_PORT_ASIC0)
      self.asic = port.newComponent(Tomahawk5, addr=port.addr,
         coreResets=[
            scd.inventory.getReset('switch_chip_reset'),
         ],
         pcieResets=[
            scd.inventory.getReset('switch_chip_pcie_reset'),
         ],
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
         SysCpldCause(0x0f, SysCpldCause.SEU, 'bitshadow rx parity error'),
         SysCpldCause(0x10, SysCpldCause.REBOOT, 'Software Reboot via CPLD'),
         SysCpldCause(0x11, SysCpldCause.POWERLOSS, 'Supervisor unseated'),
         SysCpldCause(0x20, SysCpldCause.RAIL, 'CPLD_PWR_FAULT'),
         SysCpldCause(0x21, SysCpldCause.RAIL, 'POS5V0_FAULT'),
         SysCpldCause(0x22, SysCpldCause.RAIL, 'POS3V3_FAULT'),
         SysCpldCause(0x23, SysCpldCause.RAIL, 'POS2V5_FAULT'),
         SysCpldCause(0x24, SysCpldCause.RAIL, 'POS1V8_FAULT'),
         SysCpldCause(0x25, SysCpldCause.RAIL, 'POS0V8_VDD_FAULT'),
         SysCpldCause(0x26, SysCpldCause.RAIL, 'POS1V2_FAULT'),
         SysCpldCause(0x27, SysCpldCause.RAIL, 'POS1V5_FAULT'),
         SysCpldCause(0x28, SysCpldCause.RAIL, 'POS0V8_PCIE_FAULT'),
         SysCpldCause(0x29, SysCpldCause.RAIL, 'POS0V75_AVDD_0_FAULT'),
         SysCpldCause(0x2a, SysCpldCause.RAIL, 'POS0V75_AVDD_1_FAULT'),
         SysCpldCause(0x2b, SysCpldCause.RAIL, 'POS0V9_AVDD_0_FAULT'),
         SysCpldCause(0x2c, SysCpldCause.RAIL, 'POS0V9_AVDD_1_FAULT'),
         SysCpldCause(0x2d, SysCpldCause.RAIL, 'POS3V3_OPTICS_A_FAULT'),
         SysCpldCause(0x2e, SysCpldCause.RAIL, 'POS3V3_OPTICS_B_FAULT'),
      ], regmap=SysCpldReloadCauseRegistersV2)

@registerPlatform()
class QuicksilverDd(QuicksilverBase):
   SID = [
      'Shearwater4Mk2',
      'Shearwater4Mk2QuicksilverDD',
      'Shearwater4Mk2N',
      'Shearwater4Mk2NQuicksilverDD',
   ]
   SKU = ['DCS-7060X6-64DE']

   PORTS = PortLayout(
      (QsfpDD(i) for i in incrange(1, 64)),
      (Sfp(i) for i in incrange(65, 66)),
   )

@registerPlatform()
class QuicksilverP(QuicksilverBase):
   SID = [
      'Shearwater4Mk2QuicksilverP',
      'Shearwater4Mk2NQuicksilverP',
   ]
   SKU = ['DCS-7060X6-64PE']

   PORTS = PortLayout(
      (Osfp(i) for i in incrange(1, 64)),
      (Sfp(i) for i in incrange(65, 66)),
   )
