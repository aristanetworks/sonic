import pytest

from .helpers import (
   classname,
   getAllSystems,
)

from ..cause import ReloadCausePriority
from ...components.dpm.ucd import UcdReloadCauseProvider
from ...components.dpm.adm1266 import AdmReloadCauseProvider

NEW_VERSION_PRIORITIES = [ReloadCausePriority.PREREBOOT,
                          ReloadCausePriority.HARDWARE_MAIN,
                          ReloadCausePriority.HARDWARE_SECONDARY,
                          ReloadCausePriority.BERT]

def isProviderPriorityVersionNew(provider):
   if provider.getPriority() in NEW_VERSION_PRIORITIES:
      return True
   return False

@pytest.mark.parametrize('platform', getAllSystems(), ids=classname)
def testPlatformReloadCauseDescs(platform):
   if not platform.SKU or not platform.SID:
      return
   if platform.PROTOTYPE:
      return
   inventory = platform.getInventory()
   for provider in inventory.getReloadCauseProviders():
      descs = provider.getReloadCauseDescs()
      for desc in descs:
         assert desc.typ, (
            f'{classname(platform)}/{provider.getSourceName()}: empty type')
         assert desc.description, (
            f'{classname(platform)}/{provider.getSourceName()}: empty description')
         assert desc.code is not None, (
            f'{classname(platform)}/{provider.getSourceName()}: missing code')
      if isinstance(provider, UcdReloadCauseProvider):
         assert len(descs) == len(provider.ucd.causes), (
            f'{classname(platform)}/{provider.getSourceName()}: '
            f'expected {len(provider.ucd.causes)} descs, got {len(descs)}')
      elif isinstance(provider, AdmReloadCauseProvider):
         assert len(descs) == len(provider.adm.causes), (
            f'{classname(platform)}/{provider.getSourceName()}: '
            f'expected {len(provider.adm.causes)} descs, got {len(descs)}')

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
      # BERT is injected on all platforms regardless of their priority scheme,
      # so it cannot be used as a version indicator. Remove this skip once all
      # platforms have migrated to the new priority scheme.
      if provider.getPriority() == ReloadCausePriority.BERT:
         continue
      if providerVersion is None:
         providerVersion = isProviderPriorityVersionNew(provider)
      else:
         assert isProviderPriorityVersionNew(provider) == providerVersion, (
            f"{classname(platform)}: detect usage of ReloadCauseProvider priority "
            "from at least two different standards. Please check definitions."
         )
