
# pylint: disable=import-outside-toplevel

from ....tests.testing import unittest


class PlatformUniquenessTest(unittest.TestCase):

   @classmethod
   def setUpClass(cls):
      from ...platform import loadPlatforms
      loadPlatforms()

   def testNoDuplicatePlatformSids(self):
      from ...platform import getManager
      sidToClass = {}
      for platform in getManager().platforms:
         for sid in platform.SID:
            if sid in sidToClass:
               self.fail(
                  f'SID {sid!r} claimed by both '
                  f'{sidToClass[sid].__name__} and {platform.__name__}')
            sidToClass[sid] = platform

   def testNoDuplicatePlatformSkus(self):
      from ...platform import getManager
      skuToClass = {}
      for platform in getManager().platforms:
         for sku in platform.SKU:
            if sku in skuToClass:
               self.fail(
                  f'SKU {sku!r} claimed by both '
                  f'{skuToClass[sku].__name__} and {platform.__name__}')
            skuToClass[sku] = platform


if __name__ == '__main__':
   unittest.main()
