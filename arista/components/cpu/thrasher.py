from ...core.quirk import RegMapSetQuirk
from ...core.register import Register, RegBitField

from ..cpld import SysCpld, SysCpldCommonRegisters
from ..scd import ScdReloadCauseRegisters

class ThrasherSysCpldRegisters(SysCpldCommonRegisters):
   PWR_CTRL_STS = Register(0x05,
      RegBitField(7, 'pwrCtrl7', ro=False),
      RegBitField(6, 'pwrCtrl6', ro=False),
      RegBitField(5, 'pwrCtrl5', ro=False),
      RegBitField(4, 'pwrCtrl4', ro=False),
      RegBitField(3, 'pwrCtrl3', ro=False),
      RegBitField(2, 'pwrCtrl2', ro=False),
      RegBitField(1, 'pwrCtrl1', ro=False),
      RegBitField(0, 'switchCardPowerGood'),
   )
   SCD_CTRL_STS_0 = Register(0x0A,
      RegBitField(5, 'scd0Reset', ro=False),
      RegBitField(4, 'scd0Hold', ro=False),
      RegBitField(3, 'scd0Program', ro=False),
      RegBitField(0, 'scd0ConfDone'),
   )
   SCD_CTRL_STS_1 = Register(0x0B,
      RegBitField(5, 'scd1Reset', ro=False),
      RegBitField(4, 'scd1Hold', ro=False),
      RegBitField(3, 'scd1Program', ro=False),
      RegBitField(0, 'scd1ConfDone'),
   )
   WD_CTRL = Register(0x11,
      RegBitField(3, 'watchdogPwrCycEn', ro=False),
      RegBitField(2, 'powerCycleOnCrc', ro=False),
   )

class CpuScdPowerCycleOnWdFaultQuirk(RegMapSetQuirk):
   description = 'enable power cycle on watchdog interrupt'
   REG_NAME = 'watchdogPwrCycEn'
   REG_VALUE = True

class ThrasherSysCpld(SysCpld):
   REGISTER_CLS = ThrasherSysCpldRegisters

class ThrasherReloadCauseRegisters(ScdReloadCauseRegisters):
   pass
