
import os

def readFileContent(path):
   with open(path) as f:
      return f.read()

def writeFileContent(path, value, encoding='utf-8'):
   with open(path, 'w', encoding=encoding) as f:
      f.write(value)

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
