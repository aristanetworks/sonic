from ..cpld import LeakDetectionCpldRegistersV1
from ...core.register import Register, RegBitField, RegBitRange, RegisterMap

class MarconiCpldRegistersBase(RegisterMap):
   SYSTEM_PWR_CYCLE = Register(0x70, name='systemPwrCycle', ro=False)
   NON_STANDBY_PWR_CYCLE = Register(0x79, name='nonStandbyPwrCycle', ro=False)
   SWC_PWR_STATUS = Register(0x20,
      RegBitField(2, 'swcPwrStatus'),
   )
   NON_STANDBY_PWR_CTRL = Register(0x7c,
      RegBitRange(1, 2, 'nonStandbyPwrCtrl', ro=False),
   )
   HOST_CPU_PWR = Register(0x72,
      RegBitField(0, 'hostCpuReset', ro=False),
      RegBitField(1, 'hostCpuPwrStatus'),
   )
   REVISION = Register(0x01, name='revision')
   MINOR = Register(0x00, name='revisionMinor')

class MarconiCpldRegisters(MarconiCpldRegistersBase, LeakDetectionCpldRegistersV1):
   pass
