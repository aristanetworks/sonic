from ..core.fixed import FixedSystem
from ..core.platform import registerPlatform
from ..core.port import PortLayout
from ..core.psu import PsuSlot
from ..core.utils import incrange

from ..components.asic.bfn.tofino import Tofino
from ..components.dpm.ucd import Ucd90120A, UcdGpi
from ..components.max6658 import Max6658
from ..components.psu.delta import DPS750AB, DPS1900AB
from ..components.psu.emerson import DS750PED
from ..components.scd import Scd

from ..descs.gpio import GpioDesc
from ..descs.reset import ResetDesc
from ..descs.sensor import Position, SensorDesc
from ..descs.xcvr import Qsfp28, Sfp

from .cpu.rook import RookCpu

@registerPlatform()
class Alhambra(FixedSystem):

   SID = ['Alhambra', 'AlhambraSsd']
   SKU = ['DCS-7170-64C', 'DCS-7170-64C-M']

   PORTS = PortLayout(
      (Qsfp28(i, leds=4) for i in incrange(1, 64)),
      (Sfp(i) for i in incrange(65, 66)),
   )

   def __init__(self, hasLmSensor=True, hasCpuLeds=True, psus=None):
      super(Alhambra, self).__init__()

      cpu = self.newComponent(RookCpu, hasLmSensor=hasLmSensor,
                              hasCpuLeds=hasCpuLeds)
      cpu.addCpuDpm()
      cpu.cpld.newComponent(Ucd90120A, addr=cpu.switchDpmAddr(), causes={
         'powerloss': UcdGpi(1),
         'overtemp': UcdGpi(2),
         'reboot': UcdGpi(4),
         'watchdog': UcdGpi(5),
      })
      self.cpu = cpu
      self.syscpld = cpu.syscpld

      port = self.cpu.getPciPort(0)
      scd = port.newComponent(Scd, addr=port.addr)
      self.scd = scd

      scd.createWatchdog()

      scd.newComponent(Max6658, addr=scd.i2cAddr(7, 0x4c), sensors=[
         SensorDesc(diode=0, name='Board sensor',
                    position=Position.OTHER, target=60, overheat=70, critical=80),
         SensorDesc(diode=1, name='Switch Chip sensor',
                    position=Position.OTHER, target=85, overheat=100, critical=110),
      ])

      scd.addSmbusMasterRange(0x8000, 9, 0x80)

      scd.addResets([
         ResetDesc('switch_chip_reset', addr=0x4000, bit=8, auto=False),
         ResetDesc('security_chip_reset', addr=0x4000, bit=1),
         ResetDesc('repeater_sfp_reset', addr=0x4000, bit=0),
      ])

      scd.addGpios([
         GpioDesc("psu1_present", 0x5000, 0, ro=True),
         GpioDesc("psu2_present", 0x5000, 1, ro=True),
         GpioDesc("psu1_status", 0x5000, 8, ro=True),
         GpioDesc("psu2_status", 0x5000, 9, ro=True),
         GpioDesc("psu1_ac_status", 0x5000, 10, ro=True),
         GpioDesc("psu2_ac_status", 0x5000, 11, ro=True),
      ])

      scd.setMsiRearmOffset(0x190)

      intrRegs = [
         scd.createInterrupt(addr=0x3000, num=0, mask=0x60003ff),
         scd.createInterrupt(addr=0x3030, num=1),
         scd.createInterrupt(addr=0x3060, num=2),
      ]

      scd.addXcvrSlots(
         ports=self.PORTS.getQsfps(),
         addr=0xA010,
         bus=8,
         ledAddr=0x6100,
         intrRegs=intrRegs,
         intrRegIdxFn=lambda xcvrId: xcvrId // 33 + 1,
         intrBitFn=lambda xcvrId: (xcvrId - 1) % 32,
         isHwLpModeAvail=False
      )

      scd.addXcvrSlots(
         ports=self.PORTS.getSfps(),
         addr=0xA500,
         bus=72,
         ledAddr=0x7200
      )

      leds, ledfmt = cpu.leds, '%s_status'
      if not hasCpuLeds:
         leds, ledfmt = scd, '%s'
         scd.addLeds([
            (0x7220, 'status'),
            (0x7230, 'fan_status'),
            (0x7240, 'psu1'),
            (0x7250, 'psu2'),
            (0x7260, 'beacon'),
         ])

      for psuId in incrange(1, 2):
         addrFunc=lambda addr, i=psuId: \
               scd.i2cAddr(4 + i, addr, t=3, datr=2, datw=3, block=False)
         name = "psu%d" % psuId
         scd.newComponent(
            PsuSlot,
            slotId=psuId,
            addrFunc=addrFunc,
            presentGpio=scd.inventory.getGpio("%s_present" % name),
            inputOkGpio=scd.inventory.getGpio("%s_ac_status" % name),
            outputOkGpio=scd.inventory.getGpio("%s_status" % name),
            led=leds.inventory.getLed(ledfmt % name),
            psus=psus or [
               DPS750AB,
               DPS1900AB,
               DS750PED,
            ],
         )

      port = self.cpu.getPciPort(1)
      port.newComponent(Tofino, addr=port.addr,
         coreResets=[
            scd.inventory.getReset('switch_chip_reset'),
         ],
      )
