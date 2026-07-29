from ...descs.cause import ReloadCauseDesc, CauseDesc
# First mock sonic_platform_base
from . import sonic_platform_base
sonic_platform_base.mock()
sonic_platform_base.mockChassis()

# pylint: disable=wrong-import-position
from ..sonic_platform.chassis import Chassis

def testReloadCauseDescValidity():
   for v in vars(ReloadCauseDesc).values():
      if isinstance(v, CauseDesc):
         assert v.typ in Chassis.REBOOT_CAUSE_DICT, f"Found unexpected desc {v.typ}"
