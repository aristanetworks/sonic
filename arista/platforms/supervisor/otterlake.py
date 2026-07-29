
from ...components.denali.psu import DenaliPsuSlotDesc
from ...components.denali.supervisor import DenaliSupervisor
from ...components.dpm.ucd import Ucd90120A, Ucd90160, UcdMon, UcdGpi, UcdPriority
from ...components.eeprom import At24C512
from ...components.microsemi import MicrosemiPortDesc

from ...descs.cause import ReloadCauseDesc

from ...core.platform import registerPlatform

from ..cpu.sprucefish import SprucefishCpu

@registerPlatform()
class OtterLake(DenaliSupervisor):

   PLATFORM = 'sprucefish'
   SID = ['Otterlake']
   SKU = ['DCS-7800-SUP', 'DCS-7800-SUP1A', 'DCS-7800-SUP1S']

   MAX_POWER_DRAW = 72
   TYP_POWER_DRAW = 61

   LINECARD_PORTS = [
      MicrosemiPortDesc(32, 8, 0),
      MicrosemiPortDesc(33, 9, 0),
      MicrosemiPortDesc(34, 10, 0),
      MicrosemiPortDesc(35, 11, 0),
      MicrosemiPortDesc(36, 12, 0),
      MicrosemiPortDesc(37, 13, 0),
      MicrosemiPortDesc(38, 14, 0),
      MicrosemiPortDesc(39, 15, 0),
   ]

   FABRIC_PORTS = [
      MicrosemiPortDesc(24, 1, 0),
      MicrosemiPortDesc(25, 2, 0),
      MicrosemiPortDesc(26, 3, 0),
      MicrosemiPortDesc(27, 4, 0),
      MicrosemiPortDesc(28, 5, 0),
      MicrosemiPortDesc(29, 6, 0),
   ]

   PSUS = [
      DenaliPsuSlotDesc(psuId=1, bank=1, slot=1, bus=16, addr=0x70),
      DenaliPsuSlotDesc(psuId=2, bank=1, slot=2, bus=16, addr=0x71),
      DenaliPsuSlotDesc(psuId=3, bank=1, slot=3, bus=16, addr=0x72),
      DenaliPsuSlotDesc(psuId=4, bank=1, slot=4, bus=17, addr=0x70),
      DenaliPsuSlotDesc(psuId=5, bank=1, slot=5, bus=17, addr=0x71),
      DenaliPsuSlotDesc(psuId=6, bank=1, slot=6, bus=17, addr=0x72),
      DenaliPsuSlotDesc(psuId=7, bank=2, slot=1, bus=18, addr=0x70),
      DenaliPsuSlotDesc(psuId=8, bank=2, slot=2, bus=18, addr=0x71),
      DenaliPsuSlotDesc(psuId=9, bank=2, slot=3, bus=18, addr=0x72),
      DenaliPsuSlotDesc(psuId=10, bank=2, slot=4, bus=19, addr=0x70),
      DenaliPsuSlotDesc(psuId=11, bank=2, slot=5, bus=19, addr=0x71),
      DenaliPsuSlotDesc(psuId=12, bank=2, slot=6, bus=19, addr=0x72),
   ]

   def addCpuComplex(self):
      self.cpu = self.newComponent(SprucefishCpu)

      self.cpu.cpld.newComponent(Ucd90160, self.cpu.cpuDpmAddr(),
                                 causePriority=UcdPriority.HARDWARE_SECONDARY)
      self.cpu.cpld.newComponent(Ucd90120A, self.cpu.shimDpmAddr(), causes=[
         UcdGpi(4, ReloadCauseDesc.REBOOT, 'Rebooted by peer supervisor'),
         UcdGpi(5, ReloadCauseDesc.REBOOT),
         UcdGpi(6, ReloadCauseDesc.WATCHDOG),
         UcdMon(9, ReloadCauseDesc.POWERLOSS),
      ], causePriority=UcdPriority.HARDWARE_MAIN)

      self.eeprom = self.cpu.cpld.newComponent(At24C512, label='supervisor_shim',
                                               addr=self.cpu.shimEepromAddr())
