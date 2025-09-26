import pytest


from ..adm1266 import (
   Adm1266,
   AdmCauseOneHot,
   AdmCauseUnique,
   AdmGpio,
   AdmPdio
)

from ....core.fabric import Fabric
from ....core.linecard import Linecard
from ....core.modular import Modular
from ....core.platform import loadPlatforms, getPlatforms
from ....descs.cause import ReloadCauseDesc
from ....libs.integer import isBitSet
from ....tests.logging import getLogger

def setBit(value, bit):
   return value | (1 << bit)

def clearBit(value, bit):
   return value & ~(1 << bit)

class MockBlackboxFault:
   """Mock BlackboxFault for testing fault cause validation"""
   GPIO_MAP = [1, 2, 3, None, None, None, 8, 9, 4, 5, 6, 7, None, None, None, None]

   def __init__(self, current=0, action=0, gpio_in=0, gpio_out=0,
                pdio_in=0, pdio_out=0, powerup=1, timestamp=None):
      self.current = current
      self.action = action
      self.gpio_in = gpio_in
      self.gpio_out = gpio_out
      self.pdio_in = pdio_in
      self.pdio_out = pdio_out
      self.powerup = powerup
      self.timestamp = timestamp or b'\x00' * 8

   def getTime(self):
      return "2025-01-01 00:00:00 UTC"

   def summary(self):
      return f"current={self.current} action={self.action} gpio_in={self.gpio_in} "\
             f"gpio_out={self.gpio_out} pdio_in={self.pdio_in} "\
             f"pdio_out={self.pdio_out}"


@pytest.fixture(scope="class")
def logger(request):
   request.cls.logger = getLogger(request.cls.__name__)
   yield


@pytest.mark.usefixtures("logger")
class TestAdm1266CauseConfiguration:
   def validatePins(self, cause):
      assert cause.gpios or cause.pdios, \
         "Must provide either GPIO or PDIO pins"

   def validateCauseOneHot(self, cause):
      self.validatePins(cause)
      assert len(cause.gpios + cause.pdios) == 1, \
         "One hot cause must specify exactly one pin"

   def validateCauseUnique(self, cause):
      self.validatePins(cause)

      # verify that pins specified are actually within the masks
      for pin in cause.gpios:
         pinIndex = pin.pin - 1
         isInput = isBitSet(pinIndex, cause.gpioInMask)
         isOutput = isBitSet(pinIndex, cause.gpioOutMask)
         assert isInput or isOutput, \
            f"{pin.typ.value} {pin.pin} must be configured as input or output"
      for pin in cause.pdios:
         pinIndex = pin.pin - 1
         isInput = isBitSet(pinIndex, cause.pdioInMask)
         isOutput = isBitSet(pinIndex, cause.pdioOutMask)
         assert isInput or isOutput, \
            f"{pin.typ.value} {pin.pin} must be configured as input or output"

      # verify that activeLow bits are within the masks
      assert \
         not (cause.gpioActiveLowMask & ~(cause.gpioInMask | cause.gpioOutMask)), \
         "active low mask must be within the input/output masks"
      assert \
         not (cause.pdioActiveLowMask & ~(cause.pdioInMask | cause.pdioOutMask)), \
         "active low mask must be within the input/output masks"

      maxGpioMask = 0b111111111
      maxPdioMask = 0xFFFF
      # verify that gpi/o masks are 9 bits or less, pdi/o 16 bits or less
      assert cause.gpioInMask < maxGpioMask and cause.gpioOutMask < maxGpioMask, \
         f"GPIO pin masks must be within {bin(maxGpioMask)}"
      assert cause.pdioInMask < maxPdioMask and cause.pdioOutMask < maxPdioMask, \
         f"PDIO pin masks must be within {bin(maxPdioMask)}"

   def testPlatformAdm1266CauseConfigs(self):
      loadPlatforms()
      ignoreTup = tuple([Modular, Fabric])

      for platformCls in getPlatforms():
         if issubclass(platformCls, ignoreTup):
            continue
         if issubclass(platformCls, Linecard) and not platformCls.CPU_CLS:
            continue
         platform = platformCls()

         if issubclass(platformCls, Linecard):
            platform.CPU_CLS.addCpuDpm(bus=platform, addr=platform.pca.i2cAddr(0x4f))

         for component in platform.iterComponents(filters=[]):
            if isinstance(component, Adm1266):
               self.logger.info(
                  f"Validating ADM1266 cause configuration on {platform}")
               for cause in component.causes:
                  if isinstance(cause, AdmCauseOneHot):
                     self.validateCauseOneHot(cause)
                  elif isinstance(cause, AdmCauseUnique):
                     self.validateCauseUnique(cause)


