
from __future__ import absolute_import, division, print_function

from ..common import I2cComponent
from ..cpld import SysCpld, SysCpldCommonRegisters

from ...accessors.fan import FanImpl
from ...accessors.led import LedImpl

from ...core.log import getLogger
from ...core.register import Register, RegBitField

from ...drivers.cpld import SysCpldI2cDriver
from ...drivers.i2c import I2cKernelFanDriver
from ...drivers.psu import UpperlakePsuDriver
from ...drivers.sysfs import LedSysfsDriver

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
      RegBitField(0, 'scdReset', ro=True),
   )
   SEU_CONTROL = Register(0x10,
      RegBitField(0, 'enableCpldSeuCheck', ro=False),
      RegBitField(1, 'powerCycleOnCpldSeu', ro=False),
      RegBitField(7, 'cpldSeuDetected'),
   )

class CrowSysCpld(SysCpld):
   def __init__(self, addr, drivers=None, registerCls=CrowCpldRegisters, **kwargs):
      self.psus = []
      if not drivers:
         drivers = [UpperlakePsuDriver(driverName='psuStatusDriver', addr=addr),
                    SysCpldI2cDriver(addr=addr, registerCls=registerCls)]
      super(CrowSysCpld, self).__init__(addr=addr, drivers=drivers,
                                        registerCls=registerCls, **kwargs)

class KoiSysCpld(CrowSysCpld):
   def powerCycleOnSeu(self, value=None):
      res1 = self.drivers['SysCpldI2cDriver'].regs.powerCycleOnCrc(value)
      res2 = self.drivers['SysCpldI2cDriver'].regs.powerCycleOnCpldSeu(value)
      return res1 or res2

   def hasSeuError(self):
      return self.drivers['SysCpldI2cDriver'].regs.scdCrcError() or \
             self.drivers['SysCpldI2cDriver'].regs.cpldSeuDetected()

class CrowFanCpldComponent(I2cComponent):
   def __init__(self, addr=None, drivers=None, waitFile=None, fans=[], **kwargs):
      if not drivers:
         fanSysfsDriver = I2cKernelFanDriver(name='crow_cpld',
               module='crow-fan-driver', addr=addr, maxPwm=255, waitFile=waitFile)
         ledSysfsDriver = LedSysfsDriver(sysfsPath='/sys/class/leds')
         drivers = [fanSysfsDriver, ledSysfsDriver]
      super(CrowFanCpldComponent, self).__init__(addr=addr, drivers=drivers,
                                                 **kwargs)
      for fan in fans:
         self.createFan(fan.fanId)

   def createFan(self, fanId, driver='I2cKernelFanDriver',
                 ledDriver='LedSysfsDriver', **kwargs):
      logging.debug('creating crow fan %s', fanId)
      driver = self.drivers[driver]
      led = LedImpl(name='fan%s' % fanId, driver=self.drivers[ledDriver])
      fan = FanImpl(fanId=fanId, driver=driver, led=led, **kwargs)
      self.inventory.addFan(fan)
      return fan

