
try:
   from sonic_platform_base.fan_drawer_base import FanDrawerBase
   from .fan import Fan
except ImportError as e:
   raise ImportError("%s - required module not found" % e)

class FanDrawer(FanDrawerBase):
   def __init__(self, parent, slot):
      FanDrawerBase.__init__(self)
      self._parent = parent
      self._fan_list = [Fan(self, fan) for fan in slot.getFans()]
      self._slot = slot
      self._hotswappable = True

   def get_name(self):
      return self._slot.getName()

   def get_model(self):
      return self._slot.getModel()

   def get_presence(self):
      return self._slot.getPresence()

   def get_serial(self):
      return 'N/A'

   def get_revision(self):
      return 'N/A'

   def get_status(self):
      return self._slot.getPresence() and not self._slot.getFault()

   def get_status_led(self, color=None):
      return self._slot.getLed().getColor()

   def set_status_led(self, color):
      try:
         self._slot.getLed().setColor(color)
         return True
      except (IOError, OSError, ValueError):
         return False

   def get_maximum_consumed_power(self):
      return self._slot.getMaxPowerDraw()

   def get_position_in_parent(self):
      return self._slot.getId()

   def is_replaceable(self):
      return self._hotswappable

   def get_interrupt_file(self):
      return None

class FanDrawerLegacy(FanDrawerBase):
   def __init__(self, fan):
      FanDrawerBase.__init__(self)
      # XXX: temporary 1:1 fan to fan_drawer mapping
      self._fan_list = [fan]

   def get_name(self):
      return self._fan_list[0].get_name()

   def get_status_led(self, color=None):
      return self._fan_list[0].get_status_led(color)

   def set_status_led(self, color):
      return self._fan_list[0].set_status_led(color)

   def get_interrupt_file(self):
      return None
