
from ..components.xcvr import Osfp, Qsfp, Sfp, Ethernet
from ..inventory.xcvr import (
   Osfp as OsfpInv,
   OsfpSlot as OsfpSlotInv,
   Qsfp as QsfpInv,
   QsfpSlot as QsfpSlotInv,
   Sfp as SfpInv,
   SfpSlot as SfpSlotInv,
   Ethernet as EthernetInv,
   EthernetSlot as EthernetSlotInv,
)

from .component.slot import SlotComponent

class EthernetImpl(EthernetInv):
   def __init__(self, slot):
      self.slot = slot
      self.addr = None

   def getType(self):
      return "ethernet"

   def getId(self):
      return self.slot.getId()

   def getName(self):
      return self.slot.getName()

   def getI2cAddr(self):
      return self.addr

class SfpImpl(SfpInv):
   def __init__(self, addrFunc, slot):
      self.addr = addrFunc(self.ADDR)
      self.slot = slot

   def getType(self):
      return "sfp"

   def getId(self):
      return self.slot.getId()

   def getName(self):
      return self.slot.getName()

   def getI2cAddr(self):
      return self.addr

class QsfpImpl(QsfpInv):
   def __init__(self, addrFunc, slot):
      self.addr = addrFunc(self.ADDR)
      self.slot = slot

   def getType(self):
      return "qsfp"

   def getId(self):
      return self.slot.getId()

   def getName(self):
      return self.slot.getName()

   def getI2cAddr(self):
      return self.addr

class OsfpImpl(OsfpInv):
   def __init__(self, addrFunc, slot):
      self.addr = addrFunc(self.ADDR)
      self.slot = slot

   def getType(self):
      return "osfp"

   def getId(self):
      return self.slot.getId()

   def getName(self):
      return self.slot.getName()

   def getI2cAddr(self):
      return self.addr

class BackplaneImpl(EthernetImpl):
   def __init__(self, eeprom, slot):
      super().__init__(slot)
      self.addr = eeprom.addr

   def getType(self):
      return 'backplane'

class EthernetSlotImpl(EthernetSlotInv):
   def __init__(self, slot):
      self.slot = slot

   def getId(self):
      return self.slot.getId()

   def getName(self):
      return self.slot.getName()

   def getPresence(self):
      return self.slot.getPresence()

   def getLeds(self):
      return self.slot.leds

   def getDefaultLed(self):
      return self.slot.defaultLed

   def getInterruptLine(self):
      # Not supported for Ethernet
      return None

   def getReset(self):
      # Not supported for Ethernet
      return None

   def getLowPowerMode(self):
      # Not supported for Ethernet
      return False

   def setLowPowerMode(self, value):
      # Not supported for Ethernet
      return False

   def getModuleSelect(self):
      # Not supported for Ethernet
      return True

   def setModuleSelect(self, value):
      # Not supported for Ethernet
      return True

   def getRxLos(self):
      # Not supported for Ethernet
      return False

   def getTxDisable(self):
      # Not supported for Ethernet
      return False

   def setTxDisable(self, value):
      # Not supported for Ethernet
      return False

   def getTxFault(self):
      # Not supported for Ethernet
      return False

   def getXcvr(self):
      return self.slot.getXcvr()

class SfpSlotImpl(SfpSlotInv):
   def __init__(self, slot):
      self.slot = slot

   def getId(self):
      return self.slot.getId()

   def getName(self):
      return self.slot.getName()

   def getPresence(self):
      return self.slot.getPresence()

   def getLeds(self):
      return self.slot.leds

   def getDefaultLed(self):
      return self.slot.defaultLed

   def getInterruptLine(self):
      return self.slot.getInterruptLine()

   def getReset(self):
      # Not supported for SFP
      return None

   def getLowPowerMode(self):
      # Not supported for SFP
      return False

   def setLowPowerMode(self, value):
      # Not supported for SFP
      return False

   def getModuleSelect(self):
      # Not supported for SFP
      return True

   def setModuleSelect(self, value):
      # Not supported for SFP
      return True

   def getRxLos(self):
      return self.slot.getRxLos()

   def getTxDisable(self):
      return self.slot.getTxDisable()

   def setTxDisable(self, value):
      return self.slot.setTxDisable(value)

   def getTxFault(self):
      return self.slot.getTxFault()

   def getXcvr(self):
      return self.slot.getXcvr()

