from ..core.cooling import CoolingConfig, CoolingLogicIncPid
from ..core.fixed import FixedSystem
from ..core.platform import registerPlatform
from ..core.port import PortLayout
from ..core.psu import PsuSlot
from ..core.utils import incrange

from ..components.asic.xgs.tomahawk6 import Tomahawk6
from ..components.cpld import SysCpld
from ..components.dpm.ucd import Ucd90320, UcdGpi, UcdMon, UcdPriority
from ..components.lm75 import Tmp75
from ..components.pca954x import Pca9548
from ..components.psu.ecb import createPmbusECB, Tps16890
from ..components.scd import Scd
from ..components.tmp401 import Tmp431
from ..components.vrm.ibc import Pwr689
from ..components.vrm.tda38740 import Xdpe1a2g5b, Xdpe1b284b, Tda38740a

from ..descs.cause import ReloadCauseDesc
from ..descs.led import LedDesc, LedKind
from ..descs.psu import PsuStatusPolicy
from ..descs.reset import ResetDesc
from ..descs.sensor import Position, SensorDesc
from ..descs.xcvr import Osfp1600, Qsfp28

from .cpu.marconi import MarconiCpu

OSFP_TRICOLOR_LED = {'defaultLed': '%s:rgb:1', 'leds': [
   LedDesc(addr=0, name='%s:rgb:1', **LedKind.desc(LedKind.RGB_8_F)),
   LedDesc(addr=16, name='%s:rgb:2', **LedKind.desc(LedKind.RGB_8_F)),
]}
QSFP_TRICOLOR_LED = {'defaultLed': '%s:rgb:1', 'leds': [
   LedDesc(addr=0, name='%s:rgb:1', **LedKind.desc(LedKind.RGB_8_F)),
]}

class Windsurf(object):
   '''
   Windsurf rear board which contains power and leak detection circuitry.
   '''
   def __init__(self, cpu, psuSlotId):
      fcBus = cpu.getSmbus(cpu.SMBUS_FC)
      cpu.cpld.newComponent(
         Tmp75,
         addr=fcBus.i2cAddr(0x48),
         sensors=[
            SensorDesc(diode=0, name='Rear card', position=Position.OUTLET,
                       target=75, overheat=80, critical=85),
         ]
      )

      # ECB connected to 48V bus bar
      cpu.cpld.newComponent(
         PsuSlot,
         slotId=psuSlotId,
         addrFunc=fcBus.i2cAddr,
         presentGpio=True,
         psus=[createPmbusECB(Tps16890, senseRes=11000, slotId=psuSlotId,
                              addr=0x52)],
         forcePsuLoad=True,
         psuStatusPolicy=PsuStatusPolicy.PMBUS_STATUS,
      )

