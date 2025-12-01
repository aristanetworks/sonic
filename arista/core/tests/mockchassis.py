
from ...core.card import CardSlot
from ...core.cpu import Cpu
from ...core.modular import Modular
from ...core.linecard import Linecard
from ...core.pci import PciRoot
from ...core.supervisor import Supervisor

from ...components.cookie import CookieComponentBase, SlotCookieComponent
from ...components.scd import Scd

class MockCookieComponent(CookieComponentBase):
   def __init__(self, *args, **kwargs):
      super().__init__(*args, slotId=0, **kwargs)

   def addLinecard(self, card):
      card.cookies = card.newComponent(SlotCookieComponent,
                                       slotId=card.slot.slotId,
                                       platformCookies=self)

   def loadCookieFile(self):
      pass

   def storeCauses(self):
      pass

class MockCpu(Cpu):
   def __init__(self):
      super(Cpu, self).__init__()
      self.pciRoot = PciRoot()
      scdPort = self.pciRoot.rootPort(bus=0x0f)
      self.scd = self.pciRoot.newComponent(Scd, addr=scdPort.addr)
      self.cookies = self.newComponent(MockCookieComponent)


class MockCardSlot(CardSlot):
   def getEeprom(self):
      if self.card:
         return self.card.getEeprom()
      return None

   def getPresence(self):
      return self.card is not None

class MockChassis(Modular):
   NUM_SUPERVISORS = 1
   NUM_LINECARDS = 4

class MockSupervisor(Supervisor):
   ABSOLUTE_CARD_OFFSET = 3

   def getChassis(self):
      if not self.chassis:
         self.chassis = MockChassis()
         self.chassis.insertSupervisor(self, self.getSlotId(), active=True)
      return self.chassis

   def addCpuComplex(self):
      self.cpu = MockCpu()

   def getPciPort(self, bus):
      return self.cpu.pciRoot.rootPort(bus=bus)

   def getSmbus(self, bus):
      return self.cpu.scd.getSmbus(bus)

   def getCookies(self):
      return self.cpu.cookies

   def createLinecardSlot(self, lcId, serial=None):
      assert lcId >= 0
      assert lcId < self.getChassis().NUM_LINECARDS
      if not serial:
         serial = f'FakeSerial{lcId}'
      slot = MockCardSlot(parent=self, slotId=self.ABSOLUTE_CARD_OFFSET + lcId)
      self.linecardSlots.append(slot)

   def createLinecardSlots(self):
      for lcId in range(self.getChassis().NUM_LINECARDS):
         self.createLinecardSlot(lcId)

   def insertLinecard(self, lcId, cls, **kwargs):
      slot = self.linecardSlots[lcId]
      slot.loadCard(card=cls(slot=slot, **kwargs))

class MockEeprom(object):
   def __init__(self, data):
      self.data = data

   def prefdl(self):
      return self.data

   def prefdlCached(self):
      return self.data

   def clearPrefdlCache(self):
      pass

class MockLinecard(Linecard):
   def __init__(self, serial=None, **kwargs):
      super().__init__(**kwargs)
      if not serial:
         if self.slot:
            serial = f'FakeSerial{self.slot.slotId}'
         else:
            serial = 'FakeSerial'
      self.eeprom = MockEeprom({
         'SID': 'MockLinecard',
         'Serial': serial,
      })

   def refresh(self):
      pass

   def loadStandbyDomain(self):
      pass

   def loadCpuDomain(self):
      pass

   def loadMainDomain(self):
      pass

   def getEeprom(self):
      return self.eeprom.prefdl()

   def getRelativeSlotId(self):
      return self.getSlotId() - MockSupervisor.ABSOLUTE_CARD_OFFSET

   def getLastPostCode(self):
      return None

   def hasNextPostCodeAvail(self):
      return False

   def powerOnIs(self, on, lcpuCtx=None):
      pass

   def poweredOn(self):
      return False
