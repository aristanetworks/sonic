
import os

def touch(path, mode=0o644, times=None):
   try:
      with open(path, 'a'):
         pass
      os.chmod(path, mode)
      os.utime(path, times)
   except IOError:
      return False
   return True

def rmfile(path, raises=False):
   try:
      os.remove(path)
   except (OSError, IOError):
      if raises:
         raise
