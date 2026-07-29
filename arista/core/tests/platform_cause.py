import pytest

from .helpers import (
   classname,
   getAllSystems,
)

from ..cause import ReloadCausePriority

NEW_VERSION_PRIORITIES = [ReloadCausePriority.PREREBOOT,
                          ReloadCausePriority.HARDWARE_MAIN,
                          ReloadCausePriority.HARDWARE_SECONDARY]

def isProviderPriorityVersionNew(provider):
   if provider.getPriority() in NEW_VERSION_PRIORITIES:
      return True
   return False

@pytest.mark.parametrize('platform', getAllSystems(), ids=classname)
def testPlatformReloadCauseProviderVersion(platform):
   providerVersion = None
   # Filter finalized classes with SID and SKU
   if not platform.SKU or not platform.SID:
      return
   # Allow test flexibility to prototype SKU
   if platform.PROTOTYPE:
      return
   inventory = platform.getInventory()
   providerList = inventory.getReloadCauseProviders()
   for provider in providerList:
      if providerVersion is None:
         providerVersion = isProviderPriorityVersionNew(provider)
      else:
         assert isProviderPriorityVersionNew(provider) == providerVersion, (
            f"{classname(platform)}: detect usage of ReloadCauseProvider priority "
            "from at least two different standards. Please check definitions."
         )