class SteamerLaneBase(FixedSystem):
   HAS_WINDSURF = False

   PORTS = PortLayout(
      (Osfp1600(i, **OSFP_TRICOLOR_LED) for i in incrange(1, 64)),
      (Qsfp28(65, **QSFP_TRICOLOR_LED),),
   )

   COOLING = CoolingConfig(
      logic=CoolingLogicIncPid,
      kp=9,
      ki=0.75,
      kd=0,
      negHyst=0,
      posHyst=0,
   )

   PORT_LED_POLICY = True

   def __init__(self, **kwargs):
      super().__init__(**kwargs)

      self.psuCounter = 1

      self.cpu = self.newComponent(MarconiCpu)

      # NOTE: should all the devices that hangs off the CPU i2c bus be declared
      # in a dedicated method. If the BMC takes ownership of those it would
      # make things easier to not load them from the CPU

      scBus = self.cpu.getSmbus(self.cpu.SMBUS_SC)

      # Virtual CPLD inside the switchcard SCD
      self.syscpld = self.cpu.cpld.newComponent(
         SysCpld,
         addr=scBus.i2cAddr(0x23)
      )
      # TODO: define syscpld registers (pwr_cycle_en)

      self.pca = self.cpu.cpld.newComponent(
         Pca9548,
         addr=scBus.i2cAddr(0x74)
      )
      # TODO: define GpioRegister for PCA IO expander

      polBus = self.cpu.getSmbus(self.cpu.SMBUS_POL)

      self.cpu.cpld.newComponent(
         Ucd90320,
         addr=polBus.i2cAddr(0x11),
         causes=[
            UcdMon(1, ReloadCauseDesc.POWERLOSS, "Busbar"),
            UcdMon(2, ReloadCauseDesc.POWERLOSS, "ECB output"),
            UcdGpi(12, ReloadCauseDesc.CPU),
            UcdGpi(13, ReloadCauseDesc.OVERTEMP),
            UcdGpi(14, ReloadCauseDesc.OVERTEMP),
            UcdGpi(15, ReloadCauseDesc.OVERTEMP),
            UcdGpi(17, ReloadCauseDesc.WATCHDOG),
            UcdGpi(22, ReloadCauseDesc.LEAK_DETECTED, "Rope 2"),
            UcdGpi(23, ReloadCauseDesc.LEAK_DETECTED, "Rope 1"),
            UcdGpi(24, ReloadCauseDesc.RAIL, "CPU"),
            UcdGpi(25, ReloadCauseDesc.RMC_REBOOT), # Not used on MV3
            UcdGpi(27, ReloadCauseDesc.RAIL, "TH6"),
            UcdGpi(32, ReloadCauseDesc.POWERLOSS, "ECB enable"),
         ],
         causePriority=UcdPriority.HARDWARE_MAIN
      )
      self.cpu.cpld.newComponent(
         Ucd90320,
         addr=polBus.i2cAddr(0x13),
         causePriority=UcdPriority.HARDWARE_SECONDARY
      )

      pwrBus = self.cpu.getSmbus(self.cpu.SMBUS_PWR)

      # 4 ECB on SWC connected to 48V bus bar
      for addr in [0x52, 0x53, 0x54, 0x55]:
         self.cpu.cpld.newComponent(
            PsuSlot,
            slotId=self.psuCounter,
            addrFunc=pwrBus.i2cAddr,
            presentGpio=True,
            psus=[createPmbusECB(Tps16890, senseRes=1330, slotId=self.psuCounter,
                                 addr=addr)],
            forcePsuLoad=True,
            psuStatusPolicy=PsuStatusPolicy.PMBUS_STATUS,
         )
         self.psuCounter += 1

      ibcs = [
         (0x10, 'POS12V_LHS'),
         (0x11, 'POS12V_RHS'),
         (0x12, 'POS12V_MCORE_LHS'),
         (0x13, 'POS12V_MCORE_RHS'),
         (0x14, 'POS12V_OPTICS0'),
         (0x15, 'POS12V_OPTICS1'),
         (0x16, 'POS12V_OPTICS2'),
         (0x17, 'POS12V_OPTICS3'),
      ]
      for ibcId, (addr, name) in enumerate(ibcs):
         self.cpu.cpld.newComponent(
            Pwr689,
            addr=pwrBus.i2cAddr(addr),
            sensors=[
               SensorDesc(diode=0, name='IBC %d %s' % (ibcId, name),
                          position=Position.OTHER, target=100, overheat=105,
                          critical=110),
            ]
         )

      vrms = [
         (Tda38740a, 0x4a, ['POS1V2_VDDA']),
         (Tda38740a, 0x4b, ['POS1V8_VDD0']),
         (Tda38740a, 0x4e, ['POS1V5_RVDD_0']),
         (Tda38740a, 0x4f, ['POS1V5_RVDD_1']),
         (Xdpe1a2g5b, 0x60, ['TH6_MCORE']),
         (Xdpe1b284b, 0x62, ['POS0V75_PHYCORE_0', 'POS0V75_PHYCORE_1']),
         (Xdpe1b284b, 0x64, ['POS0V75_PHYCORE_2', 'POS0V75_PHYCORE_3']),
         (Xdpe1b284b, 0x66, ['POS0V75_PHYCORE_4', 'POS0V75_PHYCORE_5']),
         (Xdpe1b284b, 0x68, ['POS0V75_PHYCORE_6', 'POS0V75_PHYCORE_7']),
         (Xdpe1b284b, 0x6a, ['POS0V72_TRVDD_01', 'POS0V72_TRVDD_23']),
         (Xdpe1b284b, 0x6c, ['POS0V72_TRVDD_45', 'POS0V72_TRVDD_67']),
         (Xdpe1b284b, 0x6e, ['POS0V75_TRVDD_0', 'POS0V9_TRVDD_0']),
         (Xdpe1b284b, 0x70, ['POS0V75_TRVDD_1', 'POS0V9_TRVDD_1']),
         (Xdpe1a2g5b, 0x72, ['POS3V3_OPTICS0', 'POS3V3_OPTICS1']),
         (Xdpe1a2g5b, 0x74, ['POS3V3_OPTICS2', 'POS3V3_OPTICS3']),
      ]
      vrmTempParams = {'target': 105, 'overheat': 115, 'critical': 120}
      for vrmId, (cls, addr, diodes) in enumerate(vrms):
         self.cpu.cpld.newComponent(
            cls,
            addr=pwrBus.i2cAddr(addr),
            sensors=[
               SensorDesc(diode=diodeId, name="VRM %d %s" % (vrmId, name),
                          **vrmTempParams) for diodeId, name in enumerate(diodes)
            ]
         )

      port = self.cpu.getPciPort(self.cpu.PCI_PORT_SCD0)
      self.scd = scd = port.newComponent(Scd, addr=port.addr)
      scd.setMsiRearmOffset(0x180)
      scd.addSmbusMasterRange(0x8000, 11, 0x80, 8)

      # PCB/TH6 temp sensors
      pcbDiodeTempParams = {'target': 75, 'overheat': 80, 'critical': 90}
      th6DiodeTempParams = {'target': 100, 'overheat': 105, 'critical': 110}
      tmp431s = [
         (0, 0x4c, ['Back center PCB', 'TH6 diode 0']),
         (1, 0x4c, ['Front left PCB', 'TH6 diode 1']),
         (2, 0x4c, ['Back left PCB', 'TH6 diode 2']),
      ]
      for bus, addr, (pcbDiode, th6Diode) in tmp431s:
         scd.newComponent(
            Tmp431,
            addr=scd.i2cAddr(bus, addr),
            sensors=[
               SensorDesc(diode=0, name=pcbDiode, position=Position.OTHER,
                          **pcbDiodeTempParams),
               SensorDesc(diode=1, name=th6Diode, position=Position.OTHER,
                          **th6DiodeTempParams),
            ]
         )

      if self.HAS_WINDSURF:
         self.windsurf = Windsurf(self.cpu, psuSlotId=self.psuCounter)
         self.psuCounter += 1

      intrRegs = [
         scd.createInterrupt(addr=0x3000, num=0),
         scd.createInterrupt(addr=0x3030, num=1),
         scd.createInterrupt(addr=0x3060, num=2),
      ]

      scd.createWatchdog(intr=scd.getInterrupt(0), bit=20)

      scd.addXcvrSlots(
         ports=self.PORTS.getOsfps(),
         addr=0xA010,
         bus=8,
         ledAddr=0x6100,
         ledAddrOffsetFn=lambda x: 0x10,
         intrRegs=intrRegs,
         intrRegIdxFn=lambda xcvrId: xcvrId // 33 + 1,
         intrBitFn=lambda xcvrId: (xcvrId - 1) % 32,
      )

      scd.addXcvrSlots(
         ports=self.PORTS.getQsfps(),
         addr=0xA410,
         bus=6,
         ledAddr=0x6900,
         ledAddrOffsetFn=lambda x: 0x40,
         intrRegs=intrRegs,
         intrRegIdxFn=lambda _: 0,
         intrBitFn=lambda xcvrId: xcvrId - 65 + 9,
      )

      scd.addResets([
         ResetDesc('switch_chip_pcie_reset', addr=0x4000, bit=1, auto=False),
         ResetDesc('switch_chip_reset', addr=0x4000, bit=0, auto=False),
      ])

      port = self.cpu.getPciPort(self.cpu.PCI_PORT_ASIC1)
      self.asic = port.newComponent(Tomahawk6, addr=port.addr,
         coreResets=[
            scd.inventory.getReset('switch_chip_reset'),
         ],
         pcieResets=[
            scd.inventory.getReset('switch_chip_pcie_reset'),
         ],
      )

@registerPlatform()
class SteamerLaneMv3(SteamerLaneBase):
   HAS_WINDSURF = True

   SID = ['SteamerLaneMv3']
   SKU = ['7060XE7-64PRS-MV3-L', 'DCS-7060XE7-64PRS-MV3-L']
