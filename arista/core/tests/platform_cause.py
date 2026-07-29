from unittest import mock

import pytest

from .helpers import (
   classname,
   getAllSystems,
)

from ..cause import ReloadCausePriority
from ..domain import PowerDomain

from ...components.denali.tests.chassis import DenaliChassisTest
from ...components.dpm.ucd import UcdReloadCauseProvider
from ...components.dpm.adm1266 import AdmReloadCauseProvider
from ...platforms.chassis.camp import Camp
from ...platforms.chassis.northface import NorthFace
from ...platforms.fabric.brooks import Brooks
from ...platforms.fabric.dragonfly import Dragonfly
from ...platforms.fabric.eldridge import Eldridge
from ...platforms.linecard.clearwater2 import Clearwater2, Clearwater2Ms
from ...platforms.linecard.wolverine import (
   WolverineO,
   WolverineQCpu,
   WolverineQCpuBkMs,
)
from ...platforms.supervisor.otterlake import OtterLake

NEW_VERSION_PRIORITIES = [ReloadCausePriority.PREREBOOT,
                          ReloadCausePriority.HARDWARE_MAIN,
                          ReloadCausePriority.HARDWARE_SECONDARY,
                          ReloadCausePriority.BERT]

MODULAR_PLATFORM_CASES = (
   (
      Camp,
      OtterLake,
      Brooks,
      None,
   ),
   (
      NorthFace,
      OtterLake,
      Eldridge,
      None,
   ),
   (
      NorthFace,
      OtterLake,
      Dragonfly,
      {
         1: Clearwater2,
         2: Clearwater2Ms,
         3: WolverineO,
         4: WolverineQCpu,
         5: WolverineQCpuBkMs,
      },
   ),
)

def isProviderPriorityVersionNew(provider):
   if provider.getPriority() in NEW_VERSION_PRIORITIES:
      return True
   return False

def assertPlatformReloadCauseProviderVersion(platform):
   providerVersion = None
   for provider in platform.getInventory().getReloadCauseProviders():
      # BERT is injected on all platforms regardless of their priority scheme,
      # so it cannot be used as a version indicator. Remove this skip once all
      # platforms have migrated to the new priority scheme.
      if provider.getPriority() == ReloadCausePriority.BERT:
         continue

      currentVersion = isProviderPriorityVersionNew(provider)
      if providerVersion is None:
         providerVersion = currentVersion
      else:
         assert currentVersion == providerVersion, (
            f"{classname(platform)}: detect usage of ReloadCauseProvider priority "
            "from at least two different standards. Please check definitions."
         )

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
         expectedDescs = len(provider.ucd.causes) + len(provider.ucd.rails)
         assert len(descs) == expectedDescs, (
            f'{classname(platform)}/{provider.getSourceName()}: '
            f'expected {expectedDescs} descs, got {len(descs)}')
      elif isinstance(provider, AdmReloadCauseProvider):
         assert len(descs) == len(provider.adm.causes), (
            f'{classname(platform)}/{provider.getSourceName()}: '
            f'expected {len(provider.adm.causes)} descs, got {len(descs)}')

@pytest.mark.parametrize('platform', getAllSystems(), ids=classname)
def testPlatformReloadCauseProviderVersion(platform):
   # Filter finalized classes with SID and SKU
   if not platform.SKU or not platform.SID:
      return
   # Allow test flexibility to prototype SKU
   if platform.PROTOTYPE:
      return

   assertPlatformReloadCauseProviderVersion(platform)

@pytest.mark.parametrize(
   'chassisCls,supervisorCls,fabricCls,linecards',
   MODULAR_PLATFORM_CASES,
   ids=(
      'Camp-OtterLake-Brooks',
      'NorthFace-OtterLake-Eldridge',
      'NorthFace-OtterLake-Dragonfly',
   ),
)
def testModularPlatformReloadCauseProviderVersion(
   chassisCls,
   supervisorCls,
   fabricCls,
   linecards,
):
   chassis = DenaliChassisTest.buildBasicChassis(
      chassisCls,
      supervisorCls,
      fabricCls,
      linecards=linecards,
   )

   # PCA9555 inputs always read zero in simulation, which otherwise hides the
   # linecard control-domain providers from MetaInventory.
   with mock.patch.object(PowerDomain, 'isEnabled', return_value=True):
      for linecard in chassis.iterLinecards():
         assertPlatformReloadCauseProviderVersion(linecard)
