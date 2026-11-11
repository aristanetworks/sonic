
from ...core.register import RegisterMap, RegBitField, Rw1cRegister
from ...descs.cause import ReloadCauseDesc

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
   def __str__(self):
      return 'Ast2720()'
   RELOAD_CAUSE_REGMAP = Ast2720ReloadCauseRegisters
   WDT_BOOTSTATUS_PATHS = [
      '/sys/class/watchdog/watchdog0/bootstatus',
      '/sys/class/watchdog/watchdog1/bootstatus',
   ]
   WDT_BOOTSTATUS_VAL_REASON_MAP = {
      0x0001: (ReloadCauseDesc.CPU_OVERTEMP, 'overheat reset'),
      0x0002: (ReloadCauseDesc.NO_FANS, 'fan fault reset'),
      0x0010: (ReloadCauseDesc.POWERLOSS, 'power under voltage'),
      0x0040: (ReloadCauseDesc.POWERLOSS, 'power over voltage'),
      0x0020: (ReloadCauseDesc.WATCHDOG, 'timeout detected via bootstatus'),
      0x0004: (ReloadCauseDesc.UNKNOWN, 'external reset'),
      0x0008: (ReloadCauseDesc.UNKNOWN, 'external reset'),
   }