class QsfpSlotImpl(QsfpSlotInv):
   def __init__(self, slot):
      self.slot = slot

   def getId(self):
      return self.slot.getId()

   def getName(self):
      return self.slot.getName()

   def getPresence(self):
      return self.slot.getPresence()

   def getLeds(self):
      return self.slot.leds

   def getDefaultLed(self):
      return self.slot.defaultLed

   def getInterruptLine(self):
      return self.slot.getInterruptLine()

   def getReset(self):
      return self.slot.getReset()

   def getLowPowerMode(self):
      return self.slot.getLowPowerMode()

   def setLowPowerMode(self, value):
      return self.slot.setLowPowerMode(value)

   def getModuleSelect(self):
      return self.slot.getModuleSelect()

   def setModuleSelect(self, value):
      return self.slot.setModuleSelect(value)

   def getRxLos(self):
      # Not supported for QSFP
      return False

   def getTxDisable(self):
      # Not supported for QSFP
      return False

   def setTxDisable(self, value):
      # Not supported for QSFP
      return False

   def getTxFault(self):
      # Not supported for QSFP
      return False

   def getXcvr(self):
      return self.slot.getXcvr()

class OsfpSlotImpl(OsfpSlotInv):
   def __init__(self, slot):
      self.slot = slot

   def getId(self):
      return self.slot.getId()

   def getName(self):
      return self.slot.getName()

   def getPresence(self):
      return self.slot.getPresence()

   def getLeds(self):
      return self.slot.leds

   def getDefaultLed(self):
      return self.slot.defaultLed

   def getInterruptLine(self):
      return self.slot.getInterruptLine()

   def getReset(self):
      return self.slot.getReset()

   def getLowPowerMode(self):
      return self.slot.getLowPowerMode()

   def setLowPowerMode(self, value):
      return self.slot.setLowPowerMode(value)

   def getModuleSelect(self):
      return self.slot.getModuleSelect()

   def setModuleSelect(self, value):
      return self.slot.setModuleSelect(value)

   def getRxLos(self):
      # Not supported for OSFP
      return False

   def getTxDisable(self):
      # Not supported for OSFP
      return False

   def setTxDisable(self, value):
      # Not supported for OSFP
      return False

   def getTxFault(self):
      # Not supported for OSFP
      return False

   def getXcvr(self):
      return self.slot.getXcvr()

class XcvrSlot(SlotComponent):
   def __init__(self, slotId=None, name=None, addrFunc=None, interrupt=None,
                presentGpio=None, leds=None, defaultLed=None, **kwargs):
      super().__init__(**kwargs)
      self.addrFunc = addrFunc
      self.slotId = slotId
      self.name = name
      self.interrupt = interrupt
      self.presentGpio = presentGpio
      self.leds = leds
      self.defaultLed = defaultLed
      self.xcvrInv = None
      self.xcvr = None

   def getId(self):
      return self.slotId

   def getName(self):
      return self.name

   def getPresence(self):
      if self.presentGpio:
         return self.presentGpio.isActive()
      return False

   def getInterruptLine(self):
      return self.interrupt

   def getXcvr(self):
      return self.xcvrInv

   def getLeds(self):
      return self.leds

   def getDefaultLed(self):
      return self.defaultLed

class EthernetSlot(XcvrSlot):
   def __init__(self, **kwargs):
      super().__init__(**kwargs)
      self.ethernetSlotInv = self.inventory.addEthernetSlot(EthernetSlotImpl(self))
      self.addEthernet()

   def addEthernet(self):
      self.xcvrInv = self.inventory.addEthernet(EthernetImpl(self.ethernetSlotInv))
      self.xcvr = self.newComponent(
         cls=Ethernet,
         portName=self.name
      )

   def getPresence(self):
      # Currently not supported
      return False

