import os
import time

from ..core.component.i2c import I2cByteQuirk
from ..core.fixed import FixedSystem
from ..core.hwapi import HwApi
from ..core.log import getLogger
from ..core.platform import registerPlatform
from ..core.port import PortLayout
from ..core.psu import PsuSlot
from ..core.quirk import Quirk
from ..core.utils import incrange

from ..components.asic.xgs.tomahawk6 import Tomahawk6
from ..components.dpm.ucd import Ucd90320, UcdGpi, UcdPriority
from ..components.lm75 import Tmp75
from ..components.max6581 import Max6581
from ..components.pca954x import Pca9548
from ..components.psu.arista import Pwr591
from ..components.psu.delta import ECD1502005
from ..components.psu.liteon import LiteOn2400HV
from ..components.scd import Scd
from ..components.vrm.tda38740 import Tda38740a, Xdpe1a2g5b, Xdpe1b284b

from ..descs.cause import ReloadCauseDesc, ReloadCauseAltSource
from ..descs.gpio import GpioDesc
from ..descs.led import LedDesc, LedKind
from ..descs.rail import RailDesc, RailDirection, VoltageDesc
from ..descs.reset import ResetDesc
from ..descs.sensor import Position, SensorDesc
from ..descs.xcvr import Osfp1600, Qsfp28

from .chassis.canvas import Canvas
from .cpu.thrasher import ThrasherCpu

logging = getLogger(__name__)

OSFP_TRICOLOR_LED = {'defaultLed': '%s:rgb:a', 'leds': [
    LedDesc(addr=0x00, name='%s:rgb:a', **LedKind.desc(LedKind.RGB_8_F)),
    LedDesc(addr=0x10, name='%s:rgb:b', **LedKind.desc(LedKind.RGB_8_F)),
]}

QSFP_TRICOLOR_LED = {'defaultLed': '%s:rgb:a', 'leds': [
    LedDesc(addr=0x00, name='%s:rgb:a', **LedKind.desc(LedKind.RGB_8_F)),
    LedDesc(addr=0x10, name='%s:rgb:b', **LedKind.desc(LedKind.RGB_8_F)),
    LedDesc(addr=0x20, name='%s:rgb:c', **LedKind.desc(LedKind.RGB_8_F)),
    LedDesc(addr=0x30, name='%s:rgb:d', **LedKind.desc(LedKind.RGB_8_F)),
]}

class AsicPcieResetQuirk(Quirk):
   description = "Toggle ASIC PCIe Reset if the ASIC is not enumerated"
   when = Quirk.When.RESET

   def run(self, component):
      if component.isOutOfReset() and os.path.exists(component.addr.getSysfsPath()):
         return

      logging.debug("%s: not enumerated, toggling pcie resets.", component)
      for reset in component.pcieResets:
         reset.resetIn()
      time.sleep(component.pcieResetDelay / 1000.)
      for reset in component.pcieResets:
         reset.resetOut()

