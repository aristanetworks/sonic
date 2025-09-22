
from ...core.register import Register, RegBitField

from ..cpld import SysCpld, SysCpldCommonRegisters
from ..scd import ScdReloadCauseRegisters

class ShearwaterSysCpldRegisters(SysCpldCommonRegisters):
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
   SCD_CTRL_STS = Register(0x0A,
      RegBitField(6, 'scdInit', flip=True),
      RegBitField(5, 'scdReset', ro=False),
      RegBitField(4, 'scdHold', ro=False),
      RegBitField(3, 'scdConfig', ro=False),
      RegBitField(1, 'scdInitDone'),
      RegBitField(0, 'scdConfDone'),
   )
   PWR_CYC_EN = Register(0x11,
      RegBitField(2, 'powerCycleOnCrc', ro=False),
   )
   RT_FAULT_0 = Register(0x46,
      RegBitField(2, 'scdCrcError'),
   )

class ShearwaterSysCpld(SysCpld):
   REGISTER_CLS = ShearwaterSysCpldRegisters

class ShearwaterReloadCauseRegisters(ScdReloadCauseRegisters):
   pass
