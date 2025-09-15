# Copyright (c) 2025 Arista Networks, Inc.  All rights reserved.
# Arista Networks, Inc. Confidential and Proprietary.

from ...core.psu import PsuModel, PsuIdent

from . import PmbusPsu
from .helper import psuDescHelper, Position

class MobyDcDc(PsuModel):
   CAPACITY = 1000
   AUTODETECT_PMBUS = False

   MANUFACTURER = 'N/A'
   PMBUS_ADDR = 0x10
   PMBUS_CLS = PmbusPsu
   IDENTIFIERS = [
      PsuIdent('DCDC-48V-to-12V', 'DCDC-48V-to-12V', None),
   ]
   DESCRIPTION = psuDescHelper(
      sensors=[
          ('internal', Position.OTHER, 100, 120, 130),
      ],
      hasFans=False,
      outputMinVoltage=11.25,
      outputMaxVoltage=13.39
   )

class MobyDcDcAddr18(MobyDcDc):
   PMBUS_ADDR = 0x12
