
import itertools

class HwApi():
   def __init__(self, *values):
      self.values = [int(v) for v in values]

   def _equal(self, other):
      for a, b in itertools.zip_longest(self.values, other.values, fillvalue=0):
         if a != b:
            return False
      return True

   def _greater(self, other):
      for a, b in itertools.zip_longest(self.values, other.values, fillvalue=0):
         if a > b:
            return True
      return False

   def _less(self, other):
      for a, b in itertools.zip_longest(self.values, other.values, fillvalue=0):
         if a < b:
            return True
      return False

   def __gt__(self, other):
      return self._greater(other) if isinstance(other, HwApi) else False

   def __ge__(self, other):
      if not isinstance(other, HwApi):
         return False
      return self._greater(other) or self._equal(other)

   def __lt__(self, other):
      return self._less(other) if isinstance(other, HwApi) else False

   def __le__(self, other):
      if not isinstance(other, HwApi):
         return False
      return self._less(other) or self._equal(other)

   def __eq__(self, other):
      return self._equal(other) if isinstance(other, HwApi) else False

   def __str__(self):
      return 'HwApi(%s)' % '.'.join(str(v) for v in self.values)

   def majorOnly(self):
      return HwApi(self.values[0])

   @classmethod
   def parse(cls, value):
      if isinteger(value):
         return HwApi(value)
      return HwApi((int(v) for v in value.split('.')))
