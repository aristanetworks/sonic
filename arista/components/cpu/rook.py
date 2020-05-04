from ..common import I2cComponent
from ..cpld import SysCpld, SysCpldCommonRegisters

from ...accessors.fan import FanImpl
from ...accessors.led import LedImpl

from ...core.log import getLogger
from ...core.register import Register, RegBitField

from ...drivers.i2c import I2cKernelFanDriver
from ...drivers.rook import RookLedSysfsDriver, RookStatusLedKernelDriver
from ...drivers.sysfs import LedSysfsDriver

logging = getLogger(__name__)

class RookCpldRegisters(SysCpldCommonRegisters):
   INTERRUPT_STS = Register(0x08,
      RegBitField(0, 'scdCrcError'),
   )
   SCD_CTRL_STS = Register(0x0A,
      RegBitField(0, 'scdConfDone'),
      RegBitField(1, 'scdInitDone'),
      RegBitField(5, 'scdReset', ro=False),
   )
   PWR_CYC_EN = Register(0x17,
      RegBitField(0, 'powerCycleOnCrc', ro=False),
   )

class RookSysCpld(SysCpld):
   def __init__(self, addr, drivers=None, registerCls=RookCpldRegisters, **kwargs):
      super(RookSysCpld, self).__init__(addr=addr, drivers=drivers,
                                        registerCls=registerCls, **kwargs)

class RookStatusLeds(I2cComponent):
   def __init__(self, addr=None, leds=None, **kwargs):
      drivers = [
         RookStatusLedKernelDriver(addr=addr),
         RookLedSysfsDriver(sysfsPath='/sys/class/leds/'),
      ]
      super(RookStatusLeds, self).__init__(addr=addr, drivers=drivers, **kwargs)
      for led in leds or []:
         self.createLed(led)

   def createLed(self, led):
      led = LedImpl(name=led.name, colors=led.colors,
                    driver=self.drivers['RookLedSysfsDriver'])
      self.inventory.addLed(led)
      return led

class LAFanCpldComponent(I2cComponent):
   def __init__(self, addr=None, drivers=None, waitFile=None, fans=[], **kwargs):
      if not drivers:
         fanSysfsDriver = I2cKernelFanDriver(name='la_cpld',
               module='rook-fan-cpld', addr=addr, maxPwm=255, waitFile=waitFile)
         ledSysfsDriver = LedSysfsDriver(sysfsPath='/sys/class/leds')
         drivers = [fanSysfsDriver, ledSysfsDriver]
      super(LAFanCpldComponent, self).__init__(addr=addr, drivers=drivers,
                                               **kwargs)
      for fan in fans:
         self.createFan(fan.fanId)

   def createFan(self, fanId, driver='I2cKernelFanDriver',
                 ledDriver='LedSysfsDriver', **kwargs):
      logging.debug('creating LA fan %s', fanId)
      driver = self.drivers[driver]
      led = LedImpl(name='fan%s' % fanId, driver=self.drivers[ledDriver])
      fan = FanImpl(fanId=fanId, driver=driver, led=led, **kwargs)
      self.inventory.addFan(fan)
      return fan

class TehamaFanCpldComponent(I2cComponent):
   def __init__(self, addr=None, drivers=None, waitFile=None, fans=[], **kwargs):
      if not drivers:
         fanSysfsDriver = I2cKernelFanDriver(name='tehama_cpld',
               module='rook-fan-cpld', addr=addr, maxPwm=255, waitFile=waitFile)
         ledSysfsDriver = LedSysfsDriver(sysfsPath='/sys/class/leds')
         drivers = [fanSysfsDriver, ledSysfsDriver]
      super(TehamaFanCpldComponent, self).__init__(addr=addr, drivers=drivers,
                                                   **kwargs)
      for fan in fans:
         self.createFan(fan.fanId)

   def createFan(self, fanId, driver='I2cKernelFanDriver',
                 ledDriver='LedSysfsDriver', **kwargs):
      logging.debug('creating Tehama fan %s', fanId)
      driver = self.drivers[driver]
      led = LedImpl(name='fan%s' % fanId, driver=self.drivers[ledDriver])
      fan = FanImpl(fanId=fanId, driver=driver, led=led, **kwargs)
      self.inventory.addFan(fan)
      return fan

