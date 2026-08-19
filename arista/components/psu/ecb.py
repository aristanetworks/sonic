# Copyright (c) 2026 Arista Networks, Inc.  All rights reserved.
# Arista Networks, Inc. Confidential and Proprietary.

from ...core.psu import PsuModel, PsuIdent, getPsuManager

from ...descs.rail import RailDesc, RailDirection

from . import PmbusPsu
from .helper import psuDescHelper, Position

class TiEcb(PsuModel):
   MANUFACTURER = 'TI'
   PMBUS_CLS = PmbusPsu

   # Resistance of IMON sense resistor in ohms
   SENSE_RESISTANCE = 1

   @classmethod
   def makeDescription(cls, senseRes):
      raise NotImplementedError

def _makeTPS16890Description(senseRes):
   # TPS16890 telemetry conversion using PMBus DIRECT format:
   #    X = (1/m) * (Y * 10^-R - b)
   # where Y is the 2 byte value read from PMBus register.
   # Voltage (V): m = 1166, b = 0, R = -2
   # Current (A): m = 9.547 * SENSE_RESISTANCE, b = 0, R = -3
   # Power (W): m = 1.08 * SENSE_RESISTANCE, b = 0, R = -4
   # Temperature (C): m = 140, b = 32103, R = -2
   TPS16890_VOLTAGE_SCALE = 100. / 1166
   TPS16890_CURRENT_SCALE_PER_OHM = 1000. / 9.547
   TPS16890_POWER_SCALE_PER_OHM = 10000. / 1.08
   currentScale = TPS16890_CURRENT_SCALE_PER_OHM / senseRes
   voltageScale = TPS16890_VOLTAGE_SCALE
   powerScale = TPS16890_POWER_SCALE_PER_OHM / senseRes
   tempScale = 100. / 140
   tempOffset = -32103. / 140

   desc = psuDescHelper(
      # TempSysfsImpl applies Y * scale + offset
      sensors=[
         ('internal', Position.OTHER, 100, 105, 110, tempScale, tempOffset),
      ],
      hasFans=False,
      inputRailId=None,
      outputRailId=None,
      outputMinVoltage=45.5,
      outputMaxVoltage=52.5,
   )
   # TPS16890 only has input telemetry (vin/iin/pin) but it's only a circuit
   # breaker so output values should be very similar. Use direction=INPUT and
   # define the rail twice so
   # - LabelSysfsImpl resolves the correct sysfs labels
   # - Psu can access rails[0] (input) and rails[1] (output)
   desc.rails = [
      RailDesc(railId=1, direction=RailDirection.INPUT,
               currentScale=currentScale, voltageScale=voltageScale,
               powerScale=powerScale),
      RailDesc(railId=1, direction=RailDirection.INPUT,
               currentScale=currentScale, voltageScale=voltageScale,
               powerScale=powerScale),
   ]
   return desc

class Tps16890(TiEcb):
   CAPACITY = 1600
   AUTODETECT_PMBUS = False

   PMBUS_ADDR = 0x10
   IDENTIFIERS = [
      PsuIdent('TPS16890', 'TPS16890', None),
   ]

   @classmethod
   def makeDescription(cls, senseRes):
      return _makeTPS16890Description(senseRes)

   DESCRIPTION = _makeTPS16890Description(TiEcb.SENSE_RESISTANCE)

class AdEcb(PsuModel):
   MANUFACTURER = 'AnalogDevices'
   PMBUS_CLS = PmbusPsu

   SENSE_RESISTANCE = 1

   @classmethod
   def makeDescription(cls, senseRes):
      raise NotImplementedError

def _makeLTC4287Description(senseRes):
   # LTC conversion of raw ADC values read over PMBus:
   #    X = (1/m) * Y * 10^-R - b
   # where Y is the 2 byte value read from PMBus register.
   # Voltage (V): m = 32, b = 0, R = 1
   # Current (A): m = 1024 * SENSE_RESISTANCE, b = 0, R = 3
   # Power (W): m = SENSE_RESISTANCE, b = 0, R = 4
   # Temperature (C): m = 1, b = 273.15, R = 0
   LTC4287_VOLTAGE_SCALE = 1. / 320
   LTC4287_CURRENT_SCALE_PER_OHM = 1. / 1024000
   LTC4287_POWER_SCALE_PER_OHM = 1. / 10000
   currentScale = LTC4287_CURRENT_SCALE_PER_OHM / senseRes
   voltageScale = LTC4287_VOLTAGE_SCALE
   powerScale = LTC4287_POWER_SCALE_PER_OHM / senseRes

   desc = psuDescHelper(
      sensors=[
         ('internal', Position.OTHER, 100, 105, 110, 1, -273.15),
      ],
      hasFans=False,
      inputRailId=None,
      outputRailId=None,
      outputMinVoltage=45.5,
      outputMaxVoltage=52.5,
   )
   # LTC4287 exposes a mix of input and output telemetry:
   # - vin/pin are INPUT (no iin available)
   # - vout1/iout1 are OUTPUT (no pout available)
   # Use INPUT for rails[0] (power) and OUTPUT for rails[1] (voltage/current)
   desc.rails = [
      RailDesc(railId=1, direction=RailDirection.INPUT,
               powerScale=powerScale),
      RailDesc(railId=1, direction=RailDirection.OUTPUT,
               currentScale=currentScale, voltageScale=voltageScale),
   ]
   return desc

class Ltc4287(AdEcb):
   CAPACITY = 1600
   AUTODETECT_PMBUS = False

   PMBUS_ADDR = 0x10
   IDENTIFIERS = [
      PsuIdent('LTC4287', 'LTC4287', None),
   ]

   @classmethod
   def makeDescription(cls, senseRes):
      return _makeLTC4287Description(senseRes)

   DESCRIPTION = _makeLTC4287Description(AdEcb.SENSE_RESISTANCE)

def createPmbusECB(cls, senseRes, slotId=1, addr=0x10):
   # slotId is included in the generated class name to keep it unique
   name = '%s_%d' % (cls.__name__, slotId)
   PmbusECB = type(name, (cls,), {
      'PMBUS_ADDR': addr,
      'SENSE_RESISTANCE': senseRes,
      'DESCRIPTION': cls.makeDescription(senseRes),
   })
   getPsuManager().psus_.append(PmbusECB)
   return PmbusECB
