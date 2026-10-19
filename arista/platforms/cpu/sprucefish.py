from ...core.cpu import Cpu
from ...core.pci import PciRoot
from ...core.register import Register, RegisterMap, RegBitField

from ...components.cpu.intel.coretemp import Coretemp
from ...components.scd import Scd
from ...components.eeprom import At24C512
from ...components.max6658 import Max6658

from ...descs.sensor import SensorDesc, Position
from ...descs.xcvr import Sfp

class CpldSeuRegisterMap(RegisterMap):
   SCD_CTRL = Register(0x2300,
      RegBitField(3, 'powerCycleOnSeu', ro=False),
      RegBitField(2, 'hasSeuError', ro=False),
   )

class SprucefishCpu(Cpu):

   PLATFORM = 'sprucefish'

   def __init__(self, **kwargs):
      super(SprucefishCpu, self).__init__(**kwargs)

      self.pciRoot = self.newComponent(PciRoot)

      port = self.pciRoot.rootPort(bus=0xff, device=0x0b, func=3)
      cpld = port.newComponent(Scd, addr=port.addr)
      self.cpld = cpld

      cpld.createPowerCycle()
      cpld.addSeuReporter(CpldSeuRegisterMap)
      cpld.addSmbusMasterRange(0x8000, 0, 0x80, 9)
      # TODO: add led and interrupt logic for SFP port
      cpld.addXcvrSlots(
         ports=[Sfp(index=1, leds=0)],
         addr=0x5010,
         bus=3,
         ledAddr=None,
         ledAddrOffsetFn=None,
      )

      cpld.addLeds([
         (0x6050, 'status'),
         (0x6060, 'active'),
         (0x6070, 'fan_status'),
         (0x6080, 'fabric_status'),
         (0x6090, 'psu_status'),
         (0x60A0, 'linecard_status'),
         (0x60B0, 'beacon'),
      ])

      self.newComponent(Coretemp, sensors=[
         SensorDesc(diode=0, name='Physical id 0',
                    position=Position.OTHER, target=82, overheat=95, critical=104),
         SensorDesc(diode=1, name='CPU core0',
                    position=Position.OTHER, target=82, overheat=95, critical=104),
         SensorDesc(diode=2, name='CPU core1',
                    position=Position.OTHER, target=82, overheat=95, critical=104),
         SensorDesc(diode=3, name='CPU core2',
                    position=Position.OTHER, target=82, overheat=95, critical=104),
         SensorDesc(diode=4, name='CPU core3',
                    position=Position.OTHER, target=82, overheat=95, critical=104),
         SensorDesc(diode=5, name='CPU core4',
                    position=Position.OTHER, target=82, overheat=95, critical=104),
         SensorDesc(diode=6, name='CPU core5',
                    position=Position.OTHER, target=82, overheat=95, critical=104),
      ])

      self.eeprom = cpld.newComponent(At24C512, addr=cpld.i2cAddr(0, 0x50),
                                      label='supervisor')

      self.max6658 = cpld.newComponent(Max6658, addr=cpld.i2cAddr(0, 0x4c),
                                       sensors=[
         SensorDesc(diode=0, name='Supervisor front',
                    position=Position.INLET, target=44, overheat=50, critical=55),
     ])

   def cpuDpmAddr(self, addr=0x4e, **kwargs):
      return self.cpld.i2cAddr(1, addr, **kwargs)

   def shimDpmAddr(self, addr=0x75, **kwargs):
      return self.cpld.i2cAddr(1, addr, **kwargs)

   def shimEepromAddr(self):
      return self.cpld.i2cAddr(0, 0x51)