@pytest.mark.usefixtures("logger")
class TestAdmCauseOneHot:
   @pytest.mark.parametrize("pinType", ["gpio", "pdio"])
   @pytest.mark.parametrize("pinNum", [1, 2, 4, 8, 12, 16])
   @pytest.mark.parametrize("direction", ["IN", "OUT", "INOUT"])
   @pytest.mark.parametrize("activeLow", [False, True])
   @pytest.mark.parametrize("pinSetIn", [False, True])
   @pytest.mark.parametrize("pinSetOut", [False, True])
   def testOneHotCauses(self, pinType, pinNum, direction,
                        activeLow, pinSetIn, pinSetOut):
      """Parameterized test for AdmCauseOneHot fault matching"""

      # Skip invalid combinations
      if pinType == "gpio" and pinNum > 9:
         pytest.skip("GPIO pins only go up to 9")

      if pinType == "gpio":
         pin = AdmGpio(pinNum)
      else:
         pin = AdmPdio(pinNum)

      directionEnum = getattr(AdmCauseOneHot.Direction, direction)
      cause = AdmCauseOneHot(
         ReloadCauseDesc.OVERTEMP,
         pin,
         direction=directionEnum,
         activeLow=activeLow
      )

      # Calculate expected result for the test (match or not match)
      expected = False
      if direction == "IN":
         expected = pinSetIn != activeLow
      elif direction == "OUT":
         expected = pinSetOut != activeLow
      elif direction == "INOUT":
         expected = (pinSetIn != activeLow) or (pinSetOut != activeLow)

      # Create bit patterns for fault
      gpio_in = gpio_out = pdio_in = pdio_out = 0

      if pinType == "gpio":
         bit = MockBlackboxFault.GPIO_MAP.index(pin.pin)
         if pinSetIn:
            gpio_in = 1 << bit
         if pinSetOut:
            gpio_out = 1 << bit
      else:  # pdio
         bit = pinNum - 1
         if pinSetIn:
            pdio_in = 1 << bit
         if pinSetOut:
            pdio_out = 1 << bit

      fault = MockBlackboxFault(
         gpio_in=gpio_in,
         gpio_out=gpio_out,
         pdio_in=pdio_in,
         pdio_out=pdio_out
      )

      self.logger.debug(f"Expecting cause ({pinType}{pinNum} {direction} "
                        f"activeLow={activeLow}) to "
                        f"{'NOT ' if not expected else ''}MATCH with fault "
                        f"{fault.summary()}")

      result = cause.matchesFault(fault)
      assert result == expected, (
         f"OneHot test failed: pinType={pinType}, pinNum={pinNum}, "
         f"direction={direction}, activeLow={activeLow}, "
         f"pinSetIn={pinSetIn}, pinSetOut={pinSetOut}, "
         f"gpio_in={bin(gpio_in)}, gpio_out={bin(gpio_out)}, "
         f"pdio_in={bin(pdio_in)}, pdio_out={bin(pdio_out)}, "
         f"expected={expected}, got={result}"
      )

   def testOneHotGpioMatch(self):
      cause = AdmCauseOneHot(
         ReloadCauseDesc.OVERTEMP,
         AdmGpio(5),
         direction=AdmCauseOneHot.Direction.IN,
         activeLow=False
      )
      fault = MockBlackboxFault(gpio_in=0b1000000000)
      assert cause.matchesFault(fault)

   def testOneHotGpioNoMatch(self):
      cause = AdmCauseOneHot(
         ReloadCauseDesc.OVERTEMP,
         AdmGpio(5),
         direction=AdmCauseOneHot.Direction.IN,
         activeLow=False
      )
      fault = MockBlackboxFault(gpio_in=0b100000)
      assert not cause.matchesFault(fault)

   def testOneHotPdioMatch(self):
      cause = AdmCauseOneHot(
         ReloadCauseDesc.OVERTEMP,
         AdmPdio(10),
         direction=AdmCauseOneHot.Direction.IN,
         activeLow=False
      )
      fault = MockBlackboxFault(pdio_in=0b1000000000)
      assert cause.matchesFault(fault)

   def testOneHotPdioNoMatch(self):
      cause = AdmCauseOneHot(
         ReloadCauseDesc.OVERTEMP,
         AdmPdio(10),
         direction=AdmCauseOneHot.Direction.IN,
         activeLow=False
      )
      fault = MockBlackboxFault(pdio_in=0b10000000000)
      assert not cause.matchesFault(fault)

   def testOneHotOutputMatch(self):
      cause = AdmCauseOneHot(
         ReloadCauseDesc.OVERTEMP,
         AdmGpio(3),
         direction=AdmCauseOneHot.Direction.OUT,
         activeLow=False
      )
      fault = MockBlackboxFault(gpio_out=0b100)
      assert cause.matchesFault(fault)

   def testOneHotOutputNoMatch(self):
      cause = AdmCauseOneHot(
         ReloadCauseDesc.OVERTEMP,
         AdmGpio(3),
         direction=AdmCauseOneHot.Direction.OUT,
         activeLow=False
      )
      fault = MockBlackboxFault(gpio_in=0b100, gpio_out=0)
      assert not cause.matchesFault(fault)

   def testOneHotInputOutputMatch(self):
      cause = AdmCauseOneHot(
         ReloadCauseDesc.OVERTEMP,
         AdmGpio(8),
         direction=AdmCauseOneHot.Direction.INOUT,
         activeLow=False
      )
      fault = MockBlackboxFault(gpio_in=0b1000000, gpio_out=0b1)
      assert cause.matchesFault(fault)

   def testOneHotInputOutputNoMatch(self):
      cause = AdmCauseOneHot(
         ReloadCauseDesc.OVERTEMP,
         AdmGpio(8),
         direction=AdmCauseOneHot.Direction.INOUT,
         activeLow=False
      )
      # neither in nor out have gpio 8 set
      fault = MockBlackboxFault(gpio_in=0b100000, gpio_out=0b10000000)
      assert not cause.matchesFault(fault)

   def testOneHotActiveLowMatch(self):
      cause = AdmCauseOneHot(
         ReloadCauseDesc.OVERTEMP,
         AdmPdio(2),
         direction=AdmCauseOneHot.Direction.IN,
         activeLow=True
      )
      fault = MockBlackboxFault(pdio_in=0b101)
      assert cause.matchesFault(fault)

   def testOneHotActiveLowNoMatch(self):
      cause = AdmCauseOneHot(
         ReloadCauseDesc.OVERTEMP,
         AdmPdio(2),
         direction=AdmCauseOneHot.Direction.IN,
         activeLow=True
      )
      fault = MockBlackboxFault(pdio_in=0b010)
      assert not cause.matchesFault(fault)

