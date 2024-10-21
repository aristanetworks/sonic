from ...core.cooling import Airflow
from ...core.psu import PsuModel, PsuIdent

from . import PmbusPsu
from .helper import psuDescHelper, Position

class DeltaPsu(PsuModel):
   MANUFACTURER = 'delta'
   PMBUS_ADDR = 0x58
   PMBUS_CLS = PmbusPsu

class DPS495CB(DeltaPsu):
   CAPACITY = 500
   DESCRIPTION = psuDescHelper(
      sensors=[
         ('hotspot', Position.OTHER, 80, 95, 100),
         ('inlet', Position.INLET, 55, 70, 75),
      ],
      maxRpm=23000, # has a slow fan revision at 18000 (S0-S3)
   )
   IDENTIFIERS = [
      PsuIdent('DPS-495CB A',   'PWR-500AC-F', Airflow.EXHAUST),
      PsuIdent('DPS-495CB-1 A', 'PWR-500AC-R', Airflow.INTAKE),
      PsuIdent('DPS-495CB C',   'PWR-501AC-F', Airflow.EXHAUST),
      PsuIdent('DPS-495CB-1 C', 'PWR-501AC-R', Airflow.INTAKE),
   ]

class DPS500AB(DeltaPsu):
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
      PsuIdent('DPS-500AB-40 A', 'PWR-511-AC-RED', Airflow.EXHAUST),
      PsuIdent('DPS-500AB-41 A', 'PWR-511-DC-RED', Airflow.EXHAUST),
      PsuIdent('DPS-500AB-42 A', 'PWR-511-DC-BLUE', Airflow.INTAKE),
      PsuIdent('DPS-500AB-43 A', 'PWR-511-AC-BLUE', Airflow.INTAKE),
   ]

class DPS750AB(DeltaPsu):
   CAPACITY = 750
   DESCRIPTION = psuDescHelper(
      sensors=[
         ('hotspot', Position.OTHER, 80, 95, 100),
         ('inlet', Position.INLET, 55, 70, 75),
      ],
      maxRpm=23000, # A model has slower fans, others have 25500
   )
   IDENTIFIERS = [
      PsuIdent('DPS-750AB-24 A', 'PWR-745AC-F', Airflow.EXHAUST),
      PsuIdent('DPS-750AB-24 B', 'PWR-747AC-RED', Airflow.EXHAUST),
      PsuIdent('DPS-750AB-24 C', 'PWR-745AC-F', Airflow.EXHAUST),
      PsuIdent('DPS-750AB-25 A', 'PWR-745AC-R', Airflow.INTAKE),
      PsuIdent('DPS-750AB-25 B', 'PWR-747AC-BLUE', Airflow.INTAKE),
      PsuIdent('DPS-750AB-25 C', 'PWR-745AC-R', Airflow.INTAKE),
   ]

class DPS1500AB(DeltaPsu):
   CAPACITY = 1500
   DESCRIPTION = psuDescHelper(
      sensors=[
         ('secondary hotspot', Position.OTHER, 80, 108, 113),
         ('inlet', Position.INLET, 55, 65, 70),
         ('primary hotspot', Position.OTHER, 80, 88, 93),
      ],
      maxRpm=23000,
   )
   IDENTIFIERS = [
      PsuIdent('DPS-1500AB-7 A',  'PWR-1511-AC-RED', Airflow.EXHAUST),
      PsuIdent('DPS-1500AB-7 B',  'PWR-1512-AC-RED', Airflow.EXHAUST),
      PsuIdent('DPS-1500AB-8 A',  'PWR-1511-AC-BLUE', Airflow.INTAKE),
      PsuIdent('DPS-1500AB-8 B',  'PWR-1512-AC-BLUE', Airflow.INTAKE),
      PsuIdent('DPS-1500AB-9 A',  'PWR-1511-DC-RED', Airflow.EXHAUST),
      PsuIdent('DPS-1500AB-10 A', 'PWR-1511-DC-BLUE', Airflow.INTAKE),
   ]

class DPS1600AB(DeltaPsu):
   CAPACITY = 1600
   DESCRIPTION = psuDescHelper(
      sensors=[
         ('inlet', Position.INLET, 62, 70, 75),
         ('secondary hotspot', Position.OTHER, 92, 98, 105),
         ('primary hotspot', Position.OTHER, 88, 95, 100),
      ],
      maxRpm=25500,
   )
   IDENTIFIERS = [
      PsuIdent('DPS-1600AB-14 A', 'PWR-1611-DC-RED', Airflow.EXHAUST),
   ]

