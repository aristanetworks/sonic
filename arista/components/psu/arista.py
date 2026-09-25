from ...core.cooling import Airflow
from ...core.psu import PsuModel, PsuIdent

from . import PmbusPsu
from .helper import psuDescHelper, Position

class AristaPsu(PsuModel):
   MANUFACTURER = 'arista'
   PMBUS_ADDR = 0x58
   PMBUS_CLS = PmbusPsu

class Pwr568(AristaPsu):
   CAPACITY = 2000
   DESCRIPTION = psuDescHelper(
      sensors=[
         ('inlet', Position.OTHER, 60, 65, 70),
         ('secondary hotspot', Position.OTHER, 110, 120, 130),
         ('primary hotspot', Position.OTHER, 110, 115, 120),
      ],
      maxRpm=25500,
   )
   IDENTIFIERS = [
      PsuIdent('PWR-00568', 'PWR-2011-AC-RED', Airflow.EXHAUST),
   ]

class Pwr581(AristaPsu):
   CAPACITY = 500
   DESCRIPTION = psuDescHelper(
      sensors=[
         ('inlet', Position.INLET, 55, 65, 70),
         ('primary hotspot', Position.OTHER, 80, 88, 93),
         ('secondary hotspot', Position.OTHER, 80, 108, 113),
      ],
      maxRpm=20500,
   )
   IDENTIFIERS = [
      PsuIdent('PWR-00581', 'PWR-512-AC-RED', Airflow.EXHAUST),
      PsuIdent('PWR-00582', 'PWR-512-AC-BLUE', Airflow.INTAKE),
   ]

class Pwr585(AristaPsu):
   # Also for Pwr586
   CAPACITY = 1500
   DESCRIPTION = psuDescHelper(
      sensors=[
         ('secondary hotspot', Position.OTHER, 80, 108, 113),
         ('inlet', Position.OTHER, 55, 65, 70),
         ('primary hotspot', Position.OTHER, 80, 88, 93),
      ],
      maxRpm=23000,
   )
   IDENTIFIERS = [
      PsuIdent('PWR-00585', 'PWR-1513-AC-RED', Airflow.EXHAUST),
      PsuIdent('PWR-00586', 'PWR-1513-AC-BLUE', Airflow.INTAKE),
   ]

class Pwr591(AristaPsu):
   CAPACITY = 2400
   DESCRIPTION = psuDescHelper(
      sensors=[
         ('inlet', Position.OTHER, 60, 65, 70),
         ('secondary hotspot', Position.OTHER, 110, 120, 130),
         ('primary hotspot', Position.OTHER, 110, 115, 120),
      ],
      maxRpm=25500,
   )
   IDENTIFIERS = [
      PsuIdent('PWR-00591', 'PWR-2411-MC-RED', Airflow.EXHAUST),
   ]

class Pwr602(AristaPsu):
   CAPACITY = 3200
   DESCRIPTION = psuDescHelper(
      sensors=[
         ('inlet', Position.OTHER, 60, 65, 70),
         ('secondary hotspot', Position.OTHER, 110, 120, 130),
         ('primary hotspot', Position.OTHER, 110, 115, 120),
      ],
      maxRpm=38300,
   )
   IDENTIFIERS = [
      PsuIdent('PWR-00602', 'PWR-3211-DC-RED', Airflow.EXHAUST),
   ]

class Pwr603(AristaPsu):
   CAPACITY = 3200
   DESCRIPTION = psuDescHelper(
      sensors=[
         ('inlet', Position.OTHER, 60, 65, 70),
         ('secondary hotspot', Position.OTHER, 110, 120, 130),
         ('primary hotspot', Position.OTHER, 110, 115, 120),
      ],
      maxRpm=38300,
   )
   IDENTIFIERS = [
      PsuIdent('PWR-00603', 'PWR-3211-HV-RED', Airflow.EXHAUST),
   ]

class Pwr634(AristaPsu):
   CAPACITY = 560
   DESCRIPTION = psuDescHelper(
      sensors=[
         ('inlet', Position.OTHER, 60, 65, 70),
         ('secondary hotspot', Position.OTHER, 110, 120, 130),
         ('primary hotspot', Position.OTHER, 110, 115, 120),
      ],
      maxRpm=25500,
   )
   IDENTIFIERS = [
      PsuIdent('PWR-00634', 'PWR-00634-AC-BLUE', Airflow.EXHAUST),
   ]

class Pwr663(AristaPsu):
   CAPACITY = 2400
   DESCRIPTION = psuDescHelper(
      sensors=[
         ('inlet', Position.OTHER, 60, 65, 70),
         ('secondary hotspot', Position.OTHER, 110, 120, 130),
         ('primary hotspot', Position.OTHER, 110, 115, 120),
      ],
      maxRpm=25500,
   )
   IDENTIFIERS = [
      PsuIdent('PWR-00663', 'PWR-2422-HV-RED', Airflow.EXHAUST),
   ]
