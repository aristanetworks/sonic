import pytest

from ...core.asic import SwitchChip
from ...core.pci import (
   DownstreamPciPort,
   PciBridge,
   PciPort,
   PciRoot,
   PciSwitch,
   PciSysfsPath,
   RootPciBridge,
   RootPciPort,
   UpstreamPciPort,
)
from ...tests.testing import patch

from .helpers import (
   classname,
   getAllSystems,
   isAncestorToComponent,
)

@pytest.mark.parametrize('platform', getAllSystems(), ids=classname)
def testSetup(platform):
   mocks = []
   for c in platform.iterComponents():
      mocks.append(patch.object(c, 'setup').start())

   platform.setup()

   for m in mocks:
      m.assert_called_once()

@pytest.mark.parametrize('platform', getAllSystems(), ids=classname)
def testPciAddrDuplication(platform):
   pciElements = (
      DownstreamPciPort,
      PciBridge,
      PciPort,
      PciRoot,
      PciSwitch,
      RootPciBridge,
      RootPciPort,
      UpstreamPciPort
   )
   sysfsSet = set()
   for c in platform.iterComponents(filters=None):
      if not isinstance(c, pciElements) and isinstance(c.addr, PciSysfsPath):
         sysfsPath = c.addr.getSysfsPath()
         assert sysfsPath not in sysfsSet
         sysfsSet.add(sysfsPath)

@pytest.mark.parametrize('platform', getAllSystems(), ids=classname)
def testSwitchAsicIdDieIdUniqueness(platform):
   asicIdDieIdPairs = set()
   # Iterate through all SwitchChip components to catch duplicates
   # even if they were overwritten in the inventory.

   # For multi-die ASICs (e.g., Jericho3 with NUM_DIES=2), the same asicId
   # can be used with different dieId values, so we check the (asicId, dieId) tuple.
   for c in platform.iterComponents(filters=None):
      if isinstance(c, SwitchChip):
         pair = (c.asicId, c.dieId)
         assert pair not in asicIdDieIdPairs, \
            f"Platform {platform.__class__.__name__} has duplicate " \
            f"(asicId, dieId) pair {pair}"
         asicIdDieIdPairs.add(pair)

@pytest.mark.parametrize('platform', getAllSystems(), ids=classname)
def testCorrectParenting(platform):
   for c in platform.iterComponents(filters=None):
      assert c in c.parent.components

      parent = None
      if hasattr(c, 'addr'):
         # FIXME: use a common `parent` attribute for all these Addr types
         parent = getattr(c.addr, 'scd_', None) or parent # ScdI2cAddr
         parent = getattr(c.addr, 'pca_', None) or parent # PcaI2cAddr
         parent = getattr(c.addr, 'port', None) or parent # PciAddr
         parent = parent or c.parent

      if parent is not None:
         assert isAncestorToComponent(c, parent)