@pytest.mark.usefixtures("logger")
class TestAdmCauseUnique: # pylint: disable=too-many-public-methods
   """Parameterized test cases for AdmCauseUnique fault matching"""
   causePins = [[1], [4, 5], [1, 2, 3], [2, 6, 8]]
   activeLowPins = [[], [1], [1, 2]]
   outputPins = [[], [1], [1, 2]]
   inputOutputPins = [[], [3], [3, 4]]
   extraActivePin = [True, False]
   missingActivePin = [True, False]

   def _runTest(
      self, pinType, causePins, activeLowPins, outputPins, inputOutputPins,
      extraActivePin, missingActivePin):
      """Parameterized test for AdmCauseUnique fault matching"""

      # Skip invalid combinations
      if pinType == "gpio" \
            and max(causePins+activeLowPins+outputPins+inputOutputPins) > 9:
         pytest.skip("GPIO pins only go up to 9")
      if set(outputPins).intersection(set(inputOutputPins)):
         pytest.skip("Pin cannot be both output and input/output")

      outMask = 0
      if pinType == "gpio":
         pins = AdmGpio.fromPins(*causePins)
         maxPinNum = 9
         inMask = 0b111111111
      elif pinType == "pdio":
         pins = AdmPdio.fromPins(*causePins)
         maxPinNum = 16
         inMask = 0xFFFF
      else:
         pins = [*AdmGpio.fromPins(*causePins), *AdmPdio.fromPins(*causePins)]
         maxPinNum = 9
         inMask = 0b111111111

      # if a pin is an output pin, it is not an input pin
      for pin in outputPins:
         bitPos = pin - 1
         outMask = setBit(outMask, bitPos)
         inMask = clearBit(inMask, bitPos)
      for pin in inputOutputPins:
         outMask = setBit(outMask, pin - 1)

      # Active low mask
      activeLowMask = 0
      for pin in activeLowPins:
         activeLowMask = setBit(activeLowMask, pin - 1)

      gpioMasks = {
         "gpioInMask": inMask,
         "gpioOutMask": outMask,
         "gpioActiveLowMask": activeLowMask,
      }
      pdioMasks = {
         "pdioInMask": inMask,
         "pdioOutMask": outMask,
         "pdioActiveLowMask": activeLowMask,
      }

      if pinType == "gpio":
         masks = gpioMasks
      elif pinType == "pdio":
         masks = pdioMasks
      else:
         masks = {**gpioMasks, **pdioMasks}
      cause = AdmCauseUnique(
         ReloadCauseDesc.OVERTEMP,
         pins,
         **masks
      )

      activePins = set(causePins)

      # These are the two "no match" scenarios
      if missingActivePin:
         removedPin = activePins.pop()
      if extraActivePin:
         excludedPins = activePins | {removedPin} if missingActivePin else activePins
         extraPin = next(
            (i for i in range(1, maxPinNum + 1) if i not in excludedPins), None)

         if extraPin is None:
            pytest.skip("No extra pin available for cause-fault mismatch")

         activePins.add(extraPin)

      # Create mock fault bit patterns
      # by default all pins inactive
      gpio_in = gpio_out = pdio_in = pdio_out = activeLowMask

      for pin in activePins:
         isActiveLow = pin in activeLowPins
         isInput = pin not in outputPins
         isOutput = pin in outputPins or pin in inputOutputPins

         if pinType in ( "gpio", "mixed" ):
            bit = MockBlackboxFault.GPIO_MAP.index(pin)
            if isInput:
               if isActiveLow:
                  gpio_in = clearBit(gpio_in, bit)
               else:
                  gpio_in = setBit(gpio_in, bit)
            if isOutput:
               if isActiveLow:
                  gpio_out = clearBit(gpio_out, bit)
               else:
                  gpio_out = setBit(gpio_out, bit)
         if pinType in ( "pdio", "mixed" ):
            bit = pin - 1
            if isInput:
               if isActiveLow:
                  pdio_in = clearBit(pdio_in, bit)
               else:
                  pdio_in = setBit(pdio_in, bit)
            if isOutput:
               if isActiveLow:
                  pdio_out = clearBit(pdio_out, bit)
               else:
                  pdio_out = setBit(pdio_out, bit)

      # Calculate expected result
      # Should match if:
      # 1. No extra pins are active in fault
      # 2. All cause pins are active in fault
      # 3. No cause pins are missing from fault
      expected = not(extraActivePin or missingActivePin)

      fault = MockBlackboxFault(
         gpio_in=gpio_in,
         gpio_out=gpio_out,
         pdio_in=pdio_in,
         pdio_out=pdio_out
      )

      self.logger.debug(f"Expecting cause ({pinType}{causePins} OUT={outputPins} "
                        f"INOUT={inputOutputPins} ACTIVELOW={activeLowPins}) to "
                        f"{'NOT ' if not expected else ''}MATCH with fault "
                        f"{fault.summary()}")

      result = cause.matchesFault(fault)

      assert result == expected, (
         f"Unique test failed: pinType={pinType}, causePins={causePins}, "
         f"activePins={activePins}, "
         f"activeLowPins={activeLowPins}, outputPins={outputPins}, "
         f"inputOutputPins={inputOutputPins}, extraActivePin={extraActivePin}, "
         f"missingActivePin={missingActivePin}, inMask={bin(inMask)}, "
         f"outMask={bin(outMask)}, activeLowMask={bin(activeLowMask)}, "
         f"gpio_in={bin(gpio_in)}, gpio_out={bin(gpio_out)}, "
         f"pdio_in={bin(pdio_in)}, pdio_out={bin(pdio_out)}, "
         f"expected={expected}, got={result}"
      )

   @pytest.mark.parametrize("causePins", causePins)
   @pytest.mark.parametrize("activeLowPins", activeLowPins)
   @pytest.mark.parametrize("outputPins", outputPins)
   @pytest.mark.parametrize("inputOutputPins", inputOutputPins)
   @pytest.mark.parametrize("extraActivePin", extraActivePin)
   @pytest.mark.parametrize("missingActivePin", missingActivePin)
   def testUniqueGpioCauses(self, causePins, activeLowPins, outputPins,
                            inputOutputPins, extraActivePin, missingActivePin):
      self._runTest("gpio", causePins, activeLowPins, outputPins, inputOutputPins,
                   extraActivePin, missingActivePin)

   @pytest.mark.parametrize("causePins", causePins + [[6, 8, 10, 12]])
   @pytest.mark.parametrize("activeLowPins", activeLowPins + [[1, 12]])
   @pytest.mark.parametrize("outputPins", outputPins + [[10], [1, 12]])
   @pytest.mark.parametrize("inputOutputPins", inputOutputPins + [[11], [3, 13]])
   @pytest.mark.parametrize("extraActivePin", extraActivePin)
   @pytest.mark.parametrize("missingActivePin", missingActivePin)
   def testUniquePdioCauses(self, causePins, activeLowPins, outputPins,
                            inputOutputPins, extraActivePin, missingActivePin):
      self._runTest("pdio", causePins, activeLowPins, outputPins, inputOutputPins,
                   extraActivePin, missingActivePin)

   @pytest.mark.parametrize("causePins", causePins)
   @pytest.mark.parametrize("activeLowPins", activeLowPins)
   @pytest.mark.parametrize("outputPins", outputPins)
   @pytest.mark.parametrize("inputOutputPins", inputOutputPins)
   @pytest.mark.parametrize("extraActivePin", extraActivePin)
   @pytest.mark.parametrize("missingActivePin", missingActivePin)
   def testUniqueMixedCauses(self, causePins, activeLowPins, outputPins,
                            inputOutputPins, extraActivePin, missingActivePin):
      self._runTest("mixed", causePins, activeLowPins, outputPins, inputOutputPins,
                   extraActivePin, missingActivePin)


   def testUniqueGpioMatch(self):
      # inmask, outmask, activeLowMask
      cause = AdmCauseUnique(
         ReloadCauseDesc.OVERTEMP,
         AdmGpio.fromPins(7, 8),
         0b111000000,
         0b000000000,
         0b000000000
      )
      # only pins 7, 8, 9 are taken into account for the fault
      # bit index 11, 6, 7 respectively
      fault = MockBlackboxFault(gpio_in=0b100001000111)
      assert cause.matchesFault(fault)

   def testUniqueGpioNoMatchSubset(self):
      cause = AdmCauseUnique(
         ReloadCauseDesc.OVERTEMP,
         AdmGpio.fromPins(7, 8),
         0b111000000,
         0b000000000,
         0b000000000
      )
      # missing a pin (8)
      fault = MockBlackboxFault(gpio_in=0b100000000000)
      assert not cause.matchesFault(fault)

   def testUniqueGpioNoMatchSuperset(self):
      cause = AdmCauseUnique(
         ReloadCauseDesc.OVERTEMP,
         AdmGpio.fromPins(7, 8),
         0b111000000,
         0b000000000,
         0b000000000
      )
      # extra pin (9)
      fault = MockBlackboxFault(gpio_in=0b100110000000)
      assert not cause.matchesFault(fault)

   def testUniquePdioMatch(self):
      cause = AdmCauseUnique(
         ReloadCauseDesc.OVERTEMP,
         AdmPdio.fromPins(9, 10, 11, 12),
         pdioInMask=0b001111110000000,
         pdioOutMask=0b000000000000000,
         pdioActiveLowMask=0b000000000000000
         )
      fault = MockBlackboxFault(pdio_in=0b111100000111)
      assert cause.matchesFault(fault)

   def testUniquePdioNoMatchSubset(self):
      cause = AdmCauseUnique(
         ReloadCauseDesc.OVERTEMP,
         AdmPdio.fromPins(9, 10, 11, 12),
         pdioInMask=0b001111110000000,
         pdioOutMask=0b000000000000000,
         pdioActiveLowMask=0b000000000000000
         )
      fault = MockBlackboxFault(pdio_in=0b1100000111)
      assert not cause.matchesFault(fault)

   def testUniquePdioNoMatchSuperset(self):
      cause = AdmCauseUnique(
         ReloadCauseDesc.OVERTEMP,
         AdmPdio.fromPins(9, 10, 11, 12),
         pdioInMask=0b001111110000000,
         pdioOutMask=0b000000000000000,
         pdioActiveLowMask=0b000000000000000
         )
      fault = MockBlackboxFault(pdio_in=0b1111100000000)
      assert not cause.matchesFault(fault)

   def testUniqueGpioPdioMixMatch(self):
      # inmask, outmask, activeLowMask
      cause = AdmCauseUnique(
         ReloadCauseDesc.OVERTEMP,
         [*AdmGpio.fromPins(7, 8), *AdmPdio.fromPins(9, 10, 11, 12)],
         0b111000000,
         0b000000000,
         0b000000000,
         0b001111110000000,
         0b000000000000000,
         0b000000000000000
      )
      fault = MockBlackboxFault(gpio_in=0b100001000111, pdio_in=0b111100000111)
      assert cause.matchesFault(fault)

   def testUniqueGpioPdioMixNoMatchPdioSubset(self):
      # inmask, outmask, activeLowMask
      cause = AdmCauseUnique(
         ReloadCauseDesc.OVERTEMP,
         [*AdmGpio.fromPins(7, 8), *AdmPdio.fromPins(9, 10, 11, 12)],
         0b111000000,
         0b000000000,
         0b000000000,
         0b001111110000000,
         0b000000000000000,
         0b000000000000000
      )
      fault = MockBlackboxFault(gpio_in=0b100001000111, pdio_in=0b1100000111)
      assert not cause.matchesFault(fault)

   def testUniqueGpioPdioMixNoMatchPdioSuperset(self):
      # inmask, outmask, activeLowMask
      cause = AdmCauseUnique(
         ReloadCauseDesc.OVERTEMP,
         [*AdmGpio.fromPins(7, 8), *AdmPdio.fromPins(9, 10, 11, 12)],
         0b111000000,
         0b000000000,
         0b000000000,
         0b001111110000000,
         0b000000000000000,
         0b000000000000000
      )
      fault = MockBlackboxFault(gpio_in=0b100001000111, pdio_in=0b1111100000000)
      assert not cause.matchesFault(fault)

   def testUniqueGpioPdioMixNoMatchGpioSubset(self):
      # inmask, outmask, activeLowMask
      cause = AdmCauseUnique(
         ReloadCauseDesc.OVERTEMP,
         [*AdmGpio.fromPins(7, 8), *AdmPdio.fromPins(9, 10, 11, 12)],
         0b111000000,
         0b000000000,
         0b000000000,
         0b001111110000000,
         0b000000000000000,
         0b000000000000000
      )
      fault = MockBlackboxFault(gpio_in=0b100000000000, pdio_in=0b111100000111)
      assert not cause.matchesFault(fault)

   def testUniqueGpioPdioMixNoMatchGpioSuperset(self):
      # inmask, outmask, activeLowMask
      cause = AdmCauseUnique(
         ReloadCauseDesc.OVERTEMP,
         [*AdmGpio.fromPins(7, 8), *AdmPdio.fromPins(9, 10, 11, 12)],
         0b111000000,
         0b000000000,
         0b000000000,
         0b001111110000000,
         0b000000000000000,
         0b000000000000000
      )
      fault = MockBlackboxFault(gpio_in=0b100110000000, pdio_in=0b111100000111)
      assert not cause.matchesFault(fault)

   def testUniqueOutputMatch(self):
      cause = AdmCauseUnique(
         ReloadCauseDesc.OVERTEMP,
         AdmGpio.fromPins(8, 9),
         0b100000000,
         0b011000000,
         0b000000000
      )
      fault = MockBlackboxFault(gpio_in=0b10000000, gpio_out=0b1000000)
      assert cause.matchesFault(fault)

   def testUniqueOutputNoMatch(self):
      cause = AdmCauseUnique(
         ReloadCauseDesc.OVERTEMP,
         AdmGpio.fromPins(8, 9),
         0b100000000,
         0b011000000,
         0b000000000
      )
      fault = MockBlackboxFault(gpio_in=0b11000000)
      assert not cause.matchesFault(fault)

   def testUniqueInputOutputMatch(self):
      cause = AdmCauseUnique(
         ReloadCauseDesc.OVERTEMP,
         AdmPdio.fromPins(1, 2, 3, 5),
         pdioInMask=0b11111,
         pdioOutMask=0b01110,
         pdioActiveLowMask=0b000000000000000
      )
      fault = MockBlackboxFault(pdio_in=0b10101, pdio_out=0b0110)
      assert cause.matchesFault(fault)

   def testUniqueInputOutputNoMatch(self):
      cause = AdmCauseUnique(
         ReloadCauseDesc.OVERTEMP,
         AdmPdio.fromPins(1, 2, 3, 5),
         pdioInMask=0b11111,
         pdioOutMask=0b01110,
         pdioActiveLowMask=0b000000000000000
      )
      # neither in nor out have pdio 2 set
      fault = MockBlackboxFault(pdio_in=0b10101, pdio_out=0b0100)
      assert not cause.matchesFault(fault)

   def testUniqueBothDirectionsVerified(self):
      # even if a cause is mapped to only output pins, we still verify the input pins
      cause = AdmCauseUnique(
         ReloadCauseDesc.OVERTEMP,
         AdmGpio.fromPins(1, 2),
         0b100,
         0b011,
         0b000
      )
      fault = MockBlackboxFault(gpio_in=0b000, gpio_out=0b011)
      assert cause.matchesFault(fault)
      fault = MockBlackboxFault(gpio_in=0b100, gpio_out=0b011)
      assert not cause.matchesFault(fault)

   def testUniqueActiveLowMatch(self):
      cause = AdmCauseUnique(
         ReloadCauseDesc.OVERTEMP,
         AdmGpio.fromPins(1, 2, 3),
         0b0000,
         0b1111,
         0b0011
      )
      fault = MockBlackboxFault(gpio_in=0b0011, gpio_out=0b0100)
      assert cause.matchesFault(fault)

   def testUniqueActiveLowNoMatch(self):
      cause = AdmCauseUnique(
         ReloadCauseDesc.OVERTEMP,
         AdmGpio.fromPins(1, 2, 3),
         0b0000,
         0b1111,
         0b0011
      )
      fault = MockBlackboxFault(gpio_in=0b0011, gpio_out=0b0110)
      assert not cause.matchesFault(fault)


