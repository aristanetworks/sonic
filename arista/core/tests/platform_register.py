# Copyright (c) 2019 Arista Networks, Inc.  All rights reserved.
# Arista Networks, Inc. Confidential and Proprietary.

from ...tests.testing import unittest

from .. import platform
from ..fixed import FixedSystem

class UniqueKeyDict(dict):
   def __setitem__(self, key, value):
      assert key not in self, \
         'Key %s already exists in %s' % (key, self.keys())
      dict.__setitem__(self, key, value)

class UniqueList(list):
   def append(self, value):
      assert value not in self, \
         'Value %s already exists in %s' % (value, self)
      list.append(self, value)

class RegisterTest(unittest.TestCase):
   @unittest.skip("affect later tests as clearing platform.platforms")
   def testUniquePlatform(self):
      platform.platformSkuIndex = UniqueKeyDict()
      platform.platformSidIndex = UniqueKeyDict()
      platform.platforms = UniqueList()

      platform.loadPlatforms()

   def testPlatformInfo(self):
      platform.loadPlatforms()

      for cls in platform.getPlatforms():
         self.assertIsInstance(cls.PLATFORM, (type(None), str))
         self.assertIsInstance(cls.SID, list)
         self.assertIsInstance(cls.SKU, list)

   def testPlatformInstance(self):
      platform.loadPlatforms()

      for cls in platform.getPlatforms():
         if not issubclass(cls, FixedSystem):
            continue
         cls()

if __name__ == '__main__':
   unittest.main()
