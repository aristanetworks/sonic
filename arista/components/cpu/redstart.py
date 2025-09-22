
from ..cpld import SysCpld
from ..scd import ScdReloadCauseRegisters

from .shearwater import (
   ShearwaterSysCpldRegisters,
   ShearwaterPowerCycleOnRailFaultQuirk
)

class RedstartSysCpld(SysCpld):
   REGISTER_CLS = ShearwaterSysCpldRegisters
   QUIRKS = [ShearwaterPowerCycleOnRailFaultQuirk()]

class RedstartReloadCauseRegisters(ScdReloadCauseRegisters):
   pass
