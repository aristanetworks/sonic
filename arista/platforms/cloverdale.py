from ..core.fan import FanSlot
from ..core.fixed import FixedSystem
from ..core.platform import registerPlatform
from ..core.port import PortLayout
from ..core.psu import PsuSlot
from ..core.types import PciAddr
from ..core.utils import incrange

from ..components.asic.xgs.trident2 import Trident2
from ..components.cpu.amd.k10temp import K10Temp
from ..components.cpu.raven import RavenFanComplex
from ..components.dpm.ucd import Ucd90120A, Ucd90160, UcdGpi, UcdMon, UcdPriority
from ..components.lm73 import Lm73
from ..components.max6658 import Max6658
from ..components.psu.artesyn import DS460
from ..components.scd import Scd

from ..descs.cause import ReloadCauseDesc
from ..descs.fan import FanDesc, FanPosition
from ..descs.led import LedDesc, LedColor
from ..descs.gpio import GpioDesc
from ..descs.reset import ResetDesc
from ..descs.sensor import Position, SensorDesc
from ..descs.xcvr import Qsfp28

@registerPlatform()
class Cloverdale(FixedSystem):

   # This platform doesn't have sid= on the cmdline and therefore needs to rely
   # on platform= instead. Alternatively we rely on SKU
   PLATFORM = 'raven'
   SID = ['Cloverdale', 'CloverdaleSsd']
   SKU = ['DCS-7050QX-32']

   PORTS = PortLayout(
      (Qsfp28(i, leds=4) for i in incrange(1, 24)),
      (Qsfp28(i) for i in incrange(25, 32)),
   )

   def __init__(self):
      super().__init__()

      # FIXME: cleanup later
      self.qsfp40gAutoRange = incrange(1, 24)
      self.qsfp40gOnlyRange = incrange(25, 32)

      self.newComponent(Trident2, PciAddr(bus=0x02))

      scd = self.newComponent(Scd, PciAddr(bus=0x04))

      scd.createWatchdog()

      scd.createPowerCycle()

      self.newComponent(K10Temp, addr=PciAddr(device=0x18, func=3), sensors=[
         SensorDesc(diode=0, name='Cpu temp sensor',
                    position=Position.OTHER, target=62, overheat=95, critical=100),
      ])

      fanComplex = self.newComponent(RavenFanComplex)
      for slotId in incrange(1, 4):
         fanDesc = FanDesc(fanId=slotId, position=FanPosition.INLET)
         ledDesc = LedDesc(name='fan%d' % slotId,
                           colors=[LedColor.RED, LedColor.GREEN, LedColor.OFF])
         self.newComponent(
            FanSlot,
            slotId=slotId,
            led=fanComplex.addFanLed(ledDesc),
            fans=[
               fanComplex.addFan(fanDesc),
            ],
         )

      scd.newComponent(Max6658, scd.i2cAddr(0, 0x4c),
                       waitFile='/sys/class/hwmon/hwmon2', sensors=[
         SensorDesc(diode=0, name='Board sensor',
                    position=Position.OTHER, target=36, overheat=55, critical=70),
         SensorDesc(diode=1, name='Front-panel temp sensor',
                    position=Position.INLET, target=42, overheat=65, critical=75),
      ])
      scd.newComponent(Lm73, scd.i2cAddr(1, 0x48),
                       waitFile='/sys/class/hwmon/hwmon3', sensors=[
         SensorDesc(diode=0, name='Rear temp sensor',
                    position=Position.OUTLET, target=42, overheat=65, critical=75),
      ])
      # Due to a risk of an unrecoverable firmware corruption when a pmbus
      # transaction is done at the same moment of the poweroff, the handling of
      # the DPM is disabled. If you want rail information use it at your own risk
      # The current implementation will just read the firmware information once.
      scd.newComponent(Ucd90120A, scd.i2cAddr(1, 0x4e, t=3),
                       causePriority=UcdPriority.HARDWARE_SECONDARY)
      scd.newComponent(Ucd90160, scd.i2cAddr(5, 0x4e, t=3), causes=[
         UcdGpi(2, ReloadCauseDesc.REBOOT),
         UcdGpi(3, ReloadCauseDesc.WATCHDOG),
         UcdMon(13, ReloadCauseDesc.POWERLOSS),
      ], causePriority=UcdPriority.HARDWARE_MAIN)

      scd.addLeds([
         (0x6050, 'status'),
         (0x6060, 'fan_status'),
         (0x6070, 'psu1'),
         (0x6080, 'psu2'),
         (0x6090, 'beacon'),
      ])

      scd.addGpios([
         GpioDesc("psu1_present", 0x5000, 0, ro=True),
         GpioDesc("psu2_present", 0x5000, 1, ro=True),
      ])

      for psuId in incrange(1, 2):
         addrFunc=lambda addr, i=psuId: \
                  scd.i2cAddr(2 + i, addr, t=3, datr=3, datw=3, block=False)
         name = "psu%d" % psuId
         scd.newComponent(
            PsuSlot,
            slotId=psuId,
            addrFunc=addrFunc,
            presentGpio=scd.inventory.getGpio("%s_present" % name),
            led=scd.inventory.getLed(name),
            forcePsuLoad=True,
            psus=[
               DS460,
            ],
         )

      scd.addSmbusMasterRange(0x8000, 5)

      scd.addResets([
         ResetDesc('switch_chip_reset', addr=0x4000, bit=0),
         ResetDesc('phy1_reset', addr=0x4000, bit=2),
         ResetDesc('phy2_reset', addr=0x4000, bit=3),
         ResetDesc('phy3_reset', addr=0x4000, bit=4),
         ResetDesc('phy4_reset', addr=0x4000, bit=5),
      ])

      intrRegs = [
         scd.createInterrupt(addr=0x3000, num=0),
         scd.createInterrupt(addr=0x3030, num=1),
      ]

      scd.addXcvrSlots(
         ports=[self.PORTS.getPort(index) for index in self.qsfp40gAutoRange],
         addr=0x5010,
         bus=8,
         ledAddr=0x6100,
         intrRegs=intrRegs,
         intrRegIdxFn=lambda xcvrId: 1,
         intrBitFn=lambda xcvrId: xcvrId - 1,
         isHwLpModeAvail=False,
      )

      scd.addXcvrSlots(
         ports=[self.PORTS.getPort(index) for index in self.qsfp40gOnlyRange],
         addr=0x5190,
         bus=32,
         ledAddr=0x6720,
         ledAddrOffsetFn=lambda xcvrId: 0x30 if xcvrId % 2 else 0x50,
         intrRegs=intrRegs,
         intrRegIdxFn=lambda xcvrId: 1,
         intrBitFn=lambda xcvrId: xcvrId - 1,
         isHwLpModeAvail=False,
      )
