
from ...core.register import RegisterMap, RegBitField, Rw1cRegister

from . import AspeedSoc

SCU0_BASE = 0x12c02000
SCU1_BASE = 0x14c02000

SCU0_SYSTEM_RESET_EVENT_LOG_SET_0_REG_OFFSET = 0x50

class Ast2720ReloadCauseRegisters(RegisterMap):
   RESET_LOG_0 = Rw1cRegister(
      SCU0_SYSTEM_RESET_EVENT_LOG_SET_0_REG_OFFSET,
      RegBitField(11, 'pwrst', ro=False),
      base=SCU0_BASE,
   )

class Ast2720(AspeedSoc):
   I2C_BASE   = 0x14c0f000
   I2C_STRIDE = 0x100
   I2C_SUFFIX = 'i2c-bus'

   RELOAD_CAUSE_REGMAP = Ast2720ReloadCauseRegisters
