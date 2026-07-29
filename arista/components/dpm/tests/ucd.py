import pytest

from ....descs.cause import ReloadCauseDesc
from ....core.tests.helpers import (
   classname,
   getAllSystems,
)
from ..ucd import (
   UcdReloadCauseProvider,
   UcdGpi,
   UcdMon,
)

@pytest.mark.parametrize("platform", getAllSystems(), ids=classname)
def testUcdGpiTypeCheck(platform):

   validValues = [
      value for name, value in vars(ReloadCauseDesc).items()
      if not name.startswith('__') and isinstance(value, str)
   ]

   rcProviders = platform.getInventory().getReloadCauseProviders()

   errors = []
   def checkCauses(causes):
      for cause in causes:
         assert isinstance(cause, (UcdGpi, UcdMon))
         if cause.name not in validValues:
            errors.append(f"Reload cause name '{cause.name}' on "
                          f"{platform} is not valid.")
   for rcp in rcProviders:
      if isinstance(rcp, UcdReloadCauseProvider):
         checkCauses(rcp.ucd.causes)

   if errors:
      errorMsg = "\n".join(errors)
      pytest.fail(f"UcdGpi reload cause name validation failed\n"
                  f"{errorMsg}\nAllowed values from "
                  f"class ReloadCauseDesc: {validValues}")
