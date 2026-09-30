from unittest.mock import Mock

from ....tests.testing import unittest, patch

from ...identity.bmc import PlatformIdentityBmc
from ...identity.dmi import PlatformIdentityDmi
from ...identity.factory import createPlatformIdentity
from ...identity.non_dmi import PlatformIdentityNonDmi


class PlatformIdentityFactoryTest(unittest.TestCase):

   @patch('arista.core.identity.factory.isBmcEnvironment', return_value=True)
   def testBmcIdentity(self, _mockIsBmc):
      identity = createPlatformIdentity(Mock(), cmdline={})
      self.assertIsInstance(identity, PlatformIdentityBmc)

   @patch('arista.core.identity.factory.isBmcEnvironment', return_value=False)
   def testDmiIdentity(self, _mockIsBmc):
      identity = createPlatformIdentity(
         Mock(), cmdline={'arista.identify_dmi': '1'})
      self.assertIsInstance(identity, PlatformIdentityDmi)

   @patch('arista.core.identity.factory.isBmcEnvironment', return_value=False)
   def testNonDmiIdentity(self, _mockIsBmc):
      identity = createPlatformIdentity(Mock(), cmdline={})
      self.assertIsInstance(identity, PlatformIdentityNonDmi)


if __name__ == '__main__':
   unittest.main()
