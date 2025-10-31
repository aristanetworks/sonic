
from ...core.hwapi import HwApi
from ...core.platform import registerPlatform
from ...core.port import PortLayout
from ...core.quirk import SysfsQuirk
from ...core.types import MdioSpeed
from ...core.utils import incrange

from ...components.asic.dnx.jericho2 import Jericho2
from ...components.denali.desc import DenaliAsicDesc
from ...components.denali.linecard import DenaliLinecard, GpioRegisterMap
from ...components.dpm.ucd import Ucd90320, UcdGpi, UcdMon
from ...components.eeprom import At24C512
from ...components.lm73 import Lm73
from ...components.lm75 import Tmp75
from ...components.max6581 import Max6581
from ...components.pca9555 import Pca9555
from ...components.phy.babbage import Babbage
from ...components.plx import PlxPortDesc
from ...components.tmp464 import Tmp464

from ...descs.sensor import Position, SensorDesc
from ...descs.reset import ResetDesc
from ...descs.xcvr import Qsfp28

class ClearwaterBase(DenaliLinecard):
   SCD_PCI_OFFSET = 3
   XCVR_BUS_OFFSET = 0
   ASICS = [
      DenaliAsicDesc(cls=Jericho2, asicId=0, rstIdx=1),
   ]

   STANDBY_TEMP_SENSORS_CLS = Lm73
   GPIO1_CLS = Pca9555
   PHY_CLS = Babbage

   PLX_PORTS = [
      PlxPortDesc(port=0, name='sup1', upstream=True),
      PlxPortDesc(port=2, name='sup2', upstream=True),
      PlxPortDesc(port=3, name='je0'),
      PlxPortDesc(port=5, name='scd'),
   ]

   PORTS = PortLayout(
      (Qsfp28(i) for i in incrange(1, 48)),
   )

   def createPorts(self):
      intrRegs = [self.scd.getInterrupt(intId) for intId in incrange(0, 6)]
      # IRQ2 -> port 32:1 (bit 31:0)
      # IRQ3 -> port 48:33 (bit 15:0)
      self.scd.addXcvrSlots(
         ports=self.PORTS.getQsfps(),
         addr=0xA010,
         bus=self.XCVR_BUS_OFFSET,
         ledAddr=0x6100,
         intrRegs=intrRegs,
         intrRegIdxFn=lambda xcvrId: xcvrId // 32 + 2,
         intrBitFn=lambda xcvrId: (xcvrId - 1) % 32,
         isHwModSelAvail=False,
      )

      self.scd.addMdioMasterRange(0x9000, 12, speed=MdioSpeed.S10)

      for i in range(12):
         phyId = i + 1
         resetDesc = ResetDesc('phy%d_reset' % phyId, addr=0x4000, bit=8 + i)
         reset = self.scd.addReset(resetDesc)
         mdios = [self.scd.addMdio(i, 0), self.scd.addMdio(i, 1)]
         phy = self.PHY_CLS(phyId, mdios, reset=reset)
         self.inventory.addPhy(phy)

   def cwMainDomainCommon(self):
      self.scd.addSmbusMasterRange(0x8000, 14, spacing=0x80)

      for intId in incrange(0, 6):
         addr = 0x3000 + intId * 0x30
         self.scd.createInterrupt(addr=addr, num=intId)

      scdPort = self.scd.addr.port.upstream
      scdPort.quirks.extend([
         SysfsQuirk("aer/correctable_ratelimit_interval_ms", "60000",
                    "Suppress excessive SCD correctable errors"),
         SysfsQuirk("aer/correctable_ratelimit_burst", "1",
                    "Suppress excessive SCD correctable errors")
      ])

      # At the moment there is no unique name for objects added to the kernel such
      # as leds, mdios, ... As a result, the kernel does some renaming, which is
      # not handled by the platform library. Until we have support for something
      # like slot prefixes for kernel objects, we only create the ports in LCPU
      # mode.
      if self.cpu:
         self.createPorts()
         self.cpu.addScdComponents(self.scd)

   def mainDomain(self):
      self.cwMainDomainCommon()

   def cwStandbyDomainCommon(self):
      bus = self.pca

      if self.STANDBY_TEMP_SENSORS_CLS:
         # The front sensor is currently defined as INLET because we don't have
         # sensor data from the LSI. The position should be changed to OTHER.
         self.pca.newComponent(self.STANDBY_TEMP_SENSORS_CLS, addr=bus.i2cAddr(0x49),
                               sensors=[
            SensorDesc(diode=0, name='Front', position=Position.INLET,
                       target=65, overheat=75, critical=85),
         ])
         self.pca.newComponent(self.STANDBY_TEMP_SENSORS_CLS, addr=bus.i2cAddr(0x4a),
                               sensors=[
            SensorDesc(diode=0, name='Mid', position=Position.OTHER,
                       target=80, overheat=90, critical=95),
         ])
         self.pca.newComponent(self.STANDBY_TEMP_SENSORS_CLS, addr=bus.i2cAddr(0x48),
                               sensors=[
            SensorDesc(diode=0, name='Back', position=Position.OTHER,
                       target=80, overheat=90, critical=95),
         ])

   def standbyDomain(self):
      super(ClearwaterBase, self).standbyDomain()
      self.cwStandbyDomainCommon()

   def gpio1Addr(self):
      return 0x74

   def createGpio1(self):
      addr = self.pca.i2cAddr(self.gpio1Addr())
      self.gpio1 = self.pca.newComponent(self.GPIO1_CLS, addr=addr,
                                          registerCls=GpioRegisterMap)

   def createStandbyDpm(self):
      self.control.newComponent(Ucd90320, addr=self.pca.i2cAddr(0x11), causes=[
         UcdGpi(4, 'hotswap', 'lc eject'),
         UcdGpi(5, 'asic-overtemp'),
         UcdGpi(6, 'overtemp', 'system'),
         UcdGpi(7, 'watchdog', 'lcpu'),
         UcdGpi(8, 'mem-overtemp', 'asic memory'),
         UcdGpi(10, 'reboot'),
         UcdGpi(12, 'over-current', 'asic'),
         UcdMon(14, 'powerloss'),
      ])


