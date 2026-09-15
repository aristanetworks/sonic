from ..core.bmc import BmcHostSwitch, registerHostSwitch
from ..core.cooling import CoolingConfig, CoolingLogicIncPid
from ..core.fixed import FixedSystem, FixedChassis
from ..core.hwapi import HwApi
from ..core.liquid import LeakDetectionInterfaceV1, LeakSensorType
from ..core.platform import registerPlatform
from ..core.port import PortLayout
from ..core.psu import PsuSlot
from ..core.register import (
   Register,
   RegisterMap,
   RegBitField,
)
from ..core.utils import incrange

from ..components.asic.xgs.tomahawk6 import Tomahawk6
from ..components.cpld import SysCpld
from ..components.dpm.ucd import Ucd90320, UcdGpi, UcdMon, UcdPriority
from ..components.lm75 import Tmp75
from ..components.max31732 import Max31732
from ..components.pca954x import Pca9548
from ..components.psu.ecb import createPmbusECB, Tps16890
from ..components.scd import (
   LeakDetectionPcieRegistersV1,
   Scd,
   ScdInterruptDesc,
)
from ..components.tmp401 import Tmp431
from ..components.vrm.ibc import Pwr689
from ..components.vrm.tda38740 import Tda38740a, Xdpe1a2g5b, Xdpe1b284b
from ..components.cpu.marconi import MarconiCpldRegisters

from ..descs.cause import ReloadCauseDesc, ReloadCauseAltSource
from ..descs.led import LedDesc, LedKind
from ..descs.liquid import LeakSensorDesc, LiquidCoolingDesc
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

class SteamerLaneSysCpldRegisters(RegisterMap):
   MINOR = Register(0x00, name='revisionMinor')
   REVISION = Register(0x01, name='revision')
   SCRATCHPAD = Register(0x02, name='scratchpad', ro=False)

   FAULT_PWR_CYCLE_EN_1 = Register(0x11,
      RegBitField(6, 'railFault', ro=False),
      RegBitField(4, 'cpuFault', ro=False),
      RegBitField(3, 'watchdog', ro=False),
      RegBitField(2, 'powerCycleOnCrc', ro=False),
      RegBitField(1, 'overtemp', ro=False),
   )
   FAULT_PWR_CYCLE_EN_2 = Register(0x12,
      RegBitField(7, 'bitshadowRxParity', ro=False),
      RegBitField(0, 'leak', ro=False),
   )
   RT_FAULT_0 = Register(0x46,
      RegBitField(4, 'cpuFault'),
      RegBitField(3, 'watchdog'),
      RegBitField(2, 'scdCrcError'),
      RegBitField(1, 'overtemp'),
   )

class SteamerLaneSysCpld(SysCpld):
   REGISTER_CLS = SteamerLaneSysCpldRegisters

class SteamerLaneSwcScd(Scd):
   INTERRUPTS = [
      ScdInterruptDesc(addr=0x3000, fields=[]),
      ScdInterruptDesc(addr=0x3030, fields=[]),
      ScdInterruptDesc(addr=0x3060, fields=[]),
   ]

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
                       target=85, overheat=90, critical=95),
         ]
      )

      # ECB connected to 48V bus bar
      cpu.cpld.newComponent(
         PsuSlot,
         slotId=psuSlotId,
         addrFunc=fcBus.i2cAddr,
         presentGpio=True,
         psus=[createPmbusECB(Tps16890, senseRes=11000, slotId=psuSlotId,
                              addr=0x52, tempLimits=(90, 115, 120))],
         forcePsuLoad=True,
         psuStatusPolicy=PsuStatusPolicy.PMBUS_STATUS,
      )

class SteamerLaneChassis(FixedChassis):
   HEIGHT_RU = 2

