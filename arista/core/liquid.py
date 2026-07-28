from abc import ABC, abstractmethod
from enum import Enum


class LeakSensorType(Enum):
   """Sensor type (as used at the hardware programming level)."""

   ROPE_MINOR = 'rope_minor'
   ROPE_MAJOR = 'rope_major'


class LeakDetectionInterface(ABC):
   # pylint: disable=too-many-public-methods
   """
   Interface to liquid leak detection monitoring and control.

   This provides the internal interface, exposing test and status bits that don't
   exist in the cross-vendor API.
   """

   @abstractmethod
   def isRopePresent(self, ropeType: LeakSensorType, ropeNum: int) -> bool:
      """
      Returns whether the given rope is present.
      """

   @abstractmethod
   def isRopeBroken(self, ropeType: LeakSensorType, ropeNum: int) -> bool:
      """
      Returns whether the given rope is faulty/broken.
      """

   @abstractmethod
   def isRopeLeakDetected(self, ropeType: LeakSensorType, ropeNum: int) -> bool:
      """
      Returns whether the given rope is currently reporting a leak.
      """

   @abstractmethod
   def hasRopeStatusChanged(self, ropeType: LeakSensorType, ropeNum: int) -> bool:
      """
      Returns whether the rope status (present, broken, leak) has changed since this
      bit was last cleared.
      """

   @abstractmethod
   def clearRopeStatusChanged(self, ropeType: LeakSensorType, ropeNum: int) -> None:
      """
      Clears the status changed bit for the given rope.
      """

   @abstractmethod
   def getRopeDebounceS(self, ropeType: LeakSensorType, ropeNum: int) -> int:
      """
      Returns the given rope's debounce time in seconds.
      """

   @abstractmethod
   def setRopeDebounceS(self, ropeType: LeakSensorType, ropeNum: int,
                        debounce: int) -> None:
      """
      Sets the given rope's debounce time, in seconds.
      """

   @abstractmethod
   def isRopeLeakForced(self, ropeType: LeakSensorType, ropeNum: int) -> bool:
      """
      Returns whether the "force leak" test bit is set for the given rope.
      """

   @abstractmethod
   def setRopeLeakForced(self, ropeType: LeakSensorType, ropeNum: int,
                         forced: bool) -> None:
      """
      Sets or clears the "force leak" test bit for the given rope.
      """

   @abstractmethod
   def isLiquidDomainPowerDownEnabled(self, ropeType: LeakSensorType) -> bool:
      """
      Returns whether a leak of the given rope type will trigger a hardware power-
      down of the liquid cooled power domain.
      """

   @abstractmethod
   def setLiquidDomainPowerDownEnabled(self, ropeType: LeakSensorType,
                                       enabled: bool) -> None:
      """
      Sets whether a leak of the given rope type will trigger a hardware power-down
      of the liquid cooled power domain.
      """

   @abstractmethod
   def isSystemPowerCycleEnabled(self, ropeType: LeakSensorType) -> bool:
      """
      Returns whether a leak on any rope of the given type will trigger a power cycle
      of the whole chassis.
      """

   @abstractmethod
   def setSystemPowerCycleEnabled(self, ropeType: LeakSensorType,
                                  enabled: bool) -> None:
      """
      Sets whether a leak on any rope of the given type will trigger a power cycle of
      the whole chassis.
      """

   @abstractmethod
   def getLeakActionDelayTimeS(self, ropeType: LeakSensorType) -> int:
      """
      Gets the delay in seconds before hardware initiates a liquid domain power down
      or system power cycle when any rope of the given type reports a leak.
      """

   @abstractmethod
   def setLeakActionDelayTimeS(self, ropeType: LeakSensorType, delay: int) -> None:
      """
      Sets the delay in seconds before hardware initiates a liquid domain power down
      or system power cycle when any rope of the given type reports a leak.
      """

   @abstractmethod
   def isLeakActionDelayEnabled(self, ropeType: LeakSensorType) -> bool:
      """
      Returns whether a delay is observed before taking hardware action when any rope
      of the given type reports a leak.
      """

   @abstractmethod
   def setLeakActionDelayTimeEnabled(self, ropeType: LeakSensorType,
                                     enabled: bool) -> None:
      """
      Sets whether a delay is observed before taking hardware action when any rope of
      the given type reports a leak.
      """

   @abstractmethod
   def isWatchdogLiquidDomainPowerDownEnabled(self,
                                              ropeType: LeakSensorType) -> bool:
      ...

   @abstractmethod
   def setWatchdogLiquidDomainPowerDownEnabled(self, ropeType: LeakSensorType,
                                               enabled: bool) -> None:
      ...

   @abstractmethod
   def isWatchdogSystemPowerCycleEnabled(self, ropeType: LeakSensorType) -> bool:
      ...

   @abstractmethod
   def setWatchdogSystemPowerCycleEnabled(self, ropeType: LeakSensorType,
                                          enabled: bool) \
      -> None:
      ...

   @abstractmethod
   def getWatchdogTimeS(self, ropeType: LeakSensorType) -> int:
      ...

   @abstractmethod
   def setWatchdogTimeS(self, ropeType: LeakSensorType, time: int) -> None:
      ...

   @abstractmethod
   def isWatchdogEnabled(self, ropeType: LeakSensorType) -> bool:
      ...

   @abstractmethod
   def setWatchdogEnabled(self, ropeType: LeakSensorType, enabled: bool) -> None:
      ...