@registerPlatform()
class Clearwater(ClearwaterBase):
   SID = ['Clearwater']
   SKU = ['7800R-48QC-LC', '7800R3-48CQ-LC']

   MAX_POWER_DRAW = 462
   TYP_POWER_DRAW = 398

   SCD_PCI_OFFSET = 3
   ASIC_PCI_OFFSET = {0 : 2}

   def daughterCardBusId(self, cardId):
      return 10 + cardId

   def daughterCardSensorCls(self):
      return Lm73 if self.getHwApi() < HwApi(45) else Tmp464

   def daughterCardSensorAddr(self, busId, cardId):
      addrs = [0x49, 0x48] if self.getHwApi() < HwApi(45) else [0x48, 0x49]
      return self.scd.i2cAddr(self.daughterCardBusId(cardId), addrs[cardId])

   def createDaughterCard(self, cardId):
      busId = self.daughterCardBusId(cardId)

      self.scd.newComponent(self.daughterCardSensorCls(),
                            self.daughterCardSensorAddr(busId, cardId),
                            sensors=[
         SensorDesc(diode=0, name='Daugthercard %d' % cardId,
                    position=Position.OTHER, target=75, overheat=85, critical=95),
      ])

      self.scd.newComponent(At24C512, self.scd.i2cAddr(busId, 0x52 + cardId),
                            label='card%d_daughter%d' % (self.slot.slotId, cardId))

   def mainDomain(self):
      self.cwMainDomainCommon()

      self.scd.newComponent(Max6581, self.scd.i2cAddr(8, 0x4d), sensors=[
         SensorDesc(diode=1, name='Board sensor 1', position=Position.OTHER,
                    target=75, overheat=85, critical=95),
         SensorDesc(diode=4, name='Fap0 core1', position=Position.OTHER,
                    target=85, overheat=100, critical=105),
         SensorDesc(diode=5, name='Fap0 core0', position=Position.OTHER,
                    target=85, overheat=100, critical=105),
      ])
      self.scd.newComponent(Max6581, self.scd.i2cAddr(9, 0x4d), sensors=[
         SensorDesc(diode=2, name='Fap0 PCB', position=Position.OTHER,
                    target=85, overheat=100, critical=105),
         SensorDesc(diode=7, name='PCIE', position=Position.OTHER,
                    target=75, overheat=85, critical=95),
      ])

      self.createDaughterCard(0)
      self.createDaughterCard(1)

   def gpio1Addr(self):
      return 0x20 if self.getHwApi() < HwApi(45) else 0x74

@registerPlatform()
class ClearwaterMs(Clearwater):
   SID = ['ClearwaterMs']
   SKU = ['7800R3-48CQM-LC', '7800R-48QCM-LC']

   MAX_POWER_DRAW = 684
   TYP_POWER_DRAW = 620

   # ClearwaterMs doesn't have the temps sensors on the standby domain
   STANDBY_TEMP_SENSORS_CLS = None

   def gpio1Addr(self):
      return 0x74

   def daughterCardSensorCls(self):
      return Tmp75

   def daughterCardSensorAddr(self, busId, cardId):
      return self.scd.i2cAddr(self.daughterCardBusId(cardId), 0x48 + cardId)
