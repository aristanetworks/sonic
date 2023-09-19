
from ...core.component import Priority
from ...core.component.i2c import I2cComponent
from ...core.log import getLogger
from ...core.register import Register, RegBitField

from ...drivers.crow import CrowFanCpldKernelDriver

from ..cpld import SysCpld, SysCpldCommonRegisters

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

class CrowSysCpld(SysCpld):
   REGISTER_CLS = CrowCpldRegisters

   def powerCycleOnSeu(self, value=None):
      if not isinstance(self.driver.regs, KoiCpldRegisters):
         return super().powerCycleOnSeu(value)

      res1 = self.driver.regs.powerCycleOnCrc(value)
      res2 = self.driver.regs.powerCycleOnCpldSeu(value)
      return res1 or res2

   def hasSeuError(self):
      if not isinstance(self.driver.regs, KoiCpldRegisters):
         return super().hasSeuError()

      return self.driver.regs.scdCrcError() or \
             self.driver.regs.cpldSeuDetected()

class CrowFanCpld(I2cComponent):
   DRIVER = CrowFanCpldKernelDriver
   PRIORITY = Priority.THERMAL
