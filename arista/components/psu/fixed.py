from ...core.cooling import Airflow
from ...core.psu import PsuModel, PsuIdent

from ...descs.psu import PsuDesc

class FixedPsuModel(PsuModel):
   MANUFACTURER = 'arista'
   DESCRIPTION = PsuDesc()

class Fixed100AC(FixedPsuModel):
   CAPACITY = 100
   IDENTIFIERS = [
      PsuIdent('PWR-545-AC', 'PWR-545-AC', Airflow.EXHAUST)
   ]

class Fixed240DC(FixedPsuModel):
   CAPACITY = 240
   IDENTIFIERS = [
      PsuIdent('PWR-638-DC', 'PWR-638-DC', Airflow.EXHAUST)
   ]
