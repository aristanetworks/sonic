from ...core.bmc import Bmc
from ...core.platform import registerBmc

from ...components.aspeed.ast2720 import Ast2720
from ...components.bmc_mgmt_nic import BmcMgmtNic
from ...components.bmc_usb_device_nic import BmcUsbDeviceNic
from ...components.cookie import SonicReloadCauseCookieComponent
from ...components.eeprom import At24C512
from ...components.lm75 import Tmp75

from ...descs.cause import ReloadCausePriority
from ...descs.sensor import Position, SensorDesc

@registerBmc()
class GoldfinchBmc(Bmc, Ast2720):

   MODEL = ['Goldfinch']
   CHASSIS_EEPROM_BUS = 9
   CHASSIS_EEPROM_ADDR = 0x53
   CHASSIS_EEPROM_LABEL = 'chassisEeprom'

   def __init__(self, *args, **kwargs):
      super().__init__(*args, **kwargs)
      self.createWatchdog()
      # TODO: temp thresholds are yet to be decided
      self.newComponent(Tmp75, addr=self.getSmbus(15).i2cAddr(0x4f), sensors=[
         SensorDesc(diode=0, name='BMC temp sensor',
                    position=Position.OTHER, target=70, overheat=80, critical=90),
      ])
      self.bmcMgmtNic = self.newComponent(BmcMgmtNic, cpuEeprom=self.cpuEeprom)
      self.newComponent(BmcUsbDeviceNic, udcName='12060000.usb-vhub:p1')

      self.newComponent(SonicReloadCauseCookieComponent,
                        causePriority=ReloadCausePriority.PREREBOOT)
      self.addReloadCauseProvider(priority=ReloadCausePriority.HARDWARE_MAIN)

   @classmethod
   def readChassisEeprom(cls):
      eeprom = At24C512(
         addr=cls._getChassisEepromBus().i2cAddr(cls.CHASSIS_EEPROM_ADDR),
         label=cls.CHASSIS_EEPROM_LABEL)
      eeprom.driver.setup()
      # Use prefdl() rather than readPrefdl() to use the
      # cached file in tmpfs if available.
      return eeprom.prefdl()

   @classmethod
   def _getChassisEepromBus(cls):
      return cls.getSmbus(cls.CHASSIS_EEPROM_BUS)

   def createBmcEeprom(self):
      return self.newComponent(
         At24C512, addr=self.getSmbus(14).i2cAddr(0x50), label='bmcEeprom')

   def createCpuEeprom(self):
      return self.newComponent(
         At24C512, addr=self.getSmbus(9).i2cAddr(0x50), label='cpuEeprom')

   def createChassisEeprom(self):
      return self.newComponent(
         At24C512,
         addr=self._getChassisEepromBus().i2cAddr(self.CHASSIS_EEPROM_ADDR),
         label=self.CHASSIS_EEPROM_LABEL)

   def cpuCpldAddr(self):
      return self.getSmbus(12).i2cAddr(0x43)

   def getBmcBaseMac(self):
      return self.bmcMgmtNic.getEepromMgmtMac()
