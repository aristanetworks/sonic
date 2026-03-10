
from ...core.component import Priority
from ...core.component.i2c import I2cComponent
from ...core.quirk import RegMapSetQuirk
from ...core.register import Register, RegisterMap, RegBitField

from ...drivers.rook import (
   LaFanCpldKernelDriver,
   TehamaFanCpldKernelDriver,
   RookStatusLedKernelDriver,
)

from ..cpld import SysCpld, SysCpldCommonRegistersV2

class RookSysCpldRegisters(SysCpldCommonRegistersV2):
   pass

class RookCpldRegisters(RegisterMap):
   POWER_CONTROL = Register(0x7100,
      RegBitField(0, 'powerCycleOnScFault', ro=False),
   )

class RookCpldPowerCycleOnScFaultQuirk(RegMapSetQuirk):
   description = 'enable power cycle on switch card fault'
   REG_NAME = 'powerCycleOnScFault'
   REG_VALUE = True

class RookSysCpld(SysCpld):
   REGISTER_CLS = RookSysCpldRegisters

class RookStatusLeds(I2cComponent):
   DRIVER = RookStatusLedKernelDriver
   PRIORITY = Priority.LED

class RookFanCpld(I2cComponent):
   PRIORITY = Priority.COOLING
   FAN_COUNT = 0

class LaFanCpld(RookFanCpld):
   DRIVER = LaFanCpldKernelDriver
   FAN_COUNT = 4

class TehamaFanCpld(RookFanCpld):
   DRIVER = TehamaFanCpldKernelDriver
   FAN_COUNT = 5
