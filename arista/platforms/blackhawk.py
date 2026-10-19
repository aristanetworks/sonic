from ..core.fixed import FixedSystem
from ..core.platform import registerPlatform
from ..core.port import PortLayout
from ..core.psu import PsuSlot
from ..core.utils import incrange

from ..components.cpu.rook import TehamaFanCpld
from ..components.asic.xgs.tomahawk3 import Tomahawk3
from ..components.dpm.ucd import Ucd90320, UcdGpi
from ..components.max6581 import Max6581
from ..components.psu.delta import DPS1600AB, DPS1600CB
from ..components.scd import Scd

from ..descs.gpio import GpioDesc
from ..descs.reset import ResetDesc
from ..descs.sensor import Position, SensorDesc
from ..descs.xcvr import Osfp, QsfpDD, Sfp

from .cpu.rook import RookCpu

@registerPlatform()
class BlackhawkO(FixedSystem):

   SID = ['BlackhawkO']
   SKU = ['DCS-7060PX4-32']

   PORTS = PortLayout(
      (Osfp(i) for i in incrange(1, 32)),
      (Sfp(i) for i in incrange(33, 34)),
   )

   HW_LPMODE = True

   def __init__(self):
      super(BlackhawkO, self).__init__()

      cpu = self.newComponent(RookCpu, fanCpldCls=TehamaFanCpld, mgmtBus=14)
      cpu.cpld.newComponent(Ucd90320, addr=cpu.switchDpmAddr(0x11), causes={
         'overtemp': UcdGpi(1),
         'powerloss': UcdGpi(3),
         'watchdog': UcdGpi(5),
         'reboot': UcdGpi(6),
      })
      self.cpu = cpu
      self.syscpld = cpu.syscpld

      port = self.cpu.getPciPort(1)
      scd = port.newComponent(Scd, addr=port.addr)
      self.scd = scd

      scd.createWatchdog()

      scd.newComponent(Max6581, addr=scd.i2cAddr(8, 0x4d), sensors=[
         SensorDesc(diode=0, name='Board sensor',
                    position=Position.OTHER, target=65, overheat=75, critical=85),
         SensorDesc(diode=1, name='Switch board middle sensor',
                    position=Position.OTHER, target=55, overheat=65, critical=75),
         SensorDesc(diode=2, name='Switch board left sensor',
                    position=Position.OTHER, target=55, overheat=65, critical=75),
         SensorDesc(diode=3, name='Front-panel temp sensor',
                    position=Position.INLET, target=55, overheat=65, critical=75),
         SensorDesc(diode=6, name='Switch chip diode 1 sensor',
                    position=Position.OTHER, target=75, overheat=110, critical=125),
         SensorDesc(diode=7, name='Switch chip diode 2 sensor',
                    position=Position.OTHER, target=75, overheat=110, critical=125),
      ])

      scd.addSmbusMasterRange(0x8000, 8, 0x80)

      scd.addLeds([
         (0x6050, 'status'),
         (0x6060, 'fan_status'),
         (0x6070, 'psu1'),
         (0x6080, 'psu2'),
         (0x6090, 'beacon'),
      ])

      scd.addResets([
         ResetDesc('sat_cpld1_reset', addr=0x4000, bit=4),
         ResetDesc('sat_cpld0_reset', addr=0x4000, bit=3),
         ResetDesc('switch_chip_reset', addr=0x4000, bit=2, auto=False),
         ResetDesc('security_asic_reset', addr=0x4000, bit=0),
      ])

      scd.addGpios([
         GpioDesc("psu2_present", 0x5000, 0, ro=True),
         GpioDesc("psu1_present", 0x5000, 1, ro=True),
         GpioDesc("psu2_status", 0x5000, 8, ro=True),
         GpioDesc("psu1_status", 0x5000, 9, ro=True),
         GpioDesc("psu2_ac_status", 0x5000, 10, ro=True),
         GpioDesc("psu1_ac_status", 0x5000, 11, ro=True),
      ])

      intrRegs = [
         scd.createInterrupt(addr=0x3000, num=0),
         scd.createInterrupt(addr=0x3030, num=1),
         scd.createInterrupt(addr=0x3060, num=2),
      ]

      scd.addXcvrSlots(
         ports=self.PORTS.getOsfps(),
         addr=0xA010,
         bus=16,
         ledAddr=0x6100,
         ledAddrOffsetFn=lambda x: 0x40,
         intrRegs=intrRegs,
         intrRegIdxFn=lambda xcvrId: 1,
         intrBitFn=lambda xcvrId: xcvrId - 1,
         isHwLpModeAvail=self.HW_LPMODE,
      )

      scd.addXcvrSlots(
         ports=self.PORTS.getSfps(),
         addr=0xA210,
         bus=48,
         ledAddr=0x6900,
         ledAddrOffsetFn=lambda x: 0x40,
      )

      for psuId, bus in [(1, 12), (2, 11)]:
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
            led=cpu.leds.inventory.getLed('%s_status' % name),
            psus=[
               DPS1600CB,
               DPS1600AB,
            ],
         )

      port = self.cpu.getPciPort(0)
      port.newComponent(Tomahawk3, addr=port.addr,
         coreResets=[
            scd.inventory.getReset('switch_chip_reset'),
         ],
      )

@registerPlatform()
class BlackhawkDD(BlackhawkO):
   SID = ['BlackhawkDD', 'BlackhawkDDM']
   SKU = ['DCS-7060DX4-32', 'DCS-7060DX4-32-D']

   PORTS = PortLayout(
      (QsfpDD(i) for i in incrange(1, 32)),
      (Sfp(i) for i in incrange(33, 34)),
   )

   HW_LPMODE = False
