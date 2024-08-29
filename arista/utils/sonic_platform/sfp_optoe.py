import time

from arista.core.config import Config
from arista.utils.sonic_platform.thermal import SfpThermal
from sonic_platform_base.sonic_xcvr.sfp_optoe_base import SfpOptoeBase

EEPROM_PATH = '/sys/class/i2c-adapter/i2c-{0}/{0}-{1:04x}/eeprom'

# XXX: Temporary class while sfp refactor is in progress. Once refactor is done
# this class should replace the existing Sfp class.
class SfpOptoe(SfpOptoeBase):
   """
   Platform-specific sfp class
   """
   # pylint: disable=too-many-public-methods

   RESET_DELAY = 1

   def __init__(self, index, slot):
      SfpOptoeBase.__init__(self)
      self.index = index
      self._slot = slot
      sfp = slot.getXcvr()
      self._eepromPath = None
      if sfp.getI2cAddr():
         self._eepromPath = EEPROM_PATH.format(sfp.getI2cAddr().bus,
                                               sfp.getI2cAddr().address)
      self._sfp_type = None
      if not slot.getName().startswith('rj45') and Config().api_sfp_thermal:
         self._thermal_list.append(SfpThermal(self))

   @property
   def sfp_type(self):
      if self._sfp_type is None:
         self._sfp_type = self._detect_sfp_type()

      return self._sfp_type

   def _detect_sfp_type(self):
      info = self.get_transceiver_info()
      sfp_type = self._slot.getXcvr().getType().upper()
      if info:
         sfp_type = info.get("type_abbrv_name")
      # XXX: Need this hack until xcvrd is refactored
      if sfp_type in ["OSFP-8X", "QSFP-DD"]:
         sfp_type = "QSFP_DD"
      return sfp_type

   def get_id(self):
      return self.index

   def get_name(self):
      return self._slot.getName()

   def get_position_in_parent(self):
      return self.index

   def get_presence(self):
      return self._slot.getPresence()

   def is_replaceable(self):
      return True

   def get_status(self):
      return self.get_presence() and bool(self.get_transceiver_bulk_status())

   def get_hw_lpmode(self):
      return self._slot.getLowPowerMode()

   def set_hw_lpmode(self, lpmode):
      self._slot.setLowPowerMode(lpmode)

   def get_lpmode(self):
      try:
         return self.get_hw_lpmode()
      except NotImplementedError:
         return super().get_lpmode()
      except: # pylint: disable-msg=W0702
         return False

   def set_lpmode(self, lpmode):
      try:
         self.set_hw_lpmode(lpmode)
      except NotImplementedError:
         return super().set_lpmode(lpmode)
      except: # pylint: disable-msg=W0702
         return False
      return True

   def set_hw_reset(self, mode):
      reset = self._slot.getReset()
      if not reset:
         return
      if mode:
         reset.resetIn()
      else:
         reset.resetOut()

   def get_hw_reset(self):
      reset = self._slot.getReset()
      return reset.read() if reset else False

   def get_reset_status(self):
      return self.get_hw_reset()

   def reset(self):
      try:
         self._slot.getReset().resetIn()
      except Exception: # pylint: disable-msg=broad-except
         return False

      if Config().api_sfp_reset_lpmode:
         try:
            self._slot.setLowPowerMode(True)
         except Exception: # pylint: disable-msg=broad-except
            pass

      time.sleep(self.RESET_DELAY)

      try:
         self._slot.getReset().resetOut()
      except Exception: # pylint: disable-msg=broad-except
         return False

      # XXX: Hack to handle SFP modules plugged into non-SFP ports, which could
      # allow for a reset to "succeed" when it shouldn't
      if self.sfp_type == "SFP":
         return False
      return True

   def clear_interrupt(self):
      intr = self._slot.getInterruptLine()
      if not intr:
         return False
      self.get_presence()
      intr.clear()
      return True

   def get_interrupt_file(self):
      intr = self._slot.getInterruptLine()
      if intr:
         return intr.getFile()
      return None

   def get_eeprom_path(self):
      return self._eepromPath

   def get_error_description(self):
      if not self.get_presence():
         return self.SFP_STATUS_UNPLUGGED

      return self.SFP_STATUS_OK

   def set_write_max(self, size):
      self._slot.slot.xcvr.driver.setWriteMax(size)

   def get_write_max(self):
      return self._slot.slot.xcvr.driver.getWriteMax()

   def set_power(self, mode):
      raise NotImplementedError

   def get_power(self):
      return True
