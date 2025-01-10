
from ..cpld import SysCpld, SysCpldCommonRegistersV2

class CormorantCpldRegisters(SysCpldCommonRegistersV2):
   pass

class CormorantSysCpld(SysCpld):
   REGISTER_CLS = CormorantCpldRegisters