class DPS1600CB(DeltaPsu):
   DRIVER = 'dps800'
   CAPACITY = 1600
   DESCRIPTION = psuDescHelper(
      sensors=[
         ('inlet', Position.INLET, 62, 68, 80), # TODO: P has lower values
         ('secondary hotspot', Position.OTHER, 86, 92, 98),
         ('primary hotspot', Position.OTHER, 86, 92, 98),
      ],
      maxRpm=25500,
   )
   IDENTIFIERS = [
      PsuIdent('DPS-1600CB P', 'PWR-1611-AC-RED', Airflow.EXHAUST),
      PsuIdent('DPS-1600CB N', 'PWR-1600AC-F', Airflow.EXHAUST),
   ]

class DPS1900AB(DeltaPsu):
   DRIVER = 'dps1900'
   CAPACITY = 1900
   DESCRIPTION = psuDescHelper(
      sensors=[
         ('hotspot', Position.OTHER, 95, 110, 115),
         ('inlet', Position.INLET, 60, 70, 75),
      ],
      maxRpm=25500,
   )
   IDENTIFIERS = [
      PsuIdent('DPS-1900AB A',   'PWR-1900AC-F', Airflow.EXHAUST),
      PsuIdent('DPS-1900AB-1 A', 'PWR-1900AC-R', Airflow.INTAKE),
   ]

class ECD16020102(DeltaPsu):
   DRIVER = 'dps800'
   CAPACITY = 3000
   DESCRIPTION = psuDescHelper(
      sensors=[
         ('inlet', Position.OTHER, 60, 65, 70),
         ('primary hotspot', Position.OTHER, 70, 115, 120),
         ('secondary hotspot', Position.OTHER, 70, 120, 130),
      ],
      maxRpm=25500,
   )
   IDENTIFIERS = [
      PsuIdent('ECD16020102', 'PWR-3001-AC-RED', Airflow.EXHAUST),
   ]

class ECD26020037(DeltaPsu):
   DRIVER = 'dps800'
   CAPACITY = 3000
   DESCRIPTION = psuDescHelper(
      sensors=[
         ('inlet', Position.OTHER, 60, 65, 70),
         ('primary hotspot', Position.OTHER, 70, 115, 120),
         ('secondary hotspot', Position.OTHER, 70, 120, 130),
      ],
      maxRpm=25500,
   )
   IDENTIFIERS = [
      PsuIdent('ECD26020037', 'PWR-3001-DC-RED', Airflow.EXHAUST),
   ]

class ECD3000M(DeltaPsu):
   PMBUS_ADDR = 0x40
   DRIVER = 'dps800'
   CAPACITY = 3000
   DUAL_INPUT = True
   DESCRIPTION = psuDescHelper(
      sensors=[
         ('inlet', Position.OTHER, 60, 65, 70),
         ('primary hotspot', Position.OTHER, 70, 115, 120),
         ('secondary hotspot', Position.OTHER, 70, 120, 130),
      ],
      maxRpm=28000,
   )
   IDENTIFIERS = [
      PsuIdent('ECD16020097', 'PWR-D1-3041-AC-BLUE', Airflow.INTAKE),
      PsuIdent('ECD16020035', 'PWR-D2-3041-DC-BLUE', Airflow.INTAKE),
      PsuIdent('ECD56020024', 'PWR-D3-3041-AC-BLUE', Airflow.INTAKE),
      PsuIdent('ECD56020026', 'PWR-D4-3041-AC-BLUE', Airflow.INTAKE),
   ]

class ECD1502005(DeltaPsu):
   CAPACITY = 2400
   DESCRIPTION = psuDescHelper(
      sensors=[
         ('inlet', Position.OTHER, 60, 65, 70),
         ('secondary hotspot', Position.OTHER, 110, 120, 130),
         ('primary hotspot', Position.OTHER, 110, 115, 120),
      ],
      maxRpm=25500,
      outputMinVoltage=11.40,
      outputMaxVoltage=12.60,
   )
   IDENTIFIERS = [
      PsuIdent('ECD15020056', 'PWR-2421-HV-RED', Airflow.EXHAUST),
      PsuIdent('ECD15020057', 'PWR-2421-HV-BLUE', Airflow.INTAKE),
   ]
