# Copyright (c) 2026 Arista Networks, Inc.  All rights reserved.
# Arista Networks, Inc. Confidential and Proprietary.

from ...core.component import Priority
from ...core.component.i2c import I2cComponent

from ...drivers.pmbus import PmbusKernelDriver

class PmbusIbc(I2cComponent):
   DRIVER = PmbusKernelDriver
   PRIORITY = Priority.THERMAL

class Pwr689(PmbusIbc):
   # DCDC-48V-to-12V
   pass
