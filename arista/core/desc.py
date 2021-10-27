
from __future__ import absolute_import, division, print_function

class HwDesc(object):
   def __init__(self, **kwargs):
      self.setAttrs(**kwargs)

   def setAttrs(self, **kwargs):
      for key, value in kwargs.items():
         setattr(self, key, value)

   def __diag__(self, ctx):
      return { k : v.__diag__(ctx) if isinstance(v, HwDesc) else v
               for k, v in self.__dict__.items() }
