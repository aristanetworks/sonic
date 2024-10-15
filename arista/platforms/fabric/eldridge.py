from ...core.cooling import Airflow
from ...core.hwapi import HwApi
from ...core.platform import registerPlatform
from ...core.register import RegBitField, RegisterMap
from ...core.utils import incrange

from ...components.asic.dnx.ramon import Ramon
from ...components.denali.desc import DenaliAsicDesc
from ...components.denali.fabric import DenaliFabric
from ...components.dpm.ucd import Ucd90320
from ...components.max31790 import Max31790
from ...components.max6658 import Max6658
from ...components.pca9555 import Pca9555
from ...components.plx import PlxPortDesc
from ...components.tmp464 import Tmp464
from ...components.tmp468 import Tmp468

from ...descs.fan import FanDesc, FanPosition
from ...descs.sensor import SensorDesc, Position

from ...drivers.pca9555 import GpioRegister

class Gpio2Registers(RegisterMap):
   A = GpioRegister(0x0,
      RegBitField(0, 'fanFault1', ro=False),
      RegBitField(1, 'fanFault2', ro=False),
      RegBitField(2, 'fanFault3', ro=False),
      RegBitField(3, 'fanFault4', ro=False),
      RegBitField(4, 'fanFault5', ro=False),
      RegBitField(5, 'fanFault6', ro=False),
      RegBitField(6, 'fanFault7', ro=False),
      RegBitField(7, 'fanFault8', ro=False),
   )
   B = GpioRegister(0x1,
      RegBitField(0, 'ramon0SysReset', flip=True, ro=False),
      RegBitField(1, 'ramon0PcieReset', flip=True, ro=False),
      RegBitField(2, 'ramon1SysReset', flip=True, ro=False),
      RegBitField(3, 'ramon1PcieReset', flip=True, ro=False),
      RegBitField(4, 'ramon2SysReset', flip=True, ro=False),
      RegBitField(5, 'ramon2PcieReset', flip=True, ro=False),
      RegBitField(6, 'ramonSmbusEnable', flip=True, ro=False),
      RegBitField(7, 'polSmbusEnable', flip=True, ro=False),
   )

