from ...core.platform import registerPlatform

from ...components.asic.dnx.ramon import Ramon
from ...components.denali.desc import DenaliAsicDesc
from ...components.max31790 import Max31790
from ...components.tmp464 import Tmp464

from ...descs.sensor import SensorDesc, Position

from .dragonfly import Dragonfly

@registerPlatform()
class Brooks(Dragonfly):
   SID = ['Brooks']
   SKU = ['DCS-7804-FM']

   MAX_POWER_DRAW = 248
   TYP_POWER_DRAW = 180

   ASICS = [
      DenaliAsicDesc(cls=Ramon, asicId=0),
      DenaliAsicDesc(cls=Ramon, asicId=1),
   ]

   def createStandbyFans(self):
      chip = self.pca.newComponent(Max31790, self.pca.i2cAddr(0x2d),
                                   name='amax31790_4u')
      self.createStandbyFansForChip(chip, 1, 4)

   def createStandbySensors(self):
      slot_prefix = f'FABRIC-CARD{self.getRelativeSlotId()} '
      self.pca.newComponent(Tmp464, self.pca.i2cAddr(0x48), sensors=[
         SensorDesc(diode=0, name=slot_prefix + 'Board sensor 1',
                    position=Position.OTHER, target=75, overheat=85, critical=95),
         SensorDesc(diode=1, name=slot_prefix + 'Ramon 0 PCB',
                    position=Position.OTHER, target=70, overheat=80, critical=90),
         SensorDesc(diode=2, name=slot_prefix + 'Ramon 1 PCB',
                    position=Position.OTHER, target=70, overheat=80, critical=90),
         SensorDesc(diode=3, name=slot_prefix + 'Outlet',
                    position=Position.OUTLET, target=75, overheat=85, critical=95),
         SensorDesc(diode=4, name=slot_prefix + 'Inlet',
                    position=Position.INLET, target=75, overheat=85, critical=95),
      ])
      self.pca.newComponent(Tmp464, self.pca.i2cAddr(0x49), sensors=[
         SensorDesc(diode=0, name=slot_prefix + 'Board sensor 2',
                    position=Position.OTHER, target=75, overheat=85, critical=95),
         SensorDesc(diode=2, name=slot_prefix + 'Ramon 0 Core (secondary)',
                    position=Position.OTHER, target=75, overheat=85, critical=95),
         SensorDesc(diode=3, name=slot_prefix + 'Ramon 1 Core (secondary)',
                    position=Position.OTHER, target=75, overheat=85, critical=95),
      ])
