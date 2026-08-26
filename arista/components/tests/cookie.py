
import unittest

from ..cookie import PlatformCookieComponent
from ..denali.card import DenaliLinecardBase, DenaliLinecardSlot
from ..denali.linecard import DenaliLinecard
from ...core.inventory import Inventory
from ...core.tests.mockchassis import MockCpu, MockSupervisor
from ...descs.cause import ReloadCauseDesc, ReloadCauseScore

class MockLinecard(DenaliLinecardBase):
   CPU_CLS = MockCpu

   def __init__(self, *args, **kwargs):
      super(MockLinecard, self).__init__(*args, **kwargs)
      self.cb_call_count = 0

   def controlDomain(self):
      self.slot.parent.getCookies().addLinecard(self)
      self.cookies.register(ReloadCauseDesc.WATCHDOG, self.watchdogCallback)
      assert len(self.cookies.callbacks) == 1

   def watchdogCallback(self):
      self.cb_call_count += 1
      return True

   def isDetected(self):
      return True

   def powerControlDomainIs(self, on):
      pass

   def powerStandbyDomainIs(self, on):
      pass

   def powerLcpuIs(self, on, lcpuCtx):
      pass

   def getLastPostCode(self):
      pass

   def hasNextPostCodeAvail(self):
      pass

class CookieTest(unittest.TestCase):
   def testCallback(self):
      sup = MockSupervisor()
      pci = sup.getPciPort(0x01)
      bus = sup.getSmbus(0x03)
      slotId = DenaliLinecard.ABSOLUTE_CARD_OFFSET
      slot = DenaliLinecardSlot(sup, slotId, pci, bus)

      card = MockLinecard(slot=slot)
      slot.loadCard(card)
      card.cookies.poll()
      assert list(card.cookies.causeData.keys()) == [ReloadCauseDesc.WATCHDOG]
      serialized = card.cookies.causesToDict()
      entry = next(iter(serialized.values()))
      assert entry['score'] == ReloadCauseScore.UNKNOWN

      providers = card.getInventory().getReloadCauseProviders()
      assert len(providers) == 1

      p = providers[0]
      p.process()
      assert len(card.cookies.causeData.keys()) == 0
      assert len(p.getCauses()) == 1
      assert p.getCauses()[0].cause == ReloadCauseDesc.WATCHDOG.typ

   def testMissingJsonFieldsUseDefaults(self):
      cookies = PlatformCookieComponent(inventory=Inventory())
      cookies.fromDict({})
      assert cookies.toDict() == cookies.DEFAULT_CAUSEDATA

if __name__ == '__main__':
   unittest.main()
