from ...core.bmc import BmcSubsystem
from ...core.platform import registerPlatform

from ...components.aspeed.ast2720 import Ast2720
from ...components.cookie import SonicReloadCauseCookieComponent
from ...components.eeprom import At24C512
from ...components.bmc_usb_device_nic import BmcUsbDeviceNic
from ...components.lm75 import Tmp75

from ...descs.cause import ReloadCausePriority
from ...descs.sensor import Position, SensorDesc

@registerPlatform()
class Goldfinch(BmcSubsystem):
   SID = []
   SKU = ['Goldfinch']

   def __init__(self):
      super().__init__()
      self.bmc.createWatchdog()
      # TODO: temp thresholds are yet to be decided
      self.newComponent(Tmp75, addr=self.bmc.getSmbus(15).i2cAddr(0x4f), sensors=[
         SensorDesc(diode=0, name='BMC temp sensor',
                    position=Position.OTHER, target=70, overheat=80, critical=90),
      ])
      self.newComponent(BmcUsbDeviceNic, udcName='12060000.usb-vhub:p1')

      self.newComponent(SonicReloadCauseCookieComponent,
                        causePriority=ReloadCausePriority.PREREBOOT)
      self.bmc.addReloadCauseProvider(
         priority=ReloadCausePriority.HARDWARE_MAIN)

   def createBmc(self):
      return self.newComponent(Ast2720)

   def createBmcEeprom(self):
      return self.newComponent(
         At24C512, addr=self.bmc.getSmbus(14).i2cAddr(0x50), label='bmcEeprom')

   def createCpuEeprom(self):
      return self.newComponent(
         At24C512, addr=self.bmc.getSmbus(9).i2cAddr(0x50), label='cpuEeprom')

   def createChassisEeprom(self):
      return self.newComponent(
         At24C512, addr=self.bmc.getSmbus(9).i2cAddr(0x53), label='chassisEeprom')

   def cpuCpldAddr(self):
      return self.bmc.getSmbus(12).i2cAddr(0x43)
