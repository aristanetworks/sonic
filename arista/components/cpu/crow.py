
from ...core.component import Priority
from ...core.component.i2c import I2cComponent
from ...core.log import getLogger
from ...core.quirk import Quirk
from ...core.register import Register, RegBitField
from ...core.utils import LastRebootType, inSimulation

from ...drivers.crow import CrowFanCpldKernelDriver

from ..cpld import SysCpld, SysCpldCommonRegisters, SysCpldSeuReporter

logging = getLogger(__name__)

class CrowCpldRegisters(SysCpldCommonRegisters):
   POWER_GOOD = Register(0x05,
      RegBitField(0, 'powerGood'),
   )
   SCD_CRC_REG = Register(0x09,
      RegBitField(0, 'powerCycleOnCrc', ro=False),
   )
   SCD_CTRL_STS = Register(0x0A,
      RegBitField(0, 'scdConfDone'),
      RegBitField(1, 'scdInitDone'),
      RegBitField(2, 'scdCrcError'),
   )
   SCD_RESET_REG = Register(0x0B,
      RegBitField(0, 'scdReset', ro=False),
   )

class KoiCpldRegisters(CrowCpldRegisters):
   FAULT_STATUS = Register(0x0C,
      RegBitField(0, 'psu2DcOk'),
      RegBitField(1, 'psu1DcOk'),
      RegBitField(2, 'psu2AcOk'),
      RegBitField(3, 'psu1AcOk'),
   )
   SEU_CONTROL = Register(0x10,
      RegBitField(0, 'enableCpldSeuCheck', ro=False),
      RegBitField(1, 'powerCycleOnCpldSeu', ro=False),
      RegBitField(7, 'cpldSeuDetected'),
   )

class DramScrubberQuirk(Quirk):
   DELAYED = True
   def __init__(self, rate=3121951, description='enable DRAM scrubber'):
      # Enable memory scrubber at a defined pace
      # linux/drivers/edac/amd64_edac.c for available rates
      # linux/drivers/edac/edac_mc_sysfs.c for sysfs logic
      # here 3.12MBps ~0.02% bandwidth for DDR3 1866MT/s taking ~45mins for 8GB
      self.rate = rate
      self.description = description

   def __str__(self):
      return self.description

   def run(self, component):
      if inSimulation():
         return
      if LastRebootType.get() != LastRebootType.COLD:
         # Performing the scrubbing after a device has run for a while
         # increases the risk of finding 2bit errors which are uncorrectable.
         # Therefore do not turn on memory scrubber after a warm/fast reboot
         # If the setting was set prior to a warm/fast reboot it would persist
         return
      path = '/sys/devices/system/edac/mc/mc0/sdram_scrub_rate'
      with open(path, 'w', encoding='utf8') as f:
         f.write(str(self.rate))

class KoiSysCpldSeuReporter(SysCpldSeuReporter):
   def hasSeuError(self):
      return self.cpld.driver.regs.scdCrcError() or \
            self.cpld.driver.regs.cpldSeuDetected()

   def powerCycleOnSeu(self, on=None):
      res1 = self.cpld.driver.regs.powerCycleOnCrc(on)
      res2 = self.cpld.driver.regs.powerCycleOnCpldSeu(on)
      return res1 or res2

class CrowSysCpld(SysCpld):
   REGISTER_CLS = CrowCpldRegisters
   QUIRKS = [
      DramScrubberQuirk(),
   ]

class KoiSysCpld(CrowSysCpld):
   SEU_REPORTER_CLS = KoiSysCpldSeuReporter

class CrowFanCpld(I2cComponent):
   DRIVER = CrowFanCpldKernelDriver
   PRIORITY = Priority.THERMAL
