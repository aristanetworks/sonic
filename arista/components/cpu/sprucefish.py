
from ...core.quirk import RegMapSetQuirk
from ...core.register import Register, RegisterMap, RegBitField

class CpldSeuRegisterMap(RegisterMap):
   SCD_CTRL = Register(0x2300,
      RegBitField(3, 'powerCycleOnSeu', ro=False),
      RegBitField(2, 'hasSeuError', ro=False),
   )

class CpldWatchdogRegisterMap(RegisterMap):
   WD_CTRL = Register(0x7f00,
      RegBitField(0, 'watchdogPwrCycEn', ro=False),
   )

class CpuScdPowerCycleOnWdFaultQuirk(RegMapSetQuirk):
   description = 'enable power cycle on watchdog interrupt'
   REG_NAME = 'watchdogPwrCycEn'
   REG_VALUE = True
