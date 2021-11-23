
from ...core.register import RegBitField, RegisterMap
from ...drivers.pca9555 import GpioRegister
from ...libs.wait import waitFor

from ..pca9555 import Pca9555
from ..plx import PlxPex8700

from .card import DenaliFabricBase

class Gpio1Registers(RegisterMap):
   A = GpioRegister(0x0,
      RegBitField(0, 'powerGood'),
      RegBitField(1, 'tempAlert', flip=True),
      RegBitField(4, 'powerCycle', ro=False),
   )
   B = GpioRegister(0x1,
      RegBitField(0, 'ecbOn', ro=False),
      RegBitField(1, 'statusGreen', flip=True, ro=False),
      RegBitField(2, 'statusRed', flip=True, ro=False),
      RegBitField(3, 'pcieUpstream', ro=False),
      RegBitField(5, 'ejectorClosed', flip=True),
      RegBitField(6, 'pcieReset', flip=True, ro=False),
      RegBitField(7, 'fanFull', ro=False),
   )

class DenaliFabric(DenaliFabricBase):
   PLATFORM = None

   def createGpio1(self):
      self.gpio1 = self.pca.newComponent(Pca9555, addr=self.pca.i2cAddr(0x20),
                                         registerCls=Gpio1Registers)

   def createPlx(self):
      self.plx = self.pca.newComponent(PlxPex8700, addr=self.pca.i2cAddr(0x38))

   def powerStandbyDomainIs(self, on):
      '''Turn on card Ecbs and fan Ecbs. On Denali fabric, we expect
         Dpms will then be turned on as well as Pols by hardware. So no need to
         do anything with Dpm. When all is done, power good is asserted.'''
      assert self.gpio1, "gpio1 is not created yet."
      if on:
         self.gpio1.ecbOn(True)
         waitFor(self.gpio1.powerGood, "card to turn on",
                 interval=50)
      else:
         self.gpio1.ecbOn(False)
         # NOTE: Disabling power good check for Dragonfly
         # waitFor(lambda: (not self.gpio1.powerGood()), "cart to turn off" )