@pytest.mark.usefixtures("logger")
class TestAdmCauseCurrentAction:
   @pytest.mark.parametrize("causeType", ["onehot", "unique"])
   @pytest.mark.parametrize("current", [None, 10, 15])
   @pytest.mark.parametrize("action", [None, 5, 7])
   @pytest.mark.parametrize("faultCurrent", [10, 11, 15])
   @pytest.mark.parametrize("faultAction", [5, 6, 7])
   def testCurrentActionCauses(self, causeType, current, action,
                               faultCurrent, faultAction):
      """Test current and action matching for both OneHot and Unique causes"""

      # Calculate expected result
      currentMatches = (current is None) or (current == faultCurrent)
      actionMatches = (action is None) or (action == faultAction)
      expected = currentMatches and actionMatches

      if causeType == "onehot":
         cause = AdmCauseOneHot(
            ReloadCauseDesc.OVERTEMP,
            AdmGpio(1),
            current=current,
            action=action,
            direction=AdmCauseOneHot.Direction.IN,
            activeLow=False
         )
      else:  # unique
         cause = AdmCauseUnique(
            ReloadCauseDesc.OVERTEMP,
            AdmGpio.fromPins(1),
            0b111111111,
            0b000000000,
            0b000000000,
            current=current,
            action=action
         )
      # Create fault with pin 1 active (so pin matching passes)
      fault = MockBlackboxFault(
         current=faultCurrent,
         action=faultAction,
         gpio_in=0b1
      )

      self.logger.debug(f"Expecting cause (current={current}, action={action}) to "
                        f"{'NOT ' if not expected else ''}MATCH with fault "
                        f"{fault.summary()}")

      result = cause.matchesFault(fault)
      assert result == expected, (
         f"Current/Action {causeType} test failed: current={current}, "
         f"action={action}, faultCurrent={faultCurrent}, faultAction={faultAction}, "
         f"currentMatches={currentMatches}, actionMatches={actionMatches}, "
         f"expected={expected}, got={result}"
      )

   def testCurrentActionMatch(self):
      cause = AdmCauseOneHot(
         ReloadCauseDesc.OVERTEMP,
         AdmGpio(1),
         current=10,
         action=5,
         direction=AdmCauseOneHot.Direction.IN,
         activeLow=False
      )
      fault = MockBlackboxFault(
         current=10,
         action=5,
         gpio_in=0b1
      )
      assert cause.matchesFault(fault)

   def testCurrentActionNoMatchCurrent(self):
      cause = AdmCauseOneHot(
         ReloadCauseDesc.OVERTEMP,
         AdmGpio(1),
         current=10,
         action=5,
         direction=AdmCauseOneHot.Direction.IN,
         activeLow=False
      )
      fault = MockBlackboxFault(
         current=11,
         action=5,
         gpio_in=0b1
      )
      assert not cause.matchesFault(fault)

   def testCurrentActionNoMatchAction(self):
      cause = AdmCauseOneHot(
         ReloadCauseDesc.OVERTEMP,
         AdmGpio(1),
         current=10,
         action=5,
         direction=AdmCauseOneHot.Direction.IN,
         activeLow=False
      )
      fault = MockBlackboxFault(
         current=10,
         action=6,
         gpio_in=0b1
      )
      assert not cause.matchesFault(fault)
