# Copyright (c) 2019 Arista Networks, Inc.  All rights reserved.
# Arista Networks, Inc. Confidential and Proprietary.
from collections import Counter

from ..platform_loader import platform_loader

def test_platform_registry():
   # Because we keep SKUs and SIDs in the same index, they must be mutually
   # exclusive. Otherwise, PlatformIndex needs reimplementation.
   count = Counter()
   for pc in platform_loader.all_platforms():
      count.update(platform_loader.platforms._keysof(pc))  # pylint: disable=protected-access

   assert count, "Did not discover any platforms"
   duplicates = {k: c for k, c in count.items() if c > 1}
   assert not duplicates, "SKUs and SIDs must be unique & disjoint."
