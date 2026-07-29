
from ....core.utils import incrange

from ....platforms.chassis.camp import Camp
from ....platforms.chassis.northface import NorthFace
from ....platforms.fabric.brooks import Brooks
from ....platforms.fabric.eldridge import Eldridge
from ....platforms.fabric.dragonfly import Dragonfly
from ....platforms.linecard.clearwater import Clearwater, ClearwaterMs
from ....platforms.linecard.clearwater2 import Clearwater2, Clearwater2Ms
from ....platforms.linecard.wolverine import (
   WolverineO,
   WolverineQCpu,
   WolverineQCpuBkMs,
)
from ....platforms.supervisor.otterlake import OtterLake

from ....tests.testing import unittest

class DenaliChassisTest(unittest.TestCase):
   @classmethod
   def buildChassis(cls, chassisCls, supervisors, fabrics, linecards):
      chassis = chassisCls()
      for slotId, supervisorCls in supervisors.items():
         sup = supervisorCls(chassis=chassis, slot=None)
         sup.slotId = slotId
         chassis.insertSupervisor(sup, slotId=slotId, active=slotId == 1)

      def hookCardSlots(coll, inv):
         for i, slot in enumerate(coll, 1):
            cls = inv.get(i)
            if cls is None:
               slot.getPresence = lambda: False
            else:
               slot.getEeprom = lambda c=cls: { 'SKU': c.SKU[0], 'SID': c.SID[0] }

      hookCardSlots(chassis.active.fabricSlots, fabrics)
      hookCardSlots(chassis.active.linecardSlots, linecards)

      chassis.loadLinecards()
      chassis.loadFabrics()

      return chassis

   @classmethod
   def buildBasicChassis(cls, chassis, supervisor, fabric, linecards=None):
      linecards = linecards or {
         1: Clearwater,
         2: ClearwaterMs,
         3: Clearwater2,
         4: Clearwater2Ms,
      }
      return cls.buildChassis(
         chassis,
         supervisors={
            1: supervisor,
         },
         fabrics={
            slotId: fabric for slotId in incrange(1, 6)
         },
         linecards=linecards,
      )

   def testCampChassis(self):
      self.buildBasicChassis(Camp, OtterLake, Brooks)

   def testNorthFaceEldridgeChassis(self):
      self.buildBasicChassis(NorthFace, OtterLake, Eldridge)

   def testNorthFaceDragonflyChassis(self):
      self.buildBasicChassis(NorthFace, OtterLake, Dragonfly, linecards={
         1: Clearwater2,
         2: Clearwater2Ms,
         3: WolverineO,
         4: WolverineQCpu,
         5: WolverineQCpuBkMs,
      })

if __name__ == '__main__':
   unittest.main()
