
from ...core.cpu import Cpu
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

class MockSupervisor(Supervisor):
   def addCpuComplex(self):
      self.cpu = MockCpu()

   def getPciPort(self, bus):
      return self.cpu.pciRoot.rootPort(bus=bus)

   def getSmbus(self, bus):
      return self.cpu.scd.getSmbus(bus)

   def getCookies(self):
      return self.cpu.cookies
