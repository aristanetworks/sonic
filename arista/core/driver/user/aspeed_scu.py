
import mmap
import os

class AspeedScuDriver:
   """Driver for reading/writing Aspeed SCU registers via /dev/mem mmap."""

   def read(self, base, offset):
      fd = os.open('/dev/mem', os.O_RDONLY | os.O_SYNC)
      try:
         with mmap.mmap(fd, 0x1000, mmap.MAP_SHARED, mmap.PROT_READ,
                        offset=base) as mm:
            return int.from_bytes(mm[offset:offset + 4], 'little')
      finally:
         os.close(fd)

   def write(self, base, offset, data):
      fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
      try:
         with mmap.mmap(fd, 0x1000, mmap.MAP_SHARED,
                        mmap.PROT_READ | mmap.PROT_WRITE,
                        offset=base) as mm:
            mm[offset:offset + 4] = data.to_bytes(4, 'little')
      finally:
         os.close(fd)
