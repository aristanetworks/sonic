# Copyright (c) 2019 Arista Networks, Inc.  All rights reserved.
# Arista Networks, Inc. Confidential and Proprietary.

# pylint: disable=protected-access

from collections import Counter
from unittest.mock import patch
import pytest

from ..platform_loader import platform_loader

def test_platform_discovery():
   # Because we keep SKUs and SIDs in the same index, they must be mutually
   # exclusive. Otherwise, PlatformIndex needs reimplementation.
   count = Counter()
   for pc in platform_loader.all_platforms():
      count.update(platform_loader.platforms._keysof(pc))  # pylint: disable=protected-access

   assert count, "Did not discover any platforms"
   duplicates = {k: c for k, c in count.items() if c > 1}
   assert not duplicates, "SKUs and SIDs must be unique & disjoint."

HELP_MESSAGE = "See the NOTE in the test file"
# NOTE:
# @pytest.mark.requires_registry - marks tests that require the pre-built registry.
# If such a test fails, then most likely you ran it directly (not via `make`)
# and you did not (re)build the registry. Run `make build-registry` first
# (`make test` does it for you).

@pytest.mark.requires_registry
@pytest.mark.parametrize("index", platform_loader._indexes())
def test_platform_registry(index):
   platform_loader._discover_all()  # populate the _index
   assert set(index._index.keys()) == set(index._descriptors.keys()), HELP_MESSAGE

@pytest.mark.requires_registry
@pytest.mark.parametrize("index", platform_loader._indexes())
def test_does_not_discover_if_in_registry(index):
   # get a key, and find its platform
   a_key = next(iter(index._descriptors.keys()), None)
   assert a_key, HELP_MESSAGE

   # Trick the loader to re-discover if needed
   with patch.object(platform_loader, "_did_run_discovery", False):
      found = index.get(a_key)
      assert found
      assert not platform_loader._did_run_discovery, HELP_MESSAGE
