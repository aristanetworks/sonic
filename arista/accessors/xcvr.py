from ..inventory.xcvr import Xcvr

class XcvrImpl(Xcvr):
   def __init__(self, driver=None, interruptLine=None, reset=None, leds=None,
                **kwargs):
      self.driver = driver
      self.interruptLine = interruptLine
      self.reset = reset
      self.leds = leds or []
      typeStr = Xcvr.typeStr(kwargs['xcvrType'])
      self.name = '%s%s' % (typeStr, kwargs['xcvrId'])
      self.__dict__.update(kwargs)

   def getType(self):
      return Xcvr.typeStr(self.xcvrType)

   def getName(self):
      return self.name

   def getPresence(self):
      return self.driver.getXcvrPresence(self)

   def getLowPowerMode(self):
      return self.driver.getXcvrLowPowerMode(self)

   def setLowPowerMode(self, value):
      return self.driver.setXcvrLowPowerMode(self, value)

   def getModuleSelect(self):
      return self.driver.getXcvrModuleSelect(self)

   def setModuleSelect(self, value):
      return self.driver.setXcvrModuleSelect(self, value)

   def getTxDisable(self):
      return self.driver.getXcvrTxDisable(self)

   def setTxDisable(self, value):
      return self.driver.setXcvrTxDisable(self, value)

   def getInterruptLine(self):
      return self.interruptLine

   def getReset(self):
      return self.reset

   def getLeds(self):
      return self.leds
