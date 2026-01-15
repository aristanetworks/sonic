
import os
from contextlib import contextmanager

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

class RotatedLogFile:
   def __init__(self, name, path, keep):
      self.name = name
      self.path = path
      self.keep = keep

   def _rotate(self):
      logs = sorted(f for f in os.listdir(self.path) if f.startswith(self.name))
      while len(logs) >= self.keep:
         os.remove(os.path.join(self.path, logs.pop(0)))

   @contextmanager
   def newLog(self, suffix):
      os.makedirs(self.path, exist_ok=True)
      self._rotate()
      path = os.path.join(self.path, f'{self.name}.{suffix}.log')
      with open(path, 'wb') as f:
         yield f
