from ...core.platform import registerPlatform

from ...components.asic.dnx.ramon import Ramon
from ...components.denali.desc import DenaliAsicDesc
from ...components.plx import PlxPortDesc
from ...components.tmp464 import Tmp464
from ...descs.sensor import SensorDesc, Position

from .eldridge import Eldridge

@registerPlatform()
class Dragonfly(Eldridge):
   SID = ['Dragonfly']
   SKU = ['7808R3A-FM']

   MAX_POWER_DRAW = 518
   TYP_POWER_DRAW = 370

   ASICS = [
      DenaliAsicDesc(cls=Ramon, asicId=0),
      DenaliAsicDesc(cls=Ramon, asicId=1),
   ]

   PLX_PORTS = [
      PlxPortDesc(port=0, name='sup1', upstream=True),
      PlxPortDesc(port=1, name='ramon0'),
      PlxPortDesc(port=2, name='sup2', upstream=True),
      PlxPortDesc(port=3, name='ramon1'),
   ]

   def createStandbySensors(self):
      slot_prefix = f'FABRIC-CARD{self.getRelativeSlotId()} '
      self.pca.newComponent(Tmp464, self.pca.i2cAddr(0x48), sensors=[
         SensorDesc(diode=0, name=slot_prefix + 'Board sensor 1',
                    position=Position.OTHER, target=75, overheat=85, critical=95),
         SensorDesc(diode=1, name=slot_prefix + 'Ramon 0 PCB',
                    position=Position.OTHER, target=70, overheat=80, critical=90),
         SensorDesc(diode=2, name=slot_prefix + 'Ramon 1 PCB',
                    position=Position.OTHER, target=70, overheat=80, critical=90),
         SensorDesc(diode=4, name=slot_prefix + 'Inlet',
                    position=Position.INLET, target=75, overheat=85, critical=95),
      ])
      self.pca.newComponent(Tmp464, self.pca.i2cAddr(0x49), sensors=[
         SensorDesc(diode=0, name=slot_prefix + 'Board sensor 2',
                    position=Position.OTHER, target=75, overheat=85, critical=95),
         SensorDesc(diode=1, name=slot_prefix + 'Exhaust',
                    position=Position.OUTLET, target=75, overheat=85, critical=95),
         SensorDesc(diode=2, name=slot_prefix + 'Ramon 0 Core (secondary)',
                    position=Position.OTHER, target=75, overheat=85, critical=95),
         SensorDesc(diode=3, name=slot_prefix + 'Ramon 1 Core (secondary)',
                    position=Position.OTHER, target=75, overheat=85, critical=95),
      ])
