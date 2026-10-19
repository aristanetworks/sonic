from ..core.fixed import FixedSystem
from ..core.platform import registerPlatform
from ..core.port import PortLayout
from ..core.psu import PsuSlot
from ..core.utils import incrange

from ..components.asic.xgs.trident2 import Trident2
from ..components.dpm.ucd import Ucd90120A, UcdGpi
from ..components.max6658 import Max6658
from ..components.psu.delta import DPS495CB
from ..components.psu.artesyn import DS495SPE
from ..components.scd import Scd
from ..components.ds125br import Ds125Br

from ..descs.gpio import GpioDesc
from ..descs.reset import ResetDesc
from ..descs.sensor import Position, SensorDesc
from ..descs.xcvr import Qsfp28, Sfp

from .cpu.crow import CrowCpu

@registerPlatform()
class Clearlake(FixedSystem):

   SID = ['Clearlake', 'ClearlakeSsd']
   SKU = ['DCS-7050QX-32S', 'DCS-7050QX-32S-SSD']

   PORTS = PortLayout(
      (Sfp(i) for i in incrange(1, 4)),
      (Qsfp28(i, leds=4) for i in incrange(5, 28)),
      (Qsfp28(i) for i in incrange(29, 36)),
   )

   def __init__(self):
      super(Clearlake, self).__init__()

      # FIXME: cleanup later
      self.qsfp40gAutoRange = incrange(5, 28)
      self.qsfp40gOnlyRange = incrange(29, 36)

      cpu = self.newComponent(CrowCpu)
      self.cpu = cpu
      self.syscpld = cpu.syscpld

      port = cpu.getPciPort(1)
      scd = port.newComponent(Scd, addr=port.addr)

      self.cpu.addScdComponents(scd, hwmonBus=1)

      scd.createWatchdog()

      scd.createPowerCycle()

      scd.newComponent(Max6658, addr=scd.i2cAddr(0, 0x4c), sensors=[
         SensorDesc(diode=0, name='Board Sensor',
                    position=Position.OTHER, target=36, overheat=55, critical=70),
         SensorDesc(diode=1, name='Front-panel temp sensor',
                    position=Position.INLET, target=42, overheat=65, critical=75),
      ])

      scd.newComponent(Ucd90120A, addr=scd.i2cAddr(1, 0x4e, t=3))
      scd.newComponent(Ucd90120A, addr=scd.i2cAddr(5, 0x4e, t=3), causes={
         'reboot': UcdGpi(2),
         'watchdog': UcdGpi(3),
         'powerloss': UcdGpi(7),
      })

      scd.newComponent(Ds125Br, addr=scd.i2cAddr(6, 0x58), # qsfp36
                       amplitude=[0xaa, 0xaa, 0xaa, 0xaa, 0xa9, 0xa9, 0xa9, 0xaa])
      scd.newComponent(Ds125Br, addr=scd.i2cAddr(6, 0x59), # qsfp35
                       amplitude=[0xaa, 0xaa, 0xaa, 0xaa, 0xa8, 0xa9, 0xa8, 0xa9])
      scd.newComponent(Ds125Br, addr=scd.i2cAddr(6, 0x5a)) # sfp1-2
      scd.newComponent(Ds125Br, addr=scd.i2cAddr(6, 0x5b)) # sfp3-4

      scd.addSmbusMasterRange(0x8000, 6)

      scd.addLeds([
         (0x6050, 'status'),
         (0x6060, 'fan_status'),
         (0x6070, 'psu1'),
         (0x6080, 'psu2'),
         (0x6090, 'beacon'),
      ])

      scd.addReset(ResetDesc('switch_chip_reset', addr=0x4000, bit=0, auto=False))

      scd.addGpios([
         GpioDesc("psu1_present", 0x5000, 0, ro=True),
         GpioDesc("psu2_present", 0x5000, 1, ro=True),
         GpioDesc("mux", 0x6940, 0), # FIXME: oldSetup order/name
      ])

      for psuId in incrange(1, 2):
         addrFunc=lambda addr, i=psuId: \
                  scd.i2cAddr(2 + i, addr, t=3, datr=3, datw=3)
         name = "psu%d" % psuId
         scd.newComponent(
            PsuSlot,
            slotId=psuId,
            addrFunc=addrFunc,
            presentGpio=scd.inventory.getGpio("%s_present" % name),
            led=scd.inventory.getLed(name),
            psus=[
               DPS495CB,
               DS495SPE,
            ],
         )

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
         intrBitFn=lambda xcvrId: xcvrId - 5,
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
         intrBitFn=lambda xcvrId: xcvrId - 5,
         isHwLpModeAvail=False,
      )

      scd.addXcvrSlots(
         ports=self.PORTS.getSfps(),
         addr=0x5210,
         bus=40,
         ledAddr=0x6900,
      )

      port = cpu.getPciPort(0)
      port.newComponent(Trident2, addr=port.addr,
         coreResets=[
            scd.inventory.getReset('switch_chip_reset'),
         ],
      )


@registerPlatform()
class ClearlakePlus(Clearlake):
   SID = ['ClearlakePlus', 'ClearlakePlusSsd']
   SKU = ['DCS-7050QX2-32S', 'DCS-7050QX2-32S-SSD']