class SteamerLaneBase(FixedSystem):
   CHASSIS = SteamerLaneChassis
   HAS_WINDSURF = False
   OSFP_PORTS_PER_SCD = 32

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
         SteamerLaneSysCpld,
         addr=scBus.i2cAddr(0x23)
      )

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
            UcdGpi(12, ReloadCauseDesc.CPU,
                   altSource=ReloadCauseAltSource.CPU),
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
                                 addr=addr, tempLimits=(90, 115, 120))],
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
                          position=Position.OTHER, target=85, overheat=105,
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
      vrmTempParams = {'target': 95, 'overheat': 115, 'critical': 120}
      for vrmId, (cls, addr, diodes) in enumerate(vrms):
         self.cpu.cpld.newComponent(
            cls,
            addr=pwrBus.i2cAddr(addr),
            sensors=[
               SensorDesc(diode=diodeId, name="VRM %d %s" % (vrmId, name),
                          **vrmTempParams) for diodeId, name in enumerate(diodes)
            ]
         )

      # SCD
      hasDualScds = self.getHwApi() >= HwApi(5, 0)
      miscBus = self.OSFP_PORTS_PER_SCD if hasDualScds else 0
      osfpBus = 0 if hasDualScds else 8

      scd0 = self._createScd(
         self.cpu.PCI_PORT_SCD0,
         registerCls=LeakDetectionPcieRegistersV1,
      )
      self.scd0 = scd0

      scd1 = None
      self.scd1 = None
      if hasDualScds:
         scd1 = self._createScd(self.cpu.PCI_PORT_SCD1)
         self.scd1 = scd1

         # Dedicated SMBus master for each port
         scd0.addSmbusMasterRange(0x8000, self.OSFP_PORTS_PER_SCD - 1, 0x40, 1)
         scd1.addSmbusMasterRange(0x8000, self.OSFP_PORTS_PER_SCD - 1, 0x40, 1)
         # Additional master for miscellaneous devices
         scd0.addSmbusMaster(0x8800, self.OSFP_PORTS_PER_SCD, 8)
      else:
         scd0.addSmbusMasterRange(0x8000, 11, 0x80, 8)

      # Board/TH6 temp sensors
      boardDiodeTempParams = {'target': 90, 'overheat': 95, 'critical': 100}
      th6DiodeTempParams = {'target': 90, 'overheat': 105, 'critical': 110}
      tmp431s = [
         (0, 0x4c, ['Board Center', 'TH6C Remote Diode 0']),
         (1, 0x4c, ['Board Front Left', 'TH6C Remote Diode 1']),
         (2, 0x4c, ['Board Center Left', 'TH6C Remote Diode 2']),
      ]
      for bus, addr, (boardDiode, th6Diode) in tmp431s:
         scd0.newComponent(
            Tmp431,
            addr=scd0.i2cAddr(miscBus + bus, addr),
            sensors=[
               SensorDesc(diode=0, name=boardDiode, position=Position.OTHER,
                          **boardDiodeTempParams),
               SensorDesc(diode=1, name=th6Diode, position=Position.OTHER,
                          **th6DiodeTempParams),
            ]
         )

      if self.getHwApi() >= HwApi(4, 0):
         max31732s = [
            (0x4e, [
               SensorDesc(diode=0, name='Board Rear Center',
                          position=Position.OTHER, **boardDiodeTempParams),
               SensorDesc(diode=1, name='Underside Front Left',
                          position=Position.OTHER, betaComp=False,
                          **boardDiodeTempParams),
               SensorDesc(diode=2, name='Underside Center Left',
                          position=Position.OTHER, betaComp=False,
                          **boardDiodeTempParams),
               SensorDesc(diode=3, name='Board Rear Left',
                          position=Position.OTHER, betaComp=False,
                          **boardDiodeTempParams),
               SensorDesc(diode=4, name='Underside Rear Left',
                          position=Position.OTHER, betaComp=False,
                          **boardDiodeTempParams),
            ]),
            (0x4f, [
               SensorDesc(diode=0, name='Board Rear Right',
                          position=Position.OTHER, **boardDiodeTempParams),
               SensorDesc(diode=1, name='Underside Rear Center',
                          position=Position.OTHER, betaComp=False,
                          **boardDiodeTempParams),
               SensorDesc(diode=2, name='Underside Rear Right',
                          position=Position.OTHER, betaComp=False,
                          **boardDiodeTempParams),
               SensorDesc(diode=3, name='Underside Front Right',
                          position=Position.OTHER, betaComp=False,
                          **boardDiodeTempParams),
               SensorDesc(diode=4, name='Underside Center',
                          position=Position.OTHER, betaComp=False,
                          **boardDiodeTempParams),
            ]),
         ]
         for addr, sensors in max31732s:
            scd0.newComponent(
               Max31732,
               addr=scd0.i2cAddr(miscBus + 7, addr),
               sensors=sensors,
            )

      if self.HAS_WINDSURF:
         self.windsurf = Windsurf(self.cpu, psuSlotId=self.psuCounter)
         self.psuCounter += 1

      # TODO: update locations.
      self.cpu.cpld.addLiquidCooling(
         LiquidCoolingDesc(LeakDetectionInterfaceV1, sensors=[
            LeakSensorDesc(name="trayLeak", sensorType=LeakSensorType.ROPE_MAJOR,
                           addr=0, location="drip tray"),
            LeakSensorDesc(name="smallLeak", sensorType=LeakSensorType.ROPE_MINOR,
                           addr=0, location="unspecified"),
         ])
      )

      scd0.createWatchdog(intr=scd0.getInterrupt(0), bit=20)

      osfpPorts = self.PORTS.getOsfps()
      scd0OsfpPorts = osfpPorts if scd1 is None else [
         port for port in osfpPorts if port.index <= self.OSFP_PORTS_PER_SCD
      ]
      scd1OsfpPorts = [] if scd1 is None else [
         port for port in osfpPorts if port.index > self.OSFP_PORTS_PER_SCD
      ]

      scd0.addXcvrSlots(
         ports=scd0OsfpPorts,
         addr=0xA010,
         bus=osfpBus,
         ledAddr=0x6100,
         ledAddrOffsetFn=lambda x: 0x10,
         intrRegs=scd0.getInterrupts(),
         intrRegIdxFn=lambda xcvrId: xcvrId // 33 + 1,
         intrBitFn=lambda xcvrId: (xcvrId - 1) % 32,
      )

      if scd1 is not None:
         scd1.addXcvrSlots(
            ports=scd1OsfpPorts,
            addr=0xA010,
            bus=0,
            ledAddr=0x6500,
            ledScd=scd0, # SCD0 still handles the port LEDs
            ledAddrOffsetFn=lambda x: 0x10,
            intrRegs=scd1.getInterrupts(),
            intrRegIdxFn=lambda _: 1,
            intrBitFn=lambda xcvrId: (xcvrId - self.OSFP_PORTS_PER_SCD - 1) % 32,
         )

      scd0.addXcvrSlots(
         ports=self.PORTS.getQsfps(),
         addr=0xA410,
         bus=miscBus + 6,
         ledAddr=0x60a0,
         ledScd=self.cpu.cpld,
         ledAddrOffsetFn=lambda x: 0x40,
         intrRegs=scd0.getInterrupts(),
         intrRegIdxFn=lambda _: 0,
         intrBitFn=lambda xcvrId: xcvrId - 65 + 9,
      )

      scd0.addResets([
         ResetDesc('switch_chip_pcie_reset', addr=0x4000, bit=1, auto=False),
         ResetDesc('switch_chip_reset', addr=0x4000, bit=0, auto=False),
      ])

      port = self.cpu.getPciPort(self.cpu.PCI_PORT_ASIC1)
      self.asic = port.newComponent(Tomahawk6, addr=port.addr,
         coreResets=[
            scd0.inventory.getReset('switch_chip_reset'),
         ],
         pcieResets=[
            scd0.inventory.getReset('switch_chip_pcie_reset'),
         ],
         sensors=[
            SensorDesc(diode=0, name='Asic', position=Position.OTHER,
                       target=90, overheat=105, critical=110),
         ],
      )

   def _createScd(self, pciPort, **kwargs):
      port = self.cpu.getPciPort(pciPort)
      scd = port.newComponent(SteamerLaneSwcScd, addr=port.addr, **kwargs)
      scd.setMsiRearmOffset(0x180)
      return scd

@registerPlatform()
class SteamerLaneMv3(SteamerLaneBase):
   HAS_WINDSURF = True

   SID = ['SteamerLaneMv3']
   SKU = ['7060XE7-64PRS-MV3-L', 'DCS-7060XE7-64PRS-MV3-L']

@registerHostSwitch()
class SteamerLaneHostSwitch(BmcHostSwitch):
   SID = ['Marconi', 'SteamerLaneMv3']

   def __init__(self, *args, **kwargs):
      super().__init__(*args, **kwargs)
      self.cpld = self.newComponent(SysCpld,
                                    addr=self.parent.cpuCpldAddr(),
                                    registerCls=MarconiCpldRegisters)

      # TODO: update locations.
      self.cpld.addLiquidCooling(
         LiquidCoolingDesc(LeakDetectionInterfaceV1, sensors=[
            LeakSensorDesc(name="trayLeak", sensorType=LeakSensorType.ROPE_MAJOR,
                           addr=0, location="drip tray"),
            LeakSensorDesc(name="smallLeak", sensorType=LeakSensorType.ROPE_MINOR,
                           addr=0, location="unspecified"),
         ])
      )