class BanffBase(FixedSystem):

   CHASSIS = Canvas
   CPU_CLS = ThrasherCpu

   def __init__(self):
      super().__init__()
      self.artix50T = self._hasArtix50T()

      self.cpu = self.newComponent(self.CPU_CLS)
      self.syscpld = self.cpu.syscpld

      self.cpu.cpld.newComponent(
         Ucd90320,
         addr=self.cpu.getSmbus(self.cpu.SMBUS_PWR).i2cAddr(0x11),
         causes=[
            UcdGpi(1, ReloadCauseDesc.UNKNOWN, 'Card Unseated'),
            UcdGpi(2, ReloadCauseDesc.CPU,
                   altSource=ReloadCauseAltSource.CPU),
            UcdGpi(3, ReloadCauseDesc.WATCHDOG),
            UcdGpi(4, ReloadCauseDesc.POWERLOSS, 'Input Power Loss'),
            UcdGpi(5, ReloadCauseDesc.OVERTEMP),
            UcdGpi(6, ReloadCauseDesc.SEU, 'SCD SEU'),
         ], rails=[
            RailDesc(railId=1, name='POS12V', expectedVoltage=12.2),
            RailDesc(railId=2, name='POS3V3', expectedVoltage=3.3),
            RailDesc(railId=3, name='POS1V8_0', expectedVoltage=1.8),
            RailDesc(railId=4, name='POS0V75_TRVDD_0', expectedVoltage=0.75),
            RailDesc(railId=5, name='POS0V75_TRVDD_1', expectedVoltage=0.75),
            RailDesc(railId=6, name='POS0V9_TRVDD_0', expectedVoltage=0.9),
            RailDesc(railId=7, name='POS0V9_TRVDD_1', expectedVoltage=0.9),
            RailDesc(railId=8, name='POS1V5_RVDD_0', expectedVoltage=1.5),
            RailDesc(railId=9, name='POS1V5_RVDD_1', expectedVoltage=1.5),
            RailDesc(railId=10, name='POS3V3_OSFP_LEFT', expectedVoltage=3.4),
            RailDesc(railId=11, name='POS3V3_OSFP_RIGHT', expectedVoltage=3.4),
            RailDesc(railId=12, name='POS5V0', expectedVoltage=5.0),
            RailDesc(railId=13, name='POS0V75_CORE', expectedVoltage=0.75),
            RailDesc(railId=14, name='POS0V75_PHYCORE_0', expectedVoltage=0.75),
            RailDesc(railId=15, name='POS0V72_TRVDD_7', expectedVoltage=0.72),
            RailDesc(railId=16, name='POS3V3_RUNDLE', expectedVoltage=3.3),
            RailDesc(railId=17, name='POS5V0_SNOW_FRONT', expectedVoltage=5.0),
            RailDesc(railId=18, name='POS3V3_SNOW_FRONT', expectedVoltage=3.3),
            RailDesc(railId=19, name='POS5V0_SUNDANCE', expectedVoltage=5.0),
            RailDesc(railId=20, name='POS3V3_SUNDANCE', expectedVoltage=3.3),
            RailDesc(railId=21, name='POS5V0_SUNSHINE_LEFT', expectedVoltage=5.0),
            RailDesc(railId=22, name='POS3V3_SUNSHINE_LEFT', expectedVoltage=3.3),
            RailDesc(railId=23, name='POS5V0_SUNSHINE_RIGHT', expectedVoltage=5.0),
            RailDesc(railId=24, name='POS3V3_SUNSHINE_RIGHT', expectedVoltage=3.3),
         ], causePriority=UcdPriority.HARDWARE_MAIN
      )

      scd0SmbusCount = 8
      scd1SmbusCount = 7
      smbusSpacing = 0x80
      bus = 4
      if self.artix50T:
         scd0SmbusCount = 31
         scd1SmbusCount = 31
         smbusSpacing = 0x40
         bus = 1

      scd0 = self._createScd(self.cpu.PCI_PORT_SCD0, scd0SmbusCount,
                             smbusSpacing, bus)
      if self.artix50T:
         scd0.addSmbusMaster(0x8000 + 32 * smbusSpacing, 32, 4)
      self.scd0 = scd0

      scd1 = self._createScd(self.cpu.PCI_PORT_SCD1, scd1SmbusCount,
                             smbusSpacing, bus)
      self.scd1 = scd1

      self.cpu.cpld.newComponent(
          Max6581,
          addr=self.cpu.getSmbus(self.cpu.SMBUS_SC).i2cAddr(0x4d),
          sensors=[
              SensorDesc(diode=0, name='Board Front Bottom',
                         position=Position.OTHER,
                         target=70, overheat=80, critical=90),
              SensorDesc(diode=1, name='TH6 on-die sensor 1',
                         position=Position.OTHER,
                         target=100, overheat=105, critical=115),
              SensorDesc(diode=2, name='TH6 on-die sensor 2',
                         position=Position.OTHER,
                         target=100, overheat=105, critical=115),
              SensorDesc(diode=4, name='Banff Board Front 1',
                         position=Position.INLET,
                         target=70, overheat=80, critical=90),
              SensorDesc(diode=5, name='Banff Board Front 2',
                         position=Position.INLET,
                         target=70, overheat=80, critical=90),
              SensorDesc(diode=6, name='Banff Board Rear 1',
                         position=Position.OTHER,
                         target=70, overheat=80, critical=90),
              SensorDesc(diode=7, name='Banff Board Rear 2',
                         position=Position.OTHER,
                         target=70, overheat=80, critical=90),
          ],
          quirks=[
              I2cByteQuirk(0x4b, 0x1f, "TH6 Diode Transistor Ideality config"),
              I2cByteQuirk(0x4c, 0x3, "TH6 Diode Ideality Select config"),
          ]
      )

      self.cpu.cpld.newComponent(
          Max6581,
          addr=self.cpu.getSmbus(self.cpu.SMBUS_POL).i2cAddr(0x4d),
          sensors=[
              SensorDesc(diode=0, name='Power Board 1',
                         position=Position.OTHER,
                         target=70, overheat=80, critical=90),
              SensorDesc(diode=1, name='Power Board 2',
                         position=Position.OTHER,
                         target=70, overheat=80, critical=90),
              SensorDesc(diode=2, name='Power Board 3',
                         position=Position.OTHER,
                         target=70, overheat=80, critical=90),
              SensorDesc(diode=4, name='Power Board 4',
                         position=Position.INLET,
                         target=70, overheat=80, critical=90),
              SensorDesc(diode=5, name='Power Board 5',
                         position=Position.INLET,
                         target=70, overheat=80, critical=90),
              SensorDesc(diode=6, name='Power Board 6',
                         position=Position.OTHER,
                         target=70, overheat=80, critical=90),
              SensorDesc(diode=7, name='Power Board 7',
                         position=Position.OTHER,
                         target=70, overheat=80, critical=90),
          ]
      )

      if self.getHwApi() >= HwApi(3):
         self.cpu.cpld.newComponent(
             Tmp75,
             addr=self.cpu.getSmbus(self.cpu.SMBUS_FC).i2cAddr(0x48),
             sensors=[
                 SensorDesc(diode=0, name='Secondary Inlet Sensor',
                            position=Position.INLET,
                            target=55, overheat=65, critical=75),
             ],
         )

      vrms = [
         (Xdpe1a2g5b, 0x70, ['POS0V75_CORE']),
         (Xdpe1b284b, 0x58, ['POS0V75_PHYCORE_0', 'POS0V75_PHYCORE_1']),
         (Xdpe1b284b, 0x5a, ['POS0V75_PHYCORE_2', 'POS0V75_PHYCORE_3']),
         (Xdpe1b284b, 0x5c, ['POS0V75_PHYCORE_4', 'POS0V75_PHYCORE_5']),
         (Xdpe1b284b, 0x5e, ['POS0V75_PHYCORE_6', 'POS0V75_PHYCORE_7']),
         (Xdpe1b284b, 0x60, ['POS0V72_TRVDD_0', 'POS0V72_TRVDD_1']),
         (Xdpe1b284b, 0x62, ['POS0V72_TRVDD_2', 'POS0V72_TRVDD_3']),
         (Xdpe1b284b, 0x64, ['POS0V72_TRVDD_4', 'POS0V72_TRVDD_5']),
         (Xdpe1b284b, 0x66, ['POS0V72_TRVDD_6', 'POS0V72_TRVDD_7']),
         (Xdpe1b284b, 0x68, ['POS0V75_TRVDD_0', 'POS0V75_TRVDD_1']),
         (Xdpe1b284b, 0x6a, ['POS0V9_TRVDD_0', 'POS0V9_TRVDD_1']),
         (Tda38740a, 0x48, ['POS1V5_RVDD_0']),
         (Tda38740a, 0x49, ['POS1V5_RVDD_1']),
         (Xdpe1a2g5b, 0x72, ['POS3V3_OPTICS_LEFT']),
         (Xdpe1a2g5b, 0x74, ['POS3V3_OPTICS_RIGHT']),
      ]
      voltScaleFactor = {
         'POS3V3_OPTICS_LEFT': 2.071,
         'POS3V3_OPTICS_RIGHT': 2.071
      }
      vrmTempParams = {
         'target': 105,
         'overheat': 115,
         'critical': 125
      }
      polSmbus = self.cpu.getSmbus(self.cpu.SMBUS_POL)
      for cls, addr, sensors in vrms:
         self.cpu.cpld.newComponent(
            cls,
            addr=polSmbus.i2cAddr(addr),
            sensors=[
               SensorDesc(diode=diodeId, name=name, **vrmTempParams) \
               for diodeId, name in enumerate(sensors)
            ],
            rails=[
               RailDesc(railId=railId,
                        name=name,
                        direction=RailDirection.OUTPUT,
                        rated=False,
                        voltage=VoltageDesc(voltId=railId,
                                            name=name,
                                            direction=RailDirection.OUTPUT,
                                            scale=voltScaleFactor.get(name, 1),
                                            rated=False)) \
               for railId, name in enumerate(sensors, start=1)
            ]
         )

      scd0.addResets([
         ResetDesc('switch_chip_pcie_reset', addr=0x4000, bit=1, auto=False),
         ResetDesc('switch_chip_reset', addr=0x4000, bit=0, auto=False),
      ])

      scd0.addGpios([
         GpioDesc("psu1_present", addr=0x5000, bit=0, ro=True),
         GpioDesc("psu2_present", addr=0x5000, bit=1, ro=True),
         GpioDesc("psu3_present", addr=0x5000, bit=2, ro=True),
         GpioDesc("psu4_present", addr=0x5000, bit=3, ro=True),
         GpioDesc("psu1_output_ok", addr=0x5000, bit=8, ro=True),
         GpioDesc("psu2_output_ok", addr=0x5000, bit=9, ro=True),
         GpioDesc("psu3_output_ok", addr=0x5000, bit=10, ro=True),
         GpioDesc("psu4_output_ok", addr=0x5000, bit=11, ro=True),
         GpioDesc("psu1_present_changed", addr=0x5000, bit=12),
         GpioDesc("psu2_present_changed", addr=0x5000, bit=13),
         GpioDesc("psu3_present_changed", addr=0x5000, bit=14),
         GpioDesc("psu4_present_changed", addr=0x5000, bit=15),
      ])

      intrRegs0 = [
         scd0.createInterrupt(addr=0x3000, num=0),
         scd0.createInterrupt(addr=0x3030, num=1),
      ]
      if self.artix50T:
         intrRegs0.append(scd0.createInterrupt(addr=0x3060, num=2))

      self.intrRegs0 = intrRegs0

      intrRegs1 = [
         scd1.createInterrupt(addr=0x3000, num=0),
         scd1.createInterrupt(addr=0x3030, num=1),
      ]
      if self.artix50T:
         intrRegs1.append(scd1.createInterrupt(addr=0x3060, num=2))

      self.intrRegs1 = intrRegs1

      scd0.createWatchdog(intr=scd0.getInterrupt(0), bit=13)

      self._createXcvr()

      self.pca = self.cpu.cpld.newComponent(
          Pca9548,
          addr=self.cpu.getSmbus(self.cpu.SMBUS_PWR).i2cAddr(0x75),
      )

      for psuId in range(1, self.CHASSIS.PSU_SLOTS + 1):
         psuBus = self.pca.getBus(psuId - 1)
         name = "psu%d" % psuId
         self.cpu.cpld.newComponent(
            PsuSlot,
            slotId=psuId,
            addrFunc=psuBus.i2cAddr,
            presentGpio=self.scd0.inventory.getGpio("%s_present" % name),
            outputOkGpio=self.scd0.inventory.getGpio("%s_output_ok" % name),
            psus=[
               ECD1502005,
               Pwr591,
               LiteOn2400HV,
            ],
         )

      port = self.cpu.getPciPort(self.cpu.PCI_PORT_ASIC0)
      self.asic = port.newComponent(Tomahawk6, addr=port.addr,
         qspiAddr=scd0.i2cAddr(32, 0x44),
         coreResets=[
            scd0.inventory.getReset('switch_chip_reset'),
         ],
         pcieResets=[
            scd0.inventory.getReset('switch_chip_pcie_reset'),
         ],
         quirks=[
             AsicPcieResetQuirk(),
         ],
      )

   def _createScd(self, pciPort, smbusCount, smbusSpacing, bus):
      port = self.cpu.getPciPort(pciPort)
      scd = port.newComponent(Scd, addr=port.addr)
      scd.setMsiRearmOffset(0x180)
      scd.addSmbusMasterRange(0x8000, smbusCount, smbusSpacing, bus)
      scd.ledFlashCtrlAddr = 0x60E0
      return scd

   def _createXcvr(self):
      for scdIdx, (scd, intrs) in enumerate((
          (self.scd0, self.intrRegs0),
          (self.scd1, self.intrRegs1),
      )):
         ports = [p for p in self.PORTS.getOsfps() if p.scd == scdIdx]
         id2bit = {p.index : i for i, p in enumerate( ports )}
         scd.addXcvrSlots(
            ports=ports,
            addr=0xA010,
            intrRegs=intrs,
            bus=0,
            ledAddr=0x6100,
            intrRegIdxFn=lambda xcvrId: 1,
            intrBitFn=lambda xcvrId, id2bit=id2bit: id2bit[xcvrId],
         )

      self.scd0.addXcvrSlots(
         ports=self.PORTS.getQsfps(),
         addr=0xA210,
         bus=34,
         ledAddr=0x6500,
         intrRegs=self.intrRegs0,
         intrRegIdxFn=lambda xcvrId: 0,
         intrBitFn=lambda xcvrId: 26,
      )

   def _hasArtix50T(self):
      return self.getHwApi() >= HwApi(4)

@registerPlatform()
class BanffP(BanffBase):
   SID = [
      'Banff',
      'ThrasherBanff',
      'Thrasher',
      'ThrasherBBanff',
   ]
   SKU = ['DCS-7060XE7-64PS', '7060XE7-64PS']

   PORTS = PortLayout(
      (Osfp1600(i, scd=(((i - 1) // 4) % 2), **OSFP_TRICOLOR_LED)
       for i in incrange(1, 64)),
      (Qsfp28(65, **QSFP_TRICOLOR_LED),),
   )
