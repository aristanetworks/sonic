
def iterBits(n):
   while n:
      yield n & 0x1
      n >>= 1

def listToIntLsb(l):
   value = 0
   for i, v in enumerate(l):
      value |= v << (i * 8)
   return value

def isBitSet(bitIndex, value):
   return bool(value & (1 << bitIndex))
