
from .otterlake_shim import OtterLakeShim
from ...components.dpm.ucd import Ucd90120A, Ucd90160, UcdMon, UcdGpi, UcdPriority
from ...components.eeprom import At24C512


from ...descs.cause import ReloadCauseDesc

from ...core.platform import registerPlatform

from ..cpu.sprucefish import SprucefishCpu

@registerPlatform()
class OtterLake(OtterLakeShim):

   PLATFORM = 'sprucefish'
   SID = ['Otterlake']
   SKU = ['DCS-7800-SUP', 'DCS-7800-SUP1A', 'DCS-7800-SUP1S']

   MAX_POWER_DRAW = 72
   TYP_POWER_DRAW = 61

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