@registerPlatform()
class Eldridge(DenaliFabric):
   SID = ['Eldridge']
   SKU = ['DCS-7808-FM', '7808R3-FM']

   MAX_POWER_DRAW = 778
   TYP_POWER_DRAW = 510

   ASICS = [
      DenaliAsicDesc(cls=Ramon, asicId=0),
      DenaliAsicDesc(cls=Ramon, asicId=1),
      DenaliAsicDesc(cls=Ramon, asicId=2),
   ]

   PLX_PORTS = [
      PlxPortDesc(port=0, name='sup1', upstream=True),
      PlxPortDesc(port=1, name='ramon0'),
      PlxPortDesc(port=2, name='sup2', upstream=True),
      PlxPortDesc(port=3, name='ramon1'),
      PlxPortDesc(port=4, name='ramon2'),
   ]

   def createGpio2(self):
      self.gpio2 = self.pca.newComponent(Pca9555, addr=self.pca.i2cAddr(0x21),
                                         registerCls=Gpio2Registers)

   def standbyDomain(self):
      self.createGpio2()
      self.createStandbyFans()
      self.createStandbySensors()

   def createStandbyFansForChip(self, chip, begin, end):
      for i, slotId in enumerate(incrange(begin, end)):
         led = self.gpio2.addGpioLed('fanFault%d' % slotId)
         chip.addFan(FanDesc(fanId=i * 2 + 1, position=FanPosition.INLET,
                             airflow=Airflow.EXHAUST,
                             namespaceFn=self.getRelativeSlotId), led=led)
         chip.addFan(FanDesc(fanId=i * 2 + 2, position=FanPosition.OUTLET,
                             airflow=Airflow.EXHAUST,
                             namespaceFn=self.getRelativeSlotId), led=led)

   def createStandbyFans(self):
      chip1 = self.pca.newComponent(Max31790, self.pca.i2cAddr(0x2d),
                                    name='amax31790_8u')
      chip2 = self.pca.newComponent(Max31790, self.pca.i2cAddr(0x2c),
                                    name='amax31790_8u')
      self.createStandbyFansForChip(chip1, 1, 4)
      self.createStandbyFansForChip(chip2, 5, 8)

   def createOldStandbySensors(self):
      self.pca.newComponent(Tmp468, self.pca.i2cAddr(0x48), sensors=[
         SensorDesc(diode=0, name='Board sensor 1',
                    position=Position.OTHER, target=75, overheat=85, critical=95),
         SensorDesc(diode=1, name='Ramon 0 PCB',
                    position=Position.OTHER, target=70, overheat=80, critical=90),
         SensorDesc(diode=2, name='Ramon 1 PCB',
                    position=Position.OTHER, target=70, overheat=80, critical=90),
         SensorDesc(diode=3, name='Ramon 2 PCB',
                    position=Position.OTHER, target=70, overheat=80, critical=90),
         SensorDesc(diode=4, name='Inlet',
                    position=Position.INLET, target=75, overheat=85, critical=95),
         SensorDesc(diode=5, name='Exhaust',
                    position=Position.OUTLET, target=75, overheat=85, critical=95),
         SensorDesc(diode=7, name='Ramon 0 Core (secondary)',
                    position=Position.OTHER, target=75, overheat=85, critical=95),
         SensorDesc(diode=8, name='Ramon 1 Core (secondary)',
                    position=Position.OTHER, target=75, overheat=85, critical=95),
      ])
      self.pca.newComponent(Max6658, self.pca.i2cAddr(0x4c), sensors=[
         SensorDesc(diode=0, name='Ramon 2 Core (secondary)',
                    position=Position.OTHER, target=75, overheat=85, critical=95),
      ])

   def createStandbySensors(self):
      if self.getHwApi() < HwApi(42):
         self.createOldStandbySensors()
         return

      self.pca.newComponent(Tmp464, self.pca.i2cAddr(0x48), sensors=[
         SensorDesc(diode=0, name='Board sensor 1',
                    position=Position.OTHER, target=75, overheat=85, critical=95),
         SensorDesc(diode=1, name='Ramon 0 PCB',
                    position=Position.OTHER, target=70, overheat=80, critical=90),
         SensorDesc(diode=2, name='Ramon 1 PCB',
                    position=Position.OTHER, target=70, overheat=80, critical=90),
         SensorDesc(diode=3, name='Ramon 2 PCB',
                    position=Position.OTHER, target=70, overheat=80, critical=90),
         SensorDesc(diode=4, name='Inlet',
                    position=Position.INLET, target=75, overheat=85, critical=95),
      ])
      self.pca.newComponent(Tmp464, self.pca.i2cAddr(0x49), sensors=[
         SensorDesc(diode=0, name='Board sensor 2',
                    position=Position.OTHER, target=75, overheat=85, critical=95),
         SensorDesc(diode=1, name='Exhaust',
                    position=Position.OUTLET, target=75, overheat=85, critical=95),
         SensorDesc(diode=2, name='Ramon 0 Core (secondary)',
                    position=Position.OTHER, target=75, overheat=85, critical=95),
         SensorDesc(diode=3, name='Ramon 1 Core (secondary)',
                    position=Position.OTHER, target=75, overheat=85, critical=95),
         SensorDesc(diode=4, name='Ramon 2 Core (secondary)',
                    position=Position.OTHER, target=75, overheat=85, critical=95),
      ])

   def powerStandbyDomainIs(self, on):
      super(Eldridge, self).powerStandbyDomainIs(on)
      if on:
         # Always enable 2 pins to access Ramon and Pol via Smbus
         self.gpio2.ramonSmbusEnable(True)
         self.gpio2.polSmbusEnable(True)

   def createStandbyDpm(self):
      self.control.newComponent(Ucd90320, addr=self.pca.i2cAddr(0x11))