class LeakDetectionInterfaceV1(LeakDetectionInterface):
   # pylint: disable=too-many-public-methods
   """
   Adapter class for the 1st gen liquid cooling register interface.

   This provides the internal interface, exposing test and status bits that don't
   exist in the cross-vendor API.

   Constructed using a component that implements a register map conforming to the
   expected field naming conventions for ropes. This approach is needed as the
   hardware API differs depending on whether the leak detection hardware is being
   accessed from the CPU over PCIe or from a BMC.

   This interface also provides basic polyfills for missing hardware features - any
   registers that aren't implemented return 0 on reads and do nothing on writes.
   """

   # Hardware field widths (consistent across CPLD and PCIe register maps).
   DEBOUNCE_BITS = 8
   ACTION_DELAY_BITS = 6
   WATCHDOG_BITS = 6

   def __init__(self, component):
      super().__init__()

      self.component = component

   @staticmethod
   def _checkRange(value: int, bits: int, name: str) -> None:
      maxValue = (1 << bits) - 1
      if not 0 <= value <= maxValue:
         raise ValueError(
            f'{name}={value} out of range for {bits}-bit field (0..{maxValue})')

   def isRopePresent(self, ropeType: LeakSensorType, ropeNum: int) -> bool:
      return self._readRopeRegister(ropeType, ropeNum, 'Present') != 0

   def isRopeBroken(self, ropeType: LeakSensorType, ropeNum: int) -> bool:
      return self._readRopeRegister(ropeType, ropeNum, 'Break') != 0

   def isRopeLeakDetected(self, ropeType: LeakSensorType, ropeNum: int) -> bool:
      return self._readRopeRegister(ropeType, ropeNum, 'Leak') != 0

   def hasRopeStatusChanged(self, ropeType: LeakSensorType, ropeNum: int) -> bool:
      return self._readRopeRegister(ropeType, ropeNum, 'Changed') != 0

   def clearRopeStatusChanged(self, ropeType: LeakSensorType, ropeNum: int) -> None:
      self._writeRopeRegister(ropeType, ropeNum, 'Changed', 1)

   def getRopeDebounceS(self, ropeType: LeakSensorType, ropeNum: int) -> int:
      return self._readRopeRegister(ropeType, ropeNum, 'DebounceS')

   def setRopeDebounceS(self, ropeType: LeakSensorType, ropeNum: int,
                        debounce: int) -> None:
      self._checkRange(debounce, self.DEBOUNCE_BITS, 'debounce')
      self._writeRopeRegister(ropeType, ropeNum, 'DebounceS', debounce)

   def isRopeLeakForced(self, ropeType: LeakSensorType, ropeNum: int) -> bool:
      return self._readRopeRegister(ropeType, ropeNum, 'ForceLeak') != 0

   def setRopeLeakForced(self, ropeType: LeakSensorType, ropeNum: int,
                         forced: bool) -> None:
      self._writeRopeRegister(ropeType, ropeNum, 'ForceLeak', forced)

   def isLiquidDomainPowerDownEnabled(self, ropeType: LeakSensorType) -> bool:
      return self._readRegister(ropeType, 'LiquidDomainPowerDownEnable') != 0

   def setLiquidDomainPowerDownEnabled(self, ropeType: LeakSensorType,
                                       enabled: bool) -> None:
      self._writeRegister(ropeType, 'LiquidDomainPowerDownEnable', enabled)

   def isSystemPowerCycleEnabled(self, ropeType: LeakSensorType) -> bool:
      return self._readRegister(ropeType, 'SystemPowerCycleEnable') != 0

   def setSystemPowerCycleEnabled(self, ropeType: LeakSensorType,
                                  enabled: bool) -> None:
      self._writeRegister(ropeType, 'SystemPowerCycleEnable', enabled)

   def getLeakActionDelayTimeS(self, ropeType: LeakSensorType) -> int:
      return self._readRegister(ropeType, 'LeakActionDelayTimeS')

   def setLeakActionDelayTimeS(self, ropeType: LeakSensorType, delay: int) -> None:
      self._checkRange(delay, self.ACTION_DELAY_BITS, 'delay')
      self._writeRegister(ropeType, 'LeakActionDelayTimeS', delay)

   def isLeakActionDelayEnabled(self, ropeType: LeakSensorType) -> bool:
      return self._readRegister(ropeType, 'LeakActionDelayTimeEnable') != 0

   def setLeakActionDelayTimeEnabled(self, ropeType: LeakSensorType,
                                     enabled: bool) -> None:
      self._writeRegister(ropeType, 'LeakActionDelayTimeEnable', enabled)

   def isWatchdogLiquidDomainPowerDownEnabled(self,
                                              ropeType: LeakSensorType) -> bool:
      return self._readRegister(ropeType, 'WatchdogLiquidDomainPowerDownEnable') != 0

   def setWatchdogLiquidDomainPowerDownEnabled(self, ropeType: LeakSensorType,
                                               enabled: bool) -> None:
      self._writeRegister(ropeType, 'WatchdogLiquidDomainPowerDownEnable', enabled)

   def isWatchdogSystemPowerCycleEnabled(self, ropeType: LeakSensorType) -> bool:
      return self._readRegister(ropeType, 'WatchdogSystemPowerCycleEnable') != 0

   def setWatchdogSystemPowerCycleEnabled(self, ropeType: LeakSensorType,
                                          enabled: bool) -> None:
      self._writeRegister(ropeType, 'WatchdogSystemPowerCycleEnable', enabled)

   def getWatchdogTimeS(self, ropeType: LeakSensorType) -> int:
      return self._readRegister(ropeType, 'WatchdogTimeS')

   def setWatchdogTimeS(self, ropeType: LeakSensorType, time: int) -> None:
      self._checkRange(time, self.WATCHDOG_BITS, 'time')
      self._writeRegister(ropeType, 'WatchdogTimeS', time)

   def isWatchdogEnabled(self, ropeType: LeakSensorType) -> bool:
      return self._readRegister(ropeType, 'WatchdogEnable') != 0

   def setWatchdogEnabled(self, ropeType: LeakSensorType, enabled: bool) -> None:
      self._writeRegister(ropeType, 'WatchdogEnable', enabled)

   def _readRegister(self, ropeType: LeakSensorType, regName: str) -> int:
      """
      Reads a severity-specific value from a register, returning 0 if not
      implemented.
      """

      regName = self._makeRegisterName(ropeType, regName)
      return getattr(self.component.driver.regs, regName, lambda: 0)()

   def _writeRegister(self, ropeType: LeakSensorType, regName: str,
                      value: int) -> None:
      """
      Writes a severity-specific value to a register, acting as a no-op if not
      implemented.
      """

      regName = self._makeRegisterName(ropeType, regName)
      getattr(self.component.driver.regs, regName, lambda _: None)(int(value))

   def _readRopeRegister(self, ropeType: LeakSensorType, ropeNum: int,
                         regName: str) -> int:
      """
      Reads a rope-specific value from a register, returning 0 if not implemented.
      """

      regName = self._makeRopeRegisterName(ropeType, ropeNum, regName)
      return getattr(self.component.driver.regs, regName, lambda: 0)()

   def _writeRopeRegister(self, ropeType: LeakSensorType, ropeNum: int, regName: str,
                          value: int) -> None:
      """
      Writes a rope-specific value to a register, acting as a no-op if not
      implemented.
      """

      regName = self._makeRopeRegisterName(ropeType, ropeNum, regName)
      getattr(self.component.driver.regs, regName, lambda _: None)(int(value))

   @staticmethod
   def _sensorTypeName(ropeType: LeakSensorType) -> str:
      if ropeType == LeakSensorType.ROPE_MINOR:
         return "minor"
      return "major"

   @staticmethod
   def _makeRegisterName(ropeType: LeakSensorType, regName: str) -> str:
      """
      Naming pattern for registers shared between ropes of the same type.
      """
      prefix = LeakDetectionInterfaceV1._sensorTypeName(ropeType)
      return f'{prefix}{regName}'

   @staticmethod
   def _makeRopeRegisterName(ropeType: LeakSensorType, ropeNum: int,
                             regName: str) -> str:
      """
      Naming pattern for registers specific to a single rope.
      """
      prefix = LeakDetectionInterfaceV1._sensorTypeName(ropeType)
      return f'{prefix}Rope{ropeNum}{regName}'
