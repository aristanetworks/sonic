# Copyright (c) 2025 Arista Networks, Inc.  All rights reserved.
# Arista Networks, Inc. Confidential and Proprietary.

from ...core.psu import PsuModel, PsuIdent

from . import PmbusPsu
from .helper import psuDescHelper, Position

class Pwr689(PsuModel):
   CAPACITY = 1000
   AUTODETECT_PMBUS = False

   MANUFACTURER = 'N/A'
   PMBUS_ADDR = 0x10
   PMBUS_CLS = PmbusPsu
   IDENTIFIERS = [
      PsuIdent('DCDC-48V-to-12V', 'PWR-689', None),
   ]
   DESCRIPTION = psuDescHelper(
      sensors=[
          ('internal', Position.OTHER, 100, 120, 130),
      ],
      hasFans=False,
      outputMinVoltage=11.25,
      outputMaxVoltage=13.39
   )

def createPmbusIBC(cls=Pwr689, addr=0x10):
   name = '%s_0x%02x' % (cls.__name__, addr)
   PmbusIBC = type(name, (cls,), {'PMBUS_ADDR': addr})
   # Register in module so PsuManager can resolve the class from cache
   globals()[name] = PmbusIBC
   return PmbusIBC
