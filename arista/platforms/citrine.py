from ..core.fixed import FixedSystem
from ..core.platform import registerPlatform
from ..core.port import PortLayout
from ..core.types import MdioSpeed
from ..core.utils import incrange
from ..core.psu import PsuSlot

from ..components.scd import Scd
from ..components.asic.dnx.jericho3 import Jericho3
from ..components.dpm.adm1266 import (
   Adm1266,
   AdmCauseUnique as AdmCauseU,
   AdmGpio
)
from ..components.lm75 import Tmp75
from ..components.phy.screamingeagle import ScreamingEagle

from ..descs.gpio import GpioDesc
from ..descs.reset import ResetDesc
from ..descs.xcvr import QsfpDD, Qsfp112
from ..descs.sensor import Position, SensorDesc

from .chassis.maunakea import MaunaKea2

from .cpu.redstart import RedstartCpu


class CitrineBase(FixedSystem):
   CHASSIS = MaunaKea2

   PORTS = PortLayout(
      (QsfpDD(i) for i in incrange(1, 16)),
      (Qsfp112(i) for i in incrange(17, 48)),
      (QsfpDD(i) for i in incrange(49, 64))
   )

   def __init__(self):
      super(CitrineBase, self).__init__()
      self.cpu = self.newComponent(RedstartCpu)
      gpioInMask = 0b000001111
      self.cpu.cpld.newComponent(Adm1266,
         addr=self.cpu.getSmbus(self.cpu.SMBUS_POL).i2cAddr(0x40),
         causes=[
            AdmCauseU(AdmCauseU.OVERTEMP,  AdmGpio(1),             gpioInMask),
            AdmCauseU(AdmCauseU.WATCHDOG,  AdmGpio.fromPins(1, 2), gpioInMask),
            AdmCauseU(AdmCauseU.POWERLOSS, AdmGpio(3),             gpioInMask,
                           description="CPU Power bad"),
            AdmCauseU(AdmCauseU.REBOOT,    AdmGpio(4),             gpioInMask),
            AdmCauseU(AdmCauseU.POWERLOSS, AdmGpio.fromPins(1, 4), gpioInMask,
                           description="Both PSUs lost input power"),
            AdmCauseU(AdmCauseU.POWERLOSS, AdmGpio.fromPins(2, 4), gpioInMask,
                           description="Both PSUs lost DC output power"),
            AdmCauseU(AdmCauseU.NOFANS, AdmGpio.fromPins(1, 2, 4), gpioInMask),
      ])

      port = self.cpu.getPciPort(self.cpu.PCI_PORT_SCD0)
      scd = port.newComponent(Scd, addr=port.addr)
      self.scd = scd

      self.scd.addMdioMasterRange(0x9000, 16, speed=MdioSpeed.S10)
      for i in range(16):
         phyId = i + 1
         self.inventory.addPhy(ScreamingEagle(
            phyId=phyId,
            mdios=[self.scd.addMdio(i, 0), self.scd.addMdio(i, 1)],
            reset=self.scd.addReset(
               ResetDesc('phy%d_reset' % phyId, addr=0x4000, bit=5 + i)
            )
         ))

      scd.createWatchdog()
      scd.setMsiRearmOffset(0x180)
      scd.addSmbusMasterRange(0x8000, 9, 0x80)

      scd.newComponent(Tmp75, addr=scd.i2cAddr(0, 0x48), sensors=[
            SensorDesc(diode=0, name='Management Card', position=Position.INLET,
                       target=95, overheat=100, critical=105),
      ])

      scd.addLeds([
         (0x6050, 'status'),
         (0x6060, 'fan_status'),
         (0x6070, 'psu_status'),
         (0x6090, 'beacon'),
         (0x60A0, 'scm'),
      ])

      scd.addResets([
         ResetDesc('switch_chip0_reset', addr=0x4000, bit=0, auto=False),
         ResetDesc('switch_chip0_pcie_reset', addr=0x4000, bit=1, auto=False),
         ResetDesc('switch_chip1_reset', addr=0x4000, bit=2, auto=False),
         ResetDesc('switch_chip1_pcie_reset', addr=0x4000, bit=3, auto=False),
      ])

      scd.addGpios([
         GpioDesc("psu1_present", 0x5000, 0, ro=True),
         GpioDesc("psu2_present", 0x5000, 1, ro=True),
         GpioDesc("psu1_status", 0x5000, 8, ro=True),
         GpioDesc("psu2_status", 0x5000, 9, ro=True),
         GpioDesc("psu1_ac_status", 0x5000, 10, ro=True),
         GpioDesc("psu2_ac_status", 0x5000, 11, ro=True),

         GpioDesc("psu1_present_changed", 0x5000, 16, ro=False),
         GpioDesc("psu2_present_changed", 0x5000, 17, ro=False),
         GpioDesc("psu1_status_changed", 0x5000, 18, ro=False),
         GpioDesc("psu2_status_changed", 0x5000, 19, ro=False),
         GpioDesc("psu1_ac_status_changed", 0x5000, 20, ro=False),
         GpioDesc("psu2_ac_status_changed", 0x5000, 21, ro=False),
      ])

      for psuId in incrange(1, 2):
         addrFunc=lambda addr, i=psuId: \
               scd.i2cAddr(i + 2, addr, t=3, datr=3, datw=3)
         name = "psu%d" % psuId
         scd.newComponent(
            PsuSlot,
            slotId=psuId,
            addrFunc=addrFunc,
            presentGpio=scd.inventory.getGpio("%s_present" % name),
            inputOkGpio=scd.inventory.getGpio("%s_ac_status" % name),
            outputOkGpio=scd.inventory.getGpio("%s_status" % name),
            psus=[],
         )

      intrRegs = [
         scd.createInterrupt(addr=0x3000, num=0),
         scd.createInterrupt(addr=0x3030, num=1),
         scd.createInterrupt(addr=0x3060, num=2),
         scd.createInterrupt(addr=0x3090, num=3),
      ]

      scd.addXcvrSlots(
         ports=self.PORTS.getAllPorts(),
         addr=0xA000,
         bus=8,
         ledAddr=0x6100,
         ledAddrOffsetFn=lambda x: 0x10,
         intrRegs=intrRegs,
         intrRegIdxFn=lambda xcvrId: 2 + ((xcvrId - 1) // 32),
         intrBitFn=lambda xcvrId: (xcvrId - 1) % 32
      )

      port = self.cpu.getPciPort(self.cpu.PCI_PORT_ASIC0)
      port.newComponent(Jericho3, addr=port.addr,
         coreResets=[
            scd.inventory.getReset('switch_chip0_reset'),
         ],
         pcieResets=[
            scd.inventory.getReset('switch_chip0_pcie_reset'),
         ],
      )

      port = self.cpu.getPciPort(self.cpu.PCI_PORT_ASIC1)
      port.newComponent(Jericho3, addr=port.addr,
         coreResets=[
            scd.inventory.getReset('switch_chip1_reset'),
         ],
         pcieResets=[
            scd.inventory.getReset('switch_chip1_pcie_reset'),
         ],
      )


@registerPlatform()
class CitrineDd(CitrineBase):
   SID = ['CitrineDd']
   SKU = ['DCS-7280R4-32QF-32DF']

@registerPlatform()
class CitrineDdBK(CitrineBase):
   SID = ['CitrineDdBK']
   SKU = ['DCS-7280R4K-32QF-32DF']
