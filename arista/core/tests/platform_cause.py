from unittest import mock

import pytest

from .helpers import (
   classname,
   getAllSystemClasses,
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

@pytest.mark.parametrize('platformCls', tuple(getAllSystemClasses()), ids=classname)
def testPlatformReloadCauseDescs(platformCls):
   if not platformCls.SKU or not platformCls.SID:
      return
   if platformCls.PROTOTYPE:
      return
   platform = platformCls()
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

@pytest.mark.parametrize('platformCls', tuple(getAllSystemClasses()), ids=classname)
def testPlatformReloadCauseProviderPriorities(platformCls):
   # Filter finalized classes with SID and SKU
   if not platformCls.SKU or not platformCls.SID:
      return
   # Allow test flexibility to prototype SKU
   if platformCls.PROTOTYPE:
      return

   platform = platformCls()
   inventory = platform.getInventory()
   for provider in inventory.getReloadCauseProviders():
      assert provider.getPriority() in ReloadCausePriority.PROVIDER_PRIORITIES, (
         f'{classname(platform)}/{provider.getSourceName()}: unexpected reload '
         f'cause provider priority {provider.getPriority()}'
      )

@pytest.mark.parametrize(
   'chassisCls,supervisorCls,fabricCls,linecards',
   MODULAR_PLATFORM_CASES,
   ids=(
      'Camp-OtterLake-Brooks',
      'NorthFace-OtterLake-Eldridge',
      'NorthFace-OtterLake-Dragonfly',
   ),
)
def testModularPlatformReloadCauseProviderPriorities(
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
         inventory = linecard.getInventory()
         for provider in inventory.getReloadCauseProviders():
            assert provider.getPriority() in (
               ReloadCausePriority.PROVIDER_PRIORITIES
            ), (
               f'{classname(linecard)}/{provider.getSourceName()}: unexpected '
               f'cause provider priority {provider.getPriority()}'
            )
