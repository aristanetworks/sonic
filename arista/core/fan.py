
from ..inventory.fan import FanSlot as FanSlotInv

from .component import Priority
from .component.slot import SlotComponent

class FanSlotImpl(FanSlotInv):
   # TODO: cleanup a bit more
   def __init__(self, slot):
      self.slot = slot

   def getId(self):
      return self.slot.getId()

   def getName(self):
      return self.slot.getName()

   def getModel(self):
      return self.slot.getModel()

   def getPresence(self):
      return self.slot.getPresence()

   def getFans(self):
      return self.slot.getFans()

   def getDirection(self):
      return self.slot.getFans()[0].getDirection()

   def getLed(self):
      return self.slot.getLed()

   def getMaxPowerDraw(self):
      return self.slot.getMaxPowerDraw()

   def getFault(self):
      return self.slot.getFault()

class FanSlot(SlotComponent):

   PRIORITY = Priority.COOLING

   def __init__(self, slotId=None, name=None, description=None, fans=None,
                faultGpio=None, presentGpio=None, maxPowerDraw=0., model='N/A',
                led=None,
                **kwargs):
      super(FanSlot, self).__init__(**kwargs)
      self.slotId = slotId
      self.name = name or 'slot%d' % self.slotId
      self.fans = fans or []
      self.led = led
      self.faultGpio = faultGpio
      self.presentGpio = presentGpio
      self.maxPowerDraw = maxPowerDraw
      self.model = model

      self.fanInv = self.inventory.addFanSlot(FanSlotImpl(self))

   def getId(self):
      return self.slotId

   def getName(self):
      return self.name

   def getModel(self):
      if self.fans:
         return self.fans[0].getModel()
      return self.model

   def getFans(self):
      return self.fans

   def getLed(self):
      return self.led

   def getFault(self):
      if self.faultGpio and self.faultGpio.isActive():
         return True
      for fan in self.fans:
         if fan.getFault():
            return True
      return False

   def getPresence(self):
      if self.presentGpio and not self.presentGpio.isActive():
         return False
      for fan in self.fans:
         if not fan.getPresence():
            return False
      return True

   def getMaxPowerDraw(self):
      return float(self.maxPowerDraw)