class SfpSlot(XcvrSlot):
   def __init__(self, rxLosGpio=None, txDisableGpio=None, txFaultGpio=None,
                **kwargs):
      super().__init__(**kwargs)
      self.rxLosGpio = rxLosGpio
      self.txDisableGpio = txDisableGpio
      self.txFaultGpio = txFaultGpio
      self.sfpSlotInv = self.inventory.addSfpSlot(SfpSlotImpl(self))
      self.addSfp()

   def addSfp(self):
      self.xcvrInv = self.inventory.addSfp(SfpImpl(self.addrFunc, self.sfpSlotInv))
      self.xcvr = self.newComponent(
         cls=Sfp,
         addr=self.xcvrInv.getI2cAddr(),
         portName=self.name
      )

   def getTxDisable(self):
      return self.txDisableGpio.isActive()

   def setTxDisable(self, value):
      return self.txDisableGpio.setActive(value)

   def getTxFault(self):
      return self.txFaultGpio.isActive()

   def getRxLos(self):
      return self.rxLosGpio.isActive()

class QsfpSlot(XcvrSlot):
   def __init__(self, lpMode=None, modSel=None, reset=None, **kwargs):
      super().__init__(**kwargs)
      self.lpMode = lpMode
      self.modSel = modSel
      self.reset = reset

      self.qsfpSlotInv = self.inventory.addQsfpSlot(QsfpSlotImpl(self))
      self.addQsfp()

   def addQsfp(self):
      self.xcvrInv = self.inventory.addQsfp(QsfpImpl(self.addrFunc,
                                                     self.qsfpSlotInv))
      self.xcvr = self.newComponent(
         cls=Qsfp,
         addr=self.xcvrInv.getI2cAddr(),
         portName=self.name
      )

   def getReset(self):
      return self.reset

   def getLowPowerMode(self):
      if not self.lpMode:
         # Indicates that a platform does not have HW support for lp mode
         raise NotImplementedError
      return self.lpMode.isActive()

   def setLowPowerMode(self, value):
      if not self.lpMode:
         raise NotImplementedError
      return self.lpMode.setActive(value)

   def getModuleSelect(self):
      if not self.modSel:
         raise NotImplementedError
      return self.modSel.isActive()

   def setModuleSelect(self, value):
      if not self.modSel:
         raise NotImplementedError
      return self.modSel.setActive(value)

class OsfpSlot(XcvrSlot):
   def __init__(self, lpMode=None, modSel=None, reset=None, **kwargs):
      super().__init__(**kwargs)
      self.lpMode = lpMode
      self.modSel = modSel
      self.reset = reset
      self.osfpSlotInv = self.inventory.addOsfpSlot(OsfpSlotImpl(self))
      self.addOsfp()

   def addOsfp(self):
      self.xcvrInv = self.inventory.addOsfp(OsfpImpl(self.addrFunc,
                                                     self.osfpSlotInv))
      self.xcvr = self.newComponent(
         cls=Osfp,
         addr=self.xcvrInv.getI2cAddr(),
         portName=self.name
      )

   def getReset(self):
      return self.reset

   def getLowPowerMode(self):
      if not self.lpMode:
         raise NotImplementedError
      return self.lpMode.isActive()

   def setLowPowerMode(self, value):
      if not self.lpMode:
         raise NotImplementedError
      return self.lpMode.setActive(value)

   def getModuleSelect(self):
      if not self.modSel:
         raise NotImplementedError
      return self.modSel.isActive()

   def setModuleSelect(self, value):
      if not self.modSel:
         raise NotImplementedError
      return self.modSel.setActive(value)

class Cartridge:
   def __init__(self, index, eeprom, interrupt, wp):
      self.index = index
      self.eeprom = eeprom
      self.interrupt = interrupt
      self.wp = wp

   def getPresence(self):
      return not self.interrupt.asserted()

class BackplaneConnector(XcvrSlot):
   def __init__(self, *args, cartridge=None, **kwargs):
      super().__init__(*args, **kwargs)
      self.slotInv = self.inventory.addEthernetSlot(EthernetSlotImpl(self))
      self.xcvrInv = self.inventory.addEthernet(BackplaneImpl(cartridge.eeprom,
                                                              self.slotInv))
      self.xcvr = cartridge.eeprom
      self.cartridge = cartridge
      self.leds = []

   def getPresence(self):
      return self.cartridge.getPresence()
