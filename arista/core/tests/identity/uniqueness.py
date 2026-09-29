from ...platform_loader import platform_loader
from ....tests.testing import unittest


class PlatformUniquenessTest(unittest.TestCase):

   def testNoDuplicatePlatformSids(self):
      sidToClass = {}
      for platform in platform_loader.all_platforms():
         for sid in platform.SID:
            if sid in sidToClass:
               self.fail(
                  f'SID {sid!r} claimed by both '
                  f'{sidToClass[sid].__name__} and {platform.__name__}')
            sidToClass[sid] = platform

   def testNoDuplicatePlatformSkus(self):
      skuToClass = {}
      for platform in platform_loader.all_platforms():
         for sku in platform.SKU:
            if sku in skuToClass:
               self.fail(
                  f'SKU {sku!r} claimed by both '
                  f'{skuToClass[sku].__name__} and {platform.__name__}')
            skuToClass[sku] = platform

if __name__ == '__main__':
   unittest.main()
